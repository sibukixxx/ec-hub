"""メッセージ分類のテスト."""

from ec_hub.models import MessageCategory
from ec_hub.modules.messenger import Messenger


def test_classify_shipping():
    messenger = Messenger.__new__(Messenger)
    assert messenger.classify_message("When will my item ship?") == MessageCategory.SHIPPING_TRACKING
    assert messenger.classify_message("Do you have tracking number?") == MessageCategory.SHIPPING_TRACKING
    assert messenger.classify_message("How long is delivery?") == MessageCategory.SHIPPING_TRACKING


def test_classify_condition():
    messenger = Messenger.__new__(Messenger)
    assert messenger.classify_message("Is this item new?") == MessageCategory.CONDITION
    assert messenger.classify_message("What is the condition?") == MessageCategory.CONDITION
    assert messenger.classify_message("Is this authentic?") == MessageCategory.CONDITION


def test_classify_return():
    messenger = Messenger.__new__(Messenger)
    assert messenger.classify_message("I want to cancel my order") == MessageCategory.RETURN_CANCEL
    assert messenger.classify_message("Can I return this item?") == MessageCategory.RETURN_CANCEL
    assert messenger.classify_message("I need a refund") == MessageCategory.RETURN_CANCEL


def test_classify_address():
    messenger = Messenger.__new__(Messenger)
    assert messenger.classify_message("I need to change my address") == MessageCategory.ADDRESS_CHANGE
    assert messenger.classify_message("Wrong address on my order") == MessageCategory.ADDRESS_CHANGE


def test_classify_other():
    messenger = Messenger.__new__(Messenger)
    assert messenger.classify_message("Hello, nice product!") == MessageCategory.OTHER
    assert messenger.classify_message("Bundles available?") == MessageCategory.OTHER


def test_get_template_reply():
    messenger = Messenger.__new__(Messenger)
    reply = messenger.get_template_reply(MessageCategory.SHIPPING_TRACKING)
    assert reply is not None
    assert "shipped" in reply.lower() or "ship" in reply.lower()

    reply_other = messenger.get_template_reply(MessageCategory.OTHER)
    assert reply_other is None
