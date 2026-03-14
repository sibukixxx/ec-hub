"""メッセージ分類のテスト."""

from unittest.mock import AsyncMock, MagicMock

from ec_hub.models import MessageCategory
from ec_hub.modules.messenger import (
    CLASSIFICATION_SYSTEM_PROMPT,
    Messenger,
    _ClaudeClassifier,
)

# --- キーワード分類テスト (フォールバック) ---


def test_classify_shipping():
    messenger = Messenger.__new__(Messenger)
    messenger._claude_classifier = None
    assert messenger.classify_by_keywords("When will my item ship?") == MessageCategory.SHIPPING_TRACKING
    assert messenger.classify_by_keywords("Do you have tracking number?") == MessageCategory.SHIPPING_TRACKING
    assert messenger.classify_by_keywords("How long is delivery?") == MessageCategory.SHIPPING_TRACKING


def test_classify_condition():
    messenger = Messenger.__new__(Messenger)
    messenger._claude_classifier = None
    assert messenger.classify_by_keywords("Is this item new?") == MessageCategory.CONDITION
    assert messenger.classify_by_keywords("What is the condition?") == MessageCategory.CONDITION
    assert messenger.classify_by_keywords("Is this authentic?") == MessageCategory.CONDITION


def test_classify_return():
    messenger = Messenger.__new__(Messenger)
    messenger._claude_classifier = None
    assert messenger.classify_by_keywords("I want to cancel my order") == MessageCategory.RETURN_CANCEL
    assert messenger.classify_by_keywords("Can I return this item?") == MessageCategory.RETURN_CANCEL
    assert messenger.classify_by_keywords("I need a refund") == MessageCategory.RETURN_CANCEL


def test_classify_address():
    messenger = Messenger.__new__(Messenger)
    messenger._claude_classifier = None
    assert messenger.classify_by_keywords("I need to change my address") == MessageCategory.ADDRESS_CHANGE
    assert messenger.classify_by_keywords("Wrong address on my order") == MessageCategory.ADDRESS_CHANGE


def test_classify_other():
    messenger = Messenger.__new__(Messenger)
    messenger._claude_classifier = None
    assert messenger.classify_by_keywords("Hello, nice product!") == MessageCategory.OTHER
    assert messenger.classify_by_keywords("Bundles available?") == MessageCategory.OTHER


def test_get_template_reply():
    messenger = Messenger.__new__(Messenger)
    reply = messenger.get_template_reply(MessageCategory.SHIPPING_TRACKING)
    assert reply is not None
    assert "shipped" in reply.lower() or "ship" in reply.lower()

    reply_other = messenger.get_template_reply(MessageCategory.OTHER)
    assert reply_other is None


# --- classify_message (非同期) テスト ---


async def test_classify_message_uses_keywords_when_no_claude():
    """Claude未設定時はキーワード分類を使用."""
    messenger = Messenger.__new__(Messenger)
    messenger._claude_classifier = None
    result = await messenger.classify_message("When will my item ship?")
    assert result == MessageCategory.SHIPPING_TRACKING


async def test_classify_message_fallback_on_error():
    """Claude API エラー時はキーワードにフォールバック."""
    messenger = Messenger.__new__(Messenger)
    mock_classifier = AsyncMock()
    mock_classifier.classify.side_effect = Exception("API error")
    messenger._claude_classifier = mock_classifier

    result = await messenger.classify_message("I need a refund")
    assert result == MessageCategory.RETURN_CANCEL


# --- _ClaudeClassifier テスト ---


async def test_claude_classifier_shipping():
    """Claude Haiku が shipping_tracking を返す場合."""
    classifier = _ClaudeClassifier.__new__(_ClaudeClassifier)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="shipping_tracking")]
    classifier._client = AsyncMock()
    classifier._client.messages.create = AsyncMock(return_value=mock_response)
    classifier._model = "claude-haiku-4-5-20251001"

    result = await classifier.classify("When will you ship my order?")
    assert result == MessageCategory.SHIPPING_TRACKING

    # API呼び出しの引数を検証
    classifier._client.messages.create.assert_called_once()
    call_kwargs = classifier._client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert call_kwargs["max_tokens"] == 32
    assert call_kwargs["system"] == CLASSIFICATION_SYSTEM_PROMPT
    assert call_kwargs["messages"] == [{"role": "user", "content": "When will you ship my order?"}]


