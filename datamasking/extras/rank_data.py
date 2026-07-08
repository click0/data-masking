# -*- coding: utf-8 -*-
"""
Ре-експорт кореневого rank_data.py.

Історично тут лежала повна копія даних звань, яка могла розійтися
з кореневою. Канонічне джерело — rank_data.py у корені проєкту
(modules/__init__.py тягне security/cryptography, тому залежність
у зворотний бік зробила б cryptography обов'язковою).
"""

from datamasking.rank_data import *  # noqa: F401,F403
from datamasking.rank_data import _DECLENSION_FORMS_LIST  # noqa: F401
