"""仕入れ価格検索の共通インターフェース."""

from __future__ import annotations

import abc

from pydantic import BaseModel, Field


class SourceProduct(BaseModel):
    """仕入れサイトの商品情報."""

    item_code: str
    source_site: str
    title: str
    price_jpy: int
    url: str
    image_url: str | None = None
    availability: bool = True
    weight_g: int | None = None
    category: str | None = None
    review_count: int | None = None
    rating: float | None = None


class SourceSearchResult(BaseModel):
    """仕入れサイトの検索結果."""

    query: str
    source_site: str
    products: list[SourceProduct] = Field(default_factory=list)


class SourceSearcher(abc.ABC):
    """仕入れ価格検索の抽象基底クラス."""

    @property
    @abc.abstractmethod
    def site_name(self) -> str: ...

    @abc.abstractmethod
    async def search(self, query: str, *, max_results: int = 10) -> SourceSearchResult:
        """キーワードで商品を検索する."""
        ...

    @abc.abstractmethod
    async def get_item(self, item_code: str) -> SourceProduct | None:
        """商品コードから商品情報を取得する."""
        ...

    async def close(self) -> None:
        """リソースの解放."""

    async def __aenter__(self) -> SourceSearcher:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
