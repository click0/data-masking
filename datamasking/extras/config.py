#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration Module v2.6.0 for data_masking.py

Provides YAML + ENV + CLI configuration loading with priority resolution:
    CLI > ENV > config_local.yaml > config.yaml > config.py > Default

config_local.yaml (v3.1.1) — приватні перекриття поверх спільного
config.yaml: лежить поруч із ним (або в поточній директорії) і/або в
теці користувача (~/.config/data-masking/, %APPDATA%\\data-masking\\).
Ключ зі значенням, відмінним від null, перекриває спільний; вкладені
секції зливаються, списки замінюються цілком.

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
from typing import Optional, Dict, Any, List, Tuple
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
    # Версія, для якої писали файл (попередження, якщо новіша за програму)
    version: str = ""
    # Ліміт розміру вхідного файлу, МБ (діє менший із цього і
    # validation.max_input_size_mb); None — лише validation.max_input_size_mb
    max_file_size_mb: Optional[int] = None
    # Суворий режим (як validation.strict_mode): попередження конфігурації —
    # помилки, нерозмасковані значення в unmask — код виходу 1
    strict_mode: bool = False
    # Розмір дайджесту blake2b, байт (1–64); None — 64 (стандарт).
    # Інше значення змінює ВСІ маски
    hash_digest_size: Optional[int] = None
    # Каталог для тимчасових файлів (tempfile); "" — системний
    temp_dir: str = ""
    # Кодування вхідного файлу: utf-8 | будь-яке кодування Python | auto
    # (auto — перше з validation.allowed_encodings, що декодує файл)
    encoding: str = "utf-8"
    # Копія наявного вихідного файлу перед перезаписом (--force)
    backup_enabled: bool = False
    backup_suffix: str = ".bak"


@dataclass
class PasswordGenerationConfig:
    """Password generation settings."""
    enabled: bool = True
    length: int = 24
    use_special_chars: bool = True
    env_var: str = "DATA_MASKING_PASSWORD"
    # Джерело випадковості; підтримується лише "secrets"
    algorithm: str = "secrets"
    # Мінімальна кількість символів кожного класу (0 — без гарантії)
    min_uppercase: int = 0
    min_lowercase: int = 0
    min_digits: int = 0
    min_special: int = 0


