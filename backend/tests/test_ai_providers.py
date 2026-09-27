import os
from types import SimpleNamespace
from unittest.mock import patch

from app.ai_planner import (
    DEEPSEEK_DEFAULT_BASE_URL,
    DeepSeekPlannerProvider,
    OpenAIPlannerProvider,
    get_planner_provider,
)
from app.schemas import AIPlannerDraft, AIPlannerItemDraft, AIPlannerTaskDraft


def draft():
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
        questions=[],
    )


class FakeResponses:
    def __init__(self, calls):
        self.calls = calls

    def parse(self, **kwargs):
        self.calls["parse"] = kwargs
        return SimpleNamespace(
            output_parsed=draft(),
            usage=SimpleNamespace(
                input_tokens=101,
                output_tokens=79,
                total_tokens=180,
            ),
        )


class FakeClient:
    def __init__(self, calls):
        self.responses = FakeResponses(calls)


def exercise(provider_name: str, base_url: str):
    calls = {}

    def fake_openai(**kwargs):
        calls["client"] = kwargs
        return FakeClient(calls)

    os.environ.update(
        {
            "AI_PROVIDER": provider_name,
            "AI_API_KEY": "ci-placeholder",
            "AI_MODEL": "deepseek-flash" if provider_name == "deepseek" else "ci-model",
            "AI_BASE_URL": base_url,
        }
    )

    with patch("app.ai_planner.OpenAI", side_effect=fake_openai):
        provider = get_planner_provider()
        generation = provider.generate("准备一次校园科技展示，需要摄影和资料整理。")

    assert calls["parse"]["text_format"] is AIPlannerDraft
    assert calls["parse"]["max_output_tokens"] == 2200
    assert calls["parse"]["store"] is False
    assert generation.input_tokens == 101
    assert generation.output_tokens == 79
    assert generation.total_tokens == 180
    return provider, calls


def main() -> None:
    provider, calls = exercise("openai", "")
    assert isinstance(provider, OpenAIPlannerProvider)
    assert "base_url" not in calls["client"]
    assert calls["parse"]["model"] == "ci-model"

    provider, calls = exercise("deepseek", DEEPSEEK_DEFAULT_BASE_URL)
    assert isinstance(provider, DeepSeekPlannerProvider)
    assert calls["client"]["base_url"] == "https://api.deepseek.com"
    assert calls["parse"]["model"] == "deepseek-flash"

    os.environ["AI_BASE_URL"] = ""
    calls = {}

    def fake_openai(**kwargs):
        calls["client"] = kwargs
        return FakeClient(calls)

    with patch("app.ai_planner.OpenAI", side_effect=fake_openai):
        provider = get_planner_provider()
        provider.generate("准备一次校园科技展示，需要摄影和资料整理。")
    assert calls["client"]["base_url"] == DEEPSEEK_DEFAULT_BASE_URL

    print("AI provider adapter tests passed")


if __name__ == "__main__":
    main()
