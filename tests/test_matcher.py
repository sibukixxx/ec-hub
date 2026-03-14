"""マッチングエンジンのテスト."""

from ec_hub.modules.matcher import (
    calc_match_score,
    calc_title_similarity,
    extract_brand,
    extract_model_number,
    extract_quantity,
    extract_size_color,
    is_good_match,
    normalize_match_threshold,
    normalize_title,
)

# --- normalize_title ---


def test_normalize_title_fullwidth_to_halfwidth():
    """全角英数字が半角に変換される."""
    assert normalize_title("Ｈｅｌｌｏ　Ｗｏｒｌｄ") == "hello world"


def test_normalize_title_lowercase():
    assert normalize_title("HELLO WORLD") == "hello world"


def test_normalize_title_removes_special_chars():
    assert normalize_title("Hello! (World) [Test]") == "hello world test"


def test_normalize_title_collapses_whitespace():
    assert normalize_title("hello   world   test") == "hello world test"


def test_normalize_title_preserves_japanese():
    result = normalize_title("バンダイ ガンプラ RG 1/144")
    assert "バンダイ" in result
    assert "ガンプラ" in result


def test_normalize_title_preserves_hyphens():
    result = normalize_title("ABC-1234 Test")
    assert "abc-1234" in result


# --- extract_brand ---


def test_extract_brand_known_single_word():
    assert extract_brand("Bandai Gundam Model Kit") == "bandai"


def test_extract_brand_known_multi_word():
    assert extract_brand("Good Smile Nendoroid Figure") == "good smile"


def test_extract_brand_case_insensitive():
    assert extract_brand("SONY Walkman Vintage") == "sony"


def test_extract_brand_japanese():
    assert extract_brand("バンダイ ガンプラ RG") == "bandai"


def test_extract_brand_none_when_unknown():
    assert extract_brand("Random Product No Brand") is None


def test_extract_brand_pokemon():
    assert extract_brand("Pokemon Card Pikachu Rare") == "pokemon"


def test_extract_brand_shimano():
    assert extract_brand("Shimano Ultegra Reel Fishing") == "shimano"


# --- extract_model_number ---


def test_extract_model_number_alphanumeric():
    assert extract_model_number("Bandai RG RX78-2 Gundam") is not None


def test_extract_model_number_with_hyphen():
    result = extract_model_number("Sony WH-1000XM5 Headphones")
    assert result is not None
    assert "1000" in result


def test_extract_model_number_hash():
    result = extract_model_number("Nendoroid #1000 Hatsune Miku")
    assert result is not None


def test_extract_model_number_none():
    assert extract_model_number("Simple Product Name") is None


def test_extract_model_number_digits_only():
    result = extract_model_number("Model 12345 Collector Edition")
    assert result is not None


# --- extract_quantity ---


def test_extract_quantity_pcs():
    assert extract_quantity("5pcs Set Japanese Plates") == 5


def test_extract_quantity_set_of():
    assert extract_quantity("Set of 3 Bowls") == 3


def test_extract_quantity_japanese():
    assert extract_quantity("3個セット 食器") == 3


def test_extract_quantity_x_notation():
    assert extract_quantity("Sticker x2 Pack") == 2


def test_extract_quantity_default_one():
    assert extract_quantity("Single Item Product") == 1


def test_extract_quantity_pack():
    assert extract_quantity("10pack Trading Cards") == 10


def test_extract_quantity_ignores_unreasonable():
    """100超の数量は無視する."""
    assert extract_quantity("200pcs Bulk Order") == 1


# --- extract_size_color ---


def test_extract_size_color_with_size():
    result = extract_size_color("T-Shirt Size L Black")
    assert result["size"] is not None
    assert "l" in result["size"]


def test_extract_size_color_with_color():
    result = extract_size_color("Backpack Red Large")
    assert result["color"] == "red"


def test_extract_size_color_with_cm():
    result = extract_size_color("Figure 30cm Tall")
    assert result["size"] is not None
    assert "30" in result["size"]


def test_extract_size_color_none():
    result = extract_size_color("Generic Product")
    assert result["size"] is None
    assert result["color"] is None


def test_extract_size_color_japanese_color():
    result = extract_size_color("バッグ 黒 大きめ")
    assert result["color"] == "黒"


# --- calc_title_similarity ---


def test_title_similarity_identical():
    sim = calc_title_similarity("Pokemon Card Pikachu", "Pokemon Card Pikachu")
    assert sim == 1.0


def test_title_similarity_partial():
    sim = calc_title_similarity("Pokemon Card Pikachu Rare", "Pokemon Card Pikachu")
    assert 0.5 < sim < 1.0