async def test_claude_classifier_condition():
    classifier = _ClaudeClassifier.__new__(_ClaudeClassifier)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="condition")]
    classifier._client = AsyncMock()
    classifier._client.messages.create = AsyncMock(return_value=mock_response)
    classifier._model = "claude-haiku-4-5-20251001"

    result = await classifier.classify("Is this genuine?")
    assert result == MessageCategory.CONDITION


async def test_claude_classifier_return_cancel():
    classifier = _ClaudeClassifier.__new__(_ClaudeClassifier)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="return_cancel")]
    classifier._client = AsyncMock()
    classifier._client.messages.create = AsyncMock(return_value=mock_response)
    classifier._model = "claude-haiku-4-5-20251001"

    result = await classifier.classify("I want my money back, the item was broken")
    assert result == MessageCategory.RETURN_CANCEL


async def test_claude_classifier_address_change():
    classifier = _ClaudeClassifier.__new__(_ClaudeClassifier)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="address_change")]
    classifier._client = AsyncMock()
    classifier._client.messages.create = AsyncMock(return_value=mock_response)
    classifier._model = "claude-haiku-4-5-20251001"

    result = await classifier.classify("Can you send it to a different address?")
    assert result == MessageCategory.ADDRESS_CHANGE


async def test_claude_classifier_other():
    classifier = _ClaudeClassifier.__new__(_ClaudeClassifier)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="other")]
    classifier._client = AsyncMock()
    classifier._client.messages.create = AsyncMock(return_value=mock_response)
    classifier._model = "claude-haiku-4-5-20251001"

    result = await classifier.classify("Do you sell bundles?")
    assert result == MessageCategory.OTHER


async def test_claude_classifier_unknown_response():
    """Claude が未知のカテゴリを返した場合は OTHER."""
    classifier = _ClaudeClassifier.__new__(_ClaudeClassifier)
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="some_unknown_category")]
    classifier._client = AsyncMock()
    classifier._client.messages.create = AsyncMock(return_value=mock_response)
    classifier._model = "claude-haiku-4-5-20251001"

    result = await classifier.classify("Random text")
    assert result == MessageCategory.OTHER


# --- Messenger 初期化テスト ---


def test_messenger_has_no_claude_by_default():
    """API未設定ではClaude分類器なし."""
    messenger = Messenger.__new__(Messenger)
    messenger._settings = {}
    messenger._claude_classifier = None
    assert messenger.has_claude_classifier is False


def test_messenger_init_with_claude():
    """claude.api_key設定済みでClaude分類器が有効化."""
    messenger = Messenger.__new__(Messenger)
    messenger._settings = {"claude": {"api_key": "test-key"}}
    messenger._claude_classifier = None
    messenger._init_claude_classifier()
    assert messenger.has_claude_classifier is True


def test_messenger_init_with_custom_model():
    """カスタムモデル指定."""
    messenger = Messenger.__new__(Messenger)
    messenger._settings = {
        "claude": {
            "api_key": "test-key",
            "classifier_model": "claude-haiku-4-5-20251001",
        },
    }
    messenger._claude_classifier = None
    messenger._init_claude_classifier()
    assert messenger.has_claude_classifier is True
    assert messenger._claude_classifier._model == "claude-haiku-4-5-20251001"


# --- listing_id 連携テスト ---


async def test_handle_message_with_listing_id():
    """listing_idを指定してメッセージ処理できる."""
    from ec_hub.db import Database

    db = Database(":memory:")
    await db.connect()
    try:
        cid = await db.add_candidate(
            item_code="B09MSG",
            source_site="amazon",
            title_jp="メッセージ商品",
            title_en="Message Product",
            cost_jpy=3000,
            ebay_price_usd=80.0,
            net_profit_jpy=5000,
            margin_rate=1.67,
        )
        lid = await db.add_listing(
            candidate_id=cid,
            sku=f"ECHUB-{cid}",
            title_en="Message Product",
            listed_price_usd=80.0,
            listed_fx_rate=150.0,
        )
        oid = await db.add_order(
            ebay_order_id="MSG-ORD-001",
            candidate_id=cid,
            listing_id=lid,
            sale_price_usd=80.0,
        )

        messenger = Messenger(db, settings={"claude": {}, "line": {}})
        result = await messenger.handle_message(
            buyer_username="buyer_msg",
            body="When will my item ship?",
            order_id=oid,
            listing_id=lid,
        )
        assert result is True

        messages = await db.get_messages(buyer_username="buyer_msg")
        inbound = [m for m in messages if m["direction"] == "inbound"]
        assert len(inbound) == 1
        assert inbound[0]["listing_id"] == lid
    finally:
        await db.close()
