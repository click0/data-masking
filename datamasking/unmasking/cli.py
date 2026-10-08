#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI entry point for data unmasking.

Extracted from unmask_data.py during the package refactoring (v2.5.0).
"""

import json
import sys
import argparse
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from datamasking.unmasking.helpers import (
    validate_file_size, auto_find_latest_pair, check_mapping_version,
)
from datamasking.unmasking.engine import (
    unmask_text_v2, unmask_text_v1,
    unmask_json_recursive, unmask_chain, unmask_json_chain,
    is_chain_mapping,
    unmask_json_with_stats, unmask_json_chain_with_stats,
)
from datamasking.unmasking.io import (
    load_mapping_file, validate_mapping_schema, show_chain_info,
    SECURITY_AVAILABLE, REMASK_AVAILABLE,
)

# ============================================================================
# OPTIONAL MODULES
# ============================================================================

CONFIG_AVAILABLE = False
try:
    from datamasking.extras.config import ConfigLoader, format_ignored_keys_warning, is_strict
    CONFIG_AVAILABLE = True
except ImportError:
    import logging as _logging
    _logging.getLogger(__name__).debug("datamasking.extras.config not available — YAML config disabled")

LOGGING_AVAILABLE = False
try:
    from datamasking.extras.masking_logger import MaskingLogger, setup_logging
    LOGGING_AVAILABLE = True
except ImportError:
    import logging as _logging
    _logging.getLogger(__name__).debug("datamasking.extras.masking_logger not available — structured logging disabled")

# Re-mask (for --to-version and --chain-info CLI args)
try:
    from datamasking.extras.re_mask import ChainUnmasker, load_chain, get_chain_info
except ImportError:
    pass

# ============================================================================
# МЕТАДАНІ
# ============================================================================
from datamasking._version import __version__  # єдине джерело версії
from datamasking._textio import read_text, check_encoding_settings
from datamasking._fsutil import atomic_write_private
import random


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def _config_password(config) -> Optional[str]:
    """Пароль з конфігу — config може бути dict АБО Config-dataclass
    (раніше `config.get(...)` падав AttributeError на dataclass)."""
    if not config:
        return None
    if isinstance(config, dict):
        return config.get('password') or None
    security = getattr(config, 'security', None)
    return getattr(security, 'password', None) or getattr(config, 'password', None) or None


def _unmask_encoding(config, masking_map) -> Tuple[str, List[str]]:
    """(кодування, дозволені) для читання замаскованого файлу."""
    system = getattr(config, 'system', None) if not isinstance(config, dict) else None
    validation = getattr(config, 'validation', None) if not isinstance(config, dict) else None
    configured = str(getattr(system, 'encoding', 'utf-8') or 'utf-8')
    allowed_cfg = getattr(validation, 'allowed_encodings', None) or ("utf-8", "cp1251", "latin-1")
    from_map = masking_map.get("input_encoding") if isinstance(masking_map, dict) else None
    if configured.lower() in ("utf-8", "utf8") and from_map:
        configured = str(from_map)
    return check_encoding_settings(configured, allowed_cfg) if configured.lower() == "auto" else (
        check_encoding_settings(configured, list(allowed_cfg) + [configured]))


def _size_limit(config: Any) -> int:
    """Ліміт розміру файлу: менший із system.max_file_size_mb і
    validation.max_input_size_mb (до 3.1.10 unmask їх не читав)."""
    from datamasking.unmasking.helpers import MAX_INPUT_FILE_SIZE
    limit = MAX_INPUT_FILE_SIZE
    for section, key in (("system", "max_file_size_mb"), ("validation", "max_input_size_mb")):
        value = getattr(getattr(config, section, None), key, None)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            limit = min(limit, value * 1024 * 1024)
    return limit


def _expected_instances(masking_map: Dict) -> int:
    """Скільки входжень масок записано в mapping (для ланцюга — у всіх проходах)."""
    maps = masking_map.get("passes", [masking_map]) if is_chain_mapping(masking_map) else [masking_map]
    return sum(len(info.get("instances", []))
               for m in maps if isinstance(m, dict)
               for cat in m.get("mappings", {}).values() if isinstance(cat, dict)
               for info in cat.values() if isinstance(info, dict))


def main(argv=None) -> int:
    """
    Головна функція CLI для unmask. Повертає код виходу (0 — успіх, 1 — помилка).
    """
    # Fix Unicode output on Windows (PyInstaller cp1252 issue)
    if sys.platform == 'win32' and getattr(sys.stdout, 'encoding', 'utf-8').lower().replace('-', '') != 'utf8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    # ========================================================================
    # ПАРСИНГ АРГУМЕНТІВ
    # ========================================================================

    epilog_text = """
