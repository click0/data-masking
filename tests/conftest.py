# -*- coding: utf-8 -*-
"""
Pytest configuration and fixtures for data-masking tests
"""
import os
import re
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
    """Тести НЕ мають змінювати config.yaml у корені репозиторію (це
    спільний конфіг, v3.1.3) і лишати там config_local.yaml.

    Вміст порівнюється до й після тесту; змінений файл відновлюється, а
    тест падає (він має працювати у tmp_path).
    """
    config_path = PROJECT_ROOT / "config.yaml"
    local_path = PROJECT_ROOT / "config_local.yaml"
    before = config_path.read_bytes() if config_path.exists() else None
    local_existed = local_path.exists()
    yield
    after = config_path.read_bytes() if config_path.exists() else None
    if after != before:
        if before is None:
            config_path.unlink()
        else:
            config_path.write_bytes(before)
        pytest.fail("test changed config.yaml in the repository root — use tmp_path/monkeypatch.chdir")
    if not local_existed and local_path.exists():
        local_path.unlink()
        pytest.fail("test left config_local.yaml in the repository root — use tmp_path")


@pytest.fixture(autouse=True)
def restore_engine_settings():
    """Глобальні налаштування рушія (MASK_*, межі дат, PRESERVE_CASE …)
    конфігурація пише в модуль constants; CLI в тестах працює в тому самому
    процесі, тож без відновлення налаштування одного тесту «протікали» б
    в інші."""
    import tempfile
    from datamasking import _fsutil
    from datamasking.masking import constants as _cfg
    saved = {k: v for k, v in vars(_cfg).items()
             if k.isupper() and isinstance(v, (bool, int, float, str, tuple, frozenset, re.Pattern))}
    saved_tempdir, saved_secure = tempfile.tempdir, _fsutil.SECURE_DELETE_TEMP
    yield
    for k, v in saved.items():
        setattr(_cfg, k, v)
    tempfile.tempdir, _fsutil.SECURE_DELETE_TEMP = saved_tempdir, saved_secure


@pytest.fixture(autouse=True)
def isolate_user_config_dir(tmp_path_factory):
    """config_local.yaml шукається і в теці користувача — тести не мають
    підхоплювати справжній файл розробника.

    Без monkeypatch: autouse-фікстура з monkeypatch створює його раніше за
    фікстури тесту, і monkeypatch.chdir тесту відкочувався б уже після
    видалення тимчасової теки (Windows не видаляє поточну директорію)."""
    home_cfg = str(tmp_path_factory.mktemp("user_config"))
    saved = {k: os.environ.get(k) for k in ("XDG_CONFIG_HOME", "APPDATA")}
    os.environ["XDG_CONFIG_HOME"] = os.environ["APPDATA"] = home_cfg
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


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
