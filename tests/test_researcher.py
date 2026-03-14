"""Researcher モジュールのテスト."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.researcher import Researcher, simplify_search_query
from ec_hub.scrapers.base import SourceProduct, SourceSearcher, SourceSearchResult

# --- テスト用モックSearcher ---

class MockSourceSearcher(SourceSearcher):
    """テスト用の仕入れ検索モック."""

    def __init__(self, products: list[SourceProduct] | None = None) -> None:
        self._products = products or []

    @property
    def site_name(self) -> str:
        return "mock"

    async def search(self, query: str, *, max_results: int = 10) -> SourceSearchResult:
        return SourceSearchResult(
            query=query,
            source_site=self.site_name,
            products=self._products[:max_results],
        )

    async def get_item(self, item_code: str) -> SourceProduct | None:
        for p in self._products:
            if p.item_code == item_code:
                return p
        return None


# --- Fixtures ---

@pytest.fixture
def fee_rules():
    return {
        "ebay_fees": {"default_rate": 0.1325},
        "payoneer": {"rate": 0.02},
        "fx_buffer": {"rate": 0.03},
        "packing": {"default_cost": 200, "small": 100, "medium": 200, "large": 300},
        "shipping": {
            "zones": {
                "US": [
                    {"max_weight_g": 500, "cost": 1500},
                    {"max_weight_g": 1000, "cost": 2000},
                ],
                "OTHER": [
                    {"max_weight_g": 500, "cost": 2000},
                ],
            },
            "destination_zones": {"US": "US"},
        },
    }


@pytest.fixture
def settings():
    return {
        "exchange_rate": {"fallback_rate": 150.0},
        "database": {"path": ":memory:"},
        "research": {
            "min_margin_rate": 0.30,
            "max_shipping_ratio": 0.50,
            "max_candidates_per_run": 50,
            "exclude_categories": ["Food & Beverages"],
        },
        "amazon": {},
        "rakuten": {},
        "line": {},
    }


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def researcher(db, settings, fee_rules):
    return Researcher(db, settings, fee_rules)


# --- simplify_search_query テスト ---

def test_simplify_search_query_basic():
    assert simplify_search_query("NEW RARE Pokemon Card Pikachu Japan") == "Pokemon Card Pikachu"


def test_simplify_search_query_short():
    assert simplify_search_query("Gundam Model Kit") == "Gundam Model Kit"


def test_simplify_search_query_long():
    result = simplify_search_query("AUTHENTIC GENUINE Super Mario Bros Figure Figurine Collectible Item Toy")
    words = result.split()
    assert len(words) <= 6


def test_simplify_search_query_removes_noise():
    result = simplify_search_query("Free Shipping From Japan Used Vintage Nendoroid 1000")
    assert "Free" not in result
    assert "Shipping" not in result
    assert "From" not in result
    assert "Japan" not in result
    assert "Nendoroid" in result


# --- find_source_price テスト ---

async def test_find_source_price_no_searchers(researcher):
    result = await researcher.find_source_price("test", [])
    assert result is None


async def test_find_source_price_returns_cheapest(researcher):
    products = [
        SourceProduct(
            item_code="A001", source_site="mock",
            title="高い商品", price_jpy=5000, url="https://example.com/a001",
        ),
        SourceProduct(
            item_code="A002", source_site="mock",
            title="安い商品", price_jpy=2000, url="https://example.com/a002",
        ),
        SourceProduct(
            item_code="A003", source_site="mock",
            title="中間", price_jpy=3000, url="https://example.com/a003",
        ),
    ]
    searcher = MockSourceSearcher(products)
    result = await researcher.find_source_price("test", [searcher])
    assert result is not None
    assert result.item_code == "A002"
    assert result.price_jpy == 2000


async def test_find_source_price_excludes_unavailable(researcher):
    products = [
        SourceProduct(
            item_code="A001", source_site="mock",
            title="在庫なし", price_jpy=1000, url="https://example.com/a001",
            availability=False,
        ),
        SourceProduct(
            item_code="A002", source_site="mock",
            title="在庫あり", price_jpy=3000, url="https://example.com/a002",
            availability=True,
        ),
    ]
    searcher = MockSourceSearcher(products)
    result = await researcher.find_source_price("test", [searcher])
    assert result is not None
    assert result.item_code == "A002"


async def test_find_source_price_multiple_searchers(researcher):
    searcher1 = MockSourceSearcher([
        SourceProduct(
            item_code="AMZ001", source_site="amazon",
            title="Amazon商品", price_jpy=4000, url="https://amazon.co.jp/dp/AMZ001",
        ),
    ])
    searcher2 = MockSourceSearcher([
        SourceProduct(
            item_code="RKT001", source_site="rakuten",
            title="楽天商品", price_jpy=2500, url="https://rakuten.co.jp/rkt001",
        ),
    ])
    result = await researcher.find_source_price("test", [searcher1, searcher2])
    assert result is not None
    assert result.item_code == "RKT001"
    assert result.price_jpy == 2500


# --- evaluate_candidate テスト ---

async def test_evaluate_candidate_profitable(researcher):
    """利益率30%以上で登録される."""
    cid = await researcher.evaluate_candidate(
        item_code="B09TEST",
        source_site="amazon",
        title_jp="テスト利益商品",
        cost_jpy=2000,
        ebay_price_usd=80.0,
        weight_g=500,
    )
    assert cid is not None

    candidates = await researcher._db.get_candidates()
    assert len(candidates) == 1
    assert candidates[0]["item_code"] == "B09TEST"
    assert candidates[0]["source_site"] == "amazon"


async def test_evaluate_candidate_low_margin(researcher):
    """利益率30%未満で除外される."""
    cid = await researcher.evaluate_candidate(
        item_code="B09EXPENSIVE",
        source_site="amazon",
        title_jp="高仕入れ商品",
        cost_jpy=10000,
        ebay_price_usd=80.0,
        weight_g=500,
    )
    assert cid is None


async def test_evaluate_candidate_high_shipping_ratio(researcher):
    """送料比率50%超で除外される."""
    cid = await researcher.evaluate_candidate(
        item_code="B09HEAVY",
        source_site="amazon",
        title_jp="重い商品",
        cost_jpy=500,
        ebay_price_usd=15.0,  # $15 * 150 = ¥2,250 → 送料¥1,500は66%
        weight_g=500,
    )
    assert cid is None


# --- research_single テスト ---

async def test_research_single_with_match(researcher):
    """仕入れ先が見つかり利益率OKの場合."""
    searcher = MockSourceSearcher([
        SourceProduct(
            item_code="AMZ001", source_site="amazon",
            title="仕入れ商品", price_jpy=2000, url="https://amazon.co.jp/dp/AMZ001",
        ),
    ])
    ebay_product = {
        "item_id": "123456",
        "title": "Test Product For Sale",
        "price_usd": 80.0,
    }
    cid = await researcher.research_single(ebay_product, [searcher])
    assert cid is not None


async def test_research_single_no_source(researcher):
    """仕入れ先が見つからない場合."""
    searcher = MockSourceSearcher([])
    ebay_product = {
        "item_id": "999999",
        "title": "No Source Product",
        "price_usd": 50.0,
    }
    cid = await researcher.research_single(ebay_product, [searcher])
    assert cid is None


async def test_research_single_no_price(researcher):
    """eBay価格がない場合."""
    searcher = MockSourceSearcher([
        SourceProduct(
            item_code="AMZ", source_site="amazon",
            title="test", price_jpy=1000, url="https://test",
        ),
    ])
    cid = await researcher.research_single({"title": "Test", "price_usd": None}, [searcher])
    assert cid is None