@dataclass
class SecurityConfig:
    """Security configuration."""
    encrypt_output: bool = False
    password_generation: PasswordGenerationConfig = field(
        default_factory=PasswordGenerationConfig
    )
    password_env_var: str = "DATA_MASKING_PASSWORD"
    password_length: int = 24
    # Підтримується лише AES-256-GCM (так шифрує security.py)
    encryption_algorithm: str = "AES-256-GCM"
    # Виведення ключа з пароля: pbkdf2 (формат .enc, який читають усі версії)
    # або scrypt (формат 2 — лише v3.0.29+); параметри scrypt і довжина солі
    key_derivation: str = "pbkdf2"
    scrypt_n: int = 16384
    scrypt_r: int = 8
    scrypt_p: int = 1
    salt_length: int = 16
    # Затирати нулями тимчасовий файл невдалого запису перед видаленням
    secure_delete_temp: bool = True
    # false — без пароля --encrypt завершується помилкою, а не генерує його
    auto_generate_password: bool = True
    # Куди зберегти ЗГЕНЕРОВАНИЙ пароль (0600, атомарно); "" — не зберігати
    password_file: str = ""


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
    # Мінімум символів оригіналу, навіть понад «половину» (Петренко → «Пе…енко»);
    # 0 — як до 3.1.4 (прізвища на «-енко» повністю синтетичні)
    surname_prefix_min: int = 2
    # None — як system.preserve_case
    preserve_case: Optional[bool] = None
    # Склеювати звання, розірвані переносом рядка
    rank_line_break_fix: bool = True
    # Текстові дати («06» жовтня 2025 року); None — як enable_dates
    enable_date_text: Optional[bool] = None
    # Прізвища / по батькові окремо; None — як enable_names (тоді
    # enable_names: false вимикає все ПІБ, як до 3.0.28)
    enable_surnames: Optional[bool] = None
    enable_patronymics: Optional[bool] = None
    # Номери документів (№ не після «наказ…»); None — як enable_orders
    enable_document_numbers: Optional[bool] = None
    # Рід маски імені/по батькові = реальний; false — псевдовипадковий
    preserve_gender: bool = True
    # Інваріанти програми, не перемикачі: приймається лише true (див.
    # ALWAYS_ON_KEYS) — без них розмаскування неможливе
    consistent_mapping: bool = True
    instance_tracking: bool = True
    context_aware: bool = True
    # Власні шаблони: рядок-regex або {pattern, name, action: mask|skip|warn}
    custom_patterns: List[Any] = field(default_factory=list)
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
    # Маска ІПН з коректною контрольною цифрою (змінює маски ІПН)
    validate_ipn_checksum: bool = False
    # Довжина слова-кандидата в ПІБ; None — 3 / без обмеження
    min_name_length: Optional[int] = None
    max_name_length: Optional[int] = None
    # false — «Іванов І.І.» не маскується (з попередженням)
    allow_abbreviated_patronymic: bool = True
    # true — маскується лише повний ПІБ із трьох слів (з попередженням)
    strict_pib_format: bool = False
    # Роки, які розпізнаються як дата ДД.ММ.РРРР (і маскуються)
    validate_date_range: bool = True
    min_date_year: int = 1900
    max_date_year: int = 2100
    allowed_encodings: List[str] = field(
        default_factory=lambda: ["utf-8", "cp1251", "latin-1"]
    )
    # Звання розпізнаються лише за вбудованим словником (лише true)
    validate_rank_dictionary: bool = True


@dataclass
class RouterRulesConfig:
    """Router rules for selective masking."""
    default_action: str = "mask"
    # Як --exclude / --only (CLI має пріоритет); разом — помилка
    skip_types: List[str] = field(default_factory=list)
    only_types: List[str] = field(default_factory=list)
    # Порядок фаз шаблонних типів (None — типовий) і перевизначення пріоритетів
    processing_order: Optional[List[str]] = None
    priority_overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enabled: bool = True
    log_to_console: bool = True
    # None — писати у file, якщо його задано; false — не писати навіть тоді
    log_to_file: Optional[bool] = None
    # Друкувати блок статистики після маскування
    log_statistics: bool = True
    # Ротація файлу логу: розмір, МБ (None — без ротації) і кількість архівів
    max_log_size_mb: Optional[int] = None
    log_rotation_count: int = 5
    # Час етапів (читання, маскування, запис) у лог
    log_performance: bool = False
    # Дозволити оригінали у виводі налагодження (за замовчуванням — ніколи)
    log_sensitive_data: bool = False


@dataclass
class RemaskConfig:
    """Re-masking (--re-mask) settings."""
    enabled: bool = True
    max_passes: int = 10
    # Ланцюг і нумерація проходів — основа --to-version (лише true)
    save_chain: bool = True
    chain_format: str = "json"
    auto_numbering: bool = True


@dataclass
class DictionariesConfig:
    """Повні переліки виключень (config.yaml); None — вбудована копія
    з masking/exclusions.py."""
    abbreviations: Optional[List[str]] = None
    non_name_words: Optional[List[str]] = None
    legal_acts: Optional[List[str]] = None


@dataclass
class ExclusionsConfig:
    """Доповнення вбудованих виключень (masking/exclusions.py)."""
    # Абревіатури, які не маскуються як прізвище (ЗСУ, МОУ …)
    abbreviations: List[str] = field(default_factory=list)
    # Слова, які не вважаються частиною ПІБ
    words: List[str] = field(default_factory=list)
    # Фрази, які не маскуються взагалі; «*» у кінці слова — будь-яке закінчення
    phrases: List[str] = field(default_factory=list)
    # Нормативні акти: дата після «<акт> … від» не зсувається
    legal_acts: List[str] = field(default_factory=list)
    # Слова/фрази, які маскуються завжди (маска тієї ж форми, unmask відновлює)
    always_mask: List[str] = field(default_factory=list)
    # Прибрати вбудовані слова / абревіатури / акти
    remove: List[str] = field(default_factory=list)


