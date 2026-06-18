import pytest
import json
from zer0code.config import ZeroCodeConfig
from zer0code.validation import ConfigValidator, ConfigValidationError

def test_default_config():
    config = ZeroCodeConfig()
    assert config.provider == "openai"
    assert config.model == "gpt-4o"
    assert config.memory_enabled is True

def test_config_save_load(tmp_path):
    from zer0code.config import CONFIG_DIR, CONFIG_FILE
    import zer0code.config as cfg_mod
    old_dir = cfg_mod.CONFIG_DIR
    old_file = cfg_mod.CONFIG_FILE
    cfg_mod.CONFIG_DIR = tmp_path
    cfg_mod.CONFIG_FILE = tmp_path / "config.json"
    try:
        config = ZeroCodeConfig(provider="deepseek", model="deepseek-v4-pro")
        config.save()
        loaded = ZeroCodeConfig.load()
        assert loaded.provider == "deepseek"
        assert loaded.model == "deepseek-v4-pro"
    finally:
        cfg_mod.CONFIG_DIR = old_dir
        cfg_mod.CONFIG_FILE = old_file

def test_provider_config():
    config = ZeroCodeConfig(provider="deepseek")
    pc = config.get_provider_config()
    assert pc["provider"] == "deepseek"
    assert "deepseek" in pc["base_url"]

def test_validation_valid():
    errors = ConfigValidator.validate({"provider": "openai", "theme": "hacker"})
    assert errors == []

def test_validation_invalid_provider():
    errors = ConfigValidator.validate({"provider": "invalid"})
    assert len(errors) == 1
    assert "provider" in errors[0].lower()

def test_validation_invalid_theme():
    errors = ConfigValidator.validate({"theme": "neon"})
    assert len(errors) == 1

def test_sanitize():
    d = {"provider": "invalid", "theme": "bad"}
    result = ConfigValidator.sanitize(d)
    assert result["provider"] == "openai"
    assert result["theme"] == "hacker"
