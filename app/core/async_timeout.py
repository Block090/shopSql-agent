"""Async timeout helpers for external model and retrieval calls."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from app.core.log import logger

T = TypeVar("T")


async def run_with_timeout(
    awaitable: Awaitable[T],
    *,
    timeout_seconds: float,
    default: T,
    operation_name: str,
) -> T:
    """Return default when an external awaitable is too slow or fails."""

    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError:
        logger.warning(f"{operation_name} 超时，已使用降级结果继续执行")
        return default
    except Exception as exc:
        logger.warning(f"{operation_name} 失败，已使用降级结果继续执行：{exc}")
        return default
