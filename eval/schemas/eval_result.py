"""
测评结果结构
"""

from dataclasses import dataclass


@dataclass
class EvalResult:
    """单条分层测评结果摘要"""

    case_id: str
    final_success: bool
    failure_layer: str | None = None
    failure_reason: str | None = None
