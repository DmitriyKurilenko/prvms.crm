"""Расчёт следующего вхождения повторяющейся задачи по RRULE (RFC 5545).

Изолирует внешний `python-dateutil`. Контракт сверён с установленной версией
2.9.0: `rrulestr("RRULE:…", dtstart=due)` парсит правило с явным началом серии,
`.after(dt, inc=False)` возвращает следующее вхождение строго после `dt` либо
`None`, если серия исчерпана (UNTIL/COUNT). Окончание серии несёт сама RRULE-
строка, поэтому отдельного поля даты окончания нет.
"""
from __future__ import annotations

from datetime import datetime

from dateutil.rrule import rrulestr


def next_occurrence(due_date: datetime | None, recurrence_rule: str) -> datetime | None:
    """Следующее вхождение после `due_date` или None (нет повтора / серия исчерпана)."""
    if not due_date or not recurrence_rule:
        return None
    try:
        rule = rrulestr(f'RRULE:{recurrence_rule}', dtstart=due_date)
    except (ValueError, TypeError):
        # Некорректная RRULE-строка не должна ронять закрытие задачи.
        return None
    return rule.after(due_date, inc=False)
