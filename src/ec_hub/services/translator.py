"""翻訳サービス.

商品タイトル・説明文の日本語→英語翻訳を提供する。
- メイン: DeepL API (月50万字まで無料)
- フォールバック: nani.now (Web翻訳サービス)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class Translator(ABC):
    """翻訳の抽象基底クラス."""

    @abstractmethod
    async def translate(self, text: str, *, source_lang: str = "JA", target_lang: str = "EN") -> str:
        """テキストを翻訳する."""
        ...

    async def close(self) -> None:
        """リソースの解放."""


class DeepLTranslator(Translator):
    """DeepL API を使った翻訳."""

    DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"

    def __init__(self, api_key: str, *, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def translate(self, text: str, *, source_lang: str = "JA", target_lang: str = "EN") -> str:
        if not self.is_configured:
            logger.warning("DeepL API未設定。原文をそのまま返します。")
            return text

        client = await self._get_client()
        try:
            resp = await client.post(
                self.DEEPL_API_URL,
                data={
                    "auth_key": self._api_key,
                    "text": text,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            translations = data.get("translations", [])
            if translations:
                translated = translations[0].get("text", text)
                logger.debug("DeepL翻訳: %s → %s", text[:30], translated[:30])
                return translated
        except httpx.HTTPError as e:
            logger.error("DeepL API翻訳失敗: %s", e)

        return text


class NaniTranslator(Translator):
    """nani.now を使った翻訳 (フォールバック用).

    nani.now は公開APIを提供していないため、
    将来的にAPI公開された場合の拡張ポイントとして用意。
    現在は原文をそのまま返す。
    """

    async def translate(self, text: str, *, source_lang: str = "JA", target_lang: str = "EN") -> str:
        logger.info("nani翻訳: API未公開のため原文を返します。")
        return text


def create_translator(settings: dict) -> Translator:
    """設定に基づいて翻訳クライアントを生成する."""
    deepl_config = settings.get("deepl", {})
    api_key = deepl_config.get("api_key", "")
    if api_key:
        return DeepLTranslator(api_key)

    logger.warning("翻訳API未設定。naniフォールバックを使用（原文返却）。")
    return NaniTranslator()
