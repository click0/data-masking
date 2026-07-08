#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести shim-ів зворотної сумісності (v3.0).

Історичні пласкі шляхи імпорту (masking, unmasking, modules, rank_data)
мають: працювати, видавати DeprecationWarning та повертати ТІ САМІ
об'єкти модулів, що й нові шляхи datamasking.* (єдиний стан).
"""
import importlib
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _fresh_import(name):
    """Імпорт з чистого аркуша: скидає модуль і його підмодулі з sys.modules."""
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            del sys.modules[key]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module(name)
    dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    return module, dep_warnings


class TestDeprecationWarnings:
    @pytest.mark.parametrize("name", ["masking", "unmasking", "modules", "rank_data"])
    def test_old_path_warns(self, name):
        _, dep_warnings = _fresh_import(name)
        assert dep_warnings, f"import {name} не видав DeprecationWarning"
        assert "datamasking" in str(dep_warnings[0].message)


class TestSameModuleObjects:
    """Старий і новий шляхи мають вести до одного об'єкта модуля."""

    def test_masking_submodules_identity(self):
        import masking.constants
        import datamasking.masking.constants as new_constants
        assert masking.constants is new_constants

    def test_live_flags_single_state(self):
        # Критично: MASK_* прапорці мають один стан через обидва шляхи
        import masking.constants as old_cfg
        import datamasking.masking.constants as new_cfg
        original = new_cfg.MASK_NAMES
        try:
            new_cfg.MASK_NAMES = not original
            assert old_cfg.MASK_NAMES == (not original)
        finally:
            new_cfg.MASK_NAMES = original

    def test_unmasking_submodules_identity(self):
        import unmasking.engine
        import datamasking.unmasking.engine as new_engine
        assert unmasking.engine is new_engine

    def test_modules_submodules_identity(self):
        import modules.tools
        import datamasking.extras.tools as new_tools
        assert modules.tools is new_tools

    def test_rank_data_identity(self):
        module, _ = _fresh_import("rank_data")
        import datamasking.rank_data as new_rank_data
        assert module is new_rank_data


class TestOldImportForms:
    """Документовані у README форми імпорту працюють як раніше."""

    def test_from_modules_tools(self):
        from modules.tools import mask_ipn_direct, mask_rank_direct, mask_pib_force
        assert callable(mask_ipn_direct)
        assert callable(mask_rank_direct)
        assert callable(mask_pib_force)

    def test_from_modules_re_mask(self):
        from modules.re_mask import ReMasker, MappingChain
        assert ReMasker is not None
        assert MappingChain is not None

    def test_from_masking_engine(self):
        from masking.engine import mask_text_context_aware
        assert callable(mask_text_context_aware)

    def test_from_unmasking_engine(self):
        from unmasking.engine import unmask_text_v2
        assert callable(unmask_text_v2)

    def test_from_rank_data_star_names(self):
        module, _ = _fresh_import("rank_data")
        # Підкреслені імена теж доступні (re-export через sys.modules)
        assert hasattr(module, "RANKS_LIST")
        assert hasattr(module, "RANK_DECLENSIONS")
        assert hasattr(module, "_DECLENSION_FORMS_LIST")

    def test_wrappers_importable(self):
        import data_masking
        import unmask_data
        assert data_masking.__version__ == unmask_data.__version__

    def test_versions_consistent_everywhere(self):
        import data_masking
        import datamasking
        import masking
        assert data_masking.__version__ == datamasking.__version__ == masking.__version__


class TestMappingVersionDetection:
    """Mapping-файли всіх поколінь розпізнаються правильною логікою.

    Регресія, спіймана при переході на 3.0: версія mapping "3.x" падала
    у v1-логіку (аналогічний баг був для 2.3+ до v2.6.x).
    """

    @pytest.mark.parametrize("version,expected", [
        ("1.0.0", "v1"),
        ("2.0.1", "v2.0"),
        ("2.1.0", "v2.1"),
        ("2.6.10", "v2.1"),
        ("3.0.0.dev1", "v2.1"),
        ("3.0.0", "v2.1"),
        ("3.2.7", "v2.1"),
        ("v2.5.0", "v2.1"),
        ("garbage", "v1"),
    ])
    def test_version_detection(self, version, expected):
        from datamasking.unmasking.helpers import check_mapping_version
        assert check_mapping_version({"version": version}) == expected

    def test_missing_version_is_v1(self):
        from datamasking.unmasking.helpers import check_mapping_version
        assert check_mapping_version({}) == "v1"
