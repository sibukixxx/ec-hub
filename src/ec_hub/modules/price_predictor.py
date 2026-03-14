"""eBay価格予測モジュール.

過去の候補・注文データを学習し、仕入れ商品のeBay販売価格を予測する。
MVP: GradientBoosting回帰モデル + 基本特徴量 (仕入れ価格, 重量, カテゴリ, ソース, 販売実績)。

使い方:
    predictor = PricePredictor(db)
    await predictor.train()                    # 過去データで学習
    prediction = predictor.predict(cost_jpy=3000, weight_g=500, ...)
    predictor.save("models/price_model.pkl")   # モデル保存
    predictor.load("models/price_model.pkl")   # モデル読込
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import numpy as np
from pydantic import BaseModel
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder

from ec_hub.db import Database

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent.parent / "models" / "price_model.pkl"

# Known categories and sources for label encoding
KNOWN_SOURCES = ["amazon", "rakuten", "yahoo_shopping", "unknown"]
KNOWN_CATEGORIES = [
    "Collectibles", "Toys & Hobbies", "Video Games", "Electronics",
    "Clothing", "Books", "Music", "Art", "Pottery & Glass",
    "Coins & Paper Money", "Sports", "Health & Beauty",
    "Home & Garden", "Jewelry & Watches", "Other",
]


class PricePrediction(BaseModel):
    """価格予測結果."""

    predicted_price_usd: float
    confidence: float  # 0.0 - 1.0
    predicted_profit_jpy: int
    predicted_margin_rate: float
    model_score: float  # R² score from training


class PricePredictor:
    """eBay販売価格の予測モデル."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._model: GradientBoostingRegressor | None = None
        self._source_encoder = LabelEncoder()
        self._category_encoder = LabelEncoder()
        self._model_score: float = 0.0
        self._is_trained: bool = False

        # Pre-fit encoders with known values
        self._source_encoder.fit(KNOWN_SOURCES)
        self._category_encoder.fit(KNOWN_CATEGORIES)

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def _encode_source(self, source: str) -> int:
        if source in self._source_encoder.classes_:
            return int(self._source_encoder.transform([source])[0])
        return int(self._source_encoder.transform(["unknown"])[0])

    def _encode_category(self, category: str | None) -> int:
        if category and category in self._category_encoder.classes_:
            return int(self._category_encoder.transform([category])[0])
        return int(self._category_encoder.transform(["Other"])[0])

    def _build_features(
        self,
        cost_jpy: int,
        weight_g: int,
        source_site: str,
        category: str | None = None,
        ebay_sold_count_30d: int = 0,
    ) -> np.ndarray:
        """特徴量ベクトルを構築する."""
        return np.array([
            cost_jpy,
            weight_g,
            self._encode_source(source_site),
            self._encode_category(category),
            ebay_sold_count_30d,
            cost_jpy / max(weight_g, 1),  # price density (JPY/g)
        ]).reshape(1, -1)

    async def train(self, min_samples: int = 10) -> float:
        """候補データからモデルを学習する.

        Returns:
            R² score (cross-validation mean)
        """
        candidates = await self._db.get_candidates(limit=10000)

        # Filter training data: approved/listed candidates with valid prices
        training_data = []
        for c in candidates:
            if c.get("status") not in ("approved", "listed", "pending"):
                continue
            cost = c.get("cost_jpy")
            price = c.get("ebay_price_usd")
            if not cost or not price or cost <= 0 or price <= 0:
                continue
            training_data.append(c)

        if len(training_data) < min_samples:
            logger.warning(
                "学習データ不足: %d件 (最低%d件必要)。ルールベース予測にフォールバック。",
                len(training_data), min_samples,
            )
            self._is_trained = False
            self._model_score = 0.0
            return 0.0

        # Build feature matrix and target
        X = np.array([
            [
                c["cost_jpy"],
                c.get("weight_g") or 500,
                self._encode_source(c.get("source_site", "unknown")),
                self._encode_category(c.get("category")),
                c.get("ebay_sold_count_30d") or 0,
                c["cost_jpy"] / max(c.get("weight_g") or 500, 1),
            ]
            for c in training_data
        ])
        y = np.array([c["ebay_price_usd"] for c in training_data])

        self._model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            min_samples_leaf=2,
            random_state=42,
        )

        # Cross-validation for score
        n_splits = min(5, len(training_data))
        if n_splits >= 2:
            scores = cross_val_score(self._model, X, y, cv=n_splits, scoring="r2")
            self._model_score = float(np.mean(scores))
        else:
            self._model_score = 0.0

        # Train on full dataset
        self._model.fit(X, y)
        self._is_trained = True

        logger.info(
            "価格予測モデル学習完了: %d件, R²=%.3f",
            len(training_data), self._model_score,
        )
        return self._model_score

    def predict(
        self,
        cost_jpy: int,
        weight_g: int = 500,
        source_site: str = "amazon",
        category: str | None = None,
        ebay_sold_count_30d: int = 0,
        fx_rate: float = 150.0,
    ) -> PricePrediction:
        """eBay販売価格を予測する."""
        if self._is_trained and self._model is not None:
            features = self._build_features(
                cost_jpy=cost_jpy,
                weight_g=weight_g,
                source_site=source_site,
                category=category,
                ebay_sold_count_30d=ebay_sold_count_30d,
            )
            predicted_usd = float(max(self._model.predict(features)[0], 0.01))
        else:
            # Fallback: rule-based estimation (cost * markup / fx_rate)
            predicted_usd = self._rule_based_estimate(cost_jpy, fx_rate)

        # Calculate predicted profit
        revenue_jpy = int(predicted_usd * fx_rate)
        ebay_fee = int(revenue_jpy * 0.1325)
        payoneer_fee = int(revenue_jpy * 0.02)
        fx_buffer = int(revenue_jpy * 0.03)
        total_cost = cost_jpy + ebay_fee + payoneer_fee + fx_buffer
        predicted_profit = revenue_jpy - total_cost
        margin_rate = predicted_profit / max(total_cost, 1)

        # Confidence based on model quality and data availability
        confidence = self._calc_confidence(ebay_sold_count_30d)

        return PricePrediction(
            predicted_price_usd=round(predicted_usd, 2),
            confidence=round(confidence, 2),
            predicted_profit_jpy=predicted_profit,
            predicted_margin_rate=round(margin_rate, 3),
            model_score=round(self._model_score, 3),
        )

    @staticmethod
    def _rule_based_estimate(cost_jpy: int, fx_rate: float) -> float:
        """ルールベースの価格推定 (フォールバック).

        仕入れ価格 × 2.5 / 為替レートで推定。
        利益率30%+手数料15%+バッファを考慮した倍率。
        """
        return round(cost_jpy * 2.5 / fx_rate, 2)

    def _calc_confidence(self, ebay_sold_count_30d: int) -> float:
        """予測信頼度を計算する."""
        if not self._is_trained:
            return 0.3  # Rule-based fallback

        # Base confidence from model score
        base = max(0.0, min(1.0, self._model_score))

        # Boost from sales evidence
        if ebay_sold_count_30d >= 10:
            sales_boost = 0.15
        elif ebay_sold_count_30d >= 3:
            sales_boost = 0.10
        elif ebay_sold_count_30d >= 1:
            sales_boost = 0.05
        else:
            sales_boost = 0.0

        return min(1.0, base * 0.8 + sales_boost + 0.1)

    def save(self, path: str | Path | None = None) -> None:
        """学習済みモデルをファイルに保存する."""
        save_path = Path(path) if path else DEFAULT_MODEL_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "model": self._model,
            "source_encoder": self._source_encoder,
            "category_encoder": self._category_encoder,
            "model_score": self._model_score,
            "is_trained": self._is_trained,
        }
        with open(save_path, "wb") as f:
            pickle.dump(data, f)  # noqa: S301

        logger.info("モデル保存: %s", save_path)

    def load(self, path: str | Path | None = None) -> bool:
        """保存済みモデルを読み込む.

        Returns:
            True if loaded successfully, False otherwise
        """
        load_path = Path(path) if path else DEFAULT_MODEL_PATH
        if not load_path.exists():
            logger.info("モデルファイルなし: %s", load_path)
            return False

        try:
            with open(load_path, "rb") as f:
                data = pickle.load(f)  # noqa: S301
            self._model = data["model"]
            self._source_encoder = data["source_encoder"]
            self._category_encoder = data["category_encoder"]
            self._model_score = data["model_score"]
            self._is_trained = data["is_trained"]
            logger.info("モデル読込: %s (R²=%.3f)", load_path, self._model_score)
            return True
        except Exception as e:
            logger.error("モデル読込失敗: %s", e)
            return False

    async def retrain_if_needed(self, min_new_samples: int = 20) -> bool:
        """新規データが十分溜まった場合に再学習する.

        Returns:
            True if retrained
        """
        candidates = await self._db.get_candidates(limit=10000)
        total = len([c for c in candidates if c.get("ebay_price_usd") and c.get("cost_jpy")])

        if total >= min_new_samples:
            score = await self.train()
            if score > 0:
                self.save()
                return True
        return False
