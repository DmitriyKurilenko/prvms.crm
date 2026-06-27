<template>
  <FeatureGate feature="crm_builtin">
    <section class="calendar-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Календарь</h1>
        <div class="header-actions">
          <PButton
            v-if="isAdminOwner"
            :label="scope === 'mine' ? 'Мои задачи' : 'Все задачи'"
            :icon="scope === 'mine' ? 'pi pi-user' : 'pi pi-users'"
            size="small"
            outlined
            @click="toggleScope"
          />
          <PButton v-if="canEdit" label="Новая задача" icon="pi pi-plus" size="small" @click="openCreate()" />
        </div>
      </div>

      <div v-if="!canView" class="surface-card" style="padding: 14px;">
        У вас нет прав для просмотра задач.
      </div>

      <div v-else class="surface-card calendar-card">
        <FullCalendar ref="calendarRef" :options="calendarOptions" />
      </div>
    </section>

    <PDialog v-model:visible="showDialog" :header="form.id ? 'Задача' : 'Новая задача'" modal :style="{ width: '480px' }">
      <div class="form-grid">
        <div class="field">
          <label>Название</label>
          <PInputText v-model="form.title" placeholder="Что нужно сделать" />
        </div>
        <div class="field">
          <label>Срок</label>
          <input v-model="form.due_local" type="datetime-local" class="dt-input" />
        </div>
        <div class="field">
          <label>Повторение</label>
          <PSelect v-model="form.recurrence_preset" :options="recurrenceOptions" optionLabel="label" optionValue="value" />
        </div>
        <div v-if="form.recurrence_preset === 'custom'" class="field">
          <label>RRULE (RFC 5545)</label>
          <PInputText v-model="form.recurrence_custom" placeholder="FREQ=WEEKLY;BYDAY=MO,WE" />
        </div>
        <div class="field">
          <label>Напоминание</label>
          <PSelect v-model="form.remind_offset" :options="reminderOptions" optionLabel="label" optionValue="value" />
        </div>
      </div>
      <template #footer>
        <PButton v-if="form.id && form.status !== 'done'" label="Выполнено" icon="pi pi-check" text size="small" @click="markDone" />
        <PButton label="Отмена" text size="small" @click="showDialog = false" />
        <PButton :label="form.id ? 'Сохранить' : 'Создать'" size="small" :disabled="!form.title.trim() || !form.due_local" @click="save" />
      </template>
    </PDialog>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import type { CalendarOptions, EventClickArg, EventInput, DatesSetArg, EventDropArg } from '@fullcalendar/core'
import type { DateClickArg } from '@fullcalendar/interaction'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmCalendarTask } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('calendar')
const toast = useToast()
const authStore = useAuthStore()
const perms = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canView = computed(() => perms.value.deals.can_view)
const canEdit = computed(() => perms.value.deals.can_update)
const isAdminOwner = computed(() => ['owner', 'admin'].includes(authStore.user?.role || ''))
const scope = ref<'mine' | 'team'>('mine')

const recurrenceOptions = [
  { label: 'Не повторять', value: 'none' },
  { label: 'Ежедневно', value: 'FREQ=DAILY' },
  { label: 'Еженедельно', value: 'FREQ=WEEKLY' },
  { label: 'Ежемесячно', value: 'FREQ=MONTHLY' },
  { label: 'Другое (RRULE)…', value: 'custom' },
]
const reminderOptions = [
  { label: 'Без напоминания', value: 0 },
  { label: 'За 15 минут', value: 15 },
  { label: 'За 1 час', value: 60 },
  { label: 'За 1 день', value: 1440 },
]

const tasks = ref<CrmCalendarTask[]>([])
const calendarRef = ref<InstanceType<typeof FullCalendar> | null>(null)

function statusClass(status: string): string {
  if (status === 'done') return 'fc-task-done'
  if (status === 'overdue') return 'fc-task-overdue'
  return 'fc-task-planned'
}

const events = computed<EventInput[]>(() =>
  tasks.value
    .filter((t) => t.due_date)
    .map((t) => ({
      id: String(t.id),
      title: scope.value === 'team' && t.responsible_name ? `${t.responsible_name}: ${t.title}` : t.title,
      start: t.due_date as string,
      allDay: false,
      classNames: [statusClass(t.status)],
      extendedProps: { task: t },
    })),
)

async function loadRange(fromISO: string, toISO: string) {
  if (!canView.value) return
  try {
    tasks.value = await crmApi.calendarActivities(fromISO.slice(0, 10), toISO.slice(0, 10), scope.value)
  } catch (err) {
    log.error('Failed to load calendar', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить календарь', life: 5000 })
  }
}

const calendarOptions = reactive<CalendarOptions>({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  firstDay: 1,
  height: 'auto',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay',
  },
  buttonText: { today: 'Сегодня', month: 'Месяц', week: 'Неделя', day: 'День' },
  events: events as unknown as EventInput[],
  editable: true,
  datesSet: (arg: DatesSetArg) => loadRange(arg.startStr, arg.endStr),
  dateClick: (arg: DateClickArg) => openCreate(arg.dateStr),
  eventClick: (arg: EventClickArg) => openEdit(arg.event.extendedProps.task as CrmCalendarTask),
  eventDrop: (arg: EventDropArg) => onEventDrop(arg),
})

