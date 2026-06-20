<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="manager?.name || 'Менеджер'"
    modal
    style="width: 520px"
  >
    <template v-if="manager">
      <div style="display: flex; flex-direction: column; gap: 14px">
        <div>
          <label class="field-label">Макс. одновременных сделок</label>
          <PInputNumber v-model="form.max_active_deals" :min="1" :max="999" style="width: 100%" />
        </div>

        <div>
          <label class="field-label">Рабочие дни</label>
          <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 4px">
            <PButton v-for="(dayLabel, dayKey) in weekDays" :key="dayKey"
              :label="dayLabel" size="small"
              :outlined="!form.schedule.working_days?.includes(dayKey)"
              @click="$emit('toggleWorkingDay', dayKey)" />
          </div>
        </div>

        <div style="display: flex; gap: 12px">
          <div style="flex: 1">
            <label class="field-label">Начало</label>
            <PInputText v-model="form.schedule.start_time" placeholder="09:00" style="width: 100%" />
          </div>
          <div style="flex: 1">
            <label class="field-label">Конец</label>
            <PInputText v-model="form.schedule.end_time" placeholder="18:00" style="width: 100%" />
          </div>
        </div>

        <div>
          <label class="field-label" style="margin-bottom: 6px; display: block">Выходные / отпуска</label>
          <div v-for="d in manager.days_off" :key="d.id" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; font-size: 0.9em">
            <span>{{ d.date }}</span>
            <span style="color: var(--text-muted)">{{ d.reason }}</span>
            <PButton icon="pi pi-times" text size="small" severity="danger" @click="$emit('removeDayOff', d.id)" />
          </div>
          <div style="display: flex; gap: 8px; align-items: flex-end; margin-top: 6px">
            <PInputText v-model="newDayOff.date" placeholder="2026-05-01" style="width: 140px" />
            <PInputText v-model="newDayOff.reason" placeholder="Причина" style="flex: 1" />
            <PButton icon="pi pi-plus" size="small" @click="$emit('addDayOff')" :disabled="!newDayOff.date" />
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px">
        <PButton label="Отмена" text @click="$emit('update:visible', false)" />
        <PButton label="Сохранить" @click="$emit('save')" />
      </div>
    </template>
  </PDialog>
</template>

<script setup lang="ts">
/**
 * Презентационный диалог настройки менеджера (лимит сделок, расписание,
 * выходные). Реактивные form/newDayOff и логика сохранения/добавления
 * остаются в родителе (TeamView) — компонент только отображает и эмитит
 * действия. Перенос 1:1.
 */
defineProps<{
  visible: boolean
  manager: any
  form: { max_active_deals: number; schedule: Record<string, any> }
  newDayOff: { date: string; reason: string }
  weekDays: Record<string, string>
}>()

defineEmits<{
  'update:visible': [boolean]
  toggleWorkingDay: [string]
  addDayOff: []
  removeDayOff: [number]
  save: []
}>()
</script>

<style scoped>
.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 4px;
}
</style>
