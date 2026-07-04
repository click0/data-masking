#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести маскування значень у лапках («...», "...", „...“).

Значення, обгорнуте в лапки (ПІБ, звання+ПІБ, ІПН), має маскуватись,
а самі лапки — лишатись на місці. Roundtrip має відновлювати оригінал.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_initials import mask
from unmasking.engine import unmask_text_v2
from unmasking.helpers import check_mapping_version


QUOTED_CASES = [
    'капітан «Петренко Іван Сергійович»',
    'сержант "Коваленко Марія Іванівна"',
    'майор „Сидоренко Олег Петрович“',
    'ІПН «2817863534» видано',
    'старший сержант «Іваненко Андрій Вікторович» отримав',
]


class TestQuotedMasking:
    @pytest.mark.parametrize("text", QUOTED_CASES)
    def test_quoted_value_is_masked(self, text):
        masked, _ = mask(text)
        assert masked != text, f"Значення в лапках не замасковано: {text!r}"

    @pytest.mark.parametrize("text", QUOTED_CASES)
    def test_quotes_preserved(self, text):
        # Кількість лапкових символів не змінюється
        masked, _ = mask(text)
        for q in '«»„“”"':
            assert masked.count(q) == text.count(q), (
                f"Лапка {q!r} втрачена/додана: {text!r} -> {masked!r}"
            )

    @pytest.mark.parametrize("text", QUOTED_CASES)
    def test_roundtrip(self, text):
        masked, md = mask(text)
        restored, _ = unmask_text_v2(masked, md, check_mapping_version(md))
        assert restored == text, (
            f"Roundtrip провалено:\n  {text!r}\n  -> {masked!r}\n  <- {restored!r}"
        )

    def test_pib_original_not_leaked(self):
        masked, _ = mask('капітан «Петренко Іван Сергійович»')
        assert 'Петренко' not in masked
        assert 'Сергійович' not in masked

    def test_matches_unquoted_behaviour(self):
        # ПІБ у лапках і без них маскується однаково детерміновано
        a, _ = mask('Петренко Іван Сергійович')
        b, _ = mask('«Петренко Іван Сергійович»')
        assert b == '«' + a + '»'


class TestServiceMarkers:
    """ПІБ маскується, коли перед ним стоять службові мітки/шум
    ("ПІБ:", "ІПН=…", лог-формати), а не сам ПІБ."""

    def test_label_pib_colon(self):
        masked, _ = mask('ПІБ: Петренко Іван Васильович')
        assert 'Петренко' not in masked
        assert masked.startswith('ПІБ: ')  # мітка лишається

    def test_data_ipn_log_line(self):
        line = ('[WARNING] data-ipn: ІПН=3698521592 — ПІБ «138» → '
                '«Міронов Андрій Петрович» (джерело data-ipn головне)')
        masked, md = mask(line)
        assert 'Міронов' not in masked
        assert '3698521592' not in masked  # ІПН теж
        from unmasking.engine import unmask_text_v2
        restored, _ = unmask_text_v2(masked, md, check_mapping_version(md))
        assert restored == line

    def test_ipn_assignment_not_treated_as_name(self):
        # ІПН=NNNNNNNNNN не має ламати розпізнавання ПІБ далі в рядку
        masked, _ = mask('ІПН=1234567890 Петренко Іван Васильович')
        assert 'Петренко' not in masked
        assert '1234567890' not in masked
