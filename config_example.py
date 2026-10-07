#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration example for data_masking.py v2.6.0

Demonstrates all available configuration options using dataclasses.
No external dependencies required — uses only Python standard library.

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.6.0
License: BSD 3-Clause "New" or "Revised" License
Year: 2025-2026
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional


# ============================================================================
# DATACLASS DEFINITIONS
# ============================================================================

@dataclass
class SystemConfig:
    """Системні налаштування."""
    version: str = "v2.6.0"
    hash_algorithm: str = "blake2b"
    faker_locale: str = "uk_UA"
    hash_digest_size: int = 64
    encoding: str = "utf-8"
    preserve_case: bool = True
    backup_enabled: bool = False
    backup_suffix: str = ".bak"
    max_file_size_mb: int = 100
    temp_dir: str = ""
    debug_mode: bool = False
    strict_mode: bool = False


@dataclass
class SecurityConfig:
    """Налаштування безпеки та шифрування."""
    encrypt_output: bool = False
    password_env_var: str = "DATA_MASKING_PASSWORD"
    password_generation: dict = field(default_factory=lambda: {
        "enabled": True,
        "length": 24,
        "use_special_chars": True,
        "algorithm": "secrets",
        "min_uppercase": 2,
        "min_lowercase": 2,
        "min_digits": 2,
        "min_special": 2,
    })
    encryption_algorithm: str = "AES-256-GCM"
    key_derivation: str = "pbkdf2"
    scrypt_n: int = 2**14
    scrypt_r: int = 8
    scrypt_p: int = 1
    salt_length: int = 16
    auto_generate_password: bool = True
    password_file: str = ""
    secure_delete_temp: bool = True


@dataclass
class MaskingRulesConfig:
    """Налаштування правил маскування."""
    surname_prefix_length: int = 3  # перші літери оригіналу в масці прізвища (максимум)
    surname_prefix_min: int = 1     # і мінімум, навіть понад «половину» (Петренко → П…енко)
    enable_ranks: bool = True
    enable_names: bool = True
    enable_surnames: bool = True
    enable_patronymics: bool = True
    enable_ipn: bool = True
    enable_passport: bool = True
    enable_military_id: bool = True
    enable_dates: bool = True
    enable_date_text: bool = True
    enable_units: bool = True
    enable_brigades: bool = True
    enable_orders: bool = True
    enable_br_numbers: bool = True
    enable_document_numbers: bool = True
    preserve_case: bool = True
    preserve_gender: bool = True
    # Незмінна поведінка програми: приймається лише True
    consistent_mapping: bool = True
    instance_tracking: bool = True
    context_aware: bool = True
    rank_line_break_fix: bool = True
    custom_patterns: List[str] = field(default_factory=list)


@dataclass
class ValidationConfig:
    """Налаштування валідації."""
    strict_mode: bool = False
    max_input_size_mb: int = 100
    allowed_encodings: List[str] = field(default_factory=lambda: ["utf-8", "cp1251", "latin-1"])
    validate_ipn_checksum: bool = False
    validate_date_range: bool = True
    min_date_year: int = 1900
    max_date_year: int = 2100
    validate_rank_dictionary: bool = True  # лише True
    strict_pib_format: bool = False
    allow_abbreviated_patronymic: bool = True
    max_name_length: int = 50
    min_name_length: int = 3


@dataclass
class RouterRulesConfig:
    """Налаштування правил маршрутизації (порядок обробки)."""
    default_action: str = "mask"
    processing_order: List[str] = field(default_factory=lambda: [
        "custom",
        "order_number",
        "br_number",
        "ipn",
        "passport_id",
        "military_id",
        "military_unit",
        "brigade_number",
        "date",
        "date_text",
        "rank",
        "pib",
    ])
    skip_types: List[str] = field(default_factory=list)
    only_types: List[str] = field(default_factory=list)
    priority_overrides: Dict[str, int] = field(default_factory=dict)


@dataclass
class LoggingConfig:
    """Налаштування логування."""
    enabled: bool = True
    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_log_size_mb: int = 10
    log_rotation_count: int = 5
    log_to_console: bool = True
    log_to_file: bool = False
    log_sensitive_data: bool = False
    log_performance: bool = False
    log_statistics: bool = True


@dataclass
class ExclusionsConfig:
    """Виключення — доповнюють вбудовані переліки (--list-exclusions).

    «*» у кінці слова — будь-яке закінчення; регістр не враховується.
    """
    abbreviations: List[str] = field(default_factory=list)  # не маскувати як прізвище
    words: List[str] = field(default_factory=list)          # не частина ПІБ
    phrases: List[str] = field(default_factory=list)        # не маскувати взагалі
    legal_acts: List[str] = field(default_factory=list)     # назва + дата «… від» без змін
    always_mask: List[str] = field(default_factory=list)    # маскувати завжди
    remove: List[str] = field(default_factory=list)         # прибрати вбудовані


@dataclass
class DictionariesConfig:
    """Повні переліки виключень (у config.yaml / config_example.yaml — самі
    списки); None — вбудована копія з програми."""
    abbreviations: Optional[List[str]] = None   # не маскуються як прізвище
    non_name_words: Optional[List[str]] = None  # не частина ПІБ
    legal_acts: Optional[List[str]] = None      # дата після «<акт> … від» без змін


@dataclass
class Config:
    """Головна конфігурація системи маскування даних.

    Об'єднує всі секції конфігурації в єдину структуру.
    """
    system: SystemConfig = field(default_factory=SystemConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    masking_rules: MaskingRulesConfig = field(default_factory=MaskingRulesConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    router_rules: RouterRulesConfig = field(default_factory=RouterRulesConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    exclusions: ExclusionsConfig = field(default_factory=ExclusionsConfig)
    dictionaries: DictionariesConfig = field(default_factory=DictionariesConfig)

    def to_dict(self) -> dict:
        """Конвертує конфігурацію у словник.

        Returns:
            dict: Словникове представлення всіх параметрів конфігурації.
        """
        return asdict(self)


# ============================================================================
# MAIN — друкує всі значення конфігурації
# ============================================================================

if __name__ == "__main__":
    config = Config()
    data = config.to_dict()

    print("=" * 70)
    print("  Data Masking Configuration Example v2.6.0")
    print("=" * 70)

    for section_name, section_data in data.items():
        print(f"\n--- {section_name} ---")
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                elif isinstance(value, list):
                    print(f"  {key}:")
                    if value:
                        for item in value:
                            print(f"    - {item}")
                    else:
                        print("    (empty)")
                else:
                    print(f"  {key}: {value}")
        else:
            print(f"  {section_data}")

    print("\n" + "=" * 70)
    print("  Кінець конфігурації")
    print("=" * 70)
