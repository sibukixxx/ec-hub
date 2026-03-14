"""REST API サーバー.

フロントエンド (Preact) から利用するJSON API。
ダッシュボード・候補管理・注文管理・リサーチ・出品・メッセージ・エクスポートのエンドポイントを提供する。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ec_hub.config import get_frontend_dist_path
from ec_hub.context import AppContext
from ec_hub.exceptions import InvalidStatusError, NotFoundError
from ec_hub.modules.matcher import calc_match_score
from ec_hub.modules.price_predictor import PricePredictor
from ec_hub.modules.profit_tracker import ProfitTracker
from ec_hub.scheduler import Scheduler
from ec_hub.scrapers.ebay import EbayScraper
from ec_hub.services.research_service import ResearchService
from ec_hub.usecases.dashboard import DashboardUseCase
from ec_hub.usecases.export import ExportUseCase
from ec_hub.usecases.listing import ListingUseCase
from ec_hub.usecases.message import MessageUseCase
from ec_hub.usecases.order import OrderUseCase
from ec_hub.usecases.profit_calc import ProfitCalcUseCase

logger = logging.getLogger(__name__)

STATIC_DIR = get_frontend_dist_path()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = AppContext.create(validate_services=True)
    await ctx.connect()
    app.state.ctx = ctx

    scheduler = Scheduler(ctx)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("API server started, AppContext connected, Scheduler started")

    yield

    scheduler.shutdown()
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
        raise HTTPException(status_code=503, detail="AppContext not ready")
    return ctx


# --- リクエスト/レスポンスモデル ---


class CandidateStatusUpdate(BaseModel):
    status: str


class BulkCandidateStatusUpdate(BaseModel):
    ids: list[int]
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


class ListingRunRequest(BaseModel):
    candidate_ids: list[int] | None = None


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
    uc = DashboardUseCase(ctx)
    return await uc.get_summary()


# --- 候補管理 ---


@app.get("/api/candidates")
async def list_candidates(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    return await ctx.candidates.list(status=status, limit=limit)


@app.get("/api/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: int,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    result = await ctx.candidates.get_by_id(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return result


@app.patch("/api/candidates/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: int,
    body: CandidateStatusUpdate,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    valid = {"pending", "approved", "rejected", "listed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    await ctx.candidates.update_status(candidate_id, body.status)
    return {"id": candidate_id, "status": body.status}


@app.post("/api/candidates/bulk-status")
async def bulk_update_candidate_status(
    body: BulkCandidateStatusUpdate,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """複数候補のステータスを一括更新する."""
    valid = {"pending", "approved", "rejected", "listed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    if not body.ids:
        raise HTTPException(status_code=400, detail="ids must not be empty")
    if len(body.ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 candidates per bulk operation")
    updated = await ctx.candidates.bulk_update_status(body.ids, body.status)
    return {"updated_count": updated, "status": body.status}


# --- 注文管理 ---


@app.get("/api/orders")
async def list_orders(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    return await ctx.orders.list(status=status, limit=limit)


@app.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    result = await ctx.orders.get_by_id(order_id)
    if not result:
        raise HTTPException(status_code=404, detail="Order not found")
    return result


# --- 利益計算 ---


@app.post("/api/calc/profit")
async def calc_profit(
    req: ProfitCalcRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    uc = ProfitCalcUseCase(ctx)
    return await uc.calculate(
        cost_jpy=req.cost_jpy,
        ebay_price_usd=req.ebay_price_usd,
        weight_g=req.weight_g,
        destination=req.destination,
    )


# --- 価格比較 ---


@app.post("/api/compare")
async def compare_prices(
    req: CompareRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """eBay販売価格と仕入れ候補を比較する."""
    tracker = ProfitTracker(ctx.db, ctx.settings, ctx.fee_rules)
    fx_rate = await tracker.get_fx_rate()

    # Search eBay
    ebay_items = []
    async with EbayScraper() as scraper:
        result = await scraper.search(req.keyword, page=1)
        for p in result.products[: req.max_results]:
            ebay_items.append(
                {
                    "item_id": p.item_id,
                    "title": p.title,
                    "price_usd": p.price,
                    "price_jpy": int((p.price or 0) * fx_rate),
                    "url": p.url,
                    "image_url": p.image_url,
                    "category": p.category,
                    "condition": p.condition.value if p.condition else None,
                    "shipping": {
                        "cost": p.shipping.cost if p.shipping else None,
                        "free": p.shipping.free_shipping if p.shipping else False,
                    },
                }
            )

    # Search candidates DB for matching items
    candidates = await ctx.candidates.list(limit=200)
    keyword_lower = req.keyword.lower()
    matched = []
    compare_anchor = ebay_items[0] if ebay_items else None
    for c in candidates:
        title = (c.get("title_jp") or "") + " " + (c.get("title_en") or "")
        if keyword_lower in title.lower():
            enriched = dict(c)
            if compare_anchor:
                compare_match = calc_match_score(
                    compare_anchor["title"],
                    title,
                    ebay_price_usd=compare_anchor.get("price_usd"),
                    source_price_jpy=c.get("cost_jpy"),
                    fx_rate=fx_rate,
                    ebay_category=compare_anchor.get("category"),
                    source_category=c.get("category"),
                )
                enriched["compare_match_score"] = compare_match["score"]
                enriched["compare_match_reason"] = " / ".join(compare_match["reasons"])
            matched.append(enriched)

    matched.sort(
        key=lambda c: (
            c.get("compare_match_score") if c.get("compare_match_score") is not None else c.get("match_score", -1),
            c.get("match_score", -1),
            c.get("margin_rate", 0),
        ),
        reverse=True,
    )

    # ML prediction
    predictor = PricePredictor(ctx.db, ctx.settings)
    predictor.load()
    if not predictor.is_trained:
        await predictor.train(min_samples=5)

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
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    predictor = PricePredictor(ctx.db, ctx.settings)
    predictor.load()
    if not predictor.is_trained:
        await predictor.train(min_samples=5)

    tracker = ProfitTracker(ctx.db, ctx.settings, ctx.fee_rules)
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
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    predictor = PricePredictor(ctx.db, ctx.settings)
    score = await predictor.train(min_samples=5)
    if score > 0:
        predictor.save()
    return {"score": round(score, 3), "trained": predictor.is_trained}


# --- リサーチ ---


@app.get("/api/research/runs")
async def list_research_runs(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """リサーチ実行履歴を取得する."""
    svc = ResearchService(ctx)
    return await svc.get_research_runs(limit=limit)


@app.get("/api/research/runs/{run_id}")
async def get_research_run(
    run_id: int,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """リサーチ実行の詳細を取得する."""
    svc = ResearchService(ctx)
    result = await svc.get_research_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Research run not found")
    return result


@app.post("/api/research/run")
async def research_run(
    req: ResearchRunRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
    background_tasks: BackgroundTasks,
) -> dict:
    """リサーチを非同期で実行する.

    即座に run_id を返し、バックグラウンドでリサーチを実行する。
    進捗は GET /api/research/runs/{run_id} で確認可能
    (completed_at が NULL なら実行中)。
    """
    svc = ResearchService(ctx)
    run_id = await svc.start_research(keywords=req.keywords, pages=req.pages)
    background_tasks.add_task(svc.execute_research, run_id, req.keywords, req.pages)
    return {"run_id": run_id, "status": "running"}


# --- 出品 ---


@app.post("/api/listing/run")
async def listing_run(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    body: ListingRunRequest | None = None,
) -> dict:
    """承認済み候補をeBayに出品する.候補IDを指定すると選択的に出品する."""
    uc = ListingUseCase(ctx)
    candidate_ids = body.candidate_ids if body else None
    listed_count = await uc.run(candidate_ids=candidate_ids)
    return {"listed_count": listed_count, "status": "completed"}


@app.get("/api/listing/preview/{candidate_id}")
async def listing_preview(
    candidate_id: int,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """出品プレビュー情報を取得する（出品はしない）."""
    uc = ListingUseCase(ctx)
    result = await uc.preview(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return result


@app.get("/api/listing/limits")
async def listing_limits(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """eBayセリングリミットの残りを確認する."""
    uc = ListingUseCase(ctx)
    return await uc.check_selling_limit()


# --- 注文管理 (拡充) ---


@app.post("/api/orders/check")
async def orders_check(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """eBay APIで新規注文を確認する."""
    uc = OrderUseCase(ctx)
    count = await uc.check_new_orders()
    return {"new_orders": count}


@app.put("/api/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: OrderStatusUpdate,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """注文ステータスを更新する."""
    try:
        return await OrderUseCase(ctx).update_status(
            order_id,
            body.status,
            actual_cost_jpy=body.actual_cost_jpy,
            tracking_number=body.tracking_number,
            shipping_cost_jpy=body.shipping_cost_jpy,
        )
    except InvalidStatusError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- メッセージ ---


@app.get("/api/messages")
async def list_messages(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    buyer: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """メッセージ一覧を取得する."""
    uc = MessageUseCase(ctx)
    return await uc.list_messages(buyer_username=buyer, category=category, limit=limit)


@app.post("/api/messages/{message_id}/reply")
async def reply_message(
    message_id: int,
    body: MessageReplyRequest,
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> dict:
    """メッセージに手動返信する."""
    try:
        return await MessageUseCase(ctx).reply(message_id, body.body)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- ジョブ実行履歴 ---


@app.get("/api/job-runs")
async def list_job_runs(
    ctx: Annotated[AppContext, Depends(get_ctx)],
    job_name: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    return await ctx.db.get_job_runs(job_name=job_name, limit=limit)


# --- システムヘルス ---


@app.get("/api/system/health")
async def system_health(
    ctx: Annotated[AppContext, Depends(get_ctx)],
) -> list[dict]:
    return await ctx.db.get_all_integration_status()


# --- エクスポート ---


@app.get("/api/export/{data_type}")
async def export_data(
    data_type: str,
    ctx: Annotated[AppContext, Depends(get_ctx)],
    format: str = Query("csv"),
) -> Response:
    """候補・注文データをCSV/JSONでエクスポートする."""
    try:
        uc = ExportUseCase(ctx)
        content, media_type = await uc.export_data(data_type, format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    headers = {}
    if media_type == "application/json":
        headers["Content-Disposition"] = f'attachment; filename="{data_type}.json"'
    elif media_type == "text/csv" and content:
        headers["Content-Disposition"] = f'attachment; filename="{data_type}.csv"'

    return Response(content=content, media_type=media_type, headers=headers)


# --- スケジューラ ---


@app.get("/api/scheduler/status")
async def scheduler_status() -> dict:
    """スケジューラの状態を確認する."""
    scheduler: Scheduler | None = getattr(app.state, "scheduler", None)
    if scheduler is None:
        # テスト環境などスケジューラ未初期化時のフォールバック
        return {"running": False, "jobs": []}
    return scheduler.get_status()


@app.post("/api/scheduler/trigger/{job_name}")
async def trigger_job(job_name: str) -> dict:
    """ジョブを手動トリガーする."""
    scheduler: Scheduler | None = getattr(app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    try:
        return await scheduler.trigger_job(job_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- 静的ファイル配信 (ビルド済みフロントエンド) ---

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
