"""価格予測モジュールのテスト."""

import pytest

from ec_hub.db import Database
from ec_hub.modules.price_predictor import PricePredictor


@pytest.fixture
async def db():
    database = Database(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def predictor(db):
    return PricePredictor(db)


async def _seed_candidates(db, count=20, *, status="approved"):
    """テスト用の候補データを投入する.

    Args:
        db: Database instance
        count: Number of candidates to create
        status: Status to assign (default: "approved" for trusted training data)
    """
    import random

    random.seed(42)
    for i in range(count):
        cost = random.randint(1000, 10000)
        # Simulate realistic pricing: price_usd ≈ cost * (1.5~3.0) / 150
        markup = random.uniform(1.5, 3.0)
        price_usd = round(cost * markup / 150, 2)
        margin = random.uniform(0.2, 0.8)
        profit = int(price_usd * 150 * margin - cost)
        candidate_id = await db.add_candidate(
            item_code=f"ITEM{i:03d}",
            source_site=random.choice(["amazon", "rakuten", "yahoo_shopping"]),
            title_jp=f"テスト商品 {i}",
            title_en=None,
            cost_jpy=cost,
            ebay_price_usd=price_usd,
            net_profit_jpy=profit,
            margin_rate=margin,
            weight_g=random.randint(100, 2000),
            category=random.choice(["Electronics", "Toys & Hobbies", "Collectibles", None]),
            ebay_sold_count_30d=random.randint(0, 50),
        )
        if status != "pending":
            await db.update_candidate_status(candidate_id, status)


async def _seed_candidates_with_status(db, status_counts):
    """異なるステータスの候補データを投入する.

    Args:
        db: Database instance
        status_counts: list of (status, count) tuples
    """
    import random

    random.seed(42)
    idx = 0
    for status, count in status_counts:
        for _ in range(count):
            cost = random.randint(1000, 10000)
            markup = random.uniform(1.5, 3.0)
            price_usd = round(cost * markup / 150, 2)
            margin = random.uniform(0.2, 0.8)
            profit = int(price_usd * 150 * margin - cost)
            candidate_id = await db.add_candidate(
                item_code=f"ITEM{idx:03d}",
                source_site=random.choice(["amazon", "rakuten", "yahoo_shopping"]),
                title_jp=f"テスト商品 {idx}",
                title_en=None,
                cost_jpy=cost,
                ebay_price_usd=price_usd,
                net_profit_jpy=profit,
                margin_rate=margin,
                weight_g=random.randint(100, 2000),
                category=random.choice(["Electronics", "Toys & Hobbies", "Collectibles", None]),
                ebay_sold_count_30d=random.randint(0, 50),
            )
            if status != "pending":
                await db.update_candidate_status(candidate_id, status)
            idx += 1


# --- 基本テスト ---

def test_initial_state(predictor):
    assert predictor.is_trained is False


def test_predict_untrained_uses_fallback(predictor):
    """未学習状態ではルールベースフォールバックを使用."""
    result = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    assert result.predicted_price_usd > 0
    # Rule-based: 3000 * 2.5 / 150 = 50.0
    assert result.predicted_price_usd == 50.0
    assert result.confidence == 0.3  # Fallback confidence
    assert result.model_score == 0.0


def test_predict_untrained_various_costs(predictor):
    """異なる仕入れ値でフォールバック予測が正しく計算される."""
    r1 = predictor.predict(cost_jpy=1000, fx_rate=150.0)
    r2 = predictor.predict(cost_jpy=5000, fx_rate=150.0)
    assert r1.predicted_price_usd < r2.predicted_price_usd


# --- 学習テスト ---

async def test_train_insufficient_data(predictor, db):
    """データ不足で学習しない."""
    # Only 3 candidates (below min_samples=10)
    for i in range(3):
        candidate_id = await db.add_candidate(
            item_code=f"ITEM{i}", source_site="amazon",
            title_jp="test", title_en=None,
            cost_jpy=3000, ebay_price_usd=50.0,
            net_profit_jpy=3000, margin_rate=0.5,
        )
        await db.update_candidate_status(candidate_id, "approved")
    score = await predictor.train(min_samples=10)
    assert score == 0.0
    assert predictor.is_trained is False


async def test_train_with_sufficient_data(predictor, db):
    """十分なデータで学習が成功する."""
    await _seed_candidates(db, count=30)
    score = await predictor.train(min_samples=10)
    assert predictor.is_trained is True
    # Score can be negative for very noisy data, but should be computed
    assert isinstance(score, float)


async def test_predict_after_training(predictor, db):
    """学習後はMLモデルで予測する."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)

    result = predictor.predict(
        cost_jpy=3000,
        weight_g=500,
        source_site="amazon",
        category="Electronics",
        ebay_sold_count_30d=10,
        fx_rate=150.0,
    )
    assert result.predicted_price_usd > 0
    assert result.confidence > 0.3  # Should be higher than fallback
    assert result.model_score != 0.0


async def test_predict_higher_cost_higher_price(predictor, db):
    """仕入れ価格が高い商品は予測価格も高くなる."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)

    cheap = predictor.predict(cost_jpy=1000, fx_rate=150.0)
    expensive = predictor.predict(cost_jpy=8000, fx_rate=150.0)
    assert expensive.predicted_price_usd > cheap.predicted_price_usd


# --- 信頼度テスト ---

def test_confidence_untrained(predictor):
    result = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    assert result.confidence == 0.3


async def test_confidence_with_sales(predictor, db):
    """販売実績が多い商品は信頼度が高い."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)

    no_sales = predictor.predict(cost_jpy=3000, ebay_sold_count_30d=0, fx_rate=150.0)
    high_sales = predictor.predict(cost_jpy=3000, ebay_sold_count_30d=15, fx_rate=150.0)
    assert high_sales.confidence >= no_sales.confidence


# --- 保存・読込テスト ---

async def test_save_and_load(predictor, db, tmp_path):
    """モデルの保存と読込."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)

    model_path = tmp_path / "test_model.pkl"
    predictor.save(model_path)
    assert model_path.exists()

    # Create a new predictor and load
    new_predictor = PricePredictor(db)
    assert new_predictor.is_trained is False
    loaded = new_predictor.load(model_path)
    assert loaded is True
    assert new_predictor.is_trained is True

    # Predictions should be consistent
    orig = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    loaded_result = new_predictor.predict(cost_jpy=3000, fx_rate=150.0)
    assert orig.predicted_price_usd == loaded_result.predicted_price_usd


def test_load_nonexistent(predictor):
    """存在しないファイルの読込はFalseを返す."""
    assert predictor.load("/nonexistent/model.pkl") is False


# --- エンコーダテスト ---

def test_encode_known_source(predictor):
    encoded = predictor._encode_source("amazon")
    assert isinstance(encoded, int)


def test_encode_unknown_source(predictor):
    """未知のソースは 'unknown' にマッピングされる."""
    encoded = predictor._encode_source("some_new_site")
    unknown_idx = predictor._encode_source("unknown")
    assert encoded == unknown_idx


def test_encode_known_category(predictor):
    encoded = predictor._encode_category("Electronics")
    assert isinstance(encoded, int)


def test_encode_none_category(predictor):
    """None カテゴリは 'Other' にマッピングされる."""
    encoded = predictor._encode_category(None)
    other_idx = predictor._encode_category("Other")
    assert encoded == other_idx


def test_encode_unknown_category(predictor):
    """未知のカテゴリは 'Other' にマッピングされる."""
    encoded = predictor._encode_category("Totally Unknown Category")
    other_idx = predictor._encode_category("Other")
    assert encoded == other_idx


# --- PricePrediction モデルテスト ---

def test_prediction_fields(predictor):
    result = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    assert hasattr(result, "predicted_price_usd")
    assert hasattr(result, "confidence")
    assert hasattr(result, "predicted_profit_jpy")
    assert hasattr(result, "predicted_margin_rate")
    assert hasattr(result, "model_score")


def test_prediction_profit_calculation(predictor):
    """利益計算が正しい."""
    result = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    # predicted_price_usd = 50.0 (rule-based)
    revenue = int(50.0 * 150)  # 7500
    ebay_fee = int(revenue * 0.1325)  # 993
    payoneer_fee = int(revenue * 0.02)  # 150
    fx_buffer = int(revenue * 0.03)  # 225
    total_cost = 3000 + ebay_fee + payoneer_fee + fx_buffer
    expected_profit = revenue - total_cost
    assert result.predicted_profit_jpy == expected_profit


# --- retrain テスト ---

async def test_retrain_if_needed(predictor, db):
    """十分なデータで再学習が実行される."""
    await _seed_candidates(db, count=30)
    retrained = await predictor.retrain_if_needed(min_new_samples=20)
    assert retrained is True
    assert predictor.is_trained is True


async def test_retrain_if_needed_insufficient(predictor, db):
    """データ不足で再学習しない."""
    retrained = await predictor.retrain_if_needed(min_new_samples=100)
    assert retrained is False


# --- Issue #016: prediction_source フィールド ---

def test_prediction_source_rule_based_when_untrained(predictor):
    """未学習時はprediction_sourceが'rule_based'."""
    result = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    assert result.prediction_source == "rule_based"


async def test_prediction_source_ml_when_trained(predictor, db):
    """学習後はprediction_sourceが'ml'."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)
    result = predictor.predict(cost_jpy=3000, fx_rate=150.0)
    assert result.prediction_source == "ml"


# --- Issue #016: 学習データフィルタリング ---

async def test_train_excludes_pending_status(predictor, db):
    """pending ステータスの候補は学習データから除外される."""
    # 30件 pending + 5件 approved → approved のみ5件 → min_samples=10 で学習不可
    await _seed_candidates_with_status(db, [("pending", 30), ("approved", 5)])
    await predictor.train(min_samples=10)
    assert predictor.is_trained is False


async def test_train_includes_trusted_statuses(predictor, db):
    """approved/listed/completed は学習データに含まれる."""
    await _seed_candidates_with_status(db, [
        ("approved", 10),
        ("listed", 10),
        ("completed", 10),
    ])
    await predictor.train(min_samples=10)
    assert predictor.is_trained is True


# --- Issue #016: モデルメタデータ ---

async def test_model_metadata_after_training(predictor, db):
    """学習後にメタデータが正しく設定される."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)

    meta = predictor.metadata
    assert meta.version == 1
    assert meta.trained_at is not None
    assert meta.sample_count == 30
    assert isinstance(meta.score, float)
    assert len(meta.feature_names) > 0


async def test_metadata_saved_and_loaded(predictor, db, tmp_path):
    """メタデータが保存・読込で保持される."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)

    model_path = tmp_path / "meta_model.pkl"
    predictor.save(model_path)

    new_predictor = PricePredictor(db)
    new_predictor.load(model_path)

    assert new_predictor.metadata.version == predictor.metadata.version
    assert new_predictor.metadata.sample_count == predictor.metadata.sample_count
    assert new_predictor.metadata.score == predictor.metadata.score


async def test_metadata_version_increments(predictor, db):
    """再学習ごとにバージョンがインクリメントされる."""
    await _seed_candidates(db, count=30)
    await predictor.train(min_samples=10)
    assert predictor.metadata.version == 1

    await predictor.train(min_samples=10)
    assert predictor.metadata.version == 2


# --- Issue #016: 低品質モデル無効化 ---

async def test_low_quality_model_disabled(predictor, db):
    """R^2スコアが閾値未満の場合モデルが無効化される."""
    await _seed_candidates(db, count=30)
    # Very high threshold that no model can meet
    score = await predictor.train(min_samples=10, min_quality_score=0.99)
    assert predictor.is_trained is False
    assert isinstance(score, float)
