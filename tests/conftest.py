# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures for data-masking tests
"""
import os
import subprocess
import pytest
import sys
from pathlib import Path

# Додаємо батьківську директорію в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# Force UTF-8 for subprocess on Windows (fixes cp1251 UnicodeDecodeError)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


@pytest.fixture
def run_cli():
    """Run a CLI command with UTF-8 encoding (cross-platform).

    Usage:
        result = run_cli(["python", "data_masking.py", "-i", "input.txt"])
        assert result.returncode == 0
        print(result.stdout)
    """
    def _run(cmd, **kwargs):
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("cwd", str(Path(__file__).parent.parent))
        return subprocess.run(cmd, **kwargs)
    return _run


@pytest.fixture
def empty_masking_dict():
    """Порожній словник маскування з правильною структурою"""
    return {
        "version": "v2.0",
        "timestamp": "2025-11-19T00:00:00",
        "mappings": {
            "rank": {},
            "surname": {},
            "name": {},
            "patronymic": {},
            "unit": {},
            "ipn": {},
            "military_id": {},
            "document_number": {},
            "date": {}
        },
        "statistics": {}
    }


@pytest.fixture
def sample_masking_dict():
    """Приклад словника маскування з даними"""
    return {
        "version": "v2.0",
        "timestamp": "2025-11-19T00:00:00",
        "mappings": {
            "surname": {
                "іванов": {
                    "masked_as": "Петренко",
                    "instances": [1]
                }
            },
            "name": {
                "петро": {
                    "masked_as": "Андрій",
                    "instances": [1]
                }
            },
            "rank": {
                "капітан": {
                    "masked_as": "майор",
                    "instances": [1, 2]
                }
            }
        },
        "statistics": {
            "surname": 1,
            "name": 1,
            "rank": 1
        }
    }


@pytest.fixture
def instance_counters():
    """Лічильники instances"""
    return {}


@pytest.fixture
def sample_text_with_pib():
    """Зразок тексту з ПІБ"""
    return "Капітан Іванов Петро Миколайович отримує премію"


@pytest.fixture
def sample_text_with_rank():
    """Зразок тексту зі званням"""
    return "Молодшому сержанту надається відпустка"
