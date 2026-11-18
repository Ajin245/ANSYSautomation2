# -*- coding: utf-8 -*-
"""Иерархическое слияние конфигов как чистая функция.

Источник смысла — ``v1/config/config_manager.py:139-160``. Отличия от v1:

* результат всегда новая структура (``copy.deepcopy``), поэтому вызывающий код
  не может случайно изменить базовый конфиг;
* ``override_config is None`` или пустой словарь тоже дают копию базы, а не
  саму базу (в v1 возвращался тот же объект);
* списки переопределяются целиком (как в v1), а не сливаются поэлементно —
  иначе настройки сетки и контактов перемешались бы по индексам.
"""

import copy


def merge_configs(base_config, override_config):
    """Рекурсивно накладывает ``override_config`` на ``base_config``.

    Словари сливаются по ключам, остальные значения (числа, строки, списки)
    замещаются значением из override. Обе входные структуры не меняются.

    Args:
        base_config (dict): базовый конфиг (может быть ``None``).
        override_config (dict): конфиг с приоритетом (может быть ``None``).

    Returns:
        dict: новый объединённый конфиг.
    """
    if base_config is None:
        base_config = {}

    merged = copy.deepcopy(base_config)
    if not override_config:
        return merged

    for key, value in override_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged
