"""eBay CSSセレクタの外部設定."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EbaySelectors(BaseModel):
    """eBay HTML パース用 CSS セレクタ定義."""

    # Search results page
    search_result_count: str = "h1.srp-controls__count-heading span.BOLD"
    search_item: str = "li.s-item"
    search_title: str = "div.s-item__title span[role='heading']"
    search_title_fallback: str = "div.s-item__title"
    search_link: str = "a.s-item__link"
    search_price: str = "span.s-item__price"
    search_image: str = "img.s-item__image-img"
    search_shipping: str = "span.s-item__shipping"
    search_condition: str = "span.SECONDARY_INFO"

    # Item detail page
    item_title: str = "h1.x-item-title__mainTitle span"
    item_price: str = "div.x-price-primary span.ux-textspanx--BOLD"
    item_price_fallback: str = "span[itemprop='price']"
    item_image: str = "img.ux-image-magnify__container--original"
    item_image_fallback: str = "div.ux-image-carousel-item img"
    item_seller: str = "span.ux-textspanx--BOLD[data-testid='ux-seller-section__item--seller']"
    item_seller_fallback: str = "div.x-sellercard-atf__info__about-seller a span"
    item_condition: str = "span.ux-icon-text__text[data-testid='ux-icon-text']"
    item_condition_fallback: str = "div.x-item-condition span.ux-textspanx"


def load_selectors(path: Path) -> EbaySelectors:
    """YAML ファイルからセレクタ設定を読み込む.

    ファイルが存在しない場合やパースエラー時はデフォルト値を返す。
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data:
            return EbaySelectors()
        return EbaySelectors(**data)
    except FileNotFoundError:
        logger.info("Selector config not found at %s, using defaults", path)
        return EbaySelectors()
    except Exception:
        logger.warning("Failed to load selector config from %s, using defaults", path, exc_info=True)
        return EbaySelectors()
