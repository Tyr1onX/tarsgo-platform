import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import errors as genai_errors
from pydantic import ValidationError

from app.ai_planner import (
    DEEPSEEK_DEFAULT_BASE_URL,
    DeepSeekPlannerProvider,
    GeminiPlannerProvider,
    OpenAIPlannerProvider,
    PlannerInvalidResponse,
    PlannerProviderError,
    PlannerRateLimitError,
    SYSTEM_PROMPT,
    ITEM_REVIEW_SYSTEM_PROMPT,
    ITEM_FACT_EXTRACTION_SYSTEM_PROMPT,
    get_planner_provider,
    provider_is_configured,
)
from app.schemas import (
    AIItemFactExtractionOut,
    AIItemFactSuggestion,
    AIItemReviewOut,
    AIItemReviewSuggestion,
    AIItemReviewTaskProposal,
    AIPlannerDraft,
    AIPlannerItemDraft,
    AIPlannerSuggestionDraft,
    AIPlannerTaskDraft,
)


def draft() -> AIPlannerDraft:
    return AIPlannerDraft(
        item=AIPlannerItemDraft(
            title="校园科技展",
            deliverable="完成现场展示并收齐素材。",
            deadline=None,
        ),
        tasks=[
            AIPlannerTaskDraft(
                title="现场摄影",
                deliverable="活动原图完整上传。",
                deadline=None,
                execution_points=["按活动流程采集关键环节"],
                cautions=["确认设备电量充足"],
                prerequisites=["获取已确认的活动流程"],
                owner_claimable=True,
                collaboration_open=True,
            )
        ],
        questions=["确认活动结束时间。"],
        suggestions=[],
    )


def review() -> AIItemReviewOut:
    return AIItemReviewOut(
        summary="当前方案仍可执行。",
        suggestions=[
            AIItemReviewSuggestion(
                kind="update_task",
                target_task_id=41,
                reason="当前已确认信息改变了执行安排。",
                proposed_task=AIItemReviewTaskProposal(
                    title="现场布展",
                    deliverable="展示设备完成布置并可运行。",
                    execution_points=["按新确认时间提前完成布展"],
                    cautions=[],
                    prerequisites=[],
                ),
            ),
            AIItemReviewSuggestion(
                kind="add_task",
                target_task_id=None,
                reason="主办方新增了方案尚未覆盖的独立交付。",
                proposed_task=AIItemReviewTaskProposal(
                    title="整理并提交活动总结材料",
                    deliverable="活动总结已按要求整理并提交。",
                    execution_points=["汇总活动结果", "按要求提交总结"],
                    cautions=[],
                    prerequisites=[],
                ),
            ),
        ],
    )


def fact_extraction() -> AIItemFactExtractionOut:
    return AIItemFactExtractionOut(
        suggestions=[
            AIItemFactSuggestion(
                text="来访时间为周三 14:00。",
                reason="更新明确写明了到达时间。",
                scope="global",
                related_task_ids=[],
                supersedes_fact_id=None,
            )
        ]
    )


def usage():
    return SimpleNamespace(input_tokens=101, output_tokens=79, total_tokens=180)


class FakeResponses:
    def __init__(self, calls, *, output_text: str | None = None):
        self.calls = calls
        self.output_text = output_text

    def parse(self, **kwargs):
        self.calls["parse_count"] = self.calls.get("parse_count", 0) + 1
        self.calls["parse"] = kwargs
        format_type = kwargs.get("text_format")
        parsed = (
            review() if format_type is AIItemReviewOut
            else fact_extraction() if format_type is AIItemFactExtractionOut
            else draft()
        )
        return SimpleNamespace(output_parsed=parsed, usage=usage())

    def create(self, **kwargs):
        self.calls["create_count"] = self.calls.get("create_count", 0) + 1
        self.calls["create"] = kwargs
        return SimpleNamespace(output_text=self.output_text, usage=usage())


