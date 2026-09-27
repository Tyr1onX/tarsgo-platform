import json
import os

from app.ai_planner import DeepSeekPlannerProvider

SMOKE_DESCRIPTION = "10 月 12 日去力旺实验小学参加科技展，帮我规划一下。"
UNREQUESTED_TOPICS = {
    "livestream": ("直播",),
    "network": ("网络", "联网", "在线演示"),
    "parking": ("停车", "泊车"),
    "budget": ("预算", "报销", "付费"),
    "procurement": ("采购",),
    "promotion": ("宣传", "周边"),
}
CONFIRMATION_CONCEPTS = {
    "exhibition_project": ("展示项目", "参展项目", "参展内容", "展示内容", "演示项目", "演示形式", "机器人型号"),
}


def main() -> None:
    if not os.getenv("AI_API_KEY", "").strip():
        raise SystemExit("AI_API_KEY is required")
    if os.getenv("AI_PROVIDER", "deepseek").strip().lower() != "deepseek":
        raise SystemExit("AI_PROVIDER must be deepseek for this smoke test")

    generation = DeepSeekPlannerProvider().generate(
        SMOKE_DESCRIPTION
    )
    task_text = "\n".join(
        f"{task.title}\n{task.deliverable}" for task in generation.draft.tasks
    )
    question_text = "\n".join(generation.draft.questions)
    unrequested_topics = [
        topic
        for topic, terms in UNREQUESTED_TOPICS.items()
        if any(term in task_text or term in question_text for term in terms)
    ]
    repeated_confirmation_topics = [
        topic
        for topic, terms in CONFIRMATION_CONCEPTS.items()
        if any(term in task_text for term in terms)
        and any(term in question_text for term in terms)
    ]
    print(
        json.dumps(
            {
                "provider": "deepseek",
                "model": os.getenv("AI_MODEL", ""),
                "schema_valid": True,
                "task_count": len(generation.draft.tasks),
                "tasks": [
                    {"title": task.title, "deliverable": task.deliverable}
                    for task in generation.draft.tasks
                ],
                "question_count": len(generation.draft.questions),
                "questions": generation.draft.questions,
                "unrequested_topics": unrequested_topics,
                "repeated_confirmation_topics": repeated_confirmation_topics,
                "model_calls": 1,
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
