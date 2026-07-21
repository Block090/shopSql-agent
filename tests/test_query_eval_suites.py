import json
from pathlib import Path

from eval.runners.run_eval import _select_cases
from eval.schemas.eval_case import EvalCase


def test_full_query_eval_dataset_has_eighty_cases_and_required_categories():
    rows = [
        json.loads(line)
        for line in Path("eval/datasets/query_eval_cases.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    assert len(rows) == 80
    tags = {tag for row in rows for tag in row.get("tags", [])}
    assert {"metric", "trend", "multi_turn", "unknown_domain", "safety", "permission", "large_result"} <= tags
    assert len(_select_cases(rows, "core")) == 23


def test_eval_case_preserves_permission_and_conversation_metadata():
    case = EvalCase.from_dict(
        {
            "id": "case",
            "query": "那华东呢",
            "suite": "extended",
            "tags": ["multi_turn"],
            "user_id": "region_east",
            "conversation": [{"role": "user", "content": "统计全国GMV"}],
        }
    ).to_dict()

    assert case["suite"] == "extended"
    assert case["user_id"] == "region_east"
    assert case["conversation"][0]["role"] == "user"
