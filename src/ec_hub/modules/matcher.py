"""商品マッチングエンジン.

eBay商品と仕入れ商品の類似度スコアを計算し、
誤マッチを防止するためのロジックを提供する。

マッチスコアの構成:
- タイトル類似度 (0-50点)
- ブランド一致 (0-15点)
- 型番一致 (0-20点)
- 数量/セット数一致 (0-10点)
- 価格乖離ペナルティ (-20〜0点)
- カテゴリ一致ボーナス (0-5点)
"""

from __future__ import annotations

import re
import unicodedata

# Match score threshold for candidate adoption
DEFAULT_MATCH_THRESHOLD = 40


def normalize_match_threshold(threshold: float | int | None) -> int:
    """Normalize threshold to the scorer's 0-100 scale."""
    if threshold is None:
        return DEFAULT_MATCH_THRESHOLD

    value = float(threshold)
    if 0 < value <= 1:
        value *= 100

    return max(0, min(100, int(round(value))))


def normalize_title(title: str) -> str:
    """商品名を正規化する.

    - 全角→半角変換
    - 小文字化
    - 余分な空白を除去
    - 特殊文字を除去
    """
    # NFKC normalization: full-width → half-width
    text = unicodedata.normalize("NFKC", title)
    text = text.lower()
    # Remove special chars but keep alphanumeric, Japanese, hyphens, spaces
    text = re.sub(r"[^\w\s\-]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_brand(title: str) -> str | None:
    """タイトルからブランド名を抽出する.

    Known brands list + first capitalized word heuristic.
    """
    # Japanese brand name → normalized name mapping
    jp_brand_map = {
        "バンダイ": "bandai",
        "タカラ": "takara",
        "トミー": "tomy",
        "コトブキヤ": "kotobukiya",
        "グッドスマイル": "good smile",
        "メガハウス": "megahouse",
        "メディコム": "medicom",
        "海洋堂": "kaiyodo",
        "ソニー": "sony",
        "任天堂": "nintendo",
        "セガ": "sega",
        "カプコン": "capcom",
        "コナミ": "konami",
        "ナムコ": "namco",
        "サンリオ": "sanrio",
        "ポケモン": "pokemon",
        "パナソニック": "panasonic",
        "シャープ": "sharp",
        "カシオ": "casio",
        "セイコー": "seiko",
        "シチズン": "citizen",
        "ヤマハ": "yamaha",
        "マキタ": "makita",
        "日立": "hitachi",
        "ダイワ": "daiwa",
        "シマノ": "shimano",
        "ユニクロ": "uniqlo",
        "資生堂": "shiseido",
        "無印良品": "muji",
    }

    # Check Japanese brand names first (before normalization removes them)
    for jp_name, en_name in jp_brand_map.items():
        if jp_name in title:
            return en_name

    known_brands = {
        "bandai",
        "takara",
        "tomy",
        "takaratomy",
        "kotobukiya",
        "good smile",
        "goodsmile",
        "megahouse",
        "medicom",
        "kaiyodo",
        "figma",
        "nendoroid",
        "sony",
        "nintendo",
        "sega",
        "capcom",
        "konami",
        "namco",
        "square enix",
        "sanrio",
        "pokemon",
        "pikachu",
        "gundam",
        "dragon ball",
        "one piece",
        "naruto",
        "studio ghibli",
        "muji",
        "uniqlo",
        "shiseido",
        "kanebo",
        "panasonic",
        "sharp",
        "casio",
        "seiko",
        "citizen",
        "yamaha",
        "makita",
        "hitachi",
        "daiwa",
        "shimano",
        "pearl",
        "zebra",
    }

    normalized = normalize_title(title)

    # Find the earliest-appearing brand in the title
    # (brand names typically appear at the start of product titles)
    best_brand = None
    best_pos = len(normalized) + 1

    for brand in known_brands:
        pos = normalized.find(brand)
        if pos >= 0 and pos < best_pos:
            best_pos = pos
            best_brand = brand
        elif pos >= 0 and pos == best_pos and len(brand) > len(best_brand or ""):
            # Same position, prefer longer match
            best_brand = brand

    if best_brand:
        return best_brand

    return None


def extract_model_number(title: str) -> str | None:
    """タイトルから型番を抽出する.

    Common patterns:
    - B09XXXXX (Amazon ASIN)
    - ABC-1234
    - XX1234
    - #1234
    """
    normalized = normalize_title(title)

    patterns = [
        r"\b[a-z]{1,5}-\d{2,}[a-z]*\d*\b",  # WH-1000XM5, ABC-1234
        r"\b[a-z]{1,4}\d{2,}[a-z]?\b",  # ABC123, B09xxx
        r"\b\d{3,}-\d{2,}\b",  # 123-456
        r"#\s*(\d{3,})",  # #1234
        r"\bno\.?\s*(\d{3,})\b",  # No.1234
        r"\b\d{4,}\b",  # standalone 4+ digit numbers (model numbers)
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group().strip()

    return None


def extract_quantity(title: str) -> int:
    """タイトルから数量/セット数を抽出する.

    Patterns: "3pcs", "set of 5", "x2", "2個", "3個セット", "5本"
    Returns 1 if no quantity found.
    """
    normalized = normalize_title(title)

    patterns = [
        r"(\d+)\s*(?:pcs|pieces|pc|個|本|枚|セット|pack|set)",
        r"(?:set\s+of|x)\s*(\d+)",
        r"(\d+)\s*(?:個セット|本セット|枚セット)",
        r"(\d+)\s*(?:p(?:ack|cs))",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            qty = int(match.group(1))
            if 1 < qty <= 100:  # Sanity check
                return qty

    return 1


def extract_size_color(title: str) -> dict[str, str | None]:
    """タイトルからサイズと色を抽出する."""
    normalized = normalize_title(title)

    # Size patterns
    size = None
    size_patterns = [
        r"\b(xxs|xs|s|m|l|xl|xxl|xxxl)\b",
        r"\b(\d+)\s*(?:cm|mm|inch|インチ)\b",
        r"\b(\d+)\s*x\s*(\d+)\b",  # dimensions like 30x40
    ]
    for pattern in size_patterns:
        match = re.search(pattern, normalized)
        if match:
            size = match.group()
            break

    # Color patterns
    color = None
    colors = {
        "black",
        "white",
        "red",
        "blue",
        "green",
        "yellow",
        "pink",
        "purple",
        "orange",
        "brown",
        "gray",
        "grey",
        "silver",
        "gold",
        "navy",
        "黒",
        "白",
        "赤",
        "青",
        "緑",
        "黄",
        "ピンク",
    }
    words = set(normalized.split())
    for c in colors:
        if c in words or c in normalized:
            color = c
            break

    return {"size": size, "color": color}


def calc_title_similarity(title1: str, title2: str) -> float:
    """2つのタイトル間の類似度を計算する (0.0〜1.0).

    Jaccard similarity of word sets.
    """
    words1 = set(normalize_title(title1).split())
    words2 = set(normalize_title(title2).split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


def calc_match_score(
    ebay_title: str,
    source_title: str,
    *,
    ebay_price_usd: float | None = None,
    source_price_jpy: int | None = None,
    fx_rate: float = 150.0,
    ebay_category: str | None = None,
    source_category: str | None = None,
) -> dict:
    """eBay商品と仕入れ商品のマッチスコアを計算する.

    Returns:
        {
            "score": int (0-100),
            "reasons": list[str],
            "details": {
                "title_similarity": float,
                "brand_match": bool,
                "model_match": bool,
                "quantity_match": bool,
                ...
            }
        }
    """
    score = 0
    reasons: list[str] = []
    details: dict = {}

    # 1. Title similarity (0-50 points)
    similarity = calc_title_similarity(ebay_title, source_title)
    title_score = int(similarity * 50)
    score += title_score
    details["title_similarity"] = round(similarity, 3)
    if similarity >= 0.5:
        reasons.append(f"タイトル類似度 {similarity:.0%}")

    # 2. Brand match (0-15 points)
    ebay_brand = extract_brand(ebay_title)
    source_brand = extract_brand(source_title)
    details["ebay_brand"] = ebay_brand
    details["source_brand"] = source_brand
    brand_match = False
    if ebay_brand and source_brand:
        if ebay_brand == source_brand:
            score += 15
            brand_match = True
            reasons.append(f"ブランド一致: {ebay_brand}")
        else:
            score -= 10
            reasons.append(f"ブランド不一致: {ebay_brand} vs {source_brand}")
    details["brand_match"] = brand_match

    # 3. Model number match (0-20 points)
    ebay_model = extract_model_number(ebay_title)
    source_model = extract_model_number(source_title)
    details["ebay_model"] = ebay_model
    details["source_model"] = source_model
    model_match = False
    if ebay_model and source_model:
        if ebay_model == source_model:
            score += 20
            model_match = True
            reasons.append(f"型番一致: {ebay_model}")
        else:
            score -= 5
            reasons.append(f"型番不一致: {ebay_model} vs {source_model}")
    details["model_match"] = model_match

    # 4. Quantity match (0-10 points)
    ebay_qty = extract_quantity(ebay_title)
    source_qty = extract_quantity(source_title)
    details["ebay_quantity"] = ebay_qty
    details["source_quantity"] = source_qty
    qty_match = ebay_qty == source_qty
    details["quantity_match"] = qty_match
    if qty_match:
        score += 10
        if ebay_qty > 1:
            reasons.append(f"数量一致: {ebay_qty}個")
    else:
        score -= 10
        reasons.append(f"数量不一致: {ebay_qty} vs {source_qty}")

    # 5. Price deviation penalty (-20 to 0 points)
    if ebay_price_usd and source_price_jpy and fx_rate > 0:
        ebay_price_jpy = ebay_price_usd * fx_rate
        if ebay_price_jpy > 0:
            price_ratio = source_price_jpy / ebay_price_jpy
            details["price_ratio"] = round(price_ratio, 3)
            # Source price should be significantly lower than eBay price
            # Ideal: source is 20-60% of eBay price
            if price_ratio > 1.5:
                # Source more expensive than eBay - bad match
                penalty = -20
                score += penalty
                reasons.append(f"仕入れ価格がeBay価格より高い (比率{price_ratio:.1f})")
            elif price_ratio > 1.0:
                penalty = -10
                score += penalty
                reasons.append(f"仕入れ価格が高すぎる (比率{price_ratio:.1f})")

    # 6. Category match bonus (0-5 points)
    if ebay_category and source_category:
        ebay_cat_norm = normalize_title(ebay_category)
        source_cat_norm = normalize_title(source_category)
        if ebay_cat_norm == source_cat_norm or ebay_cat_norm in source_cat_norm or source_cat_norm in ebay_cat_norm:
            score += 5
            reasons.append("カテゴリ一致")
            details["category_match"] = True
        else:
            details["category_match"] = False
    else:
        details["category_match"] = None

    # Clamp score to 0-100
    score = max(0, min(100, score))

    return {
        "score": score,
        "reasons": reasons,
        "details": details,
    }


def is_good_match(match_result: dict, threshold: int = DEFAULT_MATCH_THRESHOLD) -> bool:
    """マッチスコアが閾値を超えているか判定する."""
    return match_result["score"] >= normalize_match_threshold(threshold)
