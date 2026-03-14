"""Tests for typed configuration schema and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from ec_hub.config import get_frontend_dist_path, get_price_model_path, load_fee_rules, load_settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_SETTINGS_YAML = textwrap.dedent("""\
    ebay:
      app_id: "test-app"
      cert_id: "test-cert"
      dev_id: "test-dev"
      user_token: "test-token"
    line:
      channel_access_token: "test-line-token"
      user_id: "U1234"
    deepl:
      api_key: "test-deepl-key"
    claude:
      api_key: "test-claude-key"
    amazon:
      access_key: "test-access"
      secret_key: "test-secret"
      partner_tag: "tag-20"
    rakuten:
      app_id: "test-rakuten"
    database:
      path: "db/test.db"
""")

MINIMAL_FEE_RULES_YAML = textwrap.dedent("""\
    ebay_fees:
      default_rate: 0.1325
    payoneer:
      rate: 0.02
    fx_buffer:
      rate: 0.03
    packing:
      default_cost: 200
      small: 100
      medium: 200
      large: 300
    shipping:
      zones:
        US:
          - { max_weight_g: 500, cost: 1500 }
        OTHER:
          - { max_weight_g: 500, cost: 2000 }
      destination_zones:
        US: "US"
""")


@pytest.fixture()
def settings_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "settings.yaml"
    p.write_text(MINIMAL_SETTINGS_YAML, encoding="utf-8")
    return p


@pytest.fixture()
def fee_rules_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "fee_rules.yaml"
    p.write_text(MINIMAL_FEE_RULES_YAML, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Settings schema tests
# ---------------------------------------------------------------------------

class TestLoadSettingsReturnsTypedModel:
    """load_settings should return a typed Settings model, not a raw dict."""

    def test_returns_settings_model(self, settings_yaml: Path):
        from ec_hub.config_schema import Settings

        result = load_settings(settings_yaml)
        assert isinstance(result, Settings)

    def test_ebay_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.ebay.app_id == "test-app"
        assert s.ebay.cert_id == "test-cert"
        assert s.ebay.dev_id == "test-dev"
        assert s.ebay.user_token == "test-token"
        assert s.ebay.sandbox is True  # default

    def test_line_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.line.channel_access_token == "test-line-token"
        assert s.line.user_id == "U1234"

    def test_deepl_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.deepl.api_key == "test-deepl-key"

    def test_claude_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.claude.api_key == "test-claude-key"
        assert s.claude.model == "claude-haiku-4-5-20251001"  # default

    def test_amazon_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.amazon.access_key == "test-access"
        assert s.amazon.secret_key == "test-secret"
        assert s.amazon.partner_tag == "tag-20"
        assert s.amazon.country == "www.amazon.co.jp"  # default

    def test_rakuten_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.rakuten.app_id == "test-rakuten"

    def test_database_config_attributes(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.database.path == "db/test.db"

    def test_optional_sections_have_defaults(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        # These sections are not in the minimal YAML, should use defaults
        assert s.research.min_margin_rate == 0.30
        assert s.research.max_candidates_per_run == 50
        assert s.listing.max_daily_listings == 10
        assert s.exchange_rate.fallback_rate == 150.0

    def test_yahoo_shopping_defaults_to_empty(self, settings_yaml: Path):
        s = load_settings(settings_yaml)
        assert s.yahoo_shopping.app_id == ""


class TestLoadSettingsValidation:
    """load_settings should validate and fail fast on invalid config."""

    def test_invalid_ebay_site_rejected(self, tmp_path: Path):
        data = yaml.safe_load(MINIMAL_SETTINGS_YAML)
        data["ebay"]["site"] = "INVALID_SITE"
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        with pytest.raises(Exception):  # ValidationError
            load_settings(p)

    def test_negative_margin_rate_rejected(self, tmp_path: Path):
        data = yaml.safe_load(MINIMAL_SETTINGS_YAML)
        data["research"] = {"min_margin_rate": -0.5}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        with pytest.raises(Exception):
            load_settings(p)

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_settings(tmp_path / "nonexistent.yaml")


class TestEnvironmentVariableOverride:
    """Environment variables should override YAML values."""

    def test_env_overrides_ebay_app_id(self, settings_yaml: Path, monkeypatch):
        monkeypatch.setenv("EC_HUB_EBAY__APP_ID", "env-app-id")
        s = load_settings(settings_yaml)
        assert s.ebay.app_id == "env-app-id"

    def test_env_overrides_deepl_api_key(self, settings_yaml: Path, monkeypatch):
        monkeypatch.setenv("EC_HUB_DEEPL__API_KEY", "env-deepl-key")
        s = load_settings(settings_yaml)
        assert s.deepl.api_key == "env-deepl-key"

    def test_env_overrides_nested_scheduler_cron(self, settings_yaml: Path, monkeypatch):
        monkeypatch.setenv("EC_HUB_SCHEDULER__RESEARCHER__CRON", "*/10 * * * *")
        s = load_settings(settings_yaml)
        assert s.scheduler.researcher.cron == "*/10 * * * *"


# ---------------------------------------------------------------------------
# Fee rules schema tests
# ---------------------------------------------------------------------------

class TestLoadFeeRulesReturnsTypedModel:
    """load_fee_rules should return a typed FeeRules model."""

    def test_returns_fee_rules_model(self, fee_rules_yaml: Path):
        from ec_hub.config_schema import FeeRules

        result = load_fee_rules(fee_rules_yaml)
        assert isinstance(result, FeeRules)

    def test_ebay_fees_default_rate(self, fee_rules_yaml: Path):
        r = load_fee_rules(fee_rules_yaml)
        assert r.ebay_fees.default_rate == 0.1325

    def test_payoneer_rate(self, fee_rules_yaml: Path):
        r = load_fee_rules(fee_rules_yaml)
        assert r.payoneer.rate == 0.02

    def test_packing_costs(self, fee_rules_yaml: Path):
        r = load_fee_rules(fee_rules_yaml)
        assert r.packing.default_cost == 200
        assert r.packing.small == 100
        assert r.packing.medium == 200
        assert r.packing.large == 300

    def test_shipping_zones(self, fee_rules_yaml: Path):
        r = load_fee_rules(fee_rules_yaml)
        assert len(r.shipping.zones["US"]) == 1
        assert r.shipping.zones["US"][0].max_weight_g == 500
        assert r.shipping.zones["US"][0].cost == 1500

    def test_destination_zone_mapping(self, fee_rules_yaml: Path):
        r = load_fee_rules(fee_rules_yaml)
        assert r.shipping.destination_zones["US"] == "US"


class TestFeeRulesValidation:
    """Fee rules should reject invalid values."""

    def test_negative_fee_rate_rejected(self, tmp_path: Path):
        data = yaml.safe_load(MINIMAL_FEE_RULES_YAML)
        data["ebay_fees"]["default_rate"] = -0.1
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        with pytest.raises(Exception):
            load_fee_rules(p)

    def test_fee_rate_over_one_rejected(self, tmp_path: Path):
        data = yaml.safe_load(MINIMAL_FEE_RULES_YAML)
        data["ebay_fees"]["default_rate"] = 1.5
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(data), encoding="utf-8")

        with pytest.raises(Exception):
            load_fee_rules(p)


# ---------------------------------------------------------------------------
# settings.local.yaml overlay tests
# ---------------------------------------------------------------------------

class TestSettingsLocalOverlay:
    """settings.local.yaml should override settings.yaml values."""

    def test_local_overrides_base_value(self, tmp_path: Path):
        base = tmp_path / "settings.yaml"
        base.write_text(MINIMAL_SETTINGS_YAML, encoding="utf-8")
        local = tmp_path / "settings.local.yaml"
        local.write_text("ebay:\n  app_id: local-app-id\n", encoding="utf-8")

        s = load_settings(base)
        assert s.ebay.app_id == "local-app-id"
        # Non-overridden values preserved
        assert s.ebay.cert_id == "test-cert"

    def test_local_adds_new_section(self, tmp_path: Path):
        base = tmp_path / "settings.yaml"
        base.write_text(MINIMAL_SETTINGS_YAML, encoding="utf-8")
        local = tmp_path / "settings.local.yaml"
        local.write_text("yahoo_shopping:\n  app_id: local-yahoo\n", encoding="utf-8")

        s = load_settings(base)
        assert s.yahoo_shopping.app_id == "local-yahoo"

    def test_local_does_not_exist_is_fine(self, settings_yaml: Path):
        # No settings.local.yaml in tmp_path — should not raise
        s = load_settings(settings_yaml)
        assert s.ebay.app_id == "test-app"

    def test_env_overrides_local(self, tmp_path: Path, monkeypatch):
        base = tmp_path / "settings.yaml"
        base.write_text(MINIMAL_SETTINGS_YAML, encoding="utf-8")
        local = tmp_path / "settings.local.yaml"
        local.write_text("ebay:\n  app_id: local-app-id\n", encoding="utf-8")
        monkeypatch.setenv("EC_HUB_EBAY__APP_ID", "env-app-id")

        s = load_settings(base)
        assert s.ebay.app_id == "env-app-id"

    def test_deep_merge_preserves_nested_keys(self, tmp_path: Path):
        base = tmp_path / "settings.yaml"
        base.write_text(MINIMAL_SETTINGS_YAML, encoding="utf-8")
        local = tmp_path / "settings.local.yaml"
        local.write_text("amazon:\n  partner_tag: local-tag\n", encoding="utf-8")

        s = load_settings(base)
        # Overridden
        assert s.amazon.partner_tag == "local-tag"
        # Preserved from base
        assert s.amazon.access_key == "test-access"
        assert s.amazon.secret_key == "test-secret"


# ---------------------------------------------------------------------------
# Path resolution tests
# ---------------------------------------------------------------------------

class TestPathResolution:
    """Settings.resolve_paths should resolve relative paths against project root."""

    def test_resolves_relative_db_path(self):
        from ec_hub.config_schema import Settings

        s = Settings.model_validate(yaml.safe_load(MINIMAL_SETTINGS_YAML))
        project_root = Path("/fake/project")
        s.resolve_paths(project_root)
        assert s.database.resolved_path == Path("/fake/project/db/test.db")

    def test_preserves_absolute_db_path(self):
        from ec_hub.config_schema import Settings

        data = yaml.safe_load(MINIMAL_SETTINGS_YAML)
        data["database"]["path"] = "/absolute/path/db.sqlite"
        s = Settings.model_validate(data)
        s.resolve_paths(Path("/fake/project"))
        assert s.database.resolved_path == Path("/absolute/path/db.sqlite")

    def test_preserves_memory_db(self):
        from ec_hub.config_schema import Settings

        data = yaml.safe_load(MINIMAL_SETTINGS_YAML)
        data["database"]["path"] = ":memory:"
        s = Settings.model_validate(data)
        s.resolve_paths(Path("/fake/project"))
        assert s.database.resolved_path == Path(":memory:")

    def test_resolves_managed_model_and_frontend_paths(self):
        from ec_hub.config_schema import Settings

        s = Settings.model_validate(yaml.safe_load(MINIMAL_SETTINGS_YAML))
        s.resolve_paths(Path("/fake/project"))
        assert s.paths.resolved_price_model_path == Path("/fake/project/models/price_model.pkl")
        assert s.paths.resolved_frontend_dist_path == Path("/fake/project/frontend/dist")

    def test_helpers_use_configured_paths(self):
        project_root = Path(__file__).resolve().parent.parent
        settings = {
            "paths": {
                "price_model_path": "var/models/custom.pkl",
                "frontend_dist_path": "var/frontend-build",
            },
        }
        assert get_price_model_path(settings) == project_root / "var/models/custom.pkl"
        assert get_frontend_dist_path(settings) == project_root / "var/frontend-build"


# ---------------------------------------------------------------------------
# Service availability validation tests
# ---------------------------------------------------------------------------

class TestServiceAvailability:
    """Settings.validate_required_services should classify services correctly."""

    def test_all_keys_present(self):
        from ec_hub.config_schema import Settings

        s = Settings.model_validate(yaml.safe_load(MINIMAL_SETTINGS_YAML))
        result = s.validate_required_services()
        assert "ebay" in result.available
        assert "amazon" in result.available
        assert "rakuten" in result.available
        assert "deepl" in result.available
        assert "claude" in result.available
        assert "line" in result.available
        assert result.unavailable_required == []

    def test_missing_ebay_keys_is_required_failure(self):
        from ec_hub.config_schema import Settings

        data = yaml.safe_load(MINIMAL_SETTINGS_YAML)
        data["ebay"]["app_id"] = ""
        s = Settings.model_validate(data)
        result = s.validate_required_services()
        assert "ebay" in result.unavailable_required

    def test_missing_optional_keys_is_degraded(self):
        from ec_hub.config_schema import Settings

        data = yaml.safe_load(MINIMAL_SETTINGS_YAML)
        data["deepl"]["api_key"] = ""
        data["claude"]["api_key"] = ""
        s = Settings.model_validate(data)
        result = s.validate_required_services()
        assert "deepl" in result.degraded
        assert "claude" in result.degraded
        assert "ebay" in result.available

    def test_yahoo_shopping_empty_by_default_is_degraded(self):
        from ec_hub.config_schema import Settings

        s = Settings.model_validate(yaml.safe_load(MINIMAL_SETTINGS_YAML))
        result = s.validate_required_services()
        assert "yahoo_shopping" in result.degraded