# Ключі, які програма справді читає (masking/cli.py, unmasking/cli.py).
# Решта полів dataclass-ів лишається лише для сумісності зі старими
# файлами й ні на що не впливає. Шаблон --init-config і приклади
# (config_example.*, docs/config-examples/) перевіряються тестами саме
# за цим переліком — щоб документація не розходилась з кодом.
EFFECTIVE_KEYS: Dict[str, frozenset] = {
    "masking_rules": frozenset({
        "enable_names", "enable_ipn", "enable_passport", "enable_military_id",
        "enable_ranks", "enable_units", "enable_brigades", "enable_orders",
        "enable_br_numbers", "enable_dates", "surname_prefix_length", "surname_prefix_min",
        "preserve_case", "rank_line_break_fix", "enable_date_text",
        "enable_surnames", "enable_patronymics", "enable_document_numbers", "custom_patterns",
        "preserve_gender", "consistent_mapping", "instance_tracking", "context_aware",
    }),
    "system": frozenset({
        "preserve_case", "faker_locale", "hash_algorithm", "debug_mode",
        "version", "max_file_size_mb", "backup_enabled", "backup_suffix", "encoding",
        "strict_mode", "temp_dir", "hash_digest_size",
    }),
    "security": frozenset({
        "encrypt_output", "password_length", "password_env_var", "secure_delete_temp",
        "key_derivation", "scrypt_n", "scrypt_r", "scrypt_p", "salt_length",
        "auto_generate_password", "password_file", "encryption_algorithm",
        # вкладені ключі — через крапку; bool-форма зі старого шаблону теж
        "password_generation", "password_generation.enabled",
        "password_generation.length", "password_generation.algorithm",
        "password_generation.use_special_chars", "password_generation.min_uppercase",
        "password_generation.min_lowercase", "password_generation.min_digits",
        "password_generation.min_special",
    }),
    "password_generation": frozenset({"enabled", "length", "env_var", "use_special_chars"}),
    "validation": frozenset({
        "max_input_size_mb", "validate_date_range", "min_date_year", "max_date_year",
        "allowed_encodings", "strict_mode", "validate_ipn_checksum",
        "min_name_length", "max_name_length", "allow_abbreviated_patronymic", "strict_pib_format",
        "validate_rank_dictionary",
    }),
    "router_rules": frozenset({"skip_types", "only_types", "default_action",
                               "processing_order", "priority_overrides"}),
    "logging": frozenset({
        "level", "file", "enabled", "log_to_console", "log_to_file", "log_statistics",
        "format", "max_log_size_mb", "log_rotation_count", "log_performance", "log_sensitive_data",
    }),
    "remask": frozenset({"enabled", "max_passes", "chain_format", "save_chain", "auto_numbering"}),
    "exclusions": frozenset({"abbreviations", "words", "phrases", "legal_acts",
                             "always_mask", "remove"}),
    "dictionaries": frozenset({"abbreviations", "non_name_words", "legal_acts"}),
}


# Заплановані опції (варіант 3, v3.0.26): є в повному прикладі
# (config_example.yaml/.py) або в шаблоні --init-config з позначкою
# «[не реалізовано]» / «[not implemented yet]», але поки ні на що не
# впливають. Завантажувач приймає їх БЕЗ попередження (про них уже сказано
# в самому файлі); попередження — лише про ключі, яких немає ніде.
# Реалізована опція переходить звідси в EFFECTIVE_KEYS.
# План і оцінка складності — docs/TODO-config-options.md.
# З v3.0.30 усі опції реалізовано — перелік порожній (механізм лишається
# для майбутніх опцій).
PLANNED_KEYS: frozenset = frozenset()


