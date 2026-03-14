"""REST API サーバー.

フロントエンド (Preact) から利用するJSON API。
ダッシュボード・候補管理・注文管理のエンドポイントを提供する。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ec_hub.config import load_fee_rules, load_settings
from ec_hub.db import Database
from ec_hub.modules.price_predictor import PricePredictor
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.scrapers.ebay import EbayScraper

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    fee_rules = load_fee_rules()
    db_path = settings.get("database", {}).get("path", "db/ebay.db")
    db = Database(db_path)
    await db.connect()
    app.state.db = db
    app.state.settings = settings
    app.state.fee_rules = fee_rules
    logger.info("API server started, DB connected")
    yield
    await db.close()


app = FastAPI(title="ec-hub API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 依存性注入 ---


async def get_db() -> Database:
    db = app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    return db


async def get_settings() -> dict:
    return app.state.settings


async def get_fee_rules() -> dict:
    return app.state.fee_rules


# --- リクエスト/レスポンスモデル ---

class CandidateStatusUpdate(BaseModel):
    status: str


class PricePredictRequest(BaseModel):
    cost_jpy: int
    weight_g: int = 500
    source_site: str = "amazon"
    category: str | None = None
    ebay_sold_count_30d: int = 0


class CompareRequest(BaseModel):
    keyword: str
    max_results: int = 5


class ProfitCalcRequest(BaseModel):
    cost_jpy: int
    ebay_price_usd: float
    weight_g: int = 500
    destination: str = "US"


class DashboardResponse(BaseModel):
    candidates: dict
    orders: dict
    recent_profit: int
    fx_rate: float


# --- ダッシュボード ---

@app.get("/api/dashboard")
async def get_dashboard(
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[dict, Depends(get_settings)],
    fee_rules: Annotated[dict, Depends(get_fee_rules)],
) -> dict:
    candidates_pending = await db.get_candidates(status="pending", limit=1000)
    candidates_approved = await db.get_candidates(status="approved", limit=1000)
    candidates_listed = await db.get_candidates(status="listed", limit=1000)

    orders_awaiting = await db.get_orders(status="awaiting_purchase", limit=1000)
    orders_shipped = await db.get_orders(status="shipped", limit=1000)
    orders_completed = await db.get_orders(status="completed", limit=1000)

    total_profit = sum(o.get("net_profit_jpy", 0) or 0 for o in orders_completed)

    tracker = ProfitTracker(db, settings, fee_rules)
    fx_rate = await tracker.get_fx_rate()

    return {
        "candidates": {
            "pending": len(candidates_pending),
            "approved": len(candidates_approved),
            "listed": len(candidates_listed),
        },
        "orders": {
            "awaiting_purchase": len(orders_awaiting),
            "shipped": len(orders_shipped),
            "completed": len(orders_completed),
        },
        "recent_profit": total_profit,
        "fx_rate": fx_rate,
    }


# --- 候補管理 ---

@app.get("/api/candidates")
async def list_candidates(
    db: Annotated[Database, Depends(get_db)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    return await db.get_candidates(status=status, limit=limit)


@app.get("/api/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: int,
    db: Annotated[Database, Depends(get_db)],
) -> dict:
    rows = await db.get_candidates(limit=1000)
    target = next((c for c in rows if c["id"] == candidate_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return target


@app.patch("/api/candidates/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: int,
    body: CandidateStatusUpdate,
    db: Annotated[Database, Depends(get_db)],
) -> dict:
    valid = {"pending", "approved", "rejected", "listed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    await db.update_candidate_status(candidate_id, body.status)
    return {"id": candidate_id, "status": body.status}


# --- 注文管理 ---

@app.get("/api/orders")
async def list_orders(
    db: Annotated[Database, Depends(get_db)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    return await db.get_orders(status=status, limit=limit)


@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    db: Annotated[Database, Depends(get_db)],
) -> dict:
    rows = await db.get_orders(limit=1000)
    target = next((o for o in rows if o["id"] == order_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Order not found")
    return target


# --- 利益計算 ---

@app.post("/api/calc/profit")
async def calc_profit(
    req: ProfitCalcRequest,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[dict, Depends(get_settings)],
    fee_rules: Annotated[dict, Depends(get_fee_rules)],
) -> dict:
    tracker = ProfitTracker(db, settings, fee_rules)
    fx_rate = await tracker.get_fx_rate()
    breakdown = tracker.calc_net_profit(
        jpy_cost=req.cost_jpy,
        ebay_price_usd=req.ebay_price_usd,
        weight_g=req.weight_g,
        destination=req.destination,
        fx_rate=fx_rate,
    )
    return {
        "jpy_cost": breakdown.jpy_cost,
        "ebay_price_usd": breakdown.ebay_price_usd,
        "fx_rate": breakdown.fx_rate,
        "jpy_revenue": breakdown.jpy_revenue,
        "ebay_fee": breakdown.ebay_fee,
        "payoneer_fee": breakdown.payoneer_fee,
        "shipping_cost": breakdown.shipping_cost,
        "packing_cost": breakdown.packing_cost,
        "fx_buffer": breakdown.fx_buffer,
        "total_cost": breakdown.total_cost,
        "net_profit": breakdown.net_profit,
        "margin_rate": breakdown.margin_rate,
    }


# --- 価格比較 ---

@app.post("/api/compare")
async def compare_prices(
    req: CompareRequest,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[dict, Depends(get_settings)],
    fee_rules: Annotated[dict, Depends(get_fee_rules)],
) -> dict:
    """eBay販売価格と仕入れ候補を比較する."""
    tracker = ProfitTracker(db, settings, fee_rules)
    fx_rate = await tracker.get_fx_rate()

    # Search eBay
    ebay_items = []
    async with EbayScraper() as scraper:
        result = await scraper.search(req.keyword, page=1)
        for p in result.products[: req.max_results]:
            ebay_items.append({
                "item_id": p.item_id,
                "title": p.title,
                "price_usd": p.price,
                "price_jpy": int((p.price or 0) * fx_rate),
                "url": p.url,
                "image_url": p.image_url,
                "condition": p.condition.value if p.condition else None,
                "shipping": {
                    "cost": p.shipping.cost if p.shipping else None,
                    "free": p.shipping.free_shipping if p.shipping else False,
                },
            })

    # Search candidates DB for matching items
    candidates = await db.get_candidates(limit=200)
    keyword_lower = req.keyword.lower()
    matched = []
    for c in candidates:
        title = (c.get("title_jp") or "") + " " + (c.get("title_en") or "")
        if keyword_lower in title.lower():
            matched.append(c)

    # ML prediction (load only — training is done via /api/predict/train)
    predictor = PricePredictor(db)
    predictor.load()

    return {
        "keyword": req.keyword,
        "fx_rate": fx_rate,
        "ebay_items": ebay_items,
        "source_candidates": matched[:10],
        "predictor_trained": predictor.is_trained,
    }


# --- 価格予測 ---

@app.post("/api/predict/price")
async def predict_price(
    req: PricePredictRequest,
    db: Annotated[Database, Depends(get_db)],
    settings: Annotated[dict, Depends(get_settings)],
    fee_rules: Annotated[dict, Depends(get_fee_rules)],
) -> dict:
    # Load only — training is done via /api/predict/train
    predictor = PricePredictor(db)
    predictor.load()

    tracker = ProfitTracker(db, settings, fee_rules)
    fx_rate = await tracker.get_fx_rate()

    prediction = predictor.predict(
        cost_jpy=req.cost_jpy,
        weight_g=req.weight_g,
        source_site=req.source_site,
        category=req.category,
        ebay_sold_count_30d=req.ebay_sold_count_30d,
        fx_rate=fx_rate,
    )
    return prediction.model_dump()


@app.post("/api/predict/train")
async def train_model(
    db: Annotated[Database, Depends(get_db)],
) -> dict:
    predictor = PricePredictor(db)
    predictor.load()  # Preserve version for increment
    score = await predictor.train(min_samples=5)
    if predictor.is_trained:
        predictor.save()
    return {
        "score": round(score, 3),
        "trained": predictor.is_trained,
        "metadata": predictor.metadata.model_dump() if predictor.is_trained else None,
    }


# --- 静的ファイル配信 (ビルド済みフロントエンド) ---

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
