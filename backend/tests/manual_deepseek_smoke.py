import json
import os

from app.ai_planner import DeepSeekPlannerProvider


def main() -> None:
    if not os.getenv("AI_API_KEY", "").strip():
        raise SystemExit("AI_API_KEY is required")
    if os.getenv("AI_PROVIDER", "deepseek").strip().lower() != "deepseek":
        raise SystemExit("AI_PROVIDER must be deepseek for this smoke test")

    generation = DeepSeekPlannerProvider().generate(
        "10 月 12 日去小学做科技展，需要机器人展示、讲解、直播、摄影、周边发放，活动结束后整理素材。具体人员暂时还没定，之后开放认领。"
    )
    print(
        json.dumps(
            {
                "provider": "deepseek",
                "model": os.getenv("AI_MODEL", ""),
                "schema_valid": True,
                "task_count": len(generation.draft.tasks),
                "question_count": len(generation.draft.questions),
                "usage": {
                    "input_tokens": generation.input_tokens,
                    "output_tokens": generation.output_tokens,
                    "total_tokens": generation.total_tokens,
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
