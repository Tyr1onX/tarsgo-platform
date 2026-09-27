import os
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError

from .schemas import AIPlannerDraft

MAX_OUTPUT_TOKENS = 2200
REQUEST_TIMEOUT_SECONDS = 30.0
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"

SYSTEM_PROMPT = """你负责把高校机器人团队已经明确要做的运营事项整理成可编辑的执行草案。

只处理活动、宣传、纳新、摄影、直播、物资、展示、研学、对外交流等运营事务。
暂不处理机械、电控、视觉、算法等技术研发流程。

拆分时重点考虑时间、地点、人员连续性、交接点和完成标准。
天然连续、适合同一人完成的动作尽量合并；同时进行且通常无法由一人兼任的工作应拆开。
不要为了显得详细而过度拆分。每个分工应尽量回答“谁把什么做到什么程度”。
不确定的信息不要编造；会影响执行的不确定项放入 questions。
人员未明确时优先建议 owner_claimable=true。
完成标准要具体但简短，不写成长 SOP。
不要输出 owner_id、姓名或任何真实成员分配建议。
如果没有明确到可直接使用的截止日期和时间，deadline 返回 null，并在 questions 中提示确认。
最多生成 15 个一级分工、6 个确认问题。
你只生成建议草案，最终由人修改并确认。"""


@dataclass
class PlannerGeneration:
    draft: AIPlannerDraft
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class PlannerProvider(Protocol):
    def generate(self, description: str) -> PlannerGeneration: ...


class PlannerProviderError(Exception):
    pass


class PlannerTimeoutError(PlannerProviderError):
    pass


class PlannerRateLimitError(PlannerProviderError):
    pass


class PlannerInvalidResponse(PlannerProviderError):
    pass


def configured_provider_name() -> str:
    return os.getenv("AI_PROVIDER", "openai").strip().lower() or "openai"


def _client(*, base_url: str | None = None) -> OpenAI:
    kwargs = {
        "api_key": os.environ["AI_API_KEY"],
        "timeout": REQUEST_TIMEOUT_SECONDS,
        "max_retries": 0,
    }
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _generate_structured(client: OpenAI, description: str) -> PlannerGeneration:
    try:
        response = client.responses.parse(
            model=os.environ["AI_MODEL"],
            instructions=SYSTEM_PROMPT,
            input=f"今天日期：{date.today().isoformat()}\n负责人描述：\n{description}",
            text_format=AIPlannerDraft,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
        )
    except APITimeoutError as exc:
        raise PlannerTimeoutError from exc
    except RateLimitError as exc:
        raise PlannerRateLimitError from exc
    except (APIConnectionError, APIError) as exc:
        raise PlannerProviderError from exc
    except Exception as exc:
        raise PlannerInvalidResponse from exc

    draft = response.output_parsed
    if draft is None:
        raise PlannerInvalidResponse

    usage = response.usage
    return PlannerGeneration(
        draft=draft,
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
    )


class OpenAIPlannerProvider:
    def generate(self, description: str) -> PlannerGeneration:
        base_url = os.getenv("AI_BASE_URL", "").strip() or None
        return _generate_structured(_client(base_url=base_url), description)


class DeepSeekPlannerProvider:
    def generate(self, description: str) -> PlannerGeneration:
        base_url = os.getenv("AI_BASE_URL", "").strip() or DEEPSEEK_DEFAULT_BASE_URL
        return _generate_structured(_client(base_url=base_url), description)


class UnavailablePlannerProvider:
    def generate(self, description: str) -> PlannerGeneration:
        raise PlannerProviderError


def get_planner_provider() -> PlannerProvider:
    provider = configured_provider_name()
    if provider == "openai":
        return OpenAIPlannerProvider()
    if provider == "deepseek":
        return DeepSeekPlannerProvider()
    return UnavailablePlannerProvider()
