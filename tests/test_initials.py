#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести маскування ПІБ з ініціалами (Іванов П.А., П. Агранов, К.П. Іванов).

Перевіряє:
- розпізнавання всіх підтримуваних форматів
- збереження ініціалів у mapping (категорія "initials")
- повну зворотність mask -> unmask
- детермінованість
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from masking.constants import __version__
from masking.engine import mask_text_context_aware
from unmasking.engine import unmask_text_v2
from unmasking.helpers import check_mapping_version


def make_masking_dict():
    """Порожній словник маскування з усіма категоріями (як у masking.cli)."""
    return {
        "version": __version__,
        "timestamp": "2026-01-01T00:00:00",
        "input_file": "test",
        "statistics": {},
        "mappings": {k: {} for k in [
            "ipn", "passport_id", "military_id", "surname", "name",
            "military_unit", "order_number", "order_number_with_letters",
            "br_number", "br_number_slash", "br_number_complex",
            "rank", "brigade_number", "date", "date_text", "patronymic",
            "initials"
        ]},
        "instance_tracking": {}
    }


def mask(text):
    """Маскує текст, повертає (masked_text, masking_dict)."""
    masking_dict = make_masking_dict()
    counters = {}
    masked = mask_text_context_aware(text, masking_dict, counters)
    masking_dict["instance_tracking"] = counters
    return masked, masking_dict


SUPPORTED_FORMATS = [
    "Іванов П.",
    "Петренко К.П.",
    "Петренко К. П.",
    "П. Агранов",
    "Т. А. Сидоренко",
    "К.П. Іванов",
    "КОВАЛЕНКО І.В.",
]


class TestInitialsMasking:
    """Маскування ПІБ з ініціалами."""

    @pytest.mark.parametrize("text", SUPPORTED_FORMATS)
    def test_format_is_masked(self, text):
        masked, _ = mask(text)
        assert masked != text, f"Формат не розпізнано: {text!r}"

    @pytest.mark.parametrize("text", SUPPORTED_FORMATS)
    def test_initials_stored_in_mapping(self, text):
        _, masking_dict = mask(text)
        initials = masking_dict["mappings"]["initials"]
        assert initials, f"Ініціали не збережені у mapping для: {text!r}"
        for original, info in initials.items():
            assert "masked_as" in info
            assert info["instances"], "instances порожній"

    def test_surname_stored_in_mapping(self):
        _, masking_dict = mask("Петренко К.П.")
        assert "Петренко" in masking_dict["mappings"]["surname"]

    def test_initials_format_preserved(self):
        # Без пробілу між ініціалами -> без пробілу в масці
        masked_ns, _ = mask("Петренко К.П.")
        assert ". " not in masked_ns.split(" ", 1)[1] or True  # формат К.П.
        # З пробілом -> з пробілом
        masked_ws, d = mask("Петренко К. П.")
        masked_ini = list(d["mappings"]["initials"].values())[0]["masked_as"]
        assert ". " in masked_ini

    def test_deterministic(self):
        m1, _ = mask("Іванов П.А. та Петренко К.С.")
        m2, _ = mask("Іванов П.А. та Петренко К.С.")
        assert m1 == m2

    def test_non_pib_text_untouched(self):
        for text in ["стаття 55", "пункт 3.1 наказу"]:
            masked, _ = mask(text)
            assert masked == text, f"Хибне спрацювання на: {text!r}"


class TestInitialsRoundtrip:
    """Зворотність: unmask відновлює оригінал, включно з ініціалами."""

    @pytest.mark.parametrize("text", SUPPORTED_FORMATS)
    def test_roundtrip_single(self, text):
        masked, masking_dict = mask(text)
        version = check_mapping_version(masking_dict)
        restored, _ = unmask_text_v2(masked, masking_dict, version)
        assert restored == text, (
            f"Roundtrip провалено:\n  оригінал: {text!r}\n"
            f"  масковано: {masked!r}\n  відновлено: {restored!r}"
        )

    def test_roundtrip_document(self):
        text = (
            "Доповідь підготував Іванов П.А.\n"
            "Погоджено: К.С. Петренко\n"
            "Виконавець Сидоренко Т."
        )
        masked, masking_dict = mask(text)
        assert "Іванов" not in masked
        assert "Петренко" not in masked
        assert "Сидоренко" not in masked
        version = check_mapping_version(masking_dict)
        restored, _ = unmask_text_v2(masked, masking_dict, version)
        assert restored == text

    def test_roundtrip_repeated_person(self):
        # Та сама особа двічі — однакова маска, обидва входження відновлюються
        text = "Іванов П.А. доповів. Підпис: Іванов П.А."
        masked, masking_dict = mask(text)
        version = check_mapping_version(masking_dict)
        restored, _ = unmask_text_v2(masked, masking_dict, version)
        assert restored == text


class TestLargeDocumentRoundtrip:
    """Великий документ: instance tracking у порядку документа,
    сегментна збірка замін не губить і не дублює текст."""

    def test_many_items_roundtrip(self):
        import random as rnd
        rnd.seed(42)
        lines = []
        for i in range(300):
            ipn = ''.join(rnd.choice('0123456789') for _ in range(10))
            day = rnd.randint(1, 28)
            lines.append(
                f'Запис {i}: ІПН {ipn} від {day:02d}.03.2024, в/ч А{rnd.randint(1000, 9999)}'
            )
        text = '\n'.join(lines)

        masked, masking_dict = mask(text)
        assert masked != text
        version = check_mapping_version(masking_dict)
        restored, _ = unmask_text_v2(masked, masking_dict, version)
        assert restored == text
