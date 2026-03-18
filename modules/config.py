#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Module v2.3.0 for data_masking.py

Provides YAML + ENV + CLI configuration loading with priority resolution:
    CLI > ENV > config.yaml > config.py > Default

Supports dataclass-based structured configuration with automatic
type coercion and validation.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

__version__ = "2.3.0"

import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from pathlib import Path

# ---------------------------------------------------------------------------
# YAML availability check
# ---------------------------------------------------------------------------
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)


# ===========================================================================
# Dataclass definitions
# ===========================================================================

@dataclass
class SystemConfig:
    """System-level configuration."""
    hash_algorithm: str = "blake2b"
    preserve_case: bool = True
    debug_mode: bool = False


@dataclass
class PasswordGenerationConfig:
    """Password generation settings."""
    enabled: bool = True
    length: int = 24
    use_special_chars: bool = True
    env_var: str = "DATA_MASKING_PASSWORD"


@dataclass
class SecurityConfig:
    """Security configuration."""
    encrypt_output: bool = False
    password_generation: PasswordGenerationConfig = field(
        default_factory=PasswordGenerationConfig
    )
    password_env_var: str = "DATA_MASKING_PASSWORD"
    password_length: int = 24


@dataclass
class MaskingRulesConfig:
    """Masking rules configuration."""
    enable_ranks: bool = True
    enable_names: bool = True
    enable_ipn: bool = True
    enable_passport: bool = True
    enable_military_id: bool = True
    enable_dates: bool = True
    enable_brigades: bool = True
    enable_units: bool = True
    enable_orders: bool = True
    enable_br_numbers: bool = True


@dataclass
class ValidationConfig:
    """Input validation configuration."""
    strict_mode: bool = False
    max_input_size_mb: int = 100
    allowed_encodings: List[str] = field(
        default_factory=lambda: ["utf-8", "cp1251", "latin-1"]
    )


