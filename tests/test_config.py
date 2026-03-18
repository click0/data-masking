#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for modules/config.py — configuration loading and priority resolution.

Covers:
    - Default values
    - YAML loading
    - Environment variable overrides
    - CLI argument overrides
    - Priority chain (CLI > ENV > YAML > Default)
    - Utility functions (load_config, generate_config, is_yaml_available)
    - Router rules
    - Default config generation
"""

import importlib.util
import os
import sys
import tempfile

import pytest
from pathlib import Path

# Import modules/config.py directly to avoid triggering modules/__init__.py
# which may pull in heavy/optional dependencies unrelated to configuration.
_config_path = str(Path(__file__).resolve().parent.parent / "modules" / "config.py")
_spec = importlib.util.spec_from_file_location("modules.config", _config_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("modules.config", _mod)
_spec.loader.exec_module(_mod)

Config = _mod.Config
ConfigLoader = _mod.ConfigLoader
load_config = _mod.load_config
generate_config = _mod.generate_config
is_yaml_available = _mod.is_yaml_available


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_yaml_content():
    """Return sample YAML content with all major configuration sections."""
    return """\
system:
  hash_algorithm: "sha256"
  preserve_case: false
  debug_mode: true

security:
  encrypt_output: true
  password_env_var: "MY_CUSTOM_PASSWORD"
  password_length: 32

masking_rules:
  enable_ranks: false
  enable_names: true
  enable_ipn: true
  enable_passport: false
  enable_military_id: true
  enable_dates: false
  enable_brigades: true
  enable_units: false
  enable_orders: true
  enable_br_numbers: false

logging:
  level: "DEBUG"
  file: "/tmp/masking_test.log"
  format: "%(levelname)s - %(message)s"
