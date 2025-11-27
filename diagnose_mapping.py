#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Діагностика, порівняння маппінгів та верифікація відновлення тексту.

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025

Цей скрипт є інструментом контролю якості (QA) для системи маскування.
Він виконує три основні функції:

1. 🔎 Верифікація тексту (Verify):
   Порівнює оригінальний файл (input.txt) з відновленим (input_recovery.txt).
   Використовує трирівневу логіку перевірки, щоб ігнорувати зміни форматування,
   викликані склеюванням розірваних рядків.

2. ⚖️  Перевірка маппінгів (Diff):
   Порівнює два файли JSON маппінгу для виявлення "дрейфу" (Drift Check).
   Це дозволяє переконатися, що детермінована генерація працює коректно
   (однаковий вхід завжди дає однакову маску).

3. 📊 Структурний аналіз:
   Перевіряє версію формату маппінгу (v1, v2.0, v2.1) та наявність статистики.
"""

import json
import sys
import argparse
import difflib
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# ============================================================================
# ⚙️ ГЛОБАЛЬНІ НАЛАШТУВАННЯ ТА КОНСТАНТИ
# ============================================================================

# Список директорій, де скрипт автоматично шукатиме файли результатів
SEARCH_DIRS = [Path('.'), Path('output'), Path('result')]

# Глибина пошуку історії файлів (скільки останніх файлів сканувати)
HISTORY_SEARCH_LIMIT = 20

# Налаштування візуалізації (ширина таблиць та ліміти виводу)
SEPARATOR_WIDTH = 96
DIFF_LINE_LIMIT = 50

# Формати рядків для таблиць (f-strings templates)
FMT_FILE_HEADER = "{:<10} | {:<40} | {:<8} | {:<20}"
FMT_CAT_ROW     = "{:<30} | {:<12} | {:<12} | {:<10} | {:<15}"


# ============================================================================
# БЛОК 1: РОБОТА З JSON MAPPING (Аналіз та порівняння)
# ============================================================================

def find_latest_maps(n_files: int = 2) -> List[Path]:
    """
    Знаходить N останніх файлів masking_map_*.json у робочих директоріях.

    Args:
        n_files: Кількість файлів для пошуку (хоча повертає всі знайдені).

    Returns:
        List[Path]: Список шляхів, відсортований за часом зміни (найновіші перші).
    """
    candidates = []
    for d in SEARCH_DIRS:
        if d.exists():
            candidates.extend(d.glob("masking_map_*.json"))
    # Сортування: новіші файли (більший mtime) йдуть першими
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return candidates


def load_json(path: Path) -> Optional[Dict]:
    """
    Безпечне завантаження JSON файлу з обробкою помилок.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Помилка читання JSON {path}: {e}")
        return None


def analyze_category_structure(category_name: str, items: Dict[str, Any]) -> Dict[str, Any]:
    """
    Аналізує внутрішню структуру категорії (наприклад, 'rank' або 'surname').

    Визначає версію формату даних:
    - v1: проста пара "ключ": "значення"
    - v2.0: словник "ключ": {"masked_as": "...", "gender": "..."}
    - v2.1: словник з instance tracking {"instances": [1, 2]}

    Returns:
        Dict зі статистикою та версією формату.
    """
    if not items:
        return {"count": 0, "format": "empty", "has_instances": False}

    # Беремо перший елемент для визначення структури всієї категорії
    first_value = list(items.values())[0]

    if isinstance(first_value, str):
        return {
            "count": len(items),
            "format": "v1",
            "structure": "original -> string",
            "has_instances": False
        }
    elif isinstance(first_value, dict):
        has_instances = "instances" in first_value

        # Збір статистики колізій (скільки разів маска повторюється)
        all_instances = [len(v.get("instances", [])) for v in items.values() if isinstance(v, dict)]
        instance_stats = {
            "total_instances": sum(all_instances),
            "max_instances": max(all_instances) if all_instances else 0
        } if has_instances else {}

        return {
            "count": len(items),
            "format": "v2.1" if has_instances else "v2.0",
            "structure": "original -> dict",
            "has_instances": has_instances,
            "instance_stats": instance_stats
        }
    return {"count": len(items), "format": "unknown", "has_instances": False}