Examples:
  %(prog)s                                          # Auto mode
  %(prog)s output.txt --map masking_map.json        # Manual mode
  %(prog)s output.txt -o recovered.txt              # With output file
  %(prog)s output.txt --map map.enc --password pwd  # Encrypted mapping
  %(prog)s -c config.yaml                           # With config file
  %(prog)s output.txt --chain-info                  # Chain info
"""

    parser = argparse.ArgumentParser(
        description=f'Data Unmasking Script v{__version__}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_text
    )
    parser.add_argument('masked_file', nargs='?', help='Masked file path')
    parser.add_argument('--map', '-m', dest='map_file', help='Mapping file (.json or .enc)')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('-V', '--version', action='version',
                        version=f'%(prog)s {__version__}')

    if SECURITY_AVAILABLE:
        security_group = parser.add_argument_group('security options')
        security_group.add_argument('--password', help='Password for encrypted mapping files')
        security_group.add_argument('--password-env', metavar='VAR',
                                    help='Environment variable name containing password')

    if REMASK_AVAILABLE:
        remask_group = parser.add_argument_group('re-mask options')
        remask_group.add_argument('--to-version', metavar='N', type=int,
                                  help='Chain mapping only: unmask back to the state after pass N '
                                       '(0 = original; default = full restore)')
        remask_group.add_argument('--chain-info', action='store_true',
                                  help='Show chain mapping information and exit')

    if CONFIG_AVAILABLE:
        config_group = parser.add_argument_group('config options')
        config_group.add_argument('-c', '--config', metavar='FILE',
                                  help='Configuration file (.yaml or .json)')
        config_group.add_argument('--config-local', metavar='FILE',
                                  help='Private overrides on top of the configuration (default: '
                                       'config_local.yaml next to it and in the user config directory)')
        config_group.add_argument('--no-local-config', action='store_true',
                                  help='Ignore config_local.yaml files')

    parser.add_argument('--force', action='store_true',
                        help='Overwrite an existing output file')

    if LOGGING_AVAILABLE:
        log_group = parser.add_argument_group('logging options')
        log_group.add_argument('--log-level', default=None,
                               choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                               help='Logging level (default: INFO or logging.level from the configuration)')
        log_group.add_argument('--log-file', metavar='FILE',
                               help='Log file path')

    args = parser.parse_args(argv)

    # ========================================================================
    # ІНІЦІАЛІЗАЦІЯ ЛОГЕРА
    # ========================================================================

    # Логер створюється ПІСЛЯ читання конфігурації (logging.* звідти, v3.1.10);
    # повідомлення про саме завантаження конфігурації — у чергу
    logger = None
    cli_logging = getattr(args, 'log_level', None) is not None or getattr(args, 'log_file', None) is not None
    pending_logs: List[str] = []

    def log_info(msg):
        if logger:
            logger.info(msg)
        else:
            pending_logs.append(msg)

    def log_error(msg):
        if logger:
            logger.error(msg)

    def log_debug(msg):
        if logger:
            logger.debug(msg)

    # ========================================================================
    # ЗАВАНТАЖЕННЯ КОНФІГУРАЦІЇ
    # ========================================================================

    # Як і в маскуванні, конфігурація читається завжди: -c FILE, інакше
    # ./config.yaml / ./config.py, якщо є (до 3.0.27 — лише з -c, тож
    # security.password_env_var та інші спільні ключі для unmask не діяли)
    config: Any = {}
    if CONFIG_AVAILABLE:
        try:
            config_path = getattr(args, 'config', None)
            if config_path and not Path(config_path).exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")
            loader = ConfigLoader(config_path, local_path=getattr(args, 'config_local', None),
                                  use_local=not getattr(args, 'no_local_config', False))
            config = loader.load()
            source = loader.loaded_from or loader.ignored_source
            if source:
                log_info(f"Конфігурацію завантажено з {source}")
            for local in loader.local_loaded:
                log_info(f"Локальну конфігурацію завантажено з {local}")
            for notice in loader.notices:
                print(notice, file=sys.stderr)
            for ignored_source, keys in loader.ignored_by_source:
                warning = format_ignored_keys_warning(ignored_source, keys)
                if is_strict(config):
                    raise ValueError("strict_mode: " + warning.replace("Warning: ", "", 1))
                print(warning, file=sys.stderr)
        except (FileNotFoundError, PermissionError, ValueError, OSError) as e:
            print(f"❌ Помилка завантаження конфігурації: {e}")
            log_error(f"Помилка завантаження конфігурації: {e}")
            return EXIT_ERROR

    # Логер: прапорці CLI > logging.* з конфігурації > INFO у консоль
    # (до 3.1.10 unmask читав лише прапорці CLI)
    if LOGGING_AVAILABLE:
        log_cfg = getattr(config, 'logging', None) if not isinstance(config, dict) else None
        log_level = getattr(args, 'log_level', None) or 'INFO'
        log_file = getattr(args, 'log_file', None)
        console = True
        enabled = True
        if log_cfg is not None and not cli_logging:
            enabled = getattr(log_cfg, 'enabled', True) is not False
            log_level = str(getattr(log_cfg, 'level', None) or 'INFO').upper()
            if getattr(log_cfg, 'log_to_file', None) is not False:
                log_file = getattr(log_cfg, 'file', None)
            console = getattr(log_cfg, 'log_to_console', True) is not False
        if enabled:
            try:
                logger = setup_logging(level=log_level, log_file=log_file, console=console)
                logger.info(f"Data Unmasking Script v{__version__}")
                for msg in pending_logs:
                    logger.info(msg)
            except (ValueError, OSError, TypeError) as e:
                print(f"Warning: could not setup logging: {e}", file=sys.stderr)
        pending_logs.clear()

    # ========================================================================
    # ВИЗНАЧЕННЯ ПАРОЛЯ
    # ========================================================================

    password = None
    if SECURITY_AVAILABLE:
        if getattr(args, 'password', None):
            password = args.password
        elif getattr(args, 'password_env', None):
            password = os.environ.get(args.password_env, '')
            if not password:
                print(f"❌ Змінна оточення '{args.password_env}' не встановлена або порожня")
                log_error(f"Environment variable '{args.password_env}' is not set or empty")
                return EXIT_ERROR
        else:
            password = _config_password(config)
            # security.password_env_var / password_generation.env_var — назва
            # змінної з паролем (якщо відрізняється від DATA_MASKING_PASSWORD,
            # яку io.load_mapping перевіряє й так)
            if not password and not isinstance(config, dict):
                for candidate in (getattr(getattr(config, 'security', None), 'password_env_var', None),
                                  getattr(getattr(config, 'password_generation', None), 'env_var', None)):
                    if candidate and candidate != 'DATA_MASKING_PASSWORD':
                        password = os.environ.get(str(candidate), '') or None
                        break

    # ========================================================================
    # ЛОГІКА ПОШУКУ ТА ВИБОРУ ФАЙЛІВ
    # ========================================================================

    if not args.masked_file:
        result = auto_find_latest_pair()
        if result is None:
            return EXIT_ERROR
        masked_path, map_path, output_path = result
        log_info(f"Автоматичний режим: {masked_path.name}")
    else:
        masked_path = Path(args.masked_file)
        if not masked_path.exists():
            print(f"❌ Файл не знайдено: {masked_path}")
            log_error(f"Файл не знайдено: {masked_path}")
            return EXIT_ERROR

        if args.map_file:
            map_path = Path(args.map_file)
        else:
            filename = masked_path.stem
            if filename.startswith('output_'):
                map_path = masked_path.parent / f"masking_map_{filename[7:]}.json"
                # mapping або ланцюг (--re-mask), відкритий або шифрований (v3.1.10)
                for candidate in (f"masking_map_{filename[7:]}.enc", f"masking_chain_{filename[7:]}.json",
                                  f"masking_chain_{filename[7:]}.enc"):
                    if map_path.exists():
                        break
                    if (masked_path.parent / candidate).exists():
                        map_path = masked_path.parent / candidate
                        log_info(f"Знайдено mapping: {map_path.name}")
            else:
                print("❌ Будь ласка, вкажіть файл маппінгу через --map")
                log_error("Файл маппінгу не вказано")
                return EXIT_ERROR

        if not map_path.exists():
            print(f"❌ Файл маппінгу не знайдено: {map_path}")
            log_error(f"Файл маппінгу не знайдено: {map_path}")
            return EXIT_ERROR

        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Випадковий суфікс — паралельні запуски не перезаписують один одного
            output_path = masked_path.parent / f"input_recovery_{timestamp}_{random.randint(0, 999):03d}{masked_path.suffix}"

    # Вихідний файл не має збігатися із замаскованим чи mapping (до 3.1.10
    # «-o masking_map_X.json» знищував mapping) і не перезаписується без --force
    try:
        same_as = [p for p in (masked_path, map_path) if p.exists() and output_path.exists()
                   and os.path.samefile(output_path, p)]
    except OSError:
        same_as = []
    if same_as:
        print(f"❌ Вихідний файл збігається з {same_as[0]}")
        return EXIT_USAGE
    if output_path.exists() and not getattr(args, 'force', False):
        print(f"❌ Файл {output_path} уже існує (використайте --force для перезапису)")
        return EXIT_USAGE
    if output_path.is_dir():
        print(f"❌ {output_path} — каталог")
        return EXIT_USAGE

    # ========================================================================
    # ЗАВАНТАЖЕННЯ ФАЙЛІВ
    # ========================================================================

    try:
        masking_map = load_mapping_file(map_path, password=password)
        validate_mapping_schema(masking_map)
        log_info(f"Mapping завантажено: {map_path.name}")

        if REMASK_AVAILABLE and getattr(args, 'chain_info', False):
            show_chain_info(masking_map)
            return EXIT_OK

        to_version = getattr(args, 'to_version', None)
        if to_version is not None:
            # v2.5–3.0.6: викликало неіснуючий ChainUnmasker.convert_to_version
            # і падало TypeError — прапорець був мертвий
            if not is_chain_mapping(masking_map):
                print("❌ --to-version працює лише з chain mapping (--re-mask)")
                log_error("--to-version on a non-chain mapping")
                return EXIT_ERROR
            if to_version < 0 or to_version > len(masking_map.get("passes", [])):
                print(f"❌ --to-version має бути в межах 0..{len(masking_map.get('passes', []))}")
                return EXIT_ERROR

        validate_file_size(masked_path, max_size=_size_limit(config))
        # Кодування: з mapping (mask записує його, якщо вхід був не в utf-8);
        # system.encoding у конфігурації, якщо задано явно, має пріоритет
        file_encoding, allowed = _unmask_encoding(config, masking_map)
        masked_text, file_encoding = read_text(masked_path, file_encoding, allowed)
        if masked_path.suffix.lower() == '.json':
            masked_data = json.loads(masked_text)
        else:
            masked_data = masked_text

        log_debug(f"Замасковані дані завантажено: {masked_path.name}")

    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError,
            UnicodeDecodeError, ValueError, RuntimeError) as e:
        # ValueError: невалідна схема, неправильний пароль .enc, завеликий файл;
        # RuntimeError: немає cryptography для .enc
        print(f"❌ Помилка читання: {e}")
        log_error(f"Помилка читання: {e}")
        return EXIT_ERROR

    # ========================================================================
    # ПРОЦЕС UNMASK
    # ========================================================================

    start_time = time.time()

    if is_chain_mapping(masking_map):
        total_passes = masking_map.get("total_passes", len(masking_map["passes"]))
        print(f"🔄 Розмаскування {masked_path.name} (ланцюг з {total_passes} проходів)...")
        log_info(f"Розмаскування ланцюга з {total_passes} проходів")

        if masked_path.suffix.lower() == '.json':
            restored_data, stats = unmask_json_chain_with_stats(
                masked_data, masking_map, to_version=getattr(args, 'to_version', None) or 0)
        else:
            restored_data, stats = unmask_chain(masked_data, masking_map,
                                                to_version=getattr(args, 'to_version', None) or 0)
    else:
        map_version = check_mapping_version(masking_map)
        print(f"🔄 Розмаскування {masked_path.name} (логіка {map_version})...")
        log_info(f"Розмаскування {masked_path.name} (логіка {map_version})")

        if masked_path.suffix.lower() == '.json':
            restored_data, stats = unmask_json_with_stats(masked_data, masking_map, map_version)
        else:
            if map_version.startswith("v2"):
                restored_data, stats = unmask_text_v2(masked_data, masking_map, map_version)
            else:
                restored_data, stats = unmask_text_v1(masked_data, masking_map)

    # ========================================================================
    # ЗБЕРЕЖЕННЯ РЕЗУЛЬТАТУ
    # ========================================================================

    try:
        # Відновлений текст чутливіший за mapping: атомарно, 0600 (v3.1.10)
        out_text = json.dumps(restored_data, ensure_ascii=False, indent=2) \
            if masked_path.suffix.lower() == '.json' else restored_data
        atomic_write_private(output_path, out_text.encode(file_encoding))

        elapsed = time.time() - start_time
        print(f"✅ Готово! Збережено у: {output_path}")
        print(f"⏱️ Час виконання: {elapsed:.2f} сек")
        log_info(f"Збережено у: {output_path} ({elapsed:.2f} сек)")
        log_info(f"Статистика: відновлено={stats.get('restored_count', 0)}, "
                 f"пропущено={stats.get('skipped_count', 0)}")
        expected = _expected_instances(masking_map)
        if expected and stats.get('restored_count', 0) == 0:
            print("⚠️ Жодного значення не відновлено: mapping, схоже, не від цього файлу", file=sys.stderr)
            log_error("Nothing restored: the mapping does not seem to belong to this file")
        # strict_mode: файл записано, але не все відновлено — код виходу 1.
        # Не відновлено = входження з mapping, яких у тексті не знайдено
        # (для ланцюга — зайві входження масок; до 3.1.10 слово документа,
        # що збігалось із маскою, теж рахувалось як помилка)
        if CONFIG_AVAILABLE and not isinstance(config, dict) and is_strict(config):
            if is_chain_mapping(masking_map):
                unrestored = stats.get('skipped_count', 0)
            else:
                unrestored = max(0, expected - stats.get('restored_count', 0))
            if unrestored:
                print(f"❌ strict_mode: {unrestored} masked value(s) were not restored")
                log_error(f"strict_mode: {unrestored} masked value(s) were not restored")
                return EXIT_ERROR
        return EXIT_OK

    except (OSError, PermissionError, UnicodeEncodeError) as e:
        print(f"❌ Помилка збереження: {e}")
        log_error(f"Помилка збереження: {e}")
        return EXIT_ERROR
