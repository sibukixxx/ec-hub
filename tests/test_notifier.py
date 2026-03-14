"""LINE通知モジュールのテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ec_hub.modules.notifier import Notifier, Severity


@pytest.fixture
def settings():
    return {"line": {"channel_access_token": "test-token", "user_id": "test-user-id"}}


@pytest.fixture
def empty_settings():
    return {"line": {}}


@pytest.fixture
def notifier(settings):
    return Notifier(settings=settings, min_severity=Severity.INFO)


@pytest.fixture
def warning_only_notifier(settings):
    return Notifier(settings=settings, min_severity=Severity.WARNING)


@pytest.fixture
def unconfigured_notifier(empty_settings):
    return Notifier(settings=empty_settings)


def _mock_httpx_client(mock_response=None):
    """httpx.AsyncClient のコンテキストマネージャモックを生成する."""
    if mock_response is None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# --- is_configured プロパティテスト ---


def test_notifier_not_configured(unconfigured_notifier):
    """token/user_id 未設定では is_configured が False."""
    assert unconfigured_notifier.is_configured is False


def test_notifier_configured(notifier):
    """token/user_id 設定済みでは is_configured が True."""
    assert notifier.is_configured is True


# --- send メソッドテスト ---


async def test_send_unconfigured_returns_false(unconfigured_notifier):
    """未設定時の send() は False を返す."""
    result = await unconfigured_notifier.send("test message")
    assert result is False


async def test_send_success(notifier):
    """LINE API が 200 を返す場合、send() は True を返す."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.send("test message")

    assert result is True
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[1]["json"]["to"] == "test-user-id"
    assert call_kwargs[1]["json"]["messages"][0]["text"] == "test message"
    assert "Bearer test-token" in call_kwargs[1]["headers"]["Authorization"]


async def test_send_failure(notifier):
    """LINE API が HTTPError を投げる場合、send() は False を返す."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPError("API error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.send("test message")

    assert result is False


# --- severity フィルタテスト ---


async def test_severity_filter_blocks_low_severity(warning_only_notifier):
    """min_severity=WARNING の場合、INFO は送信されない."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await warning_only_notifier.send("info msg", severity=Severity.INFO)

    assert result is False
    mock_client.post.assert_not_called()


async def test_severity_filter_allows_equal_severity(warning_only_notifier):
    """min_severity=WARNING の場合、WARNING は送信される."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await warning_only_notifier.send("warn msg", severity=Severity.WARNING)

    assert result is True


async def test_severity_filter_allows_higher_severity(warning_only_notifier):
    """min_severity=WARNING の場合、CRITICAL は送信される."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await warning_only_notifier.send("critical msg", severity=Severity.CRITICAL)

    assert result is True


# --- dedupe テスト ---


async def test_dedupe_blocks_duplicate_within_window(settings):
    """同じメッセージを短時間に2回送ると、2回目はブロックされる."""
    notifier = Notifier(settings=settings, dedupe_window=3600, min_severity=Severity.INFO)
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result1 = await notifier.send("duplicate msg")
        result2 = await notifier.send("duplicate msg")

    assert result1 is True
    assert result2 is False
    assert mock_client.post.call_count == 1


async def test_dedupe_allows_different_messages(settings):
    """異なるメッセージは重複抑止されない."""
    notifier = Notifier(settings=settings, dedupe_window=3600, min_severity=Severity.INFO)
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result1 = await notifier.send("message A")
        result2 = await notifier.send("message B")

    assert result1 is True
    assert result2 is True
    assert mock_client.post.call_count == 2


# --- 各通知メソッドテスト ---


async def test_notify_candidates(notifier):
    """notify_candidates のメッセージに件数が含まれる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_candidates(5)

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "5" in sent_text
    assert "候補" in sent_text


async def test_notify_order(notifier):
    """notify_order のメッセージに注文IDと価格が含まれる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_order("ORD-12345", 99.50)

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "ORD-12345" in sent_text
    assert "$99.50" in sent_text


async def test_notify_selling_limit(notifier):
    """notify_selling_limit のメッセージに残数が含まれる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_selling_limit(10, 100)

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "10" in sent_text
    assert "100" in sent_text


async def test_notify_message_escalation(notifier):
    """200文字を超えるメッセージは切り詰められる."""
    long_body = "A" * 300
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_message_escalation("buyer123", long_body)

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "buyer123" in sent_text
    assert "..." in sent_text
    # 元の300文字がそのまま含まれていないことを確認
    assert long_body not in sent_text


async def test_notify_message_escalation_short(notifier):
    """200文字以下のメッセージは切り詰められない."""
    short_body = "Short message"
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_message_escalation("buyer456", short_body)

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "buyer456" in sent_text
    assert short_body in sent_text
    assert "..." not in sent_text


async def test_notify_daily_report(notifier):
    """notify_daily_report のメッセージにレポートの全フィールドが含まれる."""
    report = {
        "report_date": "2026-03-14",
        "orders_count": 8,
        "total_revenue_jpy": 150000,
        "total_profit_jpy": 45000,
        "new_candidates_count": 12,
    }
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_daily_report(report)

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "2026-03-14" in sent_text
    assert "8" in sent_text
    assert "150,000" in sent_text
    assert "45,000" in sent_text
    assert "12" in sent_text


async def test_notify_exchange_rate_warning(notifier):
    """notify_exchange_rate_warning のメッセージに警告内容が含まれる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_exchange_rate_warning("Using static fallback 150.00")

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "為替レート警告" in sent_text
    assert "Using static fallback 150.00" in sent_text


async def test_notify_job_failure(notifier):
    """notify_job_failure のメッセージにジョブ名とエラーが含まれる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_job_failure("researcher", "Connection timeout")

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "researcher" in sent_text
    assert "Connection timeout" in sent_text


async def test_notify_service_degraded(notifier):
    """notify_service_degraded のメッセージにサービス名とエラーが含まれる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await notifier.notify_service_degraded("ebay", "API key expired")

    assert result is True
    sent_text = mock_client.post.call_args[1]["json"]["messages"][0]["text"]
    assert "ebay" in sent_text
    assert "API key expired" in sent_text


# --- notify_order は CRITICAL なので severity=WARNING でもブロックされない ---


async def test_notify_order_with_warning_min_severity(warning_only_notifier):
    """notify_order は CRITICAL なので WARNING フィルタでも送信される."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await warning_only_notifier.notify_order("ORD-999", 50.0)

    assert result is True


async def test_notify_candidates_blocked_by_warning_filter(warning_only_notifier):
    """notify_candidates は INFO なので WARNING フィルタでブロックされる."""
    mock_client = _mock_httpx_client()

    with patch("ec_hub.modules.notifier.httpx.AsyncClient", return_value=mock_client):
        result = await warning_only_notifier.notify_candidates(3)

    assert result is False
