#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration module for data_masking.py v2.2.15

Provides YAML-based configuration loading with dataclass-style access.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class SystemConfig:
    """System-level configuration."""
    hash_algorithm: str = "blake2b"
    preserve_case: bool = True
    debug_mode: bool = False


@dataclass
class SecurityConfig:
    """Security configuration."""
    encrypt_output: bool = False
    password_generation: bool = True
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
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class RouterRulesConfig:
    """Router rules for selective masking."""
    default_action: str = "mask"


@dataclass
class AppConfig:
    """Top-level application configuration."""
    system: SystemConfig = field(default_factory=SystemConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    masking_rules: MaskingRulesConfig = field(default_factory=MaskingRulesConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    router_rules: RouterRulesConfig = field(default_factory=RouterRulesConfig)


class ConfigLoader:
    """Loads and manages application configuration.

    Supports YAML config files. Falls back to defaults if no file is found.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config = AppConfig()
        if config_path:
            self._load_from_file(config_path)

    @property
    def config(self) -> AppConfig:
        return self._config

    def _load_from_file(self, path: str) -> None:
        """Load configuration from a YAML file."""
        try:
            import yaml
        except ImportError:
            return

        filepath = Path(path)
        if not filepath.exists():
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            return

        if "system" in data:
            for k, v in data["system"].items():
                if hasattr(self._config.system, k):
                    setattr(self._config.system, k, v)

        if "security" in data:
            for k, v in data["security"].items():
                if hasattr(self._config.security, k):
                    setattr(self._config.security, k, v)

        if "masking_rules" in data:
            for k, v in data["masking_rules"].items():
                if hasattr(self._config.masking_rules, k):
                    setattr(self._config.masking_rules, k, v)

        if "logging" in data:
            for k, v in data["logging"].items():
                if hasattr(self._config.logging, k):
                    setattr(self._config.logging, k, v)
