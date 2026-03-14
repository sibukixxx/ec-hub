"""Typed configuration schema with Pydantic validation."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class _DictCompatMixin:
    """Mixin to support dict-style .get() and [] access for backward compatibility.

    Allows existing code using `settings.get("ebay", {}).get("app_id", "")`
    to work unchanged while migrating to typed attribute access.
    """

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and hasattr(self, key)

    def keys(self):
        return self.model_dump().keys()

    def values(self):
        return self.model_dump().values()

    def items(self):
        return self.model_dump().items()

    def __iter__(self):
        return iter(self.model_dump())


class _ConfigModel(_DictCompatMixin, BaseModel):
    """Base model for all config sections with dict-compatible access."""


# ---------------------------------------------------------------------------
# Settings sub-models
# ---------------------------------------------------------------------------

class EbaySite(str, Enum):
    EBAY_US = "EBAY_US"
    EBAY_GB = "EBAY_GB"
    EBAY_DE = "EBAY_DE"
    EBAY_JP = "EBAY_JP"


class EbayConfig(_ConfigModel):
    app_id: str = ""
    cert_id: str = ""
    dev_id: str = ""
    user_token: str = ""
    site: EbaySite = EbaySite.EBAY_US
    sandbox: bool = True


class LineConfig(_ConfigModel):
    channel_access_token: str = ""
    user_id: str = ""


class DeepLConfig(_ConfigModel):
    api_key: str = ""


class ClaudeConfig(_ConfigModel):
    api_key: str = ""
    model: str = "claude-haiku-4-5-20251001"


class AmazonConfig(_ConfigModel):
    access_key: str = ""
    secret_key: str = ""
    partner_tag: str = ""
    country: str = "www.amazon.co.jp"


class RakutenConfig(_ConfigModel):
    app_id: str = ""


class YahooShoppingConfig(_ConfigModel):
    app_id: str = ""


class ExchangeRateConfig(_ConfigModel):
    base_url: str = "https://api.exchangerate-api.com/v4/latest/USD"
    fallback_rate: float = 150.0


class DatabaseConfig(_ConfigModel):
    path: str = "db/ebay.db"
    resolved_path: Path | None = None


class PathsConfig(_ConfigModel):
    price_model_path: str = "models/price_model.pkl"
    frontend_dist_path: str = "frontend/dist"
    resolved_price_model_path: Path | None = None
    resolved_frontend_dist_path: Path | None = None


class SchedulerCronJob(_ConfigModel):
    cron: str | None = None
    interval_minutes: int | None = None


class SchedulerConfig(_ConfigModel):
    researcher: SchedulerCronJob = Field(default_factory=SchedulerCronJob)
    order_manager: SchedulerCronJob = Field(default_factory=SchedulerCronJob)
    messenger: SchedulerCronJob = Field(default_factory=SchedulerCronJob)
    profit_tracker: SchedulerCronJob = Field(default_factory=SchedulerCronJob)


class ResearchConfig(_ConfigModel):
    min_margin_rate: float = 0.30
    max_shipping_ratio: float = 0.50
    min_sold_count_30d: int = 1
    exclude_categories: list[str] = Field(default_factory=list)
    max_candidates_per_run: int = 50
    match_threshold: float = 40.0

    @field_validator("min_margin_rate", "max_shipping_ratio")
    @classmethod
    def rate_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("rate must be >= 0")
        return v

    @field_validator("match_threshold")
    @classmethod
    def normalize_match_threshold_value(cls, v: float) -> float:
        if 0 < v <= 1:
            v *= 100
        if v < 0 or v > 100:
            raise ValueError("match_threshold must be between 0 and 100")
        return v


class MujiConfig(_ConfigModel):
    enabled: bool = False


class ListingConfig(_ConfigModel):
    max_daily_listings: int = 10
    limit_warning_threshold: int = 3


# ---------------------------------------------------------------------------
# Root Settings model
# ---------------------------------------------------------------------------

class ServiceAvailability(BaseModel):
    """Service availability status after validation."""

    available: list[str] = Field(default_factory=list)
    degraded: list[str] = Field(default_factory=list)
    unavailable_required: list[str] = Field(default_factory=list)


class Settings(_ConfigModel):
    ebay: EbayConfig = Field(default_factory=EbayConfig)
    line: LineConfig = Field(default_factory=LineConfig)
    deepl: DeepLConfig = Field(default_factory=DeepLConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    amazon: AmazonConfig = Field(default_factory=AmazonConfig)
    rakuten: RakutenConfig = Field(default_factory=RakutenConfig)
    yahoo_shopping: YahooShoppingConfig = Field(default_factory=YahooShoppingConfig)
    exchange_rate: ExchangeRateConfig = Field(default_factory=ExchangeRateConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    muji: MujiConfig = Field(default_factory=MujiConfig)
    listing: ListingConfig = Field(default_factory=ListingConfig)

    @staticmethod
    def _resolve_path(path_value: str, project_root: Path) -> Path:
        path = Path(path_value)
        if path_value != ":memory:" and not path.is_absolute():
            return project_root / path
        return path

    def resolve_paths(self, project_root: Path) -> None:
        """Resolve relative paths in config against project root."""
        self.database.resolved_path = self._resolve_path(self.database.path, project_root)
        self.paths.resolved_price_model_path = self._resolve_path(
            self.paths.price_model_path,
            project_root,
        )
        self.paths.resolved_frontend_dist_path = self._resolve_path(
            self.paths.frontend_dist_path,
            project_root,
        )

    def validate_required_services(self) -> ServiceAvailability:
        """Check which services are available based on API key configuration.

        Required services (eBay): missing keys → unavailable_required
        Optional services (LINE, DeepL, Claude, Amazon, Rakuten, Yahoo): missing keys → degraded
        """
        result = ServiceAvailability()

        # Required: eBay (core business)
        if self.ebay.app_id and self.ebay.cert_id and self.ebay.user_token:
            result.available.append("ebay")
        else:
            result.unavailable_required.append("ebay")

        # Optional services: degraded mode if keys missing
        optional_checks: list[tuple[str, bool]] = [
            ("line", bool(self.line.channel_access_token)),
            ("deepl", bool(self.deepl.api_key)),
            ("claude", bool(self.claude.api_key)),
            ("amazon", bool(self.amazon.access_key and self.amazon.secret_key)),
            ("rakuten", bool(self.rakuten.app_id)),
            ("yahoo_shopping", bool(self.yahoo_shopping.app_id)),
        ]
        for name, has_keys in optional_checks:
            if has_keys:
                result.available.append(name)
            else:
                result.degraded.append(name)

        return result


# ---------------------------------------------------------------------------
# Fee rules sub-models
# ---------------------------------------------------------------------------

class EbayFeesConfig(_ConfigModel):
    default_rate: float = 0.1325
    category_rates: dict[str, float] = Field(default_factory=dict)

    @field_validator("default_rate")
    @classmethod
    def rate_must_be_valid(cls, v: float) -> float:
        if v < 0 or v > 1.0:
            raise ValueError("fee rate must be between 0 and 1")
        return v


class PayoneerConfig(_ConfigModel):
    rate: float = 0.02

    @field_validator("rate")
    @classmethod
    def rate_must_be_valid(cls, v: float) -> float:
        if v < 0 or v > 1.0:
            raise ValueError("fee rate must be between 0 and 1")
        return v


class FxBufferConfig(_ConfigModel):
    rate: float = 0.03


class PackingConfig(_ConfigModel):
    default_cost: int = 200
    small: int = 100
    medium: int = 200
    large: int = 300


class ShippingTier(_ConfigModel):
    max_weight_g: int
    cost: int


class ShippingConfig(_ConfigModel):
    zones: dict[str, list[ShippingTier]] = Field(default_factory=dict)
    destination_zones: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Root FeeRules model
# ---------------------------------------------------------------------------

class FeeRules(_ConfigModel):
    ebay_fees: EbayFeesConfig = Field(default_factory=EbayFeesConfig)
    payoneer: PayoneerConfig = Field(default_factory=PayoneerConfig)
    fx_buffer: FxBufferConfig = Field(default_factory=FxBufferConfig)
    packing: PackingConfig = Field(default_factory=PackingConfig)
    shipping: ShippingConfig = Field(default_factory=ShippingConfig)
