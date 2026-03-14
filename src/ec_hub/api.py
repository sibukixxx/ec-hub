"""REST API サーバー.

フロントエンド (Preact) から利用するJSON API。
ダッシュボード・候補管理・注文管理・リサーチ・出品・メッセージ・エクスポートのエンドポイントを提供する。
"""

from __future__ import annotations

import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ec_hub.context import AppContext
from ec_hub.modules.price_predictor import PricePredictor
from ec_hub.scrapers.ebay import EbayScraper
from ec_hub.services.dashboard_service import DashboardService
from ec_hub.services.listing_service import ListingService
from ec_hub.services.order_service import OrderService
from ec_hub.services.research_service import ResearchService

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = await AppContext.create()
    app.state.ctx = ctx
    logger.info("API server started, DB connected")
    yield
    await ctx.close()


app = FastAPI(title="ec-hub API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 依存性注入 ---


async def get_ctx() -> AppContext:
    ctx = app.state.ctx
    if ctx is None:
        raise HTTPException(status_code=503, detail="Application not ready")
    return ctx


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


class ResearchRunRequest(BaseModel):
    keywords: list[str] | None = None
    pages: int = 1


class OrderStatusUpdate(BaseModel):
    status: str
    actual_cost_jpy: int | None = None
    tracking_number: str | None = None
    shipping_cost_jpy: int | None = None


class MessageReplyRequest(BaseModel):
    body: str


class DashboardResponse(BaseModel):
    candidates: dict
    orders: dict
    recent_profit: int
    fx_rate: float


# --- ダッシュボード ---

@app.get("/api/dashboard")
async def get_dashboard(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    svc = DashboardService(ctx)
    return await svc.get_dashboard_summary()


# --- 候補管理 ---

@app.get("/api/candidates")
async def list_candidates(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    svc = ResearchService(ctx)
    return await svc.get_candidates(status=status, limit=limit)


@app.get("/api/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: int,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    svc = ResearchService(ctx)
    result = await svc.get_candidate(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate not found")
    # Attach research run info if available
    if result.get("research_run_id"):
        runs = await ctx.db.get_research_runs(limit=1000)
        run = next((r for r in runs if r["id"] == result["research_run_id"]), None)
        if run:
            result["research_run"] = run
    return result


@app.get("/api/research-runs")
async def list_research_runs(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    return await ctx.db.get_research_runs(limit=limit)


@app.patch("/api/candidates/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: int,
    body: CandidateStatusUpdate,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    valid = {"pending", "approved", "rejected", "listed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    svc = ResearchService(ctx)
    await svc.update_candidate_status(candidate_id, body.status)
    return {"id": candidate_id, "status": body.status}


# --- 注文管理 ---

@app.get("/api/orders")
async def list_orders(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    svc = OrderService(ctx)
    return await svc.get_orders(status=status, limit=limit)


@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    svc = OrderService(ctx)
    result = await svc.get_order(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


# --- 利益計算 ---

@app.post("/api/calc/profit")
async def calc_profit(
    req: ProfitCalcRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    svc = DashboardService(ctx)
    breakdown = await svc.calc_profit(
        cost_jpy=req.cost_jpy,
        ebay_price_usd=req.ebay_price_usd,
        weight_g=req.weight_g,
        destination=req.destination,
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
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """eBay販売価格と仕入れ候補を比較する."""
    svc = DashboardService(ctx)
    breakdown = await svc.calc_profit(
        cost_jpy=0, ebay_price_usd=0, weight_g=500, destination="US",
    )
    fx_rate = breakdown.fx_rate

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
    research_svc = ResearchService(ctx)
    candidates = await research_svc.get_candidates(limit=200)
    keyword_lower = req.keyword.lower()
    matched = []
    for c in candidates:
        title = (c.get("title_jp") or "") + " " + (c.get("title_en") or "")
        if keyword_lower in title.lower():
            matched.append(c)

    # ML prediction (load only, no training in request path)
    predictor = PricePredictor(ctx.db)
    predictor.load()

    return {
        "keyword": req.keyword,
        "fx_rate": fx_rate,
        "ebay_items": ebay_items,
        "source_candidates": matched[:10],
        "predictor_trained": predictor.is_trained,
        "prediction_source": "ml" if predictor.is_trained else "rule_based",
    }


# --- 価格予測 ---

@app.post("/api/predict/price")
async def predict_price(
    req: PricePredictRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    # Load model only, no training in request path
    predictor = PricePredictor(ctx.db)
    predictor.load()

    svc = DashboardService(ctx)
    breakdown = await svc.calc_profit(
        cost_jpy=0, ebay_price_usd=0, weight_g=500, destination="US",
    )
    fx_rate = breakdown.fx_rate

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
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    predictor = PricePredictor(ctx.db)
    score = await predictor.train(min_samples=5)
    if score > 0:
        predictor.save()
    return {"score": round(score, 3), "trained": predictor.is_trained}


# --- リサーチ ---


@app.post("/api/research/run")
async def research_run(
    req: ResearchRunRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """リサーチを手動実行する."""
    svc = ResearchService(ctx)
    registered = await svc.run_research(req.keywords, pages=req.pages)
    return {"registered": registered, "status": "completed"}


# --- 出品 ---


@app.post("/api/listing/run")
async def listing_run(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """承認済み候補をeBayに出品する."""
    svc = ListingService(ctx)
    try:
        listed_count = await svc.run_auto_listing()
        return {"listed_count": listed_count, "status": "completed"}
    finally:
        await svc.close()


@app.get("/api/listing/limits")
async def listing_limits(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """eBayセリングリミットの残りを確認する."""
    svc = ListingService(ctx)
    try:
        return await svc.check_selling_limit()
    finally:
        await svc.close()


# --- 注文管理 (拡充) ---


@app.post("/api/orders/check")
async def orders_check(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """eBay APIで新規注文を確認する."""
    svc = OrderService(ctx)
    try:
        new_orders = await svc.check_new_orders()
        for order_data in new_orders:
            await svc.register_order(**order_data)
        return {"new_orders": len(new_orders)}
    finally:
        await svc.close()


@app.put("/api/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """注文ステータスを更新する."""
    valid_statuses = {"awaiting_purchase", "purchased", "shipped", "delivered", "completed"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    order = await ctx.db.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    svc = OrderService(ctx)
    try:
        if body.status == "purchased":
            await svc.mark_purchased(order_id, body.actual_cost_jpy or 0)
        elif body.status == "shipped":
            await svc.mark_shipped(
                order_id,
                tracking_number=body.tracking_number or "",
                shipping_cost_jpy=body.shipping_cost_jpy or 0,
            )
        elif body.status == "delivered":
            from ec_hub.modules.order_manager import OrderManager
            manager = OrderManager(ctx.db, ctx.settings, ctx.fee_rules)
            try:
                await manager.mark_delivered(order_id)
            finally:
                await manager.close()
        elif body.status == "completed":
            await svc.complete_order(order_id)
        else:
            await ctx.db.update_order(order_id, status=body.status)
    finally:
        await svc.close()

    return {"id": order_id, "status": body.status}


# --- メッセージ ---


@app.get("/api/messages")
async def list_messages(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    buyer: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """メッセージ一覧を取得する."""
    return await ctx.db.get_messages(buyer_username=buyer, limit=limit)


@app.post("/api/messages/{message_id}/reply")
async def reply_message(
    message_id: int,
    body: MessageReplyRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """メッセージに手動返信する."""
    original = await ctx.db.get_message_by_id(message_id)
    if not original:
        raise HTTPException(status_code=404, detail="Message not found")

    reply_id = await ctx.db.add_message(
        buyer_username=original["buyer_username"],
        body=body.body,
        direction="outbound",
        order_id=original.get("order_id"),
        category=original.get("category"),
    )
    return {
        "id": reply_id,
        "buyer_username": original["buyer_username"],
        "direction": "outbound",
        "body": body.body,
    }


# --- エクスポート ---


@app.get("/api/export/{data_type}")
async def export_data(
    data_type: str,
    ctx: Annotated[AppContext, Depends(get_ctx)],
    format: str = Query("csv"),
) -> Response:
    """候補・注文データをCSV/JSONでエクスポートする."""
    valid_types = {"candidates", "orders"}
    if data_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {valid_types}")

    valid_formats = {"csv", "json"}
    if format not in valid_formats:
        raise HTTPException(status_code=400, detail=f"Invalid format. Must be one of: {valid_formats}")

    if data_type == "candidates":
        rows = await ctx.db.get_candidates(limit=10000)
    else:
        rows = await ctx.db.get_orders(limit=10000)

    if format == "json":
        return Response(
            content=json.dumps(rows, ensure_ascii=False, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{data_type}.json"'},
        )

    # CSV
    if not rows:
        return Response(content="", media_type="text/csv")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{data_type}.csv"'},
    )


# --- 静的ファイル配信 (ビルド済みフロントエンド) ---

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
