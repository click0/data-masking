#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration example for data_masking.py v2.2.15

Demonstrates how to use config.py dataclasses and ConfigLoader
for programmatic configuration of the masking pipeline.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

from config import (
    AppConfig,
    ConfigLoader,
    LoggingConfig,
    MaskingRulesConfig,
    SecurityConfig,
    SystemConfig,
)

# ============================================================================
# VARIANT 1: Load configuration from YAML file
# ============================================================================

loader = ConfigLoader(config_path="config.yaml")
cfg = loader.config

print(f"Hash algorithm: {cfg.system.hash_algorithm}")
print(f"Preserve case: {cfg.system.preserve_case}")
print(f"Encrypt output: {cfg.security.encrypt_output}")
print(f"Log level: {cfg.logging.level}")

# ============================================================================
# VARIANT 2: Create configuration programmatically (without YAML)
# ============================================================================

cfg = AppConfig(
    system=SystemConfig(
        hash_algorithm="blake2b",   # blake2b | md5 | sha1 | sha256 | sha512
        preserve_case=True,
        debug_mode=False,
    ),
    security=SecurityConfig(
        encrypt_output=True,
        password_generation=True,
        password_env_var="DATA_MASKING_PASSWORD",
        password_length=24,
    ),
    masking_rules=MaskingRulesConfig(
        enable_ranks=True,
        enable_names=True,
        enable_ipn=True,
        enable_passport=True,
        enable_military_id=True,
        enable_dates=True,
        enable_brigades=True,
        enable_units=True,
        enable_orders=True,
        enable_br_numbers=True,
    ),
    logging=LoggingConfig(
        level="INFO",               # DEBUG | INFO | WARNING | ERROR | CRITICAL
        file=None,                  # None = console only, or path e.g. "masking.log"
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    ),
)

# ============================================================================
# VARIANT 3: Partial override — only change what you need
# ============================================================================

cfg = AppConfig()

# Disable specific masking types
cfg.masking_rules.enable_dates = False
cfg.masking_rules.enable_br_numbers = False

# Enable debug and encryption
cfg.system.debug_mode = True
cfg.security.encrypt_output = True

# Change hash algorithm
cfg.system.hash_algorithm = "sha256"

# Write logs to file
cfg.logging.level = "DEBUG"
cfg.logging.file = "masking_debug.log"