"""


@pytest.fixture
def clean_env():
    """Remove all DATA_MASKING_* / DM_* environment variables for isolation.

    Restores original environment after the test completes.
    """
    prefixes = ("DATA_MASKING_", "DM_")
    saved = {}
    for key in list(os.environ.keys()):
        for prefix in prefixes:
            if key.startswith(prefix):
                saved[key] = os.environ.pop(key)
                break
    yield
    # Restore anything that was removed
    for key, value in saved.items():
        os.environ[key] = value
    # Also clean up anything the test may have added
    for key in list(os.environ.keys()):
        for prefix in prefixes:
            if key.startswith(prefix) and key not in saved:
                del os.environ[key]


# ===========================================================================
# TestDefaults
# ===========================================================================

class TestDefaults:
    """Verify that a freshly created Config has the documented defaults."""

    def test_default_config(self):
        """Config() should produce sensible defaults for every section."""
        cfg = Config()

        # System defaults
        assert cfg.system.hash_algorithm == "blake2b"
        assert cfg.system.preserve_case is True
        assert cfg.system.debug_mode is False

        # Security defaults
        assert cfg.security.encrypt_output is False
        assert cfg.security.password_env_var == "DATA_MASKING_PASSWORD"
        assert cfg.security.password_length == 24

        # Masking rules defaults — everything enabled
        assert cfg.masking_rules.enable_ranks is True
        assert cfg.masking_rules.enable_names is True
        assert cfg.masking_rules.enable_ipn is True
        assert cfg.masking_rules.enable_passport is True
        assert cfg.masking_rules.enable_military_id is True
        assert cfg.masking_rules.enable_dates is True
        assert cfg.masking_rules.enable_brigades is True
        assert cfg.masking_rules.enable_units is True
        assert cfg.masking_rules.enable_orders is True
        assert cfg.masking_rules.enable_br_numbers is True

        # Logging defaults
        assert cfg.logging.level == "INFO"
        assert cfg.logging.file is None
        assert "%(asctime)s" in cfg.logging.format

    def test_config_to_dict(self):
        """to_dict() should return a nested dict mirroring the dataclass tree."""
        cfg = Config()
        d = cfg.to_dict()

        assert isinstance(d, dict)
        assert "system" in d
        assert "security" in d
        assert "masking_rules" in d
        assert "logging" in d
        assert "router_rules" in d

        # Spot-check nested values
        assert d["system"]["hash_algorithm"] == "blake2b"
        assert d["security"]["encrypt_output"] is False
        assert d["masking_rules"]["enable_ranks"] is True
        assert d["logging"]["level"] == "INFO"

    def test_config_from_dict(self):
        """from_dict() should reconstruct a Config from a nested dictionary."""
        data = {
            "system": {
                "hash_algorithm": "md5",
                "preserve_case": False,
                "debug_mode": True,
            },
            "security": {
                "encrypt_output": True,
                "password_length": 16,
            },
            "masking_rules": {
                "enable_ranks": False,
                "enable_dates": False,
            },
            "logging": {
                "level": "WARNING",
                "file": "/var/log/masking.log",
            },
        }

        cfg = Config.from_dict(data)

        assert cfg.system.hash_algorithm == "md5"
        assert cfg.system.preserve_case is False
        assert cfg.system.debug_mode is True
        assert cfg.security.encrypt_output is True
        assert cfg.security.password_length == 16
        assert cfg.masking_rules.enable_ranks is False
        assert cfg.masking_rules.enable_dates is False
        # Fields not in `data` should keep their defaults
        assert cfg.masking_rules.enable_names is True
        assert cfg.logging.level == "WARNING"
        assert cfg.logging.file == "/var/log/masking.log"


# ===========================================================================
# TestYamlLoading
# ===========================================================================

@pytest.mark.skipif(
    not is_yaml_available(),
    reason="PyYAML is not installed",
)
class TestYamlLoading:
    """Tests that require PyYAML to be installed."""

    def test_load_yaml(self, temp_dir, sample_yaml_content, clean_env):
        """ConfigLoader should parse a YAML file and populate the Config."""
        yaml_file = temp_dir / "test_config.yaml"
        yaml_file.write_text(sample_yaml_content, encoding="utf-8")

        loader = ConfigLoader(config_path=str(yaml_file))
        cfg = loader.load()

        assert cfg.system.hash_algorithm == "sha256"
        assert cfg.system.preserve_case is False
        assert cfg.system.debug_mode is True

        assert cfg.security.encrypt_output is True
        assert cfg.security.password_env_var == "MY_CUSTOM_PASSWORD"
        assert cfg.security.password_length == 32

        assert cfg.masking_rules.enable_ranks is False
        assert cfg.masking_rules.enable_names is True
        assert cfg.masking_rules.enable_dates is False
        assert cfg.masking_rules.enable_units is False

        assert cfg.logging.level == "DEBUG"
        assert cfg.logging.file == "/tmp/masking_test.log"
        assert cfg.logging.format == "%(levelname)s - %(message)s"

    def test_generate_config(self, temp_dir):
        """generate_config() should create a valid YAML file on disk."""
        output = temp_dir / "generated.yaml"
        result_path = generate_config(str(output))

        assert Path(result_path).exists()
        assert output.stat().st_size > 0

        import yaml

        with open(output, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        assert isinstance(data, dict)
        assert "system" in data
        assert "security" in data
        assert "masking_rules" in data
        assert "logging" in data


# ===========================================================================
# TestEnvOverride
# ===========================================================================

class TestEnvOverride:
    """Environment variables should override YAML and default values."""

    def test_env_override(self, clean_env):
        """DATA_MASKING_* env vars should override the corresponding settings."""
        os.environ["DATA_MASKING_HASH_ALGORITHM"] = "sha512"
        os.environ["DATA_MASKING_LOG_LEVEL"] = "ERROR"

        loader = ConfigLoader()
        cfg = loader.load()

        assert cfg.system.hash_algorithm == "sha512"
        assert cfg.logging.level == "ERROR"

    def test_env_bool_parsing(self, clean_env):
        """Boolean env vars should accept '1', 'true', 'yes', 'on' as True."""
        # "true" -> True
        os.environ["DATA_MASKING_DEBUG"] = "true"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is True

        # "1" -> True
        os.environ["DATA_MASKING_DEBUG"] = "1"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is True

        # "yes" -> True
        os.environ["DATA_MASKING_DEBUG"] = "yes"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is True

        # "on" -> True
        os.environ["DATA_MASKING_DEBUG"] = "on"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is True

        # "0" -> False
        os.environ["DATA_MASKING_DEBUG"] = "0"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is False

        # "false" -> False
        os.environ["DATA_MASKING_DEBUG"] = "false"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is False

        # "no" -> False
        os.environ["DATA_MASKING_DEBUG"] = "no"
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.debug_mode is False


# ===========================================================================
# TestCliOverride
# ===========================================================================

class TestCliOverride:
    """CLI arguments should override everything else."""

    def test_cli_override(self, clean_env):
        """Dotted and plain CLI keys should set the right config attributes."""
        cli_args = {
            "masking_rules.enable_ranks": False,
            "masking_rules.enable_dates": False,
            "logging.level": "CRITICAL",
            "security.encrypt_output": True,
        }
        loader = ConfigLoader(cli_args=cli_args)
        cfg = loader.load()

        assert cfg.masking_rules.enable_ranks is False
        assert cfg.masking_rules.enable_dates is False
        assert cfg.logging.level == "CRITICAL"
        assert cfg.security.encrypt_output is True

        # Fields not specified should retain defaults
        assert cfg.masking_rules.enable_names is True
        assert cfg.system.hash_algorithm == "blake2b"


# ===========================================================================
# TestPriority
# ===========================================================================

class TestPriority:
    """Verify the priority chain: CLI > ENV > YAML > Default."""

    def test_priority_cli_over_env(self, clean_env):
        """CLI should beat ENV for the same setting."""
        os.environ["DATA_MASKING_HASH_ALGORITHM"] = "sha256"

        cli_args = {"system.hash_algorithm": "md5"}
        loader = ConfigLoader(cli_args=cli_args)
        cfg = loader.load()

        assert cfg.system.hash_algorithm == "md5"

    @pytest.mark.skipif(
        not is_yaml_available(),
        reason="PyYAML is not installed",
    )
    def test_priority_env_over_yaml(self, temp_dir, sample_yaml_content, clean_env):
        """ENV should beat YAML for the same setting."""
        yaml_file = temp_dir / "prio.yaml"
        yaml_file.write_text(sample_yaml_content, encoding="utf-8")

        # YAML sets hash_algorithm to "sha256"
        os.environ["DATA_MASKING_HASH_ALGORITHM"] = "sha512"

        loader = ConfigLoader(config_path=str(yaml_file))
        cfg = loader.load()

        assert cfg.system.hash_algorithm == "sha512"

    @pytest.mark.skipif(
        not is_yaml_available(),
        reason="PyYAML is not installed",
    )
    def test_priority_yaml_over_default(self, temp_dir, sample_yaml_content, clean_env):
        """YAML should beat default values."""
        yaml_file = temp_dir / "prio.yaml"
        yaml_file.write_text(sample_yaml_content, encoding="utf-8")

        loader = ConfigLoader(config_path=str(yaml_file))
        cfg = loader.load()

        # Default is "blake2b"; YAML sets "sha256"
        assert cfg.system.hash_algorithm == "sha256"
        # Default is True; YAML sets False
        assert cfg.masking_rules.enable_ranks is False

    @pytest.mark.skipif(
        not is_yaml_available(),
        reason="PyYAML is not installed",
    )
    def test_full_priority_chain(self, temp_dir, sample_yaml_content, clean_env):
        """All layers combined: CLI wins, then ENV, then YAML, then default."""
        yaml_file = temp_dir / "full_prio.yaml"
        yaml_file.write_text(sample_yaml_content, encoding="utf-8")

        # YAML: hash_algorithm = sha256, level = DEBUG
        # ENV:  hash_algorithm = sha512, level = ERROR
        os.environ["DATA_MASKING_HASH_ALGORITHM"] = "sha512"
        os.environ["DATA_MASKING_LOG_LEVEL"] = "ERROR"

        # CLI:  hash_algorithm = md5
        cli_args = {"system.hash_algorithm": "md5"}

        loader = ConfigLoader(config_path=str(yaml_file), cli_args=cli_args)
        cfg = loader.load()

        # CLI wins for hash_algorithm
        assert cfg.system.hash_algorithm == "md5"
        # ENV wins for log level (no CLI override)
        assert cfg.logging.level == "ERROR"
        # YAML wins for masking_rules.enable_ranks (no ENV or CLI override)
        assert cfg.masking_rules.enable_ranks is False
        # Default wins for password_length (no YAML/ENV/CLI override for security)
        # (YAML sets it to 32 though, so this checks YAML value)
        assert cfg.security.password_length == 32


# ===========================================================================
# TestUtilities
# ===========================================================================

class TestUtilities:
    """Tests for the convenience functions in the config module."""

    def test_load_config_function(self, clean_env):
        """load_config() should return a valid Config with defaults."""
        cfg = load_config()

        assert isinstance(cfg, Config)
        assert cfg.system.hash_algorithm == "blake2b"
        assert cfg.logging.level == "INFO"

    def test_generate_config_function(self, temp_dir):
        """generate_config() should create a file and return its path."""
        output = temp_dir / "gen_test.yaml"
        result = generate_config(str(output))

        assert os.path.isfile(result)
        content = Path(result).read_text(encoding="utf-8")
        assert "system:" in content
        assert "hash_algorithm" in content

    def test_is_yaml_available(self):
        """is_yaml_available() should return a boolean."""
        result = is_yaml_available()
        assert isinstance(result, bool)
        # In our test environment PyYAML is expected to be installed
        try:
            import yaml  # noqa: F401
            assert result is True
        except ImportError:
            assert result is False


# ===========================================================================
# TestRouterRules
# ===========================================================================

class TestRouterRules:
    """Tests for the router_rules configuration section."""

    def test_default_router_rules(self):
        """Default router rules should use 'mask' as the default action."""
        cfg = Config()
        assert cfg.router_rules.default_action == "mask"

    def test_custom_router_rules(self):
        """from_dict() should accept custom router_rules values."""
        data = {
            "router_rules": {
                "default_action": "skip",
            },
        }
        cfg = Config.from_dict(data)
        assert cfg.router_rules.default_action == "skip"


# ===========================================================================
# TestInitConfig — generate_default_config tests
# ===========================================================================

class TestInitConfig:
    """Tests for ConfigLoader.generate_default_config() and the generated file."""

    def test_generate_default_config_creates_file(self, temp_dir):
        """generate_default_config() should create a file at the given path."""
        output = temp_dir / "init_config.yaml"
        result_path = ConfigLoader.generate_default_config(str(output))

        assert Path(result_path).exists()
        assert Path(result_path).is_file()

    def test_generate_default_config_content(self, temp_dir):
        """Generated config file should contain all expected sections."""
        output = temp_dir / "init_config.yaml"
        ConfigLoader.generate_default_config(str(output))

        content = output.read_text(encoding="utf-8")

        # All section headers should be present
        assert "system:" in content
        assert "security:" in content
        assert "masking_rules:" in content
        assert "logging:" in content
        assert "router_rules:" in content
        assert "password_generation:" in content
        assert "validation:" in content

        # Key fields should be present
        assert "hash_algorithm" in content
        assert "encrypt_output" in content
        assert "enable_ranks" in content
        assert "level:" in content

    @pytest.mark.skipif(
        not is_yaml_available(),
        reason="PyYAML is not installed",
    )
    def test_generate_default_config_is_valid_yaml(self, temp_dir):
        """Generated config should be parseable as valid YAML."""
        import yaml

        output = temp_dir / "init_config.yaml"
        ConfigLoader.generate_default_config(str(output))

        with open(output, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        assert isinstance(data, dict)
        assert data["system"]["hash_algorithm"] == "blake2b"
        assert data["security"]["encrypt_output"] is False
        assert data["masking_rules"]["enable_ranks"] is True
        assert data["logging"]["level"] == "INFO"

    @pytest.mark.skipif(
        not is_yaml_available(),
        reason="PyYAML is not installed",
    )
    def test_generate_default_config_loadable(self, temp_dir, clean_env):
        """Generated config should be loadable via ConfigLoader."""
        output = temp_dir / "init_config.yaml"
        ConfigLoader.generate_default_config(str(output))

        loader = ConfigLoader(config_path=str(output))
        cfg = loader.load()

        assert isinstance(cfg, Config)
        assert cfg.system.hash_algorithm == "blake2b"
        assert cfg.system.preserve_case is True
        assert cfg.security.encrypt_output is False
        assert cfg.masking_rules.enable_ranks is True
        assert cfg.logging.level == "INFO"

    def test_generate_default_config_password_generation(self, temp_dir):
        """Generated config should include password generation settings."""
        output = temp_dir / "init_config.yaml"
        ConfigLoader.generate_default_config(str(output))

        content = output.read_text(encoding="utf-8")

        assert "password_generation:" in content
        assert "enabled:" in content
        assert "length:" in content
        assert "use_special_chars:" in content
        assert "env_var:" in content
