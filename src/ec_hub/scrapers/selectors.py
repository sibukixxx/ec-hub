"""CSS セレクタ外部設定の読み込み."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class SearchSelectors(BaseModel):
    """検索結果ページ用セレクタ."""

    item: str = "li.s-item"
    title: str = "div.s-item__title span[role='heading']"
    title_fallback: str = "div.s-item__title"
    link: str = "a.s-item__link"
    price: str = "span.s-item__price"
    image: str = "img.s-item__image-img"
    shipping: str = "span.s-item__shipping"
    condition: str = "span.SECONDARY_INFO"
    result_count: str = "h1.srp-controls__count-heading span.BOLD"


class ItemPageSelectors(BaseModel):
    """商品詳細ページ用セレクタ."""

    title: str = "h1.x-item-title__mainTitle span"
    price_primary: str = "div.x-price-primary span.ux-textspanx--BOLD"
    price_fallback: str = "span[itemprop='price']"
    image_primary: str = "img.ux-image-magnify__container--original"
    image_fallback: str = "div.ux-image-carousel-item img"
    seller_primary: str = "span.ux-textspanx--BOLD[data-testid='ux-seller-section__item--seller']"
    seller_fallback: str = "div.x-sellercard-atf__info__about-seller a span"
    condition_primary: str = "span.ux-icon-text__text[data-testid='ux-icon-text']"
    condition_fallback: str = "div.x-item-condition span.ux-textspanx"


class SelectorConfig(BaseModel):
    """セレクタ設定全体."""

    search: SearchSelectors = SearchSelectors()
    item_page: ItemPageSelectors = ItemPageSelectors()


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "selectors.yaml"


def load_selectors(path: str | None = None) -> SelectorConfig:
    """セレクタ設定をYAMLファイルから読み込む.

    Args:
        path: YAMLファイルパス。None の場合はデフォルトを使用。

    Returns:
        SelectorConfig
    """
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return SelectorConfig(**data)

    return SelectorConfig()
