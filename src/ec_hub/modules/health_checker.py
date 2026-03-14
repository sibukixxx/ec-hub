"""外部サービスの可用性を監視するヘルスチェッカー.

integration_status テーブルに各サービスの状態を記録する。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ec_hub.db import Database

logger = logging.getLogger(__name__)

# チェック対象サービスと設定キーのマッピング
_SERVICE_CONFIG_KEYS: dict[str, tuple[str, list[str]]] = {
    "ebay": ("ebay", ["app_id", "user_token"]),
    "deepl": ("deepl", ["api_key"]),
    "claude": ("claude", ["api_key"]),
    "amazon": ("amazon", ["access_key", "secret_key"]),
    "rakuten": ("rakuten", ["app_id"]),
    "line": ("line", ["channel_access_token", "user_id"]),
}


def _get_nested(settings: object, key: str) -> object:
    """settings から値を取得 (dict / Pydantic 両対応)."""
    if isinstance(settings, dict):
        return settings.get(key, {})
    return getattr(settings, key, {})


def _get_value(obj: object, key: str) -> str:
    """obj から key の値を文字列で取得."""
    if isinstance(obj, dict):
        return str(obj.get(key, ""))
    return str(getattr(obj, key, ""))


async def check_all_services(db: Database, settings: object) -> list[dict]:
    """全サービスの設定状態をチェックし integration_status を更新する."""
    results = []
    for service_name, (config_section, required_keys) in _SERVICE_CONFIG_KEYS.items():
        section = _get_nested(settings, config_section)
        missing = [k for k in required_keys if not _get_value(section, k)]

        if not missing:
            status = "ok"
            error_message = None
        elif len(missing) == len(required_keys):
            status = "unconfigured"
            error_message = f"API keys not configured: {', '.join(missing)}"
        else:
            status = "degraded"
            error_message = f"Missing keys: {', '.join(missing)}"

        await db.upsert_integration_status(
            service_name,
            status,
            error_message=error_message,
        )
        results.append(
            {
                "service_name": service_name,
                "status": status,
                "error_message": error_message,
            }
        )
        logger.debug("ヘルスチェック: %s → %s", service_name, status)

    return results
