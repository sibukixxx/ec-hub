"""翻訳サービスのテスト."""

from ec_hub.services.translator import (
    DeepLTranslator,
    NaniTranslator,
    create_translator,
)


def test_deepl_not_configured():
    t = DeepLTranslator(api_key="")
    assert t.is_configured is False


def test_deepl_configured():
    t = DeepLTranslator(api_key="test-key")
    assert t.is_configured is True


async def test_deepl_unconfigured_returns_original():
    t = DeepLTranslator(api_key="")
    result = await t.translate("テスト商品")
    assert result == "テスト商品"


async def test_nani_returns_original():
    t = NaniTranslator()
    result = await t.translate("テスト商品")
    assert result == "テスト商品"


def test_create_translator_with_deepl():
    t = create_translator({"deepl": {"api_key": "test-key"}})
    assert isinstance(t, DeepLTranslator)


def test_create_translator_fallback_nani():
    t = create_translator({"deepl": {"api_key": ""}})
    assert isinstance(t, NaniTranslator)


def test_create_translator_no_config():
    t = create_translator({})
    assert isinstance(t, NaniTranslator)