def compare_mappings(file1: Path, file2: Path) -> None:
    """
    Порівнює два JSON файли маппінгу (Drift Check).

    Перевіряє, чи змінилося значення маски для однакових ключів.
    Якщо 'Іванов' у файлі А став 'Петренко', а у файлі Б — 'Сидоренко',
    це означає порушення детермінованості (різний seed або алгоритм хешування).
    """
    print("=" * SEPARATOR_WIDTH)
    print("⚖️  ПОРІВНЯННЯ ФАЙЛІВ МАППІНГУ (DIFF)")
    print("=" * SEPARATOR_WIDTH)

    data1 = load_json(file1)
    data2 = load_json(file2)

    if not data1 or not data2:
        return

    # Отримання метаданих
    t1 = datetime.fromtimestamp(file1.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    t2 = datetime.fromtimestamp(file2.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')

    # Вивід таблиці файлів
    print("\n" + FMT_FILE_HEADER.format('Файл', 'Шлях', 'Версія', 'Створено'))
    print("-" * SEPARATOR_WIDTH)
    print(FMT_FILE_HEADER.format('A (New)', str(file1.name), data1.get('version','?'), t1))
    print(FMT_FILE_HEADER.format('B (Old)', str(file2.name), data2.get('version','?'), t2))

    map1 = data1.get("mappings", {})
    map2 = data2.get("mappings", {})
    all_cats = sorted(set(map1.keys()) | set(map2.keys()))

    # Вивід таблиці категорій
    print(f"\n{'─' * SEPARATOR_WIDTH}")
    print("📊 СТАТИСТИКА ПО КАТЕГОРІЯХ")
    print(f"{'─' * SEPARATOR_WIDTH}")
    print(FMT_CAT_ROW.format('Категорія', 'A Кількість', 'B Кількість', 'Різниця', 'Змінені маски'))
    print("-" * SEPARATOR_WIDTH)

    total_drift = 0

    for cat in all_cats:
        items1 = map1.get(cat, {})
        items2 = map2.get(cat, {})

        count1 = len(items1)
        count2 = len(items2)
        diff = count1 - count2
        diff_str = f"+{diff}" if diff > 0 else str(diff)

        # --- DRIFT CHECK ---
        # Перевіряємо тільки спільні ключі
        drift_count = 0
        common_keys = set(items1.keys()) & set(items2.keys())
        for key in common_keys:
            # Нормалізація для порівняння v1 та v2
            val1 = items1[key]["masked_as"] if isinstance(items1[key], dict) else items1[key]
            val2 = items2[key]["masked_as"] if isinstance(items2[key], dict) else items2[key]
            if val1 != val2:
                drift_count += 1

        drift_str = f"⚠️ {drift_count}" if drift_count > 0 else "✓ 0"
        total_drift += drift_count

        print(FMT_CAT_ROW.format(cat, count1, count2, diff_str, drift_str))

    print(f"\n{'=' * SEPARATOR_WIDTH}")
    if total_drift > 0:
        print(f"⚠️  УВАГА: Знайдено {total_drift} випадків зміни маски для тих самих даних!")
        print("   Це означає, що детермінованість порушена (або змінено seed/hash/алгоритм).")
    else:
        print("✅ Маски стабільні (для спільних ключів значення однакові).")


def diagnose_single_file(map_path: str) -> None:
    """
    Виводить детальну інформацію про один файл маппінгу без порівняння.
    Використовується, коли в історії знайдено лише один файл.
    """
    map_file = Path(map_path)
    if not map_file.exists():
        print(f"❌ ПОМИЛКА: Файл не знайдено: {map_file}")
        return

    print("=" * 80)
    print("📋 ДІАГНОСТИКА MASKING MAP")
    print("=" * 80)
    print(f"\n📂 Файл: {map_file}")

    data = load_json(map_file)
    if not data: return

    print(f"🔢 Версія:      {data.get('version', 'N/A')}")
    print(f"🕐 Timestamp:   {data.get('timestamp', 'N/A')}")

    mappings = data.get("mappings", {})
    print(f"\n{'─' * 80}")
    print("📁 КАТЕГОРІЇ")
    print(f"{'─' * 80}")

    for category_name in sorted(mappings.keys()):
        items = mappings[category_name]
        analysis = analyze_category_structure(category_name, items)
        print(f"\n  📦 {category_name.upper()}")
        print(f"     Елементів:  {analysis['count']}")
        print(f"     Формат:     {analysis.get('format')}")
        if analysis.get("has_instances"):
            stats = analysis.get("instance_stats", {})
            print(f"     ✓ Instance tracking: {stats.get('total_instances', 0)} посилань")


# ============================================================================
# БЛОК 2: ВЕРИФІКАЦІЯ ТЕКСТУ (Recovered vs Original)
# ============================================================================

def find_original_and_recovery() -> tuple[Optional[Path], Optional[Path]]:
    """
    Шукає пару файлів для перевірки: input.txt та найсвіжіший input_recovery_*.txt.
    """
    original = Path("input.txt")
    if not original.exists():
        original = Path("output/input.txt")

    recovery_candidates = []
    for d in SEARCH_DIRS:
        if d.exists():
            recovery_candidates.extend(d.glob("input_recovery_*.txt"))

    recovery_candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    latest_recovery = recovery_candidates[0] if recovery_candidates else None

    return (original if original.exists() else None), latest_recovery


def verify_text_recovery(original_path: Path, recovery_path: Path, ignore_flags: bool = False) -> None:
    """
    Порівнює оригінальний та відновлений тексти з використанням 3 рівнів перевірки.

    Рівні:
    1. Strict: Файли ідентичні байт-в-байт.
    2. Normalized: Ігнорування переносів рядків (заміна \n на пробіл) та нормалізація пробілів.
       Це потрібно, бо скрипт маскування може "склеювати" розірвані звання (Fix #20).
    3. Skeleton: Ігнорування всього форматування (видалення всіх пробілів). Перевіряє лише дані.

    Args:
        original_path: Шлях до оригіналу.
        recovery_path: Шлях до відновленого файлу.
        ignore_flags: Якщо True, "м'які" перевірки (Level 2, 3) вважаються успіхом.
    """
    print("=" * SEPARATOR_WIDTH)
    print("🔎 ВЕРИФІКАЦІЯ ВІДНОВЛЕННЯ ТЕКСТУ")
    print("=" * SEPARATOR_WIDTH)
    print(f"📄 Оригінал:   {original_path}")
    print(f"📄 Відновлено: {recovery_path}")
    print("-" * SEPARATOR_WIDTH)

    try:
        with open(original_path, 'r', encoding='utf-8') as f1, \
                open(recovery_path, 'r', encoding='utf-8') as f2:
            content_orig = f1.read()
            content_rec = f2.read()

            # Перемотуємо на початок для генерації diff
            f1.seek(0)
            f2.seek(0)
            lines_orig = f1.readlines()
            lines_rec = f2.readlines()
    except Exception as e:
        print(f"❌ Помилка читання файлів: {e}")
        return

    # --- РІВЕНЬ 1: Strict ---
    if content_orig == content_rec:
        print("\n✅ [LEVEL 1] Файли ідентичні (Byte-to-byte match).")
        return

    print("\n❌ [LEVEL 1] Сувора перевірка не пройшла. Файли мають відмінності.")

    # --- РІВЕНЬ 2: Normalized Newlines ---
    # Логіка: Замінюємо всі переноси рядків на один пробіл.
    # Потім схлопуємо множинні пробіли в один.
    orig_norm = re.sub(r'[\n\r]+', ' ', content_orig)
    rec_norm = re.sub(r'[\n\r]+', ' ', content_rec)

    orig_norm = re.sub(r'\s+', ' ', orig_norm).strip()
    rec_norm = re.sub(r'\s+', ' ', rec_norm).strip()

    if orig_norm == rec_norm:
        lines_diff = len(lines_orig) - len(lines_rec)
        print("✅ [LEVEL 2] Текст збігається при ігноруванні переносів рядків.")
        print(f"   📉 В оригіналі: {len(lines_orig)} рядків")
        print(f"   📈 Відновлено:  {len(lines_rec)} рядків")

        if lines_diff > 0:
            print(f"   ✂️  Склеєно (втрачено) переносів: {lines_diff}")
        elif lines_diff < 0:
            print(f"   ➕ Додано зайвих переносів: {abs(lines_diff)}")

        if ignore_flags: return
    else:
        print("❌ [LEVEL 2] Перевірка без переносів рядків не пройшла.")

        # Діагностика для Level 2: показати першу розбіжність
        limit_len = min(len(orig_norm), len(rec_norm))
        diff_idx = -1
        for i in range(limit_len):
            if orig_norm[i] != rec_norm[i]:
                diff_idx = i
                break

        if diff_idx != -1:
            print(f"   🔍 Перша розбіжність нормалізованого тексту на позиції {diff_idx}:")
            start_show = max(0, diff_idx - 20)
            end_show = min(limit_len, diff_idx + 20)

            # Безпечний вивід (заміна спецсимволів на крапку)
            safe_orig = orig_norm[start_show:end_show].replace('\n', ' ')
            safe_rec = rec_norm[start_show:end_show].replace('\n', ' ')

            print(f"   Orig: ...{safe_orig}...")
            print(f"   Rec:  ...{safe_rec}...")
            print(f"            {' ' * (diff_idx - start_show)}^")

    # --- РІВЕНЬ 3: Skeleton ---
    # Видаляємо ВЗАГАЛІ всі whitespace. Перевірка тільки контенту (букви, цифри).
    skeleton_orig = "".join(content_orig.split())
    skeleton_rec = "".join(content_rec.split())

    if skeleton_orig == skeleton_rec:
        print("✅ [LEVEL 3] 'Скелет' тексту збігається (дані збережені, форматування втрачено).")
        if ignore_flags: return
    else:
        print("❌ [LEVEL 3] Перевірка 'скелету' не пройшла. Втрачено або змінено дані!")

    # Генерація Diff
    print(f"\n{'─' * SEPARATOR_WIDTH}")
    print("📝 DIFF (Деталі розбіжностей)")
    print(f"{'─' * SEPARATOR_WIDTH}")

    diff = difflib.unified_diff(
        lines_orig,
        lines_rec,
        fromfile='Original',
        tofile='Recovered',
        lineterm=''
    )

    diff_lines = list(diff)

    if not diff_lines:
        print("   (Difflib не зміг візуалізувати різницю)")
    else:
        for i, line in enumerate(diff_lines):
            if i >= DIFF_LINE_LIMIT:
                print(f"\n... ще {len(diff_lines) - DIFF_LINE_LIMIT} рядків приховано ...")
                break
            if line.startswith('+'):
                print(f"\033[92m{line.rstrip()}\033[0m") # Зелений
            elif line.startswith('-'):
                print(f"\033[91m{line.rstrip()}\033[0m") # Червоний
            else:
                print(line.rstrip())


# ============================================================================
# MAIN (Точка входу)
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Утиліта діагностики, порівняння маппінгів та верифікації тексту.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("files", nargs="*", help="Шляхи до .json файлів або число (для порівняння з історією)")
    parser.add_argument("--ignore-whitespace", action="store_true",
                        help="При верифікації вважати успіхом, якщо різниця тільки в пробілах")

    args = parser.parse_args()

    # ----------------------------------------------------------
    # ЕТАП 1: ВЕРИФІКАЦІЯ ТЕКСТУ
    # Запускається автоматично, якщо знайдені потрібні файли
    # ----------------------------------------------------------
    orig, rec = find_original_and_recovery()
    if orig and rec:
        verify_text_recovery(orig, rec, args.ignore_whitespace)
        print("\n\n")
    elif not orig:
        print("ℹ️  input.txt не знайдено. Верифікацію тексту пропущено.\n")
    elif not rec:
        print("ℹ️  input_recovery_*.txt не знайдено. Верифікацію тексту пропущено.\n")

    # ----------------------------------------------------------
    # ЕТАП 2: АНАЛІЗ ТА ПОРІВНЯННЯ МАППІНГІВ
    # ----------------------------------------------------------
    files_input = args.files
    latest_maps = find_latest_maps(HISTORY_SEARCH_LIMIT)

    target_file_a = None
    target_file_b = None
    mode = "single"

    if len(files_input) == 0:
        # АВТОМАТИЧНИЙ РЕЖИМ: Порівняти останній (0) з передостаннім (1)
        if len(latest_maps) < 2:
            if latest_maps:
                diagnose_single_file(str(latest_maps[0]))
            else:
                print("❌ Файлів masking_map_*.json не знайдено.")
            return
        mode = "diff"
        target_file_a = latest_maps[0]
        target_file_b = latest_maps[1]

    elif len(files_input) == 1:
        arg = files_input[0]
        # Якщо аргумент число -> це зміщення в історії (наприклад, 2 = позаминулий файл)
        if arg.isdigit():
            idx = int(arg)
            if len(latest_maps) <= idx:
                print(f"❌ Недостатньо файлів історії для зміщення {idx}. Знайдено: {len(latest_maps)}.")
                return
            mode = "diff"
            target_file_a = latest_maps[0]
            target_file_b = latest_maps[idx]
        else:
            # Якщо аргумент шлях -> просто діагностика одного файлу
            diagnose_single_file(arg)
            return

    elif len(files_input) >= 2:
        # Явне порівняння двох вказаних файлів
        mode = "diff"
        target_file_a = Path(files_input[0])
        target_file_b = Path(files_input[1])

    if mode == "diff":
        print(f"🔍 Порівнюємо маппінги:\n A: {target_file_a}\n B: {target_file_b}")
        if not target_file_a.exists() or not target_file_b.exists():
            print("❌ Один з файлів маппінгу не існує.")
            return
        compare_mappings(target_file_a, target_file_b)

if __name__ == "__main__":
    main()
