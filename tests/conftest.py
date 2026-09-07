# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures for data-masking tests
"""
import os
import subprocess
import tempfile
import pytest
import sys
from pathlib import Path

# Коренева директорія проекту (батьківська від tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Додаємо PROJECT_ROOT до PYTHONPATH
sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 for subprocess on Windows (fixes cp1251 UnicodeDecodeError)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


# ============================================================================
# AUTOUSE FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def guard_repo_root_config_yaml():
    """Тести НЕ мають лишати config.yaml у корені репозиторію.

    Раніше фікстура мовчки ВИДАЛЯЛА config.yaml розробника після кожного
    тесту. Тепер: файл, що існував до тесту, не чіпаємо; файл, який
    створив тест, — це помилка тесту (він має працювати у tmp_path).
    """
    config_path = PROJECT_ROOT / "config.yaml"
    existed_before = config_path.exists()
    yield
    if not existed_before and config_path.exists():
        config_path.unlink()
        pytest.fail("test left config.yaml in the repository root — use tmp_path/monkeypatch.chdir")


@pytest.fixture(autouse=True)
def restore_environment():
    """Відновлює os.environ після тесту (замість видалення всіх DM_*/DATA_MASKING_*,
    включно з тими, що встановив розробник до запуску pytest)."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


# ============================================================================
# GENERAL FIXTURES
# ============================================================================

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
        kwargs.setdefault("cwd", str(PROJECT_ROOT))
        return subprocess.run(cmd, **kwargs)
    return _run


@pytest.fixture
def temp_dir():
    """Тимчасова директорія, що автоматично видаляється."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def clean_env():
    """Чисте оточення без DM_* змінних.

    Зберігає поточний стан змінних оточення і відновлює після тесту.
    """
    saved = {k: v for k, v in os.environ.items() if k.startswith("DM_")}
    for key in saved:
        del os.environ[key]
    yield
    # Відновлюємо збережені змінні
    for key in list(os.environ):
        if key.startswith("DM_"):
            del os.environ[key]
    os.environ.update(saved)


@pytest.fixture
def sample_yaml_content():
    """Приклад вмісту YAML конфігурації."""
    return """system:
  hash_algorithm: "blake2b"
  hash_digest_size: 8
  preserve_case: true
  debug_mode: false

security:
  encrypt_output: false
  password_generation: true
  password_env_var: "DATA_MASKING_PASSWORD"
  password_length: 24

masking_rules:
  enable_ranks: true
  enable_names: true
  enable_ipn: true
  enable_passport: true
  enable_military_id: true
  enable_dates: true

logging:
  level: "INFO"
  file: null
"""


@pytest.fixture
def sample_text():
    """Приклад тексту для тестування маскування."""
    return (
        "Капітан Петренко Іван Сергійович, "
        "ІПН 1234567890, паспорт 123456789."
    )


# ============================================================================
# MASKING DICT FIXTURES
# ============================================================================

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


# ============================================================================
# TEXT SAMPLE FIXTURES
# ============================================================================

@pytest.fixture
def sample_text_with_pib():
    """Зразок тексту з ПІБ"""
    return "Капітан Іванов Петро Миколайович отримує премію"


@pytest.fixture
def sample_text_with_rank():
    """Зразок тексту зі званням"""
    return "Молодшому сержанту надається відпустка"
