#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Password Generator Module v2.3.0
Генератор паролів з підтримкою ASCII, кирилиці та кастомних символів.
Використання як модуль:
    from password_generator import generate_password, PasswordConfig

    # Простий виклик
    password = generate_password()

    # З налаштуваннями
    password = generate_password(length=32, include_cyrillic_lower=True)

    # З конфігом
    config = PasswordConfig(length=24, include_cyrillic_upper=True)
    password = generate_password_from_config(config)
Використання як CLI:
    python password_generator.py
    python password_generator.py --length 32
    python password_generator.py --cyrillic
    python password_generator.py --no-special --length 16
    python password_generator.py --only-digits --length 8
    python password_generator.py --custom "€£¥§±²³"
Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.3.0
License: BSD 3-Clause "New" or "Revised" License
Year: 2025
"""
import secrets
import string
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Union
__version__ = "2.3.0"
__author__ = "Vladyslav V. Prodan"
# =============================================================================
# КОНСТАНТИ
# =============================================================================
# Українська кирилиця (33 літери + Ґ)
CYRILLIC_UPPER = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
CYRILLIC_LOWER = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
# Стандартні спецсимволи
DEFAULT_SPECIAL_CHARS = "!@#$%^&*_+-="
# =============================================================================
# КОНФІГУРАЦІЯ
# =============================================================================
@dataclass
class PasswordConfig:
    """Конфігурація генерації пароля."""

    # Довжина пароля
    length: int = 24

    # ASCII символи
    include_ascii_upper: bool = True    # A-Z (26 символів)
    include_ascii_lower: bool = True    # a-z (26 символів)
    include_digits: bool = True         # 0-9 (10 символів)
    include_special: bool = True        # Спеціальні символи
    special_chars: str = DEFAULT_SPECIAL_CHARS

    # Кирилиця (українська)
    include_cyrillic_upper: bool = False  # А-ЯІЇЄҐ (34 символи)
    include_cyrillic_lower: bool = False  # а-яіїєґ (34 символи)

    # Додаткові символи
    custom_chars: str = ""              # Будь-які Unicode символи

    # Поведінка
    auto_generate: bool = True
    show_generated: bool = True

    # Гарантувати наявність символів кожного типу
    ensure_variety: bool = True

    def get_charset_info(self) -> Dict[str, Any]:
        """Повертає інформацію про набір символів."""
        info: Dict[str, Any] = {
            'total_chars': 0,
            'components': [],
            'entropy_bits': 0.0,
            'bits_per_char': 0.0
        }

        if self.include_ascii_upper:
            info['components'].append(('ASCII upper (A-Z)', 26))
            info['total_chars'] += 26
        if self.include_ascii_lower:
            info['components'].append(('ASCII lower (a-z)', 26))
            info['total_chars'] += 26
        if self.include_digits:
            info['components'].append(('Digits (0-9)', 10))
            info['total_chars'] += 10
        if self.include_special and self.special_chars:
            info['components'].append(('Special', len(self.special_chars)))
            info['total_chars'] += len(self.special_chars)
        if self.include_cyrillic_upper:
            info['components'].append(('Cyrillic upper (А-Я)', len(CYRILLIC_UPPER)))
            info['total_chars'] += len(CYRILLIC_UPPER)
        if self.include_cyrillic_lower:
            info['components'].append(('Cyrillic lower (а-я)', len(CYRILLIC_LOWER)))
            info['total_chars'] += len(CYRILLIC_LOWER)
        if self.custom_chars:
            info['components'].append(('Custom', len(self.custom_chars)))
            info['total_chars'] += len(self.custom_chars)

        # Розрахунок ентропії
        if info['total_chars'] > 0:
            import math
            bits_per_char: float = math.log2(info['total_chars'])
            info['entropy_bits'] = round(bits_per_char * self.length, 1)
            info['bits_per_char'] = round(bits_per_char, 2)

        return info
# =============================================================================
# ГЕНЕРАЦІЯ ПАРОЛЯ
# =============================================================================
def generate_password(
    length: int = 24,
    include_ascii_upper: bool = True,
    include_ascii_lower: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
    special_chars: str = DEFAULT_SPECIAL_CHARS,
    include_cyrillic_upper: bool = False,
    include_cyrillic_lower: bool = False,
    custom_chars: str = "",
    ensure_variety: bool = True
) -> str:
    """
    Генерує криптографічно безпечний пароль.

    Args:
        length: Довжина пароля (default: 24)
        include_ascii_upper: Включати A-Z (default: True)
        include_ascii_lower: Включати a-z (default: True)
        include_digits: Включати 0-9 (default: True)
        include_special: Включати спецсимволи (default: True)
        special_chars: Набір спецсимволів (default: "!@#$%^&*_+-=")
        include_cyrillic_upper: Включати А-ЯІЇЄҐ (default: False)
        include_cyrillic_lower: Включати а-яіїєґ (default: False)
        custom_chars: Додаткові символи (default: "")
        ensure_variety: Гарантувати наявність символів кожного типу (default: True)

    Returns:
        str: Згенерований пароль

    Examples:
        # Стандартний ASCII пароль
        pwd = generate_password()

        # Пароль з кирилицею
        pwd = generate_password(include_cyrillic_lower=True)

        # Тільки цифри (PIN)
        pwd = generate_password(length=8, include_ascii_upper=False,
                                include_ascii_lower=False, include_special=False)
    """
    # Формуємо набір символів та список обов'язкових наборів
    charset = ""
    required_charsets: List[str] = []

    if include_ascii_upper:
        charset += string.ascii_uppercase
        required_charsets.append(string.ascii_uppercase)

    if include_ascii_lower:
        charset += string.ascii_lowercase
        required_charsets.append(string.ascii_lowercase)

    if include_digits:
        charset += string.digits
        required_charsets.append(string.digits)

    if include_special and special_chars:
        charset += special_chars
        required_charsets.append(special_chars)

    if include_cyrillic_upper:
        charset += CYRILLIC_UPPER
        required_charsets.append(CYRILLIC_UPPER)

    if include_cyrillic_lower:
        charset += CYRILLIC_LOWER
        required_charsets.append(CYRILLIC_LOWER)

    if custom_chars:
        charset += custom_chars
        required_charsets.append(custom_chars)

    # Fallback якщо нічого не вибрано
    if not charset:
        charset = string.ascii_letters + string.digits
        required_charsets = [string.ascii_uppercase, string.ascii_lowercase, string.digits]

    # Генеруємо базовий пароль
    password_list = [secrets.choice(charset) for _ in range(length)]

    # Гарантуємо наявність символів кожного типу (якщо довжина дозволяє)
    if ensure_variety:
        positions_used = set()
        for req_charset in required_charsets:
            if len(positions_used) >= length:
                break
            # Знаходимо позицію, яка ще не використана
            attempts = 0
            while attempts < length * 2:
                pos = secrets.randbelow(length)
                if pos not in positions_used:
                    password_list[pos] = secrets.choice(req_charset)
                    positions_used.add(pos)
                    break
                attempts += 1

    return ''.join(password_list)
def generate_password_from_config(config: PasswordConfig) -> Optional[str]:
    """
    Генерує пароль за налаштуваннями з конфігурації.

    Args:
        config: Об'єкт PasswordConfig

    Returns:
        str: Згенерований пароль або None якщо auto_generate=False
    """
    if not config.auto_generate:
        return None

    return generate_password(
        length=config.length,
        include_ascii_upper=config.include_ascii_upper,
        include_ascii_lower=config.include_ascii_lower,
        include_digits=config.include_digits,
        include_special=config.include_special,
        special_chars=config.special_chars,
        include_cyrillic_upper=config.include_cyrillic_upper,
        include_cyrillic_lower=config.include_cyrillic_lower,
        custom_chars=config.custom_chars,
        ensure_variety=config.ensure_variety
    )
def generate_passwords(
    count: int = 1,
    length: int = 24,
    include_ascii_upper: bool = True,
    include_ascii_lower: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
    special_chars: str = DEFAULT_SPECIAL_CHARS,
    include_cyrillic_upper: bool = False,
    include_cyrillic_lower: bool = False,
    custom_chars: str = "",
    ensure_variety: bool = True
) -> List[str]:
    """
    Генерує список криптографічно безпечних паролів.

    Args:
        count: Кількість паролів для генерації (default: 1)
        length: Довжина кожного пароля (default: 24)
        include_ascii_upper: Включати A-Z (default: True)
        include_ascii_lower: Включати a-z (default: True)
        include_digits: Включати 0-9 (default: True)
        include_special: Включати спецсимволи (default: True)
        special_chars: Набір спецсимволів (default: "!@#$%^&*_+-=")
        include_cyrillic_upper: Включати А-ЯІЇЄҐ (default: False)
        include_cyrillic_lower: Включати а-яіїєґ (default: False)
        custom_chars: Додаткові символи (default: "")
        ensure_variety: Гарантувати наявність символів кожного типу (default: True)

    Returns:
        List[str]: Список згенерованих паролів

    Examples:
        # Один пароль (як список)
        passwords = generate_passwords(count=1)

        # 10 паролів
        passwords = generate_passwords(count=10)

        # 5 PIN-кодів
        passwords = generate_passwords(
            count=5,
            length=4,
            include_ascii_upper=False,
            include_ascii_lower=False,
            include_special=False
        )
    """
    if count < 1:
        count = 1

    return [
        generate_password(
            length=length,
            include_ascii_upper=include_ascii_upper,
            include_ascii_lower=include_ascii_lower,
            include_digits=include_digits,
            include_special=include_special,
            special_chars=special_chars,
            include_cyrillic_upper=include_cyrillic_upper,
            include_cyrillic_lower=include_cyrillic_lower,
            custom_chars=custom_chars,
            ensure_variety=ensure_variety
        )
        for _ in range(count)
    ]
# =============================================================================
# УТИЛІТИ
# =============================================================================
def calculate_entropy(charset_size: int, length: int) -> float:
    """
    Розраховує ентропію пароля в бітах.

    Args:
        charset_size: Розмір набору символів
        length: Довжина пароля

    Returns:
        float: Ентропія в бітах
    """
    import math
    if charset_size <= 0:
        return 0.0
    return math.log2(charset_size) * length
def estimate_crack_time(entropy_bits: float, guesses_per_second: float = 1e12) -> str:
    """
    Оцінює час на brute-force атаку.

    Args:
        entropy_bits: Ентропія в бітах
        guesses_per_second: Кількість спроб на секунду (default: 1 трильйон)

    Returns:
        str: Людино-читабельний час
    """
    total_combinations = 2 ** entropy_bits
    seconds = total_combinations / guesses_per_second / 2  # В середньому половина

    if seconds < 60:
        return f"{seconds:.1f} секунд"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} хвилин"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f} годин"
    elif seconds < 31536000:
        return f"{seconds / 86400:.1f} днів"
    elif seconds < 31536000 * 1000:
        return f"{seconds / 31536000:.1f} років"
    elif seconds < 31536000 * 1e6:
        return f"{seconds / 31536000 / 1000:.1f} тисяч років"
    elif seconds < 31536000 * 1e9:
        return f"{seconds / 31536000 / 1e6:.1f} мільйонів років"
    else:
        return f"{seconds / 31536000 / 1e9:.1e} мільярдів років"
def password_strength(password: str) -> dict:
    """
    Аналізує силу пароля.

    Args:
        password: Пароль для аналізу

    Returns:
        dict: Інформація про силу пароля
    """
    has_upper = any(c in string.ascii_uppercase for c in password)
    has_lower = any(c in string.ascii_lowercase for c in password)
    has_digit = any(c in string.digits for c in password)
    has_special = any(c in DEFAULT_SPECIAL_CHARS for c in password)
    has_cyrillic = any(c in CYRILLIC_UPPER + CYRILLIC_LOWER for c in password)

    # Оцінка розміру charset
    charset_size = 0
    if has_upper:
        charset_size += 26
    if has_lower:
        charset_size += 26
    if has_digit:
        charset_size += 10
    if has_special:
        charset_size += len(DEFAULT_SPECIAL_CHARS)
    if has_cyrillic:
        charset_size += len(CYRILLIC_UPPER) + len(CYRILLIC_LOWER)

    entropy = calculate_entropy(charset_size, len(password))

    # Оцінка сили
    if entropy < 40:
        strength = "Дуже слабкий"
    elif entropy < 60:
        strength = "Слабкий"
    elif entropy < 80:
        strength = "Середній"
    elif entropy < 100:
        strength = "Сильний"
    elif entropy < 128:
        strength = "Дуже сильний"
    else:
        strength = "Надзвичайно сильний"

    return {
        'length': len(password),
        'charset_size': charset_size,
        'entropy_bits': round(entropy, 1),
        'strength': strength,
        'crack_time': estimate_crack_time(entropy),
        'has_uppercase': has_upper,
        'has_lowercase': has_lower,
        'has_digits': has_digit,
        'has_special': has_special,
        'has_cyrillic': has_cyrillic
    }
# =============================================================================
# CLI
# =============================================================================
def main():
    """CLI інтерфейс для генерації паролів."""
    parser = argparse.ArgumentParser(
        description="Генератор криптографічно безпечних паролів",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Приклади:
  %(prog)s                          # Стандартний пароль (24 символи)
  %(prog)s -n 5                     # 5 паролів
  %(prog)s --length 32              # Довжина 32 символи
  %(prog)s --cyrillic               # З кирилицею
  %(prog)s --no-special             # Без спецсимволів
  %(prog)s --only-digits -l 8       # PIN з 8 цифр
  %(prog)s --custom "€£¥"           # З кастомними символами
  %(prog)s --analyze "MyPassword"   # Аналіз існуючого пароля
"""
    )

    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('-n', '--count', type=int, default=1, metavar='N',
                        help='Кількість паролів (default: 1)')
    parser.add_argument('-l', '--length', type=int, default=24,
                        help='Довжина пароля (default: 24)')

    # Символи
    parser.add_argument('--no-upper', action='store_true',
                        help='Без великих ASCII літер (A-Z)')
    parser.add_argument('--no-lower', action='store_true',
                        help='Без малих ASCII літер (a-z)')
    parser.add_argument('--no-digits', action='store_true',
                        help='Без цифр (0-9)')
    parser.add_argument('--no-special', action='store_true',
                        help='Без спецсимволів')
    parser.add_argument('--special-chars', default=DEFAULT_SPECIAL_CHARS,
                        help='Набір спецсимволів (default: !@#$%%^&*_+-=)')

    # Кирилиця
    parser.add_argument('--cyrillic', action='store_true',
                        help='Додати кирилицю (upper + lower)')
    parser.add_argument('--cyrillic-upper', action='store_true',
                        help='Додати кирилицю upper (А-Я)')
    parser.add_argument('--cyrillic-lower', action='store_true',
                        help='Додати кирилицю lower (а-я)')

    # Кастомні
    parser.add_argument('--custom', default='', metavar='CHARS',
                        help='Додаткові символи (напр. "€£¥§")')

    # Пресети
    parser.add_argument('--only-digits', action='store_true',
                        help='Тільки цифри (PIN-style)')
    parser.add_argument('--only-alpha', action='store_true',
                        help='Тільки літери (без цифр та спецсимволів)')

    # Аналіз
    parser.add_argument('--analyze', metavar='PASSWORD',
                        help='Аналізувати існуючий пароль')

    # Вивід
    parser.add_argument('--info', action='store_true',
                        help='Показати інформацію про charset та ентропію')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Тільки пароль, без додаткової інформації')

    args = parser.parse_args()

    # Аналіз існуючого пароля
    if args.analyze:
        info = password_strength(args.analyze)
        print(f"\n{'=' * 50}")
        print(f"АНАЛІЗ ПАРОЛЯ")
        print(f"{'=' * 50}")
        print(f"Пароль: {args.analyze}")
        print(f"Довжина: {info['length']}")
        print(f"Charset: ~{info['charset_size']} символів")
        print(f"Ентропія: {info['entropy_bits']} біт")
        print(f"Сила: {info['strength']}")
        print(f"Час на brute-force: {info['crack_time']}")
        print(f"\nСклад:")
        print(f"  • Великі літери (A-Z): {'✓' if info['has_uppercase'] else '✗'}")
        print(f"  • Малі літери (a-z): {'✓' if info['has_lowercase'] else '✗'}")
        print(f"  • Цифри (0-9): {'✓' if info['has_digits'] else '✗'}")
        print(f"  • Спецсимволи: {'✓' if info['has_special'] else '✗'}")
        print(f"  • Кирилиця: {'✓' if info['has_cyrillic'] else '✗'}")
        print(f"{'=' * 50}\n")
        return

    # Визначаємо налаштування
    include_ascii_upper = not args.no_upper
    include_ascii_lower = not args.no_lower
    include_digits = not args.no_digits
    include_special = not args.no_special
    include_cyrillic_upper = args.cyrillic or args.cyrillic_upper
    include_cyrillic_lower = args.cyrillic or args.cyrillic_lower

    # Пресети
    if args.only_digits:
        include_ascii_upper = False
        include_ascii_lower = False
        include_special = False
        include_cyrillic_upper = False
        include_cyrillic_lower = False

    if args.only_alpha:
        include_digits = False
        include_special = False

    # Створюємо конфіг для інформації
    config = PasswordConfig(
        length=args.length,
        include_ascii_upper=include_ascii_upper,
        include_ascii_lower=include_ascii_lower,
        include_digits=include_digits,
        include_special=include_special,
        special_chars=args.special_chars,
        include_cyrillic_upper=include_cyrillic_upper,
        include_cyrillic_lower=include_cyrillic_lower,
        custom_chars=args.custom
    )

    # Показуємо інформацію
    if args.info and not args.quiet:
        info = config.get_charset_info()
        print(f"\n{'=' * 50}")
        print(f"НАЛАШТУВАННЯ ГЕНЕРАЦІЇ")
        print(f"{'=' * 50}")
        print(f"Довжина: {args.length}")
        print(f"Charset: {info['total_chars']} символів")
        print(f"Ентропія: {info['entropy_bits']} біт")
        print(f"Біт на символ: {info['bits_per_char']}")
        print(f"\nКомпоненти:")
        for name, count in info['components']:
            print(f"  • {name}: {count}")
        print(f"{'=' * 50}\n")

    # Генеруємо паролі
    passwords = generate_passwords(
        count=args.count,
        length=args.length,
        include_ascii_upper=include_ascii_upper,
        include_ascii_lower=include_ascii_lower,
        include_digits=include_digits,
        include_special=include_special,
        special_chars=args.special_chars,
        include_cyrillic_upper=include_cyrillic_upper,
        include_cyrillic_lower=include_cyrillic_lower,
        custom_chars=args.custom
    )

    # Виводимо
    if args.quiet:
        for pwd in passwords:
            print(pwd)
    else:
        if args.count == 1:
            print(f"\n🔐 Згенерований пароль:\n   {passwords[0]}\n")
        else:
            print(f"\n🔐 Згенеровані паролі ({args.count}):")
            for i, pwd in enumerate(passwords, 1):
                print(f"   [{i}] {pwd}")
            print()
if __name__ == "__main__":
    main()