# Ключі, що описують незмінну поведінку програми: false не підтримується
# (вимкнути це не можна, не зламавши розмаскування). Значення — пояснення
# для повідомлення про помилку (masking/cli.py).
ALWAYS_ON_KEYS: Dict[str, str] = {
    "masking_rules.consistent_mapping":
        "the same value always gets the same mask; without it unmasking "
        "could not restore the original",
    "masking_rules.instance_tracking":
        "unmasking restores every occurrence by its number in the mapping",
    "masking_rules.context_aware":
        "names and ranks are recognised only by context; to stop masking "
        "them use enable_names / enable_ranks",
    "validation.validate_rank_dictionary":
        "ranks are recognised only by the built-in dictionary; to stop "
        "masking them use enable_ranks: false",
    "remask.save_chain":
        "in --re-mask mode the chain file is the mapping; without it the "
        "output could not be unmasked",
    "remask.auto_numbering":
        "re-mask passes are always numbered; --to-version relies on it",
}


def ignored_config_keys(data: Any) -> List[str]:
    """Ключі файлу конфігурації, про які треба попередити: не діють
    (не в EFFECTIVE_KEYS) і не заплановані (не в PLANNED_KEYS).

    Повертає «section.key» у порядку файлу; невідома секція-словник
    розгортається до своїх ключів (``remask.enabled`` …).
    """
    return [k for k in _unknown_leaf_keys(data) if k not in PLANNED_KEYS]


def _effective_paths() -> frozenset:
    return frozenset(f"{s}.{k}" for s, keys in EFFECTIVE_KEYS.items() for k in keys)


def _unknown_leaf_keys(data: Any) -> List[str]:
    """Усі листові ключі поза EFFECTIVE_KEYS (і заплановані, і невідомі).

    Шлях — через крапку (``security.password_generation.enabled``), тож
    вкладені ключі в EFFECTIVE_KEYS записуються так само.
    """
    if not isinstance(data, dict):
        return []
    effective = _effective_paths()

    def leaves(value: Any, prefix: str) -> List[str]:
        is_section = isinstance(value, dict) and bool(value)
        # Ключ діючий сам по собі (не секція): bool-форма
        # security.password_generation не має ховати ключі всередині секції
        if prefix in effective and not is_section:
            return []
        if is_section:
            res: List[str] = []
            for k, v in value.items():
                res += leaves(v, f"{prefix}.{k}")
            return res
        return [prefix]

    out: List[str] = []
    for section, values in data.items():
        out += leaves(values, str(section))
    return out


LOCAL_CONFIG_NAME = "config_local.yaml"


def _dictionaries_yaml() -> str:
    from datamasking.masking.exclusions import dictionaries_yaml
    return dictionaries_yaml()


def user_config_dir() -> Path:
    """Тека налаштувань користувача: %APPDATA%\\data-masking (Windows),
    $XDG_CONFIG_HOME/data-masking або ~/.config/data-masking."""
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "data-masking"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / "data-masking"


def merge_config_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """override поверх base (новий словник; вхідні не змінюються).

    null (None) не перекриває значення з base; секції-словники зливаються
    рекурсивно; решта (числа, рядки, списки — навіть порожні) замінюється.
    """
    out = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_config_dicts(out[key], value)
        else:
            out[key] = value
    return out