def test_title_similarity_no_overlap():
    sim = calc_title_similarity("Pokemon Card", "Kitchen Knife Set")
    assert sim == 0.0


def test_title_similarity_case_insensitive():
    sim = calc_title_similarity("POKEMON CARD", "pokemon card")
    assert sim == 1.0


def test_title_similarity_empty():
    assert calc_title_similarity("", "test") == 0.0
    assert calc_title_similarity("test", "") == 0.0


# --- calc_match_score ---


def test_match_score_identical_titles():
    """同一タイトルは高スコア."""
    result = calc_match_score(
        "Bandai Gundam RG RX-78-2",
        "Bandai Gundam RG RX-78-2",
    )
    assert result["score"] >= 60


def test_match_score_different_products():
    """完全に異なる商品は低スコア."""
    result = calc_match_score(
        "Pokemon Card Pikachu",
        "Kitchen Knife Set 3pcs",
    )
    assert result["score"] < 30


def test_match_score_brand_match():
    """ブランド一致でボーナス."""
    result = calc_match_score(
        "Bandai Model Kit Figure",
        "Bandai プラモデル フィギュア",
    )
    assert result["details"]["brand_match"] is True
    assert any("ブランド一致" in r for r in result["reasons"])


def test_match_score_brand_mismatch():
    """ブランド不一致でペナルティ."""
    result = calc_match_score(
        "Sony Headphones Wireless",
        "Panasonic ヘッドフォン ワイヤレス",
    )
    assert result["details"]["brand_match"] is False
    assert any("ブランド不一致" in r for r in result["reasons"])


def test_match_score_quantity_mismatch():
    """数量不一致でペナルティ."""
    result = calc_match_score(
        "5pcs Japanese Bowl Set",
        "Japanese Bowl 1個",
    )
    assert result["details"]["quantity_match"] is False
    assert result["details"]["ebay_quantity"] == 5
    assert result["details"]["source_quantity"] == 1


def test_match_score_quantity_match():
    """数量一致でボーナス."""
    result = calc_match_score(
        "3pcs Plate Set",
        "3個セット プレート",
    )
    assert result["details"]["quantity_match"] is True


def test_match_score_price_penalty_expensive_source():
    """仕入れ価格がeBay価格より高いとペナルティ."""
    result = calc_match_score(
        "Test Product",
        "テスト商品",
        ebay_price_usd=30.0,
        source_price_jpy=10000,
        fx_rate=150.0,
    )
    # source ¥10,000 vs ebay ¥4,500 → ratio = 2.2 → penalty
    assert any("仕入れ価格" in r for r in result["reasons"])


def test_match_score_category_match():
    """カテゴリ一致でボーナス."""
    result = calc_match_score(
        "Test Figure",
        "テスト フィギュア",
        ebay_category="Toys & Hobbies",
        source_category="Toys",
    )
    assert result["details"]["category_match"] is True


def test_match_score_returns_reasons():
    """match reasonsが含まれる."""
    result = calc_match_score("Bandai Gundam RG", "Bandai Gundam RG")
    assert isinstance(result["reasons"], list)
    assert len(result["reasons"]) > 0


def test_match_score_clamped_to_0_100():
    """スコアは0-100に制限される."""
    result = calc_match_score(
        "Sony Product Type A 5pcs",
        "Panasonic Different Product Type B 10pcs",
        ebay_price_usd=10.0,
        source_price_jpy=100000,
        fx_rate=150.0,
    )
    assert 0 <= result["score"] <= 100


# --- is_good_match ---


def test_is_good_match_above_threshold():
    result = {"score": 50, "reasons": [], "details": {}}
    assert is_good_match(result, threshold=40) is True


def test_is_good_match_below_threshold():
    result = {"score": 30, "reasons": [], "details": {}}
    assert is_good_match(result, threshold=40) is False


def test_is_good_match_at_threshold():
    result = {"score": 40, "reasons": [], "details": {}}
    assert is_good_match(result, threshold=40) is True


def test_is_good_match_default_threshold():
    high = {"score": 50, "reasons": [], "details": {}}
    low = {"score": 20, "reasons": [], "details": {}}
    assert is_good_match(high) is True
    assert is_good_match(low) is False


def test_normalize_match_threshold_ratio_to_score():
    assert normalize_match_threshold(0.6) == 60


def test_is_good_match_accepts_ratio_threshold():
    result = {"score": 55, "reasons": [], "details": {}}
    assert is_good_match(result, threshold=0.5) is True
    assert is_good_match(result, threshold=0.6) is False
