"""Permission policy loading for the demo query agent."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).parents[2] / "conf" / "permission_config.yaml"


def get_permission_context(user_id: str | None) -> dict[str, Any]:
    """Return deterministic permission context for a user.

    The current project uses a YAML-backed policy to keep the demo self-contained.
    In a production deployment this function is the seam to replace with RBAC or
    an enterprise data-permission service.
    """

    config = _load_permission_config()
    effective_user_id = user_id or config.get("default_user")
    users = config.get("users") or {}
    policy = users.get(effective_user_id) or users.get(config.get("default_user")) or {}
    context = dict(policy)
    context["user_id"] = effective_user_id
    return context


@lru_cache(maxsize=1)
def _load_permission_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"default_user": None, "users": {}}
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {"default_user": None, "users": {}}
