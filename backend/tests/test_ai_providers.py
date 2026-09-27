import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from app.ai_planner import (
    DEEPSEEK_DEFAULT_BASE_URL,
    DeepSeekPlannerProvider,
    OpenAIPlannerProvider,
    PlannerInvalidResponse,
    get_planner_provider,
)
from app.schemas import AIPlannerDraft, AIPlannerItemDraft, AIPlannerTaskDraft


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
                owner_claimable=True,
                collaboration_open=True,
            )
        ],
        questions=["确认活动结束时间。"],
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
        return SimpleNamespace(output_parsed=draft(), usage=usage())

    def create(self, **kwargs):
        self.calls["create_count"] = self.calls.get("create_count", 0) + 1
        self.calls["create"] = kwargs
        return SimpleNamespace(output_text=self.output_text, usage=usage())


class FakeClient:
    def __init__(self, calls, *, output_text: str | None = None):
        self.responses = FakeResponses(calls, output_text=output_text)


def valid_json() -> str:
    return json.dumps(draft().model_dump(mode="json"), ensure_ascii=False)


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
    openai_provider, openai_generation, openai_calls = run_with_fake("openai")
    assert isinstance(openai_provider, OpenAIPlannerProvider)
    assert openai_calls.get("parse_count") == 1
    assert openai_calls.get("create_count", 0) == 0
    assert openai_calls["parse"]["text_format"] is AIPlannerDraft
    assert openai_calls["parse"]["max_output_tokens"] == 2200
    assert openai_calls["parse"]["store"] is False
    assert openai_calls["parse"]["model"] == "ci-model"
    assert "base_url" not in openai_calls["client"]
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
    assert deepseek_calls["create"]["max_output_tokens"] == 2200
    assert deepseek_calls["create"]["store"] is False

    text_format = deepseek_calls["create"]["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["schema"] == AIPlannerDraft.model_json_schema()
    assert deepseek_generation.draft == draft()
    assert deepseek_generation.input_tokens == 101
    assert deepseek_generation.output_tokens == 79
    assert deepseek_generation.total_tokens == 180
    assert deepseek_calls["create_count"] == 1

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

    print("AI provider adapter tests passed")


if __name__ == "__main__":
    main()
