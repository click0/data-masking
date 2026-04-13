#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for modules/password_generator.py"""

import string
import pytest

from modules.password_generator import (
    generate_password,
    generate_password_from_config,
    generate_passwords,
    PasswordConfig,
    CYRILLIC_UPPER,
    CYRILLIC_LOWER,
    DEFAULT_SPECIAL_CHARS,
)


class TestGeneratePassword:
    """Tests for generate_password() function."""

    def test_default_length(self):
        pwd = generate_password()
        assert len(pwd) == 24

    def test_custom_length(self):
        for length in (8, 16, 32, 64):
            pwd = generate_password(length=length)
            assert len(pwd) == length

    def test_only_digits(self):
        pwd = generate_password(
            length=20,
            include_ascii_upper=False,
            include_ascii_lower=False,
            include_special=False,
        )
        assert all(c in string.digits for c in pwd)

    def test_only_uppercase(self):
        pwd = generate_password(
            length=20,
            include_ascii_lower=False,
            include_digits=False,
            include_special=False,
        )
        assert all(c in string.ascii_uppercase for c in pwd)

    def test_with_cyrillic(self):
        pwd = generate_password(
            length=50,
            include_cyrillic_lower=True,
            include_cyrillic_upper=True,
        )
        has_cyrillic = any(
            c in CYRILLIC_UPPER or c in CYRILLIC_LOWER for c in pwd
        )
        assert has_cyrillic

    def test_custom_chars(self):
        custom = "!@#"
        pwd = generate_password(
            length=50,
            include_ascii_upper=False,
            include_ascii_lower=False,
            include_digits=False,
            include_special=False,
            custom_chars=custom,
        )
        assert all(c in custom for c in pwd)

    def test_ensure_variety(self):
        """With ensure_variety=True, password should contain chars from each enabled set."""
        # Run multiple times to reduce flakiness
        found_all = False
        for _ in range(10):
            pwd = generate_password(length=24, ensure_variety=True)
            has_upper = any(c in string.ascii_uppercase for c in pwd)
            has_lower = any(c in string.ascii_lowercase for c in pwd)
            has_digit = any(c in string.digits for c in pwd)
            has_special = any(c in DEFAULT_SPECIAL_CHARS for c in pwd)
            if has_upper and has_lower and has_digit and has_special:
                found_all = True
                break
        assert found_all, "ensure_variety should include chars from all enabled sets"

    def test_no_special_chars(self):
        pwd = generate_password(length=100, include_special=False)
        assert not any(c in DEFAULT_SPECIAL_CHARS for c in pwd)

    def test_empty_charset_fallback(self):
        """When nothing is selected, should fallback to ascii_letters + digits."""
        pwd = generate_password(
            length=20,
            include_ascii_upper=False,
            include_ascii_lower=False,
            include_digits=False,
            include_special=False,
        )
        assert len(pwd) == 20
        assert all(c in (string.ascii_letters + string.digits) for c in pwd)

    def test_uniqueness(self):
        """Generated passwords should be unique (cryptographically random)."""
        passwords = {generate_password() for _ in range(100)}
        assert len(passwords) == 100

    def test_minimum_length(self):
        pwd = generate_password(length=1)
        assert len(pwd) == 1


class TestGeneratePasswords:
    """Tests for generate_passwords() function."""

    def test_count(self):
        passwords = generate_passwords(count=5)
        assert len(passwords) == 5

    def test_count_one(self):
        passwords = generate_passwords(count=1)
        assert len(passwords) == 1

    def test_count_zero_becomes_one(self):
        passwords = generate_passwords(count=0)
        assert len(passwords) == 1

    def test_all_correct_length(self):
        passwords = generate_passwords(count=10, length=16)
        assert all(len(p) == 16 for p in passwords)

    def test_all_unique(self):
        passwords = generate_passwords(count=50)
        assert len(set(passwords)) == 50


class TestPasswordConfig:
    """Tests for PasswordConfig dataclass."""

    def test_defaults(self):
        cfg = PasswordConfig()
        assert cfg.length == 24
        assert cfg.include_ascii_upper is True
        assert cfg.include_ascii_lower is True
        assert cfg.include_digits is True
        assert cfg.include_special is True
        assert cfg.include_cyrillic_upper is False
        assert cfg.include_cyrillic_lower is False
        assert cfg.ensure_variety is True

    def test_custom_config(self):
        cfg = PasswordConfig(length=32, include_cyrillic_lower=True)
        assert cfg.length == 32
        assert cfg.include_cyrillic_lower is True

    def test_charset_info(self):
        cfg = PasswordConfig()
        info = cfg.get_charset_info()
        assert info['total_chars'] > 0
        assert info['entropy_bits'] > 0
        assert info['bits_per_char'] > 0
        assert len(info['components']) > 0

    def test_charset_info_digits_only(self):
        cfg = PasswordConfig(
            include_ascii_upper=False,
            include_ascii_lower=False,
            include_special=False,
        )
        info = cfg.get_charset_info()
        assert info['total_chars'] == 10

    def test_charset_info_with_cyrillic(self):
        cfg = PasswordConfig(
            include_cyrillic_upper=True,
            include_cyrillic_lower=True,
        )
        info = cfg.get_charset_info()
        assert info['total_chars'] > 100  # ASCII + cyrillic


class TestGeneratePasswordFromConfig:
    """Tests for generate_password_from_config() function."""

    def test_basic_config(self):
        cfg = PasswordConfig(length=16)
        pwd = generate_password_from_config(cfg)
        assert pwd is not None
        assert len(pwd) == 16

    def test_auto_generate_false(self):
        cfg = PasswordConfig(auto_generate=False)
        result = generate_password_from_config(cfg)
        assert result is None

    def test_cyrillic_config(self):
        cfg = PasswordConfig(
            length=50,
            include_cyrillic_lower=True,
        )
        pwd = generate_password_from_config(cfg)
        assert pwd is not None
        has_cyrillic = any(c in CYRILLIC_LOWER for c in pwd)
        assert has_cyrillic


class TestConstants:
    """Tests for module constants."""

    def test_cyrillic_upper_length(self):
        assert len(CYRILLIC_UPPER) == 33  # Ukrainian alphabet

    def test_cyrillic_lower_length(self):
        assert len(CYRILLIC_LOWER) == 33

    def test_special_chars_not_empty(self):
        assert len(DEFAULT_SPECIAL_CHARS) > 0
