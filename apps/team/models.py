"""Доменная модель команды тенанта.

Самостоятельный домен «команда»: профили менеджеров и их выходные. Не зависит
ни от CRM-интеграций, ни от распределения — наоборот, это они опираются на него.
Профиль привязан к `users.User` (shared-схема), сам же живёт в схеме тенанта.
"""
from django.db import models


class Manager(models.Model):
    """Профиль менеджера внутри тенанта: нагрузка, расписание, активность."""
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='+')
    display_name = models.CharField(max_length=200)
    max_active_deals = models.PositiveIntegerField(default=10)
    schedule = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name


class TimeOff(models.Model):
    """Выходной/отгул менеджера на конкретную дату."""
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE, related_name='days_off')
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.manager} — {self.date}'
