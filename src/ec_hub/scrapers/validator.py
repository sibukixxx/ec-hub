"""スクレイパー結果の妥当性検証."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from ec_hub.models import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """検証結果."""

    is_valid: bool
    warnings: list[str] = field(default_factory=list)


class ScrapeValidator:
    """スクレイパー結果の妥当性を検証."""

    def validate_search_result(self, result: SearchResult) -> ValidationResult:
        """検索結果の妥当性を検証する.

        Args:
            result: 検索結果

        Returns:
            ValidationResult: 検証結果
        """
        warnings: list[str] = []

        # 商品0件チェック
        if len(result.products) == 0:
            warnings.append("Found 0 products in search result")

        # total_results と products の整合性チェック
        if result.total_results == 0 and len(result.products) > 0:
            warnings.append("Mismatch: total_results is 0 but products found")

        # 全商品に価格がない場合
        if len(result.products) > 0:
            products_without_price = [p for p in result.products if p.price is None]
            if len(products_without_price) == len(result.products):
                warnings.append("All products are missing price information")

        is_valid = len(warnings) == 0
        return ValidationResult(is_valid=is_valid, warnings=warnings)

    def validate_html(self, html: str) -> ValidationResult:
        """HTML の妥当性を検証する.

        Args:
            html: HTML文字列

        Returns:
            ValidationResult: 検証結果
        """
        warnings: list[str] = []

        soup = BeautifulSoup(html, "lxml")

        # パース失敗の検知
        # - s-item（eBay検索結果）がない場合
        items = soup.select("li.s-item")
        if len(items) == 0:
            warnings.append("No items found in HTML (possible parse failure or page structure change)")

        is_valid = len(warnings) == 0
        return ValidationResult(is_valid=is_valid, warnings=warnings)
