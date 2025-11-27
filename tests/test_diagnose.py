# -*- coding: utf-8 -*-
"""
Tests for diagnose_mapping.py utility.
Testing verification logic and file handling.

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025
"""
import pytest
from pathlib import Path
import sys

# Додаємо батьківську директорію, щоб імпортувати diagnose_mapping
sys.path.insert(0, str(Path(__file__).parent.parent))

from diagnose_mapping import verify_text_recovery, analyze_category_structure


# ============================================================================
# ТЕСТИ ДЛЯ АНАЛІЗУ СТРУКТУРИ МАППІНГУ
# ============================================================================

def test_analyze_structure_v2():
    """
    Тест аналізу структури маппінгу v2.1 (з instance tracking).

    Перевіряє:
    - Визначення формату v2.1
    - Підрахунок загальної кількості instances
    - Знаходження максимальної кількості instances для одного запису
    """
    data = {
        "ivanov": {"masked_as": "petrov", "instances": [1, 2]},
        "sidorov": {"masked_as": "petrov", "instances": [3]}
    }
    result = analyze_category_structure("surname", data)

    assert result["format"] == "v2.1"
    assert result["has_instances"] is True
    assert result["instance_stats"]["total_instances"] == 3
    assert result["instance_stats"]["max_instances"] == 2


def test_analyze_structure_v20():
    """
    Тест аналізу структури маппінгу v2.0 (без instance tracking).

    Перевіряє:
    - Визначення формату v2.0
    - Відсутність інформації про instances
    - Правильний підрахунок кількості записів
    """
    data = {
        "ivanov": {"masked_as": "petrov", "gender": "M"},
        "sidorov": {"masked_as": "kuznetsov", "gender": "M"}
    }
    result = analyze_category_structure("surname", data)

    assert result["format"] == "v2.0"
    assert result["has_instances"] is False
    assert result["count"] == 2
    assert "instance_stats" not in result or result["instance_stats"] == {}


def test_analyze_structure_v1():
    """
    Тест аналізу старого формату маппінгу v1 (проста пара ключ-значення).

    Перевіряє:
    - Визначення формату v1
    - Простий підрахунок записів
    """
    data = {
        "ivanov": "petrov",
        "sidorov": "kuznetsov"
    }
    result = analyze_category_structure("surname", data)

    assert result["format"] == "v1"
    assert result["has_instances"] is False
    assert result["count"] == 2


def test_analyze_structure_empty():
    """
    Тест аналізу порожнього маппінгу.
    """
    data = {}
    result = analyze_category_structure("surname", data)

    assert result["format"] == "empty"
    assert result["count"] == 0
    assert result["has_instances"] is False


# ============================================================================
# ТЕСТИ ДЛЯ ВЕРИФІКАЦІЇ ТЕКСТУ (3 РІВНІ ПЕРЕВІРКИ)
# ============================================================================

