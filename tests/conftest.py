# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures for data-masking tests
"""
import pytest
import sys
from pathlib import Path

# Додаємо батьківську директорію в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))


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
