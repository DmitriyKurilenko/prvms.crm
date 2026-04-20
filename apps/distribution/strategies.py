from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from django.utils import timezone

from apps.integrations.models import ManagerProfile
from .models import DistributionLog


class DistributionStrategy(Protocol):
    def choose_manager(
        self,
        candidates: list[ManagerProfile],
        context: dict,
        config: dict,
    ) -> tuple[ManagerProfile | None, str]:
        ...


def _is_available(manager: ManagerProfile) -> bool:
    if not manager.is_active:
        return False
    today = timezone.localdate()
    return not manager.days_off.filter(date=today).exists()


def _available(candidates: list[ManagerProfile]) -> list[ManagerProfile]:
    return [m for m in candidates if _is_available(m)]


@dataclass
class MinLoadStrategy:
    """Assigns the lead to a manager with the least recent load."""

    def choose_manager(self, candidates, context, config):
        available = _available(candidates)
        if not available:
            return None, 'No available managers'

        period_days = int(config.get('period_days', 7))
        since = timezone.now() - timedelta(days=period_days)

        ranked = []
        for manager in available:
            load = DistributionLog.objects.filter(
                assigned_to=manager,
                created_at__gte=since,
            ).count()
            ranked.append((load, manager))
        ranked.sort(key=lambda item: (item[0], item[1].id))
        load, manager = ranked[0]
        return manager, f'min_load: load={load} period_days={period_days}'


@dataclass
class RoundRobinStrategy:
    """Simple cyclic assignment among available managers."""

    def choose_manager(self, candidates, context, config):
        available = sorted(_available(candidates), key=lambda m: m.id)
        if not available:
            return None, 'No available managers'

        last_index = int(config.get('last_assigned_index', -1))
        next_index = (last_index + 1) % len(available)
        manager = available[next_index]
        config['last_assigned_index'] = next_index
        return manager, f'round_robin: index={next_index}'


@dataclass
class WeightedStrategy:
    """Weighted assignment using deficit against expected quota."""

    def choose_manager(self, candidates, context, config):
        available = _available(candidates)
        if not available:
            return None, 'No available managers'

        weights = config.get('manager_weights') or {}
        period_days = int(config.get('period_days', 7))
        since = timezone.now() - timedelta(days=period_days)

        normalized = []
        for manager in available:
            weight = float(weights.get(str(manager.id), 1.0))
            normalized.append((manager, max(weight, 0.01)))
        total_weight = sum(weight for _, weight in normalized)
        total_assigned = DistributionLog.objects.filter(created_at__gte=since).count()

        best = None
        best_deficit = None
        for manager, weight in normalized:
            current = DistributionLog.objects.filter(
                assigned_to=manager,
                created_at__gte=since,
            ).count()
            expected = (weight / total_weight) * max(total_assigned, 1)
            deficit = expected - current
            if best is None or deficit > best_deficit:
                best = manager
                best_deficit = deficit
        return best, f'weighted: deficit={best_deficit:.2f}'


@dataclass
class ManualQueueStrategy:
    """Leaves entity unassigned for manual pickup."""

    def choose_manager(self, candidates, context, config):
        return None, 'manual_queue: awaiting manual pickup'


STRATEGIES: dict[str, type[DistributionStrategy]] = {
    'min_load': MinLoadStrategy,
    'round_robin': RoundRobinStrategy,
    'weighted': WeightedStrategy,
    'manual_queue': ManualQueueStrategy,
}
