from __future__ import annotations

from apps.crm.models import Activity, Deal


def backfill_closed_at() -> int:
    """Проставляет `closed_at` для won/lost сделок, у которых он пуст.

    До DEC-055 поле `closed_at` не велось, поэтому сделки, закрытые раньше,
    выпадают из периодной аналитики (`target-progress`, `loss-reasons`). Источник
    даты закрытия — последняя активность смены стадии (`stage_change`); если её
    нет — `updated_at` сделки. Идемпотентна: повторный вызов ничего не трогает,
    так как фильтрует только `closed_at IS NULL`.

    Возвращает число обновлённых сделок.
    """
    updated = 0
    qs = Deal.objects.filter(closed_at__isnull=True, stage__stage_type__in=['won', 'lost'])
    for deal in qs.iterator():
        last_move = (
            Activity.objects.filter(deal=deal, activity_type='stage_change')
            .order_by('-created_at')
            .first()
        )
        deal.closed_at = last_move.created_at if last_move else deal.updated_at
        deal.save(update_fields=['closed_at'])
        updated += 1
    return updated
