#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration example for data_masking.py v2.6.0

Demonstrates all available configuration options using dataclasses.
No external dependencies required — uses only Python standard library.

Options marked [не реалізовано] are planned but have no effect yet: the
program accepts them (without a warning) and ignores them. List and order of
implementation: docs/TODO-config-options.md.

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
    version: str = "v2.6.0"  # [не реалізовано]
    hash_algorithm: str = "blake2b"
    hash_digest_size: int = 8  # [не реалізовано]
    encoding: str = "utf-8"  # [не реалізовано]
    preserve_case: bool = True
    backup_enabled: bool = True  # [не реалізовано]
    backup_suffix: str = ".bak"  # [не реалізовано]
    max_file_size_mb: int = 50  # [не реалізовано]
    temp_dir: str = ""  # [не реалізовано]
    debug_mode: bool = False
    strict_mode: bool = False  # [не реалізовано]


@dataclass
class SecurityConfig:
    """Налаштування безпеки та шифрування."""
    encrypt_output: bool = False
    password_env_var: str = "DATA_MASKING_PASSWORD"  # [не реалізовано]
    password_generation: dict = field(default_factory=lambda: {
        "enabled": True,  # [не реалізовано]
        "length": 24,  # [не реалізовано]
        "use_special_chars": True,  # [не реалізовано]
        "algorithm": "secrets",  # [не реалізовано]
        "min_uppercase": 2,  # [не реалізовано]
        "min_lowercase": 2,  # [не реалізовано]
        "min_digits": 2,  # [не реалізовано]
        "min_special": 2,  # [не реалізовано]
    })
    encryption_algorithm: str = "AES-256-GCM"  # [не реалізовано]
    key_derivation: str = "scrypt"  # [не реалізовано]
    scrypt_n: int = 2**14  # [не реалізовано]
    scrypt_r: int = 8  # [не реалізовано]
    scrypt_p: int = 1  # [не реалізовано]
    salt_length: int = 16  # [не реалізовано]
    auto_generate_password: bool = True  # [не реалізовано]
    password_file: str = ""  # [не реалізовано]
    secure_delete_temp: bool = True  # [не реалізовано]


@dataclass
class MaskingRulesConfig:
    """Налаштування правил маскування."""
    enable_ranks: bool = True
    enable_names: bool = True
    enable_surnames: bool = True  # [не реалізовано]
    enable_patronymics: bool = True  # [не реалізовано]
    enable_ipn: bool = True
    enable_passport: bool = True
    enable_military_id: bool = True
    enable_dates: bool = True
    enable_date_text: bool = True  # [не реалізовано]
    enable_units: bool = True
    enable_brigades: bool = True
    enable_orders: bool = True
    enable_br_numbers: bool = True
    enable_document_numbers: bool = True  # [не реалізовано]
    preserve_case: bool = True  # [не реалізовано]
    preserve_gender: bool = True  # [не реалізовано]
    consistent_mapping: bool = True  # [не реалізовано]
    instance_tracking: bool = True  # [не реалізовано]
    context_aware: bool = True  # [не реалізовано]
    rank_line_break_fix: bool = True  # [не реалізовано]
    custom_patterns: List[str] = field(default_factory=list)  # [не реалізовано]


@dataclass
class ValidationConfig:
    """Налаштування валідації."""
    validate_ipn_checksum: bool = True  # [не реалізовано]
    validate_date_range: bool = True  # [не реалізовано]
    min_date_year: int = 1900  # [не реалізовано]
    max_date_year: int = 2030  # [не реалізовано]
    validate_rank_dictionary: bool = True  # [не реалізовано]
    strict_pib_format: bool = False  # [не реалізовано]
    allow_abbreviated_patronymic: bool = True  # [не реалізовано]
    max_name_length: int = 50  # [не реалізовано]
    min_name_length: int = 2  # [не реалізовано]


@dataclass
class RouterRulesConfig:
    """Налаштування правил маршрутизації (порядок обробки)."""
    default_action: str = "mask"  # [не реалізовано]
    processing_order: List[str] = field(default_factory=lambda: [  # [не реалізовано]
        "date_text",
        "date",
        "ipn",
        "passport_id",
        "military_id",
        "order_number",
        "brigade_number",
        "rank",
        "pib",
        "military_unit",
    ])
    skip_types: List[str] = field(default_factory=list)  # [не реалізовано]
    only_types: List[str] = field(default_factory=list)  # [не реалізовано]
    priority_overrides: Dict[str, int] = field(default_factory=dict)  # [не реалізовано]


@dataclass
class LoggingConfig:
    """Налаштування логування."""
    enabled: bool = True  # [не реалізовано]
    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # [не реалізовано]
    max_log_size_mb: int = 10  # [не реалізовано]
    log_rotation_count: int = 5  # [не реалізовано]
    log_to_console: bool = True  # [не реалізовано]
    log_to_file: bool = False  # [не реалізовано]
    log_sensitive_data: bool = False  # [не реалізовано]
    log_performance: bool = False  # [не реалізовано]
    log_statistics: bool = True  # [не реалізовано]


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
