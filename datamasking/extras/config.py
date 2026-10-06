#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Module v2.6.0 for data_masking.py

Provides YAML + ENV + CLI configuration loading with priority resolution:
    CLI > ENV > config.yaml > config.py > Default

Supports dataclass-based structured configuration with automatic
type coercion and validation.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025-2026
"""

from datamasking._version import __version__  # єдине джерело версії

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
    # Локаль faker для синтетичних прізвищ/імен (морфологія лишається uk)
    faker_locale: str = "uk_UA"


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
    # Скільки перших символів оригінального прізвища зберігати в масці
    # (0 = не зберігати; разом зі збереженим закінченням — не більше половини
    # прізвища: Коваль → 3, Іванов → 1, Петренко → 0)
    surname_prefix_length: int = 3
    # Tuning parameters
    rank_shift_options: List[int] = field(default_factory=lambda: [-2, -1, 1, 2])
    date_shift_days: int = 30
    date_year_min: int = 2015
    date_year_max: int = 2035
    brigade_number_max: int = 160
    max_masking_iterations: int = 10
    name_generation_max_attempts: int = 50


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


# Ключі, які програма справді читає (masking/cli.py, unmasking/cli.py).
# Решта полів dataclass-ів лишається лише для сумісності зі старими
# файлами й ні на що не впливає. Шаблон --init-config і приклади
# (config_example.*, docs/config-examples/) перевіряються тестами саме
# за цим переліком — щоб документація не розходилась з кодом.
EFFECTIVE_KEYS: Dict[str, frozenset] = {
    "masking_rules": frozenset({
        "enable_names", "enable_ipn", "enable_passport", "enable_military_id",
        "enable_ranks", "enable_units", "enable_brigades", "enable_orders",
        "enable_br_numbers", "enable_dates", "surname_prefix_length",
    }),
    "system": frozenset({"preserve_case", "faker_locale", "hash_algorithm", "debug_mode"}),
    "security": frozenset({"encrypt_output", "password_length"}),
    "validation": frozenset({"max_input_size_mb"}),
    "logging": frozenset({"level", "file"}),
}


def ignored_config_keys(data: Any) -> List[str]:
    """Ключі файлу конфігурації, які ні на що не впливають (не в EFFECTIVE_KEYS).

    Повертає «section.key» у порядку файлу; невідома секція-словник
    розгортається до своїх ключів (``remask.enabled`` …).
    """
    out: List[str] = []
    if not isinstance(data, dict):
        return out

    def leaves(value: Any, prefix: str) -> List[str]:
        if isinstance(value, dict) and value:
            res: List[str] = []
            for k, v in value.items():
                res += leaves(v, f"{prefix}.{k}")
            return res
        return [prefix]

    for section, values in data.items():
        allowed = EFFECTIVE_KEYS.get(str(section))
        if allowed is None or not isinstance(values, dict):
            out += leaves(values, str(section))
            continue
        for key, value in values.items():
            if key not in allowed:
                out += leaves(value, f"{section}.{key}")
    return out


def format_ignored_keys_warning(source: str, keys: List[str], limit: int = 10) -> str:
    """Одне попередження на файл (а не рядок на кожен ключ)."""
    shown = ", ".join(keys[:limit])
    more = f" (+{len(keys) - limit} more)" if len(keys) > limit else ""
    return (f"Warning: {source}: {len(keys)} key(s) have no effect and were ignored: "
            f"{shown}{more}. The file may come from an older version — compare with "
            f"config_example.yaml or regenerate it: data-mask --init-config")


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
                elif k == "password_generation" and isinstance(v, bool):
                    # Шаблон 2.x писав `password_generation: true` — bool
                    # замість секції; не підміняємо dataclass булевим
                    cfg.security.password_generation.enabled = v
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
        "DATA_MASKING_FAKER_LOCALE": ("system", "faker_locale", str),
        "DATA_MASKING_SURNAME_PREFIX_LENGTH": ("masking_rules", "surname_prefix_length", int),
        "DATA_MASKING_ENCRYPT_OUTPUT": ("security", "encrypt_output", bool),
        # DATA_MASKING_PASSWORD навмисно ВІДСУТНІЙ: це сам пароль, його читає CLI
        # (до 3.0.4 значення пароля записувалось у security.password_env_var)
        "DATA_MASKING_PASSWORD_ENV_VAR": ("security", "password_env_var", str),
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
        self.loaded_from: Optional[str] = None  # шлях YAML, якщо реально прочитано
        # Ключі прочитаного файлу, які ні на що не впливають (для попередження
        # в CLI): раніше вони мовчки ігнорувались, і застарілий config_example
        # на 81 ключ «працював», хоча діяли лише 16 (v3.0.22)
        self.ignored_keys: List[str] = []
        self.ignored_source: Optional[str] = None

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
        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.error("Failed to read YAML config: %s", exc)
            raise ValueError(f"Cannot read config {filepath}: {exc}") from exc
        except yaml.YAMLError as exc:  # type: ignore[union-attr]
            # Битий YAML — помилка, а не тихі дефолти з написом «Loaded config»
            logger.error("Malformed YAML config %s: %s", filepath, exc)
            raise ValueError(f"Malformed YAML in {filepath}: {exc}") from exc
        if data is None:
            return None  # порожній файл — дефолти
        if not isinstance(data, dict):
            raise ValueError(f"YAML config {filepath} must be a mapping, got {type(data).__name__}")
        logger.info("Loaded YAML config from %s", filepath)
        self.loaded_from = str(filepath)
        return data

    # ----- Python config module loading -----

    def _load_python_config(self) -> Optional[Dict[str, Any]]:
        """Attempt to import a ``config`` Python module and extract settings.

        The module is expected to expose an ``AppConfig`` or ``Config``
        instance named ``cfg`` or ``config``, or to provide a dictionary
        named ``CONFIG``.
        """
        # Лише ./config.py з поточної директорії — НЕ довільний модуль «config»
        # із sys.path (site-packages, чужі проєкти); при `python -m datamasking`
        # cwd і так у sys.path, тож import_module тягнув будь-що з такою назвою
        cfg_file = Path("config.py")
        if not cfg_file.is_file():
            logger.debug("No ./config.py found")
            return None
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("_datamasking_local_config", cfg_file)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001 — будь-яка помилка чужого коду
            logger.warning("Failed to load ./config.py: %s", exc)
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
            self.ignored_keys = ignored_config_keys(py_data)
            self.ignored_source = "config.py"

        # Step 3: YAML config file
        yaml_path = self._config_path or "config.yaml"
        yaml_data = self._load_yaml(yaml_path)
        if yaml_data:
            self._config = Config.from_dict(yaml_data)
            # YAML замінює config.py цілком — і попередження теж
            self.ignored_keys = ignored_config_keys(yaml_data)
            self.ignored_source = self.loaded_from or yaml_path

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
# Generated by `data-mask --init-config`. Only keys the program actually
# reads are listed; the values are the defaults. Keys you leave out keep
# their defaults, so the file may contain only what you change.
#
# Priority: CLI flags > ENV variables > this file > defaults.
# Ready-made sets for typical scenarios (share / strict / pii):
#   https://github.com/click0/data-masking/tree/main/docs/config-examples
# ==========================================================================

# --------------------------------------------------------------------------
# What to mask. CLI --only / --exclude (see --list-types) replace these
# flags for the run.
# --------------------------------------------------------------------------
masking_rules:
  # People: surnames, first names, patronymics, names with initials
  # (one switch for the whole name)
  enable_names: true

  # Identifiers
  enable_ipn: true            # IPN / RNOKPP, 10 digits
  enable_passport: true       # passport / ID card, 9 digits
  enable_military_id: true    # military ID: AA123456

  # Military data
  enable_ranks: true          # ranks (all cases and genders)
  enable_units: true          # military units: A1234
  enable_brigades: true       # brigade numbers

  # Documents
  enable_orders: true         # order numbers: No.123, No.45/67
  enable_br_numbers: true     # BR numbers: 75/25/3400/R

  # Dates, both DD.MM.YYYY and written-out; turn off to keep the chronology
  enable_dates: true

  # How many leading letters of the ORIGINAL surname stay in its mask
  # (0 = fully synthetic). Prefix plus the preserved ending never exceed half
  # of the surname: Коваль -> Ков…, Іванов -> І…ов, Петренко -> …енко.
  # ENV: DATA_MASKING_SURNAME_PREFIX_LENGTH
  surname_prefix_length: 3

# --------------------------------------------------------------------------
# Appearance of masks and determinism
# --------------------------------------------------------------------------
system:
  # Keep letter case: ІВАНОВ -> ГРИЦЕНКО. ENV: DATA_MASKING_PRESERVE_CASE
  preserve_case: true

  # Faker dictionaries for synthetic names (uk_UA, pl_PL, ru_RU, ...);
  # grammar stays Ukrainian. ENV: DATA_MASKING_FAKER_LOCALE
  faker_locale: "uk_UA"

  # Hash for deterministic masks (same original -> same mask). Do not change
  # it in the middle of a batch of documents.
  # blake2b | sha256 | sha512 | sha1 | md5. ENV: DATA_MASKING_HASH_ALGORITHM
  hash_algorithm: "blake2b"

  # Verbose output (same as --debug); may show fragments of the original.
  # ENV: DATA_MASKING_DEBUG
  debug_mode: false

# --------------------------------------------------------------------------
# Mapping file protection (it holds the originals)
# --------------------------------------------------------------------------
security:
  # Encrypt the mapping (same as --encrypt): AES-256-GCM, key from the
  # password via PBKDF2-HMAC-SHA256; only the .enc file is written.
  # Password: --password-env VAR -> $DATA_MASKING_PASSWORD -> generated and
  # shown once on stderr. Needs `cryptography`. ENV: DATA_MASKING_ENCRYPT_OUTPUT
  encrypt_output: false

  # Length of a generated password. ENV: DATA_MASKING_PASSWORD_LENGTH
  password_length: 24

# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
validation:
  # Maximum input file size, MB. ENV: DATA_MASKING_MAX_INPUT_SIZE_MB
  max_input_size_mb: 100

# --------------------------------------------------------------------------
# Logging (CLI --log-level / --log-file take precedence)
# --------------------------------------------------------------------------
logging:
  # DEBUG | INFO | WARNING | ERROR | CRITICAL. ENV: DATA_MASKING_LOG_LEVEL
  level: "INFO"

  # Log file; null = console only. ENV: DATA_MASKING_LOG_FILE
  file: null
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

        from datamasking.extras.config import load_config
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