class FakeClient:
    def __init__(self, calls, *, output_text: str | None = None):
        self.responses = FakeResponses(calls, output_text=output_text)


class FakeGeminiInteractions:
    def __init__(self, calls, output_text, status="completed"):
        self.calls = calls
        self.output_text = output_text
        self.status = status

    def create(self, **kwargs):
        self.calls["create_count"] = self.calls.get("create_count", 0) + 1
        self.calls["create"] = kwargs
        return SimpleNamespace(
            status=self.status,
            output_text=self.output_text,
            usage=SimpleNamespace(
                total_input_tokens=101,
                total_output_tokens=79,
                total_tokens=180,
            ),
        )


class FakeGeminiClient:
    def __init__(self, calls, output_text, status="completed"):
        self.calls = calls
        self.interactions = FakeGeminiInteractions(calls, output_text, status)

    def close(self):
        self.calls["closed"] = True


def valid_json() -> str:
    return json.dumps(draft().model_dump(mode="json"), ensure_ascii=False)


def valid_review_json() -> str:
    return json.dumps(review().model_dump(mode="json"), ensure_ascii=False)


def valid_fact_extraction_json() -> str:
    return json.dumps(fact_extraction().model_dump(mode="json"), ensure_ascii=False)


def configure(provider_name: str, base_url: str = "") -> None:
    os.environ.update(
        {
            "AI_PROVIDER": provider_name,
            "AI_API_KEY": "ci-placeholder",
            "AI_MODEL": "deepseek-flash" if provider_name == "deepseek" else "ci-model",
            "AI_BASE_URL": base_url,
        }
    )


def expect_invalid(callback) -> None:
    try:
        callback()
    except PlannerInvalidResponse:
        return
    raise AssertionError("expected PlannerInvalidResponse")


