"""查询结果产品化模块。"""

from .analysis_writer import analyze_result_with_fallback
from .fact_extractor import extract_result_facts

__all__ = ["extract_result_facts", "analyze_result_with_fallback"]
