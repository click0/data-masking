#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration example for data_masking.py v2.5.1

Demonstrates all available configuration options using dataclasses.
No external dependencies required — uses only Python standard library.

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.5.1
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
    version: str = "v2.5.1"
    hash_algorithm: str = "blake2b"
    hash_digest_size: int = 8
    encoding: str = "utf-8"
    preserve_case: bool = True
    backup_enabled: bool = True
    backup_suffix: str = ".bak"
    max_file_size_mb: int = 50
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
    encryption_algorithm: str = "AES-128-CBC"
    key_derivation: str = "scrypt"
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
    consistent_mapping: bool = True
    instance_tracking: bool = True
    context_aware: bool = True
    rank_line_break_fix: bool = True
    custom_patterns: List[str] = field(default_factory=list)


@dataclass
class ValidationConfig:
    """Налаштування валідації."""
    validate_ipn_checksum: bool = True
    validate_date_range: bool = True
    min_date_year: int = 1900
    max_date_year: int = 2030
    validate_rank_dictionary: bool = True
    strict_pib_format: bool = False
    allow_abbreviated_patronymic: bool = True
    max_name_length: int = 50
    min_name_length: int = 2


@dataclass
class RouterRulesConfig:
    """Налаштування правил маршрутизації (порядок обробки)."""
    default_action: str = "mask"
    processing_order: List[str] = field(default_factory=lambda: [
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
    print("  Data Masking Configuration Example v2.5.1")
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