def assert_generation_prompt_contract() -> None:
    required_guidance = (
        "最小但完整、能落地验收的责任分工",
        "相对独立的责任单元，而不是一个动作步骤",
        "item.deliverable 必须返回空字符串",
        "Task 不是一个待办动作，而是“需要有人对一个可确认结果负责”的责任单元",
        "个人赶路、通勤、拿电脑/普通物品",
        "同一批设备由同一责任人负责去程运输与活动后的回运、清点和交接时，默认合并",
        "若条件现在不成立，这个 Task 就不能合理开始",
        "不要默认“装箱、装车、开车、打包进箱、打印、拉微信群、使用 Excel”等具体方式",
        "做完后必须产生可观察的结果",
        "通常由同一责任人连续完成，并共同形成一个结果，就合并为一个任务",
        "deliverable 写成具体、可检查的结果",
        "没有提到直播时，不生成直播设备检查、直播值守，也不询问直播平台",
        "没有提到预算或采购时，不生成预算审批/采购任务，也不询问预算",
        "未在负责人描述或本次事项资料中提出的可选活动，不是“尚未确认的未知信息”",
        "不得生成任务或 question 去询问用户是否要增加该可选活动",
        "questions 的优先级最低",
        "先形成完整、可执行的 tasks",
        "已有任一 task，或可以合理生成一个团队 task",
        "没有任何已有或可合理生成的团队 task 能够解决该未知",
        "task 与 question 对同一未知信息绝对互斥",
        "title、deliverable、execution_points 或 prerequisites",
        "该 question 必须删除",
        "即使负责人现在直接回答会更方便",
        "先检查并定稿 tasks，再检查 questions，最后检查 suggestions",
        "suggestions 是独立于当前需求边界的“可能遗漏”提醒层",
        "它不属于本次已确认事实",
        "不得改变 tasks / questions 的需求边界",
        "本次实际检索到的团队 Knowledge 中存在真实、直接相关的依据",
        "确认过的 SOP / Playbook 中明确标注的“可提醒事项”",
        "团队执行指南将……作为此类场景的可选事项",
        "负责人对某项内容的明确否定具有最高优先级",
        "不要生成“仅作信息记录”“虽然不需要但提醒”等变体",
        "如果检索到独立且适用的宣传可提醒事项，宣传仍可单独判断",
        "明确否定的事项是否还出现在任何输出层",
        "不需要直播",
        "只允许用于判断 suggestions，绝对不得据此增加、修改或扩大 tasks / questions",
        "生成 suggestion 后不得回头把它自动塞入 task 或 question",
        "同一事项不能同时存在于 task + suggestion 或 question + suggestion",
        "0 条完全合法，通常 0～2 条最佳，最多 3 条",
        "不要为了达到上限凑数",
        "当前明确不需要的事项不得进入 suggestions",
        "当前已经明确需要的事项应该进入正式 task",
        "suggestions 同样遵守子意图不外溢",
        "questions 可以为空，0 个问题完全合法",
        "通常保持 0～3 个，不要为了接近最多 6 个而凑问题",
        "不要因为历史资料中曾经做过某项，就默认本次一定需要",
        "10 月 12 日去力旺实验小学参加科技展",
        "网络仅在直播、联网展示或在线演示等需求明确时重点确认",
        "停车仅在车辆运输或停车需求明确时确认",
        "预算仅在采购、报销或付费需求明确时确认",
        "宣传物料仅在用户明确提出宣传、展示物或物料制作时生成",
        "摄影/拍摄仅在用户提出素材采集时生成",
        "不得问“是否需要直播/线上转播”",
        "不得把照片、视频或素材写成供后续宣传",
        "未提到直播/联网展示/在线演示时，不把网络支持当作待确认未知",
        "两个 task 是否确认同一件事",
        "两个 deliverable 是否重复要求同一产物",
        "如果已生成“确认参展项目及技术负责人”，不得再问“是否已确定带哪些机器人或展示项目”",
        "execution_points 最多 6 条",
        "cautions 最多 5 条",
        "prerequisites 最多 4 条",
        "只用于“若条件现在不成立，这个 Task 就不能合理开始”的少数真实阻塞条件",
        "团队 SOP 可用于补充必要的执行要点和前置条件",
        "历史经验可用于提出与当前明确需求直接相关的注意事项",
        "不得编造“团队以前发生过”的事故、遗漏或失败",
        "只调整第 N 张任务卡",
    )
    for guidance in required_guidance:
        assert guidance in SYSTEM_PROMPT, guidance


def assert_review_prompt_contract() -> None:
    required_guidance = (
        "你不是从零规划",
        "0 条建议完全合法",
        "done 代表已发生的执行历史",
        "doing 任务只有当前新事实确实影响继续执行时才做最小调整",
        "todo 任务如能覆盖变化，优先 update_task",
        "绝不建议删除任务",
        "Knowledge 只用于改善当前明确需求",
        "团队历史经验只帮助完善执行提示",
        "不要把历史活动的日期、地点、人数、负责人或安排当成当前事实",
        "不能直接修改数据库",
    )
    for guidance in required_guidance:
        assert guidance in ITEM_REVIEW_SYSTEM_PROMPT, guidance


def run_with_fake(provider_name: str, *, output_text: str | None = None, base_url: str = ""):
    calls = {}
    configure(provider_name, base_url)

    def fake_openai(**kwargs):
        calls["client"] = kwargs
        return FakeClient(calls, output_text=output_text)

    with patch("app.ai_planner.OpenAI", side_effect=fake_openai):
        provider = get_planner_provider()
        generation = provider.generate("准备一次校园科技展示，需要摄影和资料整理。")
    return provider, generation, calls