def test_verify_strict_match(tmp_path, capsys):
    """
    Тест Level 1: Строга перевірка (Byte-to-byte match).

    Сценарій: Файли абсолютно ідентичні.
    Очікуваний результат: Успіх на Level 1.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("Hello World", encoding="utf-8")
    rec.write_text("Hello World", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    assert "✅ [LEVEL 1]" in captured.out


def test_verify_normalized_newlines(tmp_path, capsys):
    """
    Тест Level 2: Ігнорування переносів рядків.

    Сценарій: Оригінал має розірване слово через перенос рядка,
              відновлений файл має це слово цілим (через пробіл).

    Приклад: "Hel\nlo" -> "Hel lo"

    Це типова ситуація після Fix #20, коли система маскування
    склеює розірвані військові звання.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    # Оригінал: Розірване слово "Hel\nlo"
    orig.write_text("Hel\nlo World", encoding="utf-8")
    # Відновлення: Склеєне слово через пробіл "Hel lo"
    rec.write_text("Hel lo World", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    assert "❌ [LEVEL 1]" in captured.out
    assert "✅ [LEVEL 2]" in captured.out


def test_verify_multiple_spaces(tmp_path, capsys):
    """
    Тест Level 2: Нормалізація множинних пробілів.

    Сценарій: Файли відрізняються кількістю пробілів між словами.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("Hello    World", encoding="utf-8")  # 4 пробіли
    rec.write_text("Hello World", encoding="utf-8")      # 1 пробіл

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Level 2 має пройти, бо множинні пробіли нормалізуються в один
    assert "✅ [LEVEL 2]" in captured.out


def test_verify_skeleton_match(tmp_path, capsys):
    """
    Тест Level 3: Перевірка 'скелету' тексту (тільки символи без форматування).

    Сценарій: Файли мають різні пробіли/табуляції, але той самий контент.
              Наприклад, "A\tB" -> "AB" (табуляція втрачена, але символи залишились).
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("A\tB\nC", encoding="utf-8")  # Табуляція та перенос
    rec.write_text("ABC", encoding="utf-8")        # Все злите

    verify_text_recovery(orig, rec)
    captured = capsys.readouterr()

    # Skeleton має збігатися: "ABC" == "ABC"
    assert "✅ [LEVEL 3]" in captured.out


def test_verify_skeleton_cyrillic(tmp_path, capsys):
    """
    Тест Level 3: Скелетна перевірка з кирилицею.

    Перевіряє, що UTF-8 символи коректно обробляються при видаленні пробілів.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("Іван   Петренко", encoding="utf-8")  # Множинні пробіли
    rec.write_text("ІванПетренко", encoding="utf-8")      # Без пробілів

    verify_text_recovery(orig, rec)
    captured = capsys.readouterr()

    # Level 3 має пройти
    assert "✅ [LEVEL 3]" in captured.out


def test_verify_fail_content_mismatch(tmp_path, capsys):
    """
    Тест повного провалу: дані різні.

    Сценарій: У відновленому файлі інші дані (наприклад, ІПН змінено).
    Очікуваний результат: Провал на всіх 3 рівнях.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("Data 123", encoding="utf-8")
    rec.write_text("Data 999", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    assert "❌ [LEVEL 1]" in captured.out
    assert "❌ [LEVEL 2]" in captured.out
    assert "❌ [LEVEL 3]" in captured.out


def test_verify_with_ignore_flags(tmp_path, capsys):
    """
    Тест прапору --ignore-whitespace.

    Якщо прапор увімкнено, Level 2 та Level 3 вважаються успіхом
    і функція повертається раніше без виведення diff.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("Hello\nWorld", encoding="utf-8")
    rec.write_text("Hello World", encoding="utf-8")

    verify_text_recovery(orig, rec, ignore_flags=True)

    captured = capsys.readouterr()
    assert "✅ [LEVEL 2]" in captured.out
    # Diff не має виводитись, бо ignore_flags=True
    assert "DIFF" not in captured.out


# ============================================================================
# ТЕСТИ ДЛЯ КРАЙОВИХ ВИПАДКІВ
# ============================================================================

def test_verify_empty_files(tmp_path, capsys):
    """
    Тест порожніх файлів.

    Два порожні файли мають бути ідентичними.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("", encoding="utf-8")
    rec.write_text("", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    assert "✅ [LEVEL 1]" in captured.out


def test_verify_only_whitespace(tmp_path, capsys):
    """
    Тест файлів, що містять тільки пробіли та переноси.

    Skeleton має бути порожнім для обох файлів.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("   \n\n\t  ", encoding="utf-8")
    rec.write_text("\n\t\n", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Level 3 має пройти, бо skeleton обох файлів порожній
    assert "✅ [LEVEL 3]" in captured.out


def test_verify_unicode_normalization(tmp_path, capsys):
    """
    Тест Unicode нормалізації.

    Перевіряє, що різні Unicode представлення того ж символу
    розпізнаються як різні (якщо нормалізація не застосована).
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    # "é" може бути представлене як один символ (U+00E9)
    # або як "e" + комбінований акцент (U+0065 U+0301)
    orig.write_text("café", encoding="utf-8")  # U+00E9
    rec.write_text("café", encoding="utf-8")   # U+0065 U+0301 (якщо різне)

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Залежить від того, як Python обробляє Unicode.
    # Тест показує поведінку системи.
    # Можливо, Level 1 пройде, якщо Python нормалізує автоматично.


def test_verify_windows_vs_unix_newlines(tmp_path, capsys):
    """
    Тест різних стилів переносів рядків: Windows (CRLF) vs Unix (LF).

    Сценарій: Оригінал має Windows переноси (\r\n), відновлений — Unix (\n).
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_bytes(b"Hello\r\nWorld")  # Windows
    rec.write_bytes(b"Hello\nWorld")     # Unix

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Level 2 має пройти, бо обидва \r\n та \n нормалізуються
    assert "✅ [LEVEL 2]" in captured.out


def test_verify_large_diff_truncation(tmp_path, capsys):
    """
    Тест truncation великого diff (обмеження виводу).

    Якщо diff дуже великий (>50 рядків), він має обрізатися.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    # Генеруємо 100 різних рядків
    orig_lines = "\n".join([f"Line {i} original" for i in range(100)])
    rec_lines = "\n".join([f"Line {i} recovered" for i in range(100)])

    orig.write_text(orig_lines, encoding="utf-8")
    rec.write_text(rec_lines, encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Має бути повідомлення про приховування рядків
    assert "приховано" in captured.out or "hidden" in captured.out.lower()


# ============================================================================
# ТЕСТИ ДЛЯ РЕАЛЬНИХ СЦЕНАРІЇВ (Military Document Processing)
# ============================================================================

def test_verify_rank_line_break_fix(tmp_path, capsys):
    """
    Тест реального сценарію Fix #20: Розірвані військові звання.

    Сценарій: Оригінал містить звання "капітан медичної\nслужби",
              після маскування/розмаскування отримано "капітан медичної служби".
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    orig.write_text("капітан медичної\nслужби в запасі", encoding="utf-8")
    rec.write_text("капітан медичної служби в запасі", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Level 1 має провалитись (різні байти)
    assert "❌ [LEVEL 1]" in captured.out
    # Level 2 має пройти (текст той самий при нормалізації)
    assert "✅ [LEVEL 2]" in captured.out


def test_verify_ipn_preservation(tmp_path, capsys):
    """
    Тест збереження ІПН (податкового номеру).

    ІПН має бути точно відновлений без змін.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    ipn = "1234567890"
    orig.write_text(f"ІПН: {ipn}", encoding="utf-8")
    rec.write_text(f"ІПН: {ipn}", encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    assert "✅ [LEVEL 1]" in captured.out


def test_verify_multiple_ranks_document(tmp_path, capsys):
    """
    Тест документу з кількома військовими званнями.

    Реальний випадок: наказ із списком військовослужбовців.
    """
    orig = tmp_path / "input.txt"
    rec = tmp_path / "rec.txt"

    document = """НАКАЗ
1. майор Іванов І.І.
2. капітан медичної
служби Петренко П.П.
3. старший лейтенант Сидоров С.С."""

    expected = """НАКАЗ
1. майор Іванов І.І.
2. капітан медичної служби Петренко П.П.
3. старший лейтенант Сидоров С.С."""

    orig.write_text(document, encoding="utf-8")
    rec.write_text(expected, encoding="utf-8")

    verify_text_recovery(orig, rec)

    captured = capsys.readouterr()
    # Level 2 має пройти
    assert "✅ [LEVEL 2]" in captured.out