"""eBay商品データのモデル定義."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ListingCondition(str, Enum):
    NEW = "New"
    OPEN_BOX = "Open box"
    REFURBISHED = "Certified Refurbished"
    USED = "Used"
    FOR_PARTS = "For parts or not working"
    NOT_SPECIFIED = "Not Specified"


class ShippingInfo(BaseModel):
    cost: float | None = None
    free_shipping: bool = False
    estimated_delivery: str | None = None


class SellerInfo(BaseModel):
    name: str
    feedback_score: int | None = None
    feedback_percent: float | None = None


class Product(BaseModel):
    """eBay商品の詳細情報."""

    item_id: str
    title: str
    price: float | None = None
    currency: str = "USD"
    condition: ListingCondition = ListingCondition.NOT_SPECIFIED
    url: str
    image_url: str | None = None
    seller: SellerInfo | None = None
    shipping: ShippingInfo | None = None
    location: str | None = None
    category: str | None = None
    bids: int | None = None
    buy_it_now: bool = False
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class SearchResult(BaseModel):
    """検索結果のコンテナ."""

    query: str
    total_results: int = 0
    page: int = 1
    products: list[Product] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