async function onEventDrop(arg: EventDropArg) {
  if (!canEdit.value || !arg.event.start) {
    arg.revert()
    return
  }
  try {
    await crmApi.patchActivity(Number(arg.event.id), { due_date: arg.event.start.toISOString() })
  } catch (err) {
    log.error('Failed to reschedule task', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось перенести задачу', life: 5000 })
    arg.revert()
  }
}

function toggleScope() {
  scope.value = scope.value === 'mine' ? 'team' : 'mine'
  refreshCurrentRange()
}

const showDialog = ref(false)
const form = reactive({
  id: null as number | null,
  title: '',
  due_local: '',
  status: 'planned',
  recurrence_preset: 'none',
  recurrence_custom: '',
  remind_offset: 0,
})

function toLocalInput(iso: string): string {
  // ISO → 'YYYY-MM-DDTHH:mm' в локальном времени для datetime-local
  const d = new Date(iso)
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16)
}

function defaultDue(dateStr?: string): string {
  const base = dateStr ? new Date(`${dateStr}T09:00:00`) : new Date()
  const off = base.getTimezoneOffset()
  return new Date(base.getTime() - off * 60000).toISOString().slice(0, 16)
}

function openCreate(dateStr?: string) {
  if (!canEdit.value) return
  form.id = null
  form.title = ''
  form.due_local = defaultDue(dateStr)
  form.status = 'planned'
  form.recurrence_preset = 'none'
  form.recurrence_custom = ''
  form.remind_offset = 0
  showDialog.value = true
}

function presetFromRule(rule: string): string {
  if (!rule) return 'none'
  if (['FREQ=DAILY', 'FREQ=WEEKLY', 'FREQ=MONTHLY'].includes(rule)) return rule
  return 'custom'
}

function openEdit(task: CrmCalendarTask) {
  form.id = task.id
  form.title = task.title
  form.due_local = task.due_date ? toLocalInput(task.due_date) : ''
  form.status = task.status
  form.recurrence_preset = presetFromRule(task.recurrence_rule)
  form.recurrence_custom = form.recurrence_preset === 'custom' ? task.recurrence_rule : ''
  // вычисляем смещение напоминания из remind_at vs due_date
  form.remind_offset = 0
  if (task.remind_at && task.due_date) {
    const diffMin = Math.round((new Date(task.due_date).getTime() - new Date(task.remind_at).getTime()) / 60000)
    if (reminderOptions.some((o) => o.value === diffMin)) form.remind_offset = diffMin
  }
  showDialog.value = true
}

function buildPayload() {
  const dueDate = new Date(form.due_local)
  const recurrence_rule =
    form.recurrence_preset === 'none' ? '' :
    form.recurrence_preset === 'custom' ? form.recurrence_custom.trim() :
    form.recurrence_preset
  let remind_at: string | null = null
  if (form.remind_offset > 0) {
    remind_at = new Date(dueDate.getTime() - form.remind_offset * 60000).toISOString()
  }
  return {
    activity_type: 'task',
    title: form.title.trim(),
    status: form.status,
    due_date: dueDate.toISOString(),
    recurrence_rule,
    remind_at,
  }
}

async function refreshCurrentRange() {
  const api = calendarRef.value?.getApi?.()
  if (api) {
    const view = api.view
    await loadRange(view.activeStart.toISOString(), view.activeEnd.toISOString())
  }
}

async function save() {
  if (!form.title.trim() || !form.due_local) return
  try {
    if (form.id) {
      await crmApi.patchActivity(form.id, buildPayload())
    } else {
      // Задача из календаря назначается на текущего пользователя — иначе она не
      // попадёт в его календарь (выборка фильтрует по ответственному).
      await crmApi.createActivity({ ...buildPayload(), responsible_id: authStore.user?.id })
    }
    showDialog.value = false
    await refreshCurrentRange()
  } catch (err) {
    log.error('Failed to save task', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить задачу', life: 5000 })
  }
}

async function markDone() {
  if (!form.id) return
  try {
    await crmApi.patchActivity(form.id, { status: 'done' })
    showDialog.value = false
    await refreshCurrentRange()
    toast.add({ severity: 'success', summary: 'Готово', detail: 'Задача отмечена выполненной', life: 3000 })
  } catch (err) {
    log.error('Failed to complete task', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось закрыть задачу', life: 5000 })
  }
}
</script>

<style scoped>
.calendar-page { padding: 14px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.calendar-card { padding: 16px; }
.form-grid { display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 13px; color: var(--p-text-muted-color); }
.dt-input {
  height: 38px; padding: 0 10px; border: 1px solid var(--line, #d1d5db);
  border-radius: 6px; background: var(--p-inputtext-background, #fff); color: inherit;
}
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }

/* Статусные цвета событий поверх дефолтной темы FullCalendar */
.calendar-card :deep(.fc-task-planned) { background: var(--p-primary-500, #6366f1); border-color: transparent; }
.calendar-card :deep(.fc-task-overdue) { background: #ef4444; border-color: transparent; }
.calendar-card :deep(.fc-task-done) { background: #9ca3af; border-color: transparent; text-decoration: line-through; }
.calendar-card :deep(.fc) { --fc-border-color: var(--line, #e5e7eb); }
</style>