@dataclass
class RouterRulesConfig:
    """Router rules for selective masking."""
    default_action: str = "mask"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class Config:
    """Top-level application configuration.

    Aggregates all sub-configurations into a single root object.
    Supports serialisation to/from plain dicts for YAML/JSON interchange.
    """
    system: SystemConfig = field(default_factory=SystemConfig)
    password_generation: PasswordGenerationConfig = field(
        default_factory=PasswordGenerationConfig
    )
    security: SecurityConfig = field(default_factory=SecurityConfig)
    masking_rules: MaskingRulesConfig = field(default_factory=MaskingRulesConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    router_rules: RouterRulesConfig = field(default_factory=RouterRulesConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # ----- serialisation helpers -----

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create a Config instance from a nested dictionary.

        Unknown keys are silently ignored so that forward-compatible YAML
        files do not cause errors on older code.
        """
        cfg = cls()

        if "system" in data and isinstance(data["system"], dict):
            for k, v in data["system"].items():
                if hasattr(cfg.system, k):
                    setattr(cfg.system, k, v)

        if "password_generation" in data and isinstance(data["password_generation"], dict):
            for k, v in data["password_generation"].items():
                if hasattr(cfg.password_generation, k):
                    setattr(cfg.password_generation, k, v)

        if "security" in data and isinstance(data["security"], dict):
            sec = data["security"]
            for k, v in sec.items():
                if k == "password_generation" and isinstance(v, dict):
                    for pk, pv in v.items():
                        if hasattr(cfg.security.password_generation, pk):
                            setattr(cfg.security.password_generation, pk, pv)
                elif hasattr(cfg.security, k):
                    setattr(cfg.security, k, v)

        if "masking_rules" in data and isinstance(data["masking_rules"], dict):
            for k, v in data["masking_rules"].items():
                if hasattr(cfg.masking_rules, k):
                    setattr(cfg.masking_rules, k, v)

        if "validation" in data and isinstance(data["validation"], dict):
            for k, v in data["validation"].items():
                if hasattr(cfg.validation, k):
                    setattr(cfg.validation, k, v)

        if "router_rules" in data and isinstance(data["router_rules"], dict):
            for k, v in data["router_rules"].items():
                if hasattr(cfg.router_rules, k):
                    setattr(cfg.router_rules, k, v)

        if "logging" in data and isinstance(data["logging"], dict):
            for k, v in data["logging"].items():
                if hasattr(cfg.logging, k):
                    setattr(cfg.logging, k, v)

        return cfg

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the full configuration tree to a plain dictionary."""
        return asdict(self)


# ===========================================================================
# ConfigLoader — priority-based configuration resolver
# ===========================================================================

class ConfigLoader:
    """Load configuration with the following priority (highest wins):

        1. CLI arguments   (--hash-algorithm, --debug, etc.)
        2. ENV variables   (DATA_MASKING_HASH_ALGORITHM, etc.)
        3. config.yaml     (YAML file)
        4. config.py       (Python config module)
        5. Defaults        (dataclass defaults)
    """

    # Mapping: ENV variable name -> (config section, attribute name, type)
    ENV_MAPPING: Dict[str, tuple] = {
        "DATA_MASKING_HASH_ALGORITHM": ("system", "hash_algorithm", str),
        "DATA_MASKING_PRESERVE_CASE": ("system", "preserve_case", bool),
        "DATA_MASKING_DEBUG": ("system", "debug_mode", bool),
        "DATA_MASKING_ENCRYPT_OUTPUT": ("security", "encrypt_output", bool),
        "DATA_MASKING_PASSWORD": ("security", "password_env_var", str),
        "DATA_MASKING_PASSWORD_LENGTH": ("security", "password_length", int),
        "DATA_MASKING_LOG_LEVEL": ("logging", "level", str),
        "DATA_MASKING_LOG_FILE": ("logging", "file", str),
        "DATA_MASKING_STRICT_VALIDATION": ("validation", "strict_mode", bool),
        "DATA_MASKING_MAX_INPUT_SIZE_MB": ("validation", "max_input_size_mb", int),
        "DATA_MASKING_DEFAULT_ACTION": ("router_rules", "default_action", str),
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        cli_args: Optional[Dict[str, Any]] = None,
    ):
        self._config = Config()
        self._config_path = config_path
        self._cli_args = cli_args or {}

    @property
    def config(self) -> Config:
        """Return the resolved configuration object."""
        return self._config

    # ----- YAML loading -----

    def _load_yaml(self, path: str) -> Optional[Dict[str, Any]]:
        """Load configuration from a YAML file.

        Returns the parsed dictionary or ``None`` when the file does not
        exist or ``pyyaml`` is not installed.
        """
        if not YAML_AVAILABLE:
            logger.debug("PyYAML not installed — skipping YAML config")
            return None

        filepath = Path(path)
        if not filepath.exists():
            logger.debug("Config file not found: %s", filepath)
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)  # type: ignore[union-attr]
            if not isinstance(data, dict):
                logger.warning("YAML config is not a mapping — ignored")
                return None
            logger.info("Loaded YAML config from %s", filepath)
            return data
        except Exception as exc:
            logger.error("Failed to load YAML config: %s", exc)
            return None

    # ----- Python config module loading -----

    def _load_python_config(self) -> Optional[Dict[str, Any]]:
        """Attempt to import a ``config`` Python module and extract settings.

        The module is expected to expose an ``AppConfig`` or ``Config``
        instance named ``cfg`` or ``config``, or to provide a dictionary
        named ``CONFIG``.
        """
        try:
            import importlib
            mod = importlib.import_module("config")
        except ImportError:
            logger.debug("No config Python module found")
            return None

        # Try known attribute names
        for attr_name in ("CONFIG", "config", "cfg"):
            obj = getattr(mod, attr_name, None)
            if isinstance(obj, dict):
                logger.info("Loaded Python config dict '%s'", attr_name)
                return obj

        # If the module defines an AppConfig/Config dataclass instance,
        # convert it to a dict via dataclasses.asdict.
        for attr_name in ("config", "cfg"):
            obj = getattr(mod, attr_name, None)
            if obj is not None and hasattr(obj, "__dataclass_fields__"):
                logger.info("Loaded Python config dataclass '%s'", attr_name)
                return asdict(obj)

        logger.debug("config module found but no usable config object")
        return None

    # ----- ENV variable overlay -----

    def _apply_env(self) -> None:
        """Apply environment variable overrides to the current config."""
        for env_var, (section, attr, typ) in self.ENV_MAPPING.items():
            raw = os.environ.get(env_var)
            if raw is None:
                continue

            value: Any
            if typ is bool:
                value = raw.lower() in ("1", "true", "yes", "on")
            elif typ is int:
                try:
                    value = int(raw)
                except ValueError:
                    logger.warning(
                        "Invalid int for %s=%r — skipped", env_var, raw
                    )
                    continue
            else:
                value = raw

            section_obj = getattr(self._config, section, None)
            if section_obj is not None and hasattr(section_obj, attr):
                setattr(section_obj, attr, value)
                logger.debug("ENV override: %s.%s = %r", section, attr, value)

    # ----- CLI argument overlay -----

    def _apply_cli(self) -> None:
        """Apply CLI argument overrides (highest priority).

        ``cli_args`` is expected to be a flat dictionary whose keys use
        the dotted notation ``section.attribute`` (e.g.
        ``system.hash_algorithm``) **or** a plain attribute name that is
        matched against all sections.
        """
        if not self._cli_args:
            return

        for key, value in self._cli_args.items():
            if value is None:
                continue

            if "." in key:
                section_name, attr = key.split(".", 1)
                section_obj = getattr(self._config, section_name, None)
                if section_obj is not None and hasattr(section_obj, attr):
                    setattr(section_obj, attr, value)
                    logger.debug(
                        "CLI override: %s.%s = %r", section_name, attr, value
                    )
            else:
                # Try to find the attribute in any section
                for section_name in (
                    "system",
                    "security",
                    "masking_rules",
                    "validation",
                    "router_rules",
                    "logging",
                    "password_generation",
                ):
                    section_obj = getattr(self._config, section_name, None)
                    if section_obj is not None and hasattr(section_obj, key):
                        setattr(section_obj, key, value)
                        logger.debug(
                            "CLI override: %s.%s = %r",
                            section_name,
                            key,
                            value,
                        )
                        break

    # ----- Main load method -----

    def load(self) -> Config:
        """Load configuration using priority chain.

        Priority (highest wins):
            1. CLI arguments
            2. ENV variables
            3. config.yaml
            4. config.py (Python module)
            5. Dataclass defaults
        """
        # Step 5: defaults are already set via dataclass __init__

        # Step 4: Python config module
        py_data = self._load_python_config()
        if py_data:
            self._config = Config.from_dict(py_data)

        # Step 3: YAML config file
        yaml_path = self._config_path or "config.yaml"
        yaml_data = self._load_yaml(yaml_path)
        if yaml_data:
            self._config = Config.from_dict(yaml_data)

        # Step 2: ENV variable overrides
        self._apply_env()

        # Step 1: CLI argument overrides
        self._apply_cli()

        return self._config

    # ----- Default config generation -----

    @staticmethod
    def generate_default_config(output_path: str = "config.yaml") -> str:
        """Generate a default YAML configuration file with comments.

        Returns the path to the generated file.
        """
        template = """\
# ==========================================================================
# Data Masking Configuration v{version}
#
# Auto-generated default configuration.
# Adjust values as needed for your environment.
#
# Priority: CLI > ENV > config.yaml > config.py > Default
#
# Author: Vladyslav V. Prodan
# Contact: github.com/click0
# License: BSD 3-Clause
# Year: 2025
# ==========================================================================

# --------------------------------------------------------------------------
# System settings
# --------------------------------------------------------------------------
system:
  # Hash algorithm for deterministic seed generation.
  # Options: blake2b (recommended), md5, sha1, sha256, sha512
  hash_algorithm: "blake2b"

  # Preserve letter case of masked values
  preserve_case: true

  # Enable debug output (verbose logging)
  debug_mode: false

# --------------------------------------------------------------------------
# Password generation settings
# --------------------------------------------------------------------------
password_generation:
  # Enable automatic password generation
  enabled: true

  # Length of generated password (characters)
  length: 24

  # Include special characters in generated passwords
  use_special_chars: true

  # Environment variable to read password from
  env_var: "DATA_MASKING_PASSWORD"

# --------------------------------------------------------------------------
# Security settings
# --------------------------------------------------------------------------
security:
  # Encrypt the mapping file (AES-128-CBC via Fernet)
  encrypt_output: false

  # Environment variable for password (alternative to --password)
  password_env_var: "DATA_MASKING_PASSWORD"

  # Length of auto-generated password (characters)
  password_length: 24

# --------------------------------------------------------------------------
# Masking rules — enable/disable individual data types
# --------------------------------------------------------------------------
masking_rules:
  # Military ranks (with declension and case preservation)
  enable_ranks: true

  # Personal names: first name, surname, patronymic
  enable_names: true

  # Individual Tax Number / IPN (10 digits)
  enable_ipn: true

  # Passport and ID-passport (9 digits)
  enable_passport: true

  # Military ID (e.g. AA123456)
  enable_military_id: true

  # Dates in DD.MM.YYYY format (offset +/-30 days)
  enable_dates: true

  # Brigade numbers
  enable_brigades: true

  # Military unit designations (e.g. A1234)
  enable_units: true

  # Order numbers (e.g. No.123, No.45/67)
  enable_orders: true

  # BR document numbers (e.g. No.BR-123/456)
  enable_br_numbers: true

# --------------------------------------------------------------------------
# Validation settings
# --------------------------------------------------------------------------
validation:
  # Strict mode: reject input that fails validation
  strict_mode: false

  # Maximum input file size in megabytes
  max_input_size_mb: 100

  # Allowed input file encodings
  allowed_encodings:
    - "utf-8"
    - "cp1251"
    - "latin-1"

# --------------------------------------------------------------------------
# Router rules (selective masking)
# --------------------------------------------------------------------------
router_rules:
  # Default action for unmatched patterns: mask | skip | warn
  default_action: "mask"

# --------------------------------------------------------------------------
# Logging settings
# --------------------------------------------------------------------------
logging:
  # Log level: DEBUG | INFO | WARNING | ERROR | CRITICAL
  level: "INFO"

  # Log file path. null = console output only.
  file: null

  # Log message format (Python logging format string)
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
""".format(version=__version__)

        output = Path(output_path)
        output.write_text(template, encoding="utf-8")
        logger.info("Generated default config: %s", output)
        return str(output.resolve())


# ===========================================================================
# Convenience functions
# ===========================================================================

def load_config(
    config_path: Optional[str] = None,
    cli_args: Optional[Dict[str, Any]] = None,
) -> Config:
    """Load and return the resolved application configuration.

    This is the primary entry point for other modules::

        from modules.config import load_config
        cfg = load_config("config.yaml")
        print(cfg.system.hash_algorithm)
    """
    loader = ConfigLoader(config_path=config_path, cli_args=cli_args)
    return loader.load()


def generate_config(output_path: str = "config.yaml") -> str:
    """Generate a default YAML configuration file.

    Returns the absolute path of the generated file.
    """
    return ConfigLoader.generate_default_config(output_path)


def is_yaml_available() -> bool:
    """Return True if PyYAML is installed and importable."""
    return YAML_AVAILABLE