def is_strict(config: Any) -> bool:
    """system.strict_mode або validation.strict_mode."""
    return any(getattr(getattr(config, section, None), "strict_mode", False) is True
               for section in ("system", "validation"))


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
    remask: RemaskConfig = field(default_factory=RemaskConfig)
    exclusions: ExclusionsConfig = field(default_factory=ExclusionsConfig)
    dictionaries: DictionariesConfig = field(default_factory=DictionariesConfig)

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

        if "remask" in data and isinstance(data["remask"], dict):
            for k, v in data["remask"].items():
                if hasattr(cfg.remask, k):
                    setattr(cfg.remask, k, v)

        if "exclusions" in data and isinstance(data["exclusions"], dict):
            for k, v in data["exclusions"].items():
                if hasattr(cfg.exclusions, k):
                    setattr(cfg.exclusions, k, v)

        if "dictionaries" in data and isinstance(data["dictionaries"], dict):
            for k, v in data["dictionaries"].items():
                if hasattr(cfg.dictionaries, k):
                    setattr(cfg.dictionaries, k, v)

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
        3. config_local.yaml (private overrides: user config directory, then
                              next to config.yaml; non-null values win)
        4. config.yaml     (YAML file)
        5. config.py       (Python config module)
        6. Defaults        (dataclass defaults)
    """

    # Mapping: ENV variable name -> (config section, attribute name, type)
    ENV_MAPPING: Dict[str, tuple] = {
        "DATA_MASKING_HASH_ALGORITHM": ("system", "hash_algorithm", str),
        "DATA_MASKING_PRESERVE_CASE": ("system", "preserve_case", bool),
        "DATA_MASKING_DEBUG": ("system", "debug_mode", bool),
        "DATA_MASKING_FAKER_LOCALE": ("system", "faker_locale", str),
        "DATA_MASKING_SURNAME_PREFIX_LENGTH": ("masking_rules", "surname_prefix_length", int),
        "DATA_MASKING_SURNAME_PREFIX_MIN": ("masking_rules", "surname_prefix_min", int),
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
        local_path: Optional[str] = None,
        use_local: bool = True,
    ):
        self._config = Config()
        self._config_path = config_path
        self._cli_args = cli_args or {}
        # config_local.yaml: явний шлях (--config-local) або автопошук
        self._local_path = local_path
        self._use_local = use_local
        self.local_loaded: List[str] = []
        # (файл, ключі без дії) — по одному попередженню на файл
        self.ignored_by_source: List[Tuple[str, List[str]]] = []
        # Інші попередження для stderr (права доступу, немає PyYAML)
        self.notices: List[str] = []
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
        data = self._read_yaml(filepath)
        if data is not None:
            logger.info("Loaded YAML config from %s", filepath)
            self.loaded_from = str(filepath)
        return data

    @staticmethod
    def _read_yaml(filepath: Path) -> Optional[Dict[str, Any]]:
        """Прочитати YAML-словник (None — порожній файл). Raises ValueError."""
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
        return data

    # ----- config_local.yaml -----

    def local_config_paths(self) -> List[Path]:
        """Наявні config_local.yaml у порядку застосування (останній важить
        найбільше): тека користувача, потім поруч із config.yaml (або
        поточна директорія). Явний --config-local замінює автопошук."""
        if not self._use_local:
            return []
        if self._local_path:
            path = Path(self._local_path)
            if not path.is_file():
                raise ValueError(f"Local config file not found: {path}")
            return [path]
        base_dir = Path(self._config_path).parent if self._config_path else Path(".")
        found: List[Path] = []
        seen = set()
        for cand in (user_config_dir() / LOCAL_CONFIG_NAME, base_dir / LOCAL_CONFIG_NAME):
            if not cand.is_file():
                continue
            key = os.path.normcase(str(cand.resolve()))
            if key not in seen:
                seen.add(key)
                found.append(cand)
        return found

    def _load_local(self, path: Path) -> Optional[Dict[str, Any]]:
        if not YAML_AVAILABLE:
            self.notices.append(f"Warning: {path}: PyYAML is not installed — "
                                f"the local configuration was ignored (pip install pyyaml)")
            return None
        data = self._read_yaml(path)
        if os.name != "nt":
            try:
                if path.stat().st_mode & 0o077:
                    self.notices.append(f"Warning: {path} is accessible to other users; it may hold "
                                        f"private settings — chmod 600 {path}")
            except OSError:
                pass
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
        base: Dict[str, Any] = {}

        # Step 4: Python config module
        py_data = self._load_python_config()
        if py_data:
            base = py_data
            self.ignored_keys = ignored_config_keys(py_data)
            self.ignored_source = "config.py"

        # Step 3: YAML config file
        yaml_path = self._config_path or "config.yaml"
        yaml_data = self._load_yaml(yaml_path)
        if yaml_data:
            # YAML замінює config.py цілком — і попередження теж
            base = yaml_data
            self.ignored_keys = ignored_config_keys(yaml_data)
            self.ignored_source = self.loaded_from or yaml_path
        if self.ignored_keys:
            self.ignored_by_source.append((self.ignored_source or "config", self.ignored_keys))

        # Step 2.5: config_local.yaml — значення не-null перекривають спільні
        merged = base
        for path in self.local_config_paths():
            local = self._load_local(path)
            if not local:
                continue
            merged = merge_config_dicts(merged, local)
            self.local_loaded.append(str(path))
            logger.info("Loaded local config from %s", path)
            keys = ignored_config_keys(local)
            if keys:
                self.ignored_by_source.append((str(path), keys))
        if merged:
            self._config = Config.from_dict(merged)

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
# Priority: CLI > ENV > config_local.yaml > config.yaml > config.py > Default
# config_local.yaml (next to this file and/or in ~/.config/data-masking/ or
# %APPDATA%\\data-masking\\) holds private overrides: every key set there to
# a non-null value replaces the value from this file (lists as a whole).
#
# Author: Vladyslav V. Prodan
# Contact: github.com/click0
# License: BSD 3-Clause
# Year: 2025-2026
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

  # Faker locale for synthetic surnames / names / patronymics (e.g. uk_UA, ru_RU,
  # pl_PL). Grammar (endings, cases, gender) stays Ukrainian; locales without
  # patronymics fall back to uk_UA for them. ENV: DATA_MASKING_FAKER_LOCALE
  faker_locale: "uk_UA"

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
  # Encrypt the mapping file (AES-256-GCM, PBKDF2-HMAC-SHA256) — same as --encrypt.
  # The password is taken from --password / --password-env / $DATA_MASKING_PASSWORD
  # or generated (printed once to stderr).
  encrypt_output: false

  # Environment variable for password (alternative to --password)
  password_env_var: "DATA_MASKING_PASSWORD"

  # Length of auto-generated password (characters)
  password_length: 24

# --------------------------------------------------------------------------
# Masking rules — enable/disable individual data types
# --------------------------------------------------------------------------
masking_rules:
  # How many leading characters of the ORIGINAL surname to keep in its mask
  # (0 = none). Prefix plus the preserved ending stay within half of the
  # surname, but at least surname_prefix_min are kept: Коваль -> Ков…,
  # Іванов -> Ів…ов, Петренко -> Пе…енко.  ENV: DATA_MASKING_SURNAME_PREFIX_LENGTH
  surname_prefix_length: 3
  # Minimum kept even beyond the half (0 = before 3.1.4: -енко surnames fully
  # synthetic).  ENV: DATA_MASKING_SURNAME_PREFIX_MIN
  surname_prefix_min: 2

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

# --------------------------------------------------------------------------
# Exclusions (added to the built-in lists; see data-mask --list-exclusions).
# A trailing * matches any ending: "Верховн* Рад*". Case-insensitive.
# Private entries belong in config_local.yaml, not in this shared file.
# --------------------------------------------------------------------------
exclusions:
  # Abbreviations never masked as a surname
  abbreviations: []
  # Words that are never part of a name
  words: []
  # Phrases never masked at all
  phrases: []
  # Legal acts: the name is not masked, a date after "<act> ... від" is kept
  legal_acts: []
  # Words/phrases always masked (same-shape mask, restored by unmask)
  always_mask: []
  # Remove built-in words, abbreviations or legal acts
  remove: []

# --------------------------------------------------------------------------
# Dictionaries: the full built-in lists, editable. A missing key (or null)
# means the copy built into the program. Legal acts: a trailing * matches
# any ending ("закон*" = Закону, Законом ...).
# --------------------------------------------------------------------------
dictionaries:
{dictionaries}""".format(version=__version__, dictionaries=_dictionaries_yaml())

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
