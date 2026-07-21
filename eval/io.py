"""
RAG 评测文件读写工具
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """读取 JSONL 数据集，自动跳过空行"""

    dataset_path = Path(path)
    cases = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cases.append(json.loads(line))
    return cases


def write_json(path: str | Path, data: Any) -> None:
    """写入 JSON 文件，自动创建父目录"""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def write_text(path: str | Path, content: str) -> None:
    """写入文本文件，自动创建父目录"""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def _json_default(value: Any):
    """把 SQL 结果中常见的非 JSON 类型转换为可写入格式"""

    if isinstance(value, Decimal):
        return float(value)
    return str(value)