def main() -> None:
    task_deadline_schema = AIPlannerTaskDraft.model_json_schema()
    assert "deadline" in task_deadline_schema["required"]
    assert task_deadline_schema["properties"]["deadline"]["anyOf"][-1] == {"type": "null"}
    assert_generation_prompt_contract()
    assert_review_prompt_contract()
    assert "不得补充、推断或预测" in ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert "等待回复" in ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    zero_question_draft = draft().model_dump(mode="json")
    zero_question_draft["questions"] = []
    assert AIPlannerDraft.model_validate(zero_question_draft).questions == []
    assert AIItemReviewOut(summary="当前方案无需调整。", suggestions=[]).suggestions == []
    review_schema = AIItemReviewOut.model_json_schema()
    assert review_schema["properties"]["suggestions"]["maxItems"] == 6
    assert review_schema["required"] == ["summary", "suggestions"]
    proposal_schema = review_schema["$defs"]["AIItemReviewTaskProposal"]
    assert set(proposal_schema["required"]) == {
        "title", "deliverable", "execution_points", "cautions", "prerequisites"
    }
    assert "owner_id" not in proposal_schema["properties"]
    assert "result" not in proposal_schema["properties"]
    assert "deadline" not in proposal_schema["properties"]
    too_many_review_suggestions = review().model_dump(mode="json")
    too_many_review_suggestions["suggestions"] *= 4
    try:
        AIItemReviewOut.model_validate(too_many_review_suggestions)
    except ValidationError:
        pass
    else:
        raise AssertionError("AI item review should allow at most six suggestions")

    legacy_without_suggestions = draft().model_dump(mode="json")
    legacy_without_suggestions.pop("suggestions")
    assert AIPlannerDraft.model_validate(legacy_without_suggestions).suggestions == []

    suggestion = AIPlannerSuggestionDraft(
        title="  战队周边展示  ",
        reason="  类似科技展示曾使用少量战队周边作为展台展示，本次描述尚未提及。  ",
    )
    assert suggestion.title == "战队周边展示"
    assert suggestion.reason.startswith("类似科技展示")

    too_many = draft().model_dump(mode="json")
    too_many["suggestions"] = [
        {"title": f"建议{i}", "reason": "有直接相关的团队历史依据。"}
        for i in range(4)
    ]
    try:
        AIPlannerDraft.model_validate(too_many)
    except ValidationError:
        pass
    else:
        raise AssertionError("planner suggestions should allow at most 3 items")

    for bad_suggestion in (
        {"title": "x" * 81, "reason": "有依据"},
        {"title": "有效标题", "reason": "x" * 201},
        {"title": "   ", "reason": "有依据"},
    ):
        try:
            AIPlannerSuggestionDraft.model_validate(bad_suggestion)
        except ValidationError:
            pass
        else:
            raise AssertionError("planner suggestion length/content validation should fail")

    openai_provider, openai_generation, openai_calls = run_with_fake("openai")
    assert isinstance(openai_provider, OpenAIPlannerProvider)
    assert openai_calls.get("parse_count") == 1
    assert openai_calls.get("create_count", 0) == 0
    assert openai_calls["parse"]["text_format"] is AIPlannerDraft
    assert openai_calls["parse"]["max_output_tokens"] == 2200
    assert "reasoning" not in openai_calls["parse"]
    assert openai_calls["parse"]["store"] is False
    assert openai_calls["parse"]["model"] == "ci-model"
    assert openai_calls["parse"]["instructions"] == SYSTEM_PROMPT
    assert "base_url" not in openai_calls["client"]
    assert openai_calls["client"]["max_retries"] == 0
    assert openai_generation.total_tokens == 180

    deepseek_provider, deepseek_generation, deepseek_calls = run_with_fake(
        "deepseek",
        output_text=valid_json(),
        base_url=DEEPSEEK_DEFAULT_BASE_URL,
    )
    assert isinstance(deepseek_provider, DeepSeekPlannerProvider)
    assert deepseek_calls.get("create_count") == 1
    assert deepseek_calls.get("parse_count", 0) == 0
    assert deepseek_calls["client"]["base_url"] == DEEPSEEK_DEFAULT_BASE_URL
    assert deepseek_calls["create"]["model"] == "deepseek-flash"
    assert deepseek_calls["create"]["max_output_tokens"] == 4096
    assert deepseek_calls["create"]["reasoning"]["effort"] == "none"
    assert deepseek_calls["create"]["store"] is False
    assert deepseek_calls["create"]["instructions"] == SYSTEM_PROMPT
    assert deepseek_calls["client"]["max_retries"] == 0

    text_format = deepseek_calls["create"]["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"] == AIPlannerDraft.model_json_schema()
    draft_schema = text_format["schema"]
    assert "suggestions" in draft_schema["required"]
    assert draft_schema["properties"]["suggestions"]["maxItems"] == 3
    suggestion_schema = draft_schema["$defs"]["AIPlannerSuggestionDraft"]
    assert suggestion_schema["properties"]["title"]["maxLength"] == 80
    assert suggestion_schema["properties"]["reason"]["maxLength"] == 200

    task_schema = draft_schema["$defs"]["AIPlannerTaskDraft"]
    assert {"execution_points", "cautions", "prerequisites"} <= set(task_schema["required"])
    assert task_schema["properties"]["execution_points"]["maxItems"] == 6
    assert task_schema["properties"]["execution_points"]["items"]["maxLength"] == 240
    assert task_schema["properties"]["cautions"]["maxItems"] == 5
    assert task_schema["properties"]["prerequisites"]["maxItems"] == 4
    assert deepseek_generation.draft == draft()
    assert deepseek_generation.input_tokens == 101
    assert deepseek_generation.output_tokens == 79
    assert deepseek_generation.total_tokens == 180
    assert deepseek_calls["create_count"] == 1

    review_context = "【当前事项执行状态 JSON】\n{}"
    openai_review_calls = {}

    def fake_openai_review(**kwargs):
        openai_review_calls["client"] = kwargs
        return FakeClient(openai_review_calls)

    with patch("app.ai_planner.OpenAI", side_effect=fake_openai_review):
        openai_review_provider = OpenAIPlannerProvider()
        openai_review_generation = openai_review_provider.review(review_context)
    assert openai_review_calls.get("parse_count") == 1
    assert openai_review_calls.get("create_count", 0) == 0
    assert openai_review_calls["parse"]["text_format"] is AIItemReviewOut
    assert openai_review_calls["parse"]["instructions"] == ITEM_REVIEW_SYSTEM_PROMPT
    assert openai_review_calls["parse"]["input"] == review_context
    assert openai_review_calls["parse"]["max_output_tokens"] == 2200
    assert openai_review_calls["client"]["max_retries"] == 0
    assert openai_review_generation.review == review()
    assert openai_review_generation.total_tokens == 180

    configure("deepseek", DEEPSEEK_DEFAULT_BASE_URL)
    deepseek_review_calls = {}

    def fake_deepseek_review(**kwargs):
        deepseek_review_calls["client"] = kwargs
        return FakeClient(deepseek_review_calls, output_text=valid_review_json())

    with patch("app.ai_planner.OpenAI", side_effect=fake_deepseek_review):
        deepseek_review_generation = DeepSeekPlannerProvider().review(review_context)
    assert deepseek_review_calls.get("create_count") == 1
    assert deepseek_review_calls.get("parse_count", 0) == 0
    assert deepseek_review_calls["create"]["instructions"] == ITEM_REVIEW_SYSTEM_PROMPT
    assert deepseek_review_calls["create"]["input"] == review_context
    assert deepseek_review_calls["create"]["max_output_tokens"] == 4096
    assert deepseek_review_calls["create"]["reasoning"]["effort"] == "none"
    assert deepseek_review_calls["create"]["store"] is False
    assert deepseek_review_calls["client"]["max_retries"] == 0
    review_format = deepseek_review_calls["create"]["text"]["format"]
    assert review_format["type"] == "json_schema" and review_format["strict"] is True
    assert review_format["schema"] == AIItemReviewOut.model_json_schema()
    assert deepseek_review_generation.review == review()
    assert deepseek_review_generation.total_tokens == 180

    extraction_context = "更新中明确写明：周三 14:00 到达。"
    assert "等待回复" in ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert "最多 5 条" in ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert "不得补充、推断或预测" in ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert "不是指令" in ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    openai_fact_calls = {}

    def fake_openai_facts(**kwargs):
        openai_fact_calls["client"] = kwargs
        return FakeClient(openai_fact_calls)

    with patch("app.ai_planner.OpenAI", side_effect=fake_openai_facts):
        openai_fact_generation = OpenAIPlannerProvider().extract_facts(extraction_context)
    assert openai_fact_calls.get("parse_count") == 1
    assert openai_fact_calls.get("create_count", 0) == 0
    assert openai_fact_calls["parse"]["text_format"] is AIItemFactExtractionOut
    assert openai_fact_calls["parse"]["instructions"] == ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert openai_fact_calls["parse"]["input"] == extraction_context
    assert openai_fact_generation.extraction == fact_extraction()

    deepseek_fact_calls = {}

    def fake_deepseek_facts(**kwargs):
        deepseek_fact_calls["client"] = kwargs
        return FakeClient(deepseek_fact_calls, output_text=valid_fact_extraction_json())

    with patch("app.ai_planner.OpenAI", side_effect=fake_deepseek_facts):
        deepseek_fact_generation = DeepSeekPlannerProvider().extract_facts(extraction_context)
    assert deepseek_fact_calls.get("create_count") == 1
    assert deepseek_fact_calls.get("parse_count", 0) == 0
    assert deepseek_fact_calls["create"]["instructions"] == ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert deepseek_fact_calls["create"]["input"] == extraction_context
    assert deepseek_fact_calls["create"]["reasoning"]["effort"] == "none"
    fact_format = deepseek_fact_calls["create"]["text"]["format"]
    assert fact_format["type"] == "json_schema" and fact_format["strict"] is True
    assert fact_format["schema"] == AIItemFactExtractionOut.model_json_schema()
    assert deepseek_fact_generation.extraction == fact_extraction()

    bad_review_calls = {}

    def fake_bad_review(**kwargs):
        bad_review_calls["client"] = kwargs
        return FakeClient(bad_review_calls, output_text="{not valid json")

    with patch("app.ai_planner.OpenAI", side_effect=fake_bad_review):
        expect_invalid(lambda: DeepSeekPlannerProvider().review(review_context))
    assert bad_review_calls.get("create_count") == 1
    assert bad_review_calls.get("parse_count", 0) == 0

    configure("deepseek")
    default_calls = {}

    def fake_default_openai(**kwargs):
        default_calls["client"] = kwargs
        return FakeClient(default_calls, output_text=valid_json())

    with patch("app.ai_planner.OpenAI", side_effect=fake_default_openai):
        DeepSeekPlannerProvider().generate("准备一次校园科技展示，需要摄影和资料整理。")
    assert default_calls["client"]["base_url"] == DEEPSEEK_DEFAULT_BASE_URL
    assert default_calls.get("create_count") == 1
    assert default_calls.get("parse_count", 0) == 0

    for bad_output in ("", "not json"):
        configure("deepseek", DEEPSEEK_DEFAULT_BASE_URL)
        bad_calls = {}

        def fake_bad_openai(**kwargs):
            bad_calls["client"] = kwargs
            return FakeClient(bad_calls, output_text=bad_output)

        with patch("app.ai_planner.OpenAI", side_effect=fake_bad_openai):
            expect_invalid(
                lambda: DeepSeekPlannerProvider().generate(
                    "准备一次校园科技展示，需要摄影和资料整理。"
                )
            )
        assert bad_calls.get("create_count") == 1
        assert bad_calls.get("parse_count", 0) == 0

    schema_mismatch = json.dumps(
        {
            "item": {
                "title": "校园科技展",
                "deliverable": "完成现场展示。",
                "deadline": None,
            },
            "tasks": [{"title": "现场摄影"}],
            "questions": [],
        },
        ensure_ascii=False,
    )
    configure("deepseek", DEEPSEEK_DEFAULT_BASE_URL)
    mismatch_calls = {}

    def fake_mismatch_openai(**kwargs):
        mismatch_calls["client"] = kwargs
        return FakeClient(mismatch_calls, output_text=schema_mismatch)

    with patch("app.ai_planner.OpenAI", side_effect=fake_mismatch_openai):
        expect_invalid(
            lambda: DeepSeekPlannerProvider().generate(
                "准备一次校园科技展示，需要摄影和资料整理。"
            )
        )
    assert mismatch_calls.get("create_count") == 1
    assert mismatch_calls.get("parse_count", 0) == 0

    configure("gemini")
    os.environ["GEMINI_API_KEY"] = "ci-placeholder"
    os.environ["GEMINI_MODEL"] = "gemini-3.8-flash"
    assert provider_is_configured()
    assert isinstance(get_planner_provider(), GeminiPlannerProvider)
    gemini_calls = {}

    def fake_gemini(**kwargs):
        gemini_calls["client"] = kwargs
        return FakeGeminiClient(gemini_calls, valid_json())

    with patch("app.ai_planner.genai.Client", side_effect=fake_gemini):
        gemini_generation = get_planner_provider().generate("准备一次校园科技展示，需要摄影和资料整理。")
    assert gemini_calls["client"]["api_key"] == "ci-placeholder"
    assert gemini_calls["client"]["http_options"].timeout == 30000
    assert gemini_calls["client"]["http_options"].retry_options.attempts == 1
    assert gemini_calls["create_count"] == 1
    assert gemini_calls["closed"] is True
    gemini_request = gemini_calls["create"]
    assert gemini_request["model"] == "gemini-3.8-flash"
    assert gemini_request["system_instruction"] == SYSTEM_PROMPT
    assert gemini_request["store"] is False
    assert gemini_request["generation_config"] == {"max_output_tokens": 4096}
    assert gemini_request["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": AIPlannerDraft.model_json_schema(),
    }
    assert "ci-placeholder" not in repr(gemini_request)
    assert gemini_generation.draft == draft()
    assert gemini_generation.input_tokens == 101
    assert gemini_generation.output_tokens == 79
    assert gemini_generation.total_tokens == 180

    for status_code, expected_error, expected_category in (
        (503, PlannerProviderError, "provider_server_error"),
        (429, PlannerRateLimitError, "rate_limit_or_quota"),
    ):
        failed_gemini_calls = {}

        def fake_failed_gemini(**kwargs):
            failed_gemini_calls["client"] = kwargs
            client = FakeGeminiClient(failed_gemini_calls, valid_json())

            def raise_api_error(**_request):
                failed_gemini_calls["create_count"] = failed_gemini_calls.get("create_count", 0) + 1
                upstream_status = "UNAVAILABLE" if status_code == 503 else "RESOURCE_EXHAUSTED"
                raise genai_errors.APIError(
                    status_code,
                    {"error": {"message": "PRIVATE_PROVIDER_BODY", "status": upstream_status}},
                )

            client.interactions.create = raise_api_error
            return client

        with patch("app.ai_planner.genai.Client", side_effect=fake_failed_gemini):
            with patch("app.ai_planner.logger.error") as error_logger:
                try:
                    GeminiPlannerProvider().generate("PRIVATE_USER_INPUT")
                except expected_error:
                    pass
                else:
                    raise AssertionError(f"expected {expected_error.__name__}")

        assert failed_gemini_calls["create_count"] == 1
        assert failed_gemini_calls["closed"] is True
        assert error_logger.call_count == 1
        logged = error_logger.call_args.args[0] % error_logger.call_args.args[1:]
        assert logged.startswith("ai_provider_request_failed ")
        log_fields = json.loads(logged.removeprefix("ai_provider_request_failed "))
        assert log_fields["provider"] == "gemini"
        assert log_fields["model"] == "gemini-3.8-flash"
        assert log_fields["exception_type"] == "APIError"
        assert log_fields["upstream_http_status"] == status_code
        assert isinstance(log_fields["duration_ms"], int)
        assert log_fields["error_category"] == expected_category
        assert "PRIVATE_USER_INPUT" not in logged
        assert "PRIVATE_PROVIDER_BODY" not in logged
        assert "ci-placeholder" not in logged

    late_deadline_payload = draft().model_dump(mode="json")
    late_deadline_payload["item"]["deadline"] = "2026-10-12T08:00:00+08:00"
    late_deadline_payload["tasks"][0]["deadline"] = "2026-10-12T01:00:01Z"
    invalid_deadline_calls = {}

    def fake_late_deadline_gemini(**kwargs):
        invalid_deadline_calls["client"] = kwargs
        return FakeGeminiClient(
            invalid_deadline_calls,
            json.dumps(late_deadline_payload, ensure_ascii=False),
        )

    with patch("app.ai_planner.genai.Client", side_effect=fake_late_deadline_gemini):
        expect_invalid(lambda: GeminiPlannerProvider().generate("事项截止时间为 10 月 12 日。"))
    assert invalid_deadline_calls.get("create_count") == 1

    gemini_review_calls = {}

    def fake_gemini_review(**kwargs):
        gemini_review_calls["client"] = kwargs
        return FakeGeminiClient(gemini_review_calls, valid_review_json())

    with patch("app.ai_planner.genai.Client", side_effect=fake_gemini_review):
        gemini_review_generation = GeminiPlannerProvider().review(review_context)
    assert gemini_review_calls["create"]["system_instruction"] == ITEM_REVIEW_SYSTEM_PROMPT
    assert gemini_review_calls["create"]["input"] == review_context
    assert gemini_review_calls["create"]["response_format"]["schema"] == AIItemReviewOut.model_json_schema()
    assert gemini_review_calls["create"]["generation_config"] == {"max_output_tokens": 2200}
    assert gemini_review_generation.review == review()
    assert gemini_review_generation.total_tokens == 180

    gemini_facts_calls = {}

    def fake_gemini_facts(**kwargs):
        gemini_facts_calls["client"] = kwargs
        return FakeGeminiClient(gemini_facts_calls, valid_fact_extraction_json())

    with patch("app.ai_planner.genai.Client", side_effect=fake_gemini_facts):
        gemini_facts_generation = GeminiPlannerProvider().extract_facts(extraction_context)
    assert gemini_facts_calls["create"]["system_instruction"] == ITEM_FACT_EXTRACTION_SYSTEM_PROMPT
    assert gemini_facts_calls["create"]["input"] == extraction_context
    assert gemini_facts_calls["create"]["response_format"]["schema"] == AIItemFactExtractionOut.model_json_schema()
    assert gemini_facts_calls["create"]["generation_config"] == {"max_output_tokens": 2200}
    assert gemini_facts_generation.extraction == fact_extraction()

    for invalid_output, status in (("not json", "completed"), (valid_json(), "failed")):
        invalid_gemini_calls = {}

        def fake_invalid_gemini(**kwargs):
            invalid_gemini_calls["client"] = kwargs
            return FakeGeminiClient(invalid_gemini_calls, invalid_output, status=status)

        with patch("app.ai_planner.genai.Client", side_effect=fake_invalid_gemini):
            expect_invalid(lambda: GeminiPlannerProvider().generate("一个需要拆解的事项。"))
        assert invalid_gemini_calls.get("create_count") == 1
        assert invalid_gemini_calls["closed"] is True

    print("AI provider adapter tests passed")


if __name__ == "__main__":
    main()
