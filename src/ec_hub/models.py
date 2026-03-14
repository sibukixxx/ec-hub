"""eBay輸出転売システムのデータモデル定義."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# --- eBay商品関連 ---

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
    sold_count_30d: int = 0
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class SearchResult(BaseModel):
    """検索結果のコンテナ."""

    query: str
    total_results: int = 0
    page: int = 1
    products: list[Product] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


# --- 候補商品 ---

class CandidateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    LISTED = "listed"


class Candidate(BaseModel):
    """リサーチ候補商品."""

    id: int | None = None
    item_code: str
    source_site: str = "amazon"
    title_jp: str
    title_en: str | None = None
    cost_jpy: int
    ebay_price_usd: float
    net_profit_jpy: int | None = None
    margin_rate: float | None = None
    weight_g: int | None = None
    category: str | None = None
    ebay_sold_count_30d: int = 0
    image_url: str | None = None
    source_url: str | None = None
    match_score: int | None = None
    match_reason: str | None = None
    status: CandidateStatus = CandidateStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- 注文管理 ---

class OrderStatus(str, Enum):
    AWAITING_PURCHASE = "awaiting_purchase"
    PURCHASED = "purchased"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class Order(BaseModel):
    """eBay注文情報."""

    id: int | None = None
    ebay_order_id: str
    candidate_id: int | None = None
    buyer_username: str | None = None
    sale_price_usd: float
    actual_cost_jpy: int | None = None
    actual_shipping_jpy: int | None = None
    packing_cost_jpy: int = 200
    ebay_fee_jpy: int | None = None
    payoneer_fee_jpy: int | None = None
    net_profit_jpy: int | None = None
    fx_rate: float | None = None
    destination_country: str | None = None
    tracking_number: str | None = None
    status: OrderStatus = OrderStatus.AWAITING_PURCHASE
    ordered_at: datetime = Field(default_factory=datetime.utcnow)


# --- メッセージ分類 ---

class MessageCategory(str, Enum):
    SHIPPING_TRACKING = "shipping_tracking"
    CONDITION = "condition"
    RETURN_CANCEL = "return_cancel"
    ADDRESS_CHANGE = "address_change"
    OTHER = "other"


class BuyerMessage(BaseModel):
    """バイヤーからのメッセージ."""

    id: int | None = None
    ebay_message_id: str | None = None
    order_id: int | None = None
    buyer_username: str
    direction: str = "inbound"
    category: MessageCategory | None = None
    body: str
    auto_replied: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- 利益計算 ---

class ProfitBreakdown(BaseModel):
    """利益計算の内訳."""

    jpy_cost: int
    ebay_price_usd: float
    fx_rate: float
    jpy_revenue: int
    ebay_fee: int
    payoneer_fee: int
    shipping_cost: int
    packing_cost: int
    fx_buffer: int
    total_cost: int
    net_profit: int
    margin_rate: float
