<template>
  <FeatureGate feature="crm_builtin" class="view-gate">
    <section class="tasks-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Задачи</h1>
        <PButton label="Новая задача" icon="pi pi-plus" size="small" @click="showForm = true" />
      </div>

      <div class="tasks-layout">
        <!-- Left: categories -->
        <div class="surface-card categories-panel">
          <div class="cat-label">Категории</div>
          <button
            v-for="cat in categories"
            :key="cat.id"
            class="cat-btn"
            :class="{ active: activeCategory === cat.id }"
            @click="activeCategory = cat.id"
          >
            <span class="cat-name">{{ cat.label }}</span>
            <span class="cat-count" :class="{ overdue: cat.id === 'overdue' }">{{ cat.count }}</span>
          </button>
        </div>

        <!-- Right: task list -->
        <div class="surface-card tasks-list-panel">
          <div class="tasks-list-header">
            <span class="section-title">{{ activeLabel }}</span>
            <span class="tasks-count">{{ filteredTasks.length }}</span>
          </div>

          <div v-if="filteredTasks.length" class="tasks-list">
            <div
              v-for="task in filteredTasks"
              :key="task.id"
              class="task-row"
              :class="{ done: task.status === 'done' }"
            >
              <button class="task-checkbox" :class="{ checked: task.status === 'done' }" @click="toggleTask(task)">
                <i v-if="task.status === 'done'" class="pi pi-check" />
              </button>
              <div class="task-content">
                <span class="task-title" :class="{ strikethrough: task.status === 'done' }">{{ task.title }}</span>
                <div v-if="task.deal_id" class="task-deal-tag">{{ task.title }}</div>
              </div>
              <span
                class="priority-badge"
                :class="priorityClass(task)"
              >{{ priorityLabel(task) }}</span>
              <span class="task-time" :class="{ overdue: isOverdue(task) }">{{ formatTaskTime(task) }}</span>
              <button class="row-btn row-btn-danger" title="Удалить" @click="deleteTask(task.id)">
                <i class="pi pi-trash" />
              </button>
            </div>
          </div>

          <div v-else class="empty-state">
            <i class="pi pi-check-circle" style="font-size: 32px; color: var(--text-muted)" />
            <p>Нет задач в этой категории</p>
          </div>
        </div>
      </div>
    </section>

    <!-- New task dialog -->
    <PDialog v-model:visible="showForm" header="Новая задача" :style="{ width: '420px', maxWidth: '95vw' }" modal @hide="resetForm">
      <div class="form-grid">
        <div>
          <label class="field-label">Название *</label>
          <PInputText v-model="form.title" class="w-full" placeholder="Название задачи" />
        </div>
        <div>
          <label class="field-label">Описание</label>
          <PTextarea v-model="form.body" rows="3" class="w-full" autoResize />
        </div>
        <div>
          <label class="field-label">Срок выполнения</label>
          <PInputText v-model="form.due_date" type="date" class="w-full" />
        </div>
      </div>
      <template #footer>
        <PButton label="Отмена" severity="secondary" size="small" @click="showForm = false" />
        <PButton label="Создать" size="small" :disabled="!form.title.trim()" @click="createTask" />
      </template>
    </PDialog>

    <template #locked>
      <div class="surface-card" style="padding: 16px">Раздел доступен в плане CRM.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'

type Task = { id: number; title: string; status: string; due_date: string | null; deal_id: number | null; created_at: string }

const allTasks = ref<Task[]>([])
const activeCategory = ref('today')
const loading = ref(false)

const loadTasks = async () => {
  loading.value = true
  allTasks.value = await crmApi.myTasks()
  loading.value = false
}

onMounted(loadTasks)

/* Category filters */
const todayStr = () => new Date().toISOString().slice(0, 10)
const tomorrowStr = () => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}
const weekStr = () => {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  return d.toISOString().slice(0, 10)
}

const categoryFilter = (cat: string) => (t: Task) => {
  if (cat === 'overdue') return t.status === 'overdue' || (t.due_date != null && t.due_date < todayStr() && t.status !== 'done')
  if (cat === 'today') return t.due_date === todayStr()
  if (cat === 'tomorrow') return t.due_date === tomorrowStr()
  if (cat === 'week') return t.due_date != null && t.due_date > todayStr() && t.due_date <= weekStr()
  return true
}

const categories = computed(() => [
  { id: 'today', label: 'Сегодня', count: allTasks.value.filter(categoryFilter('today')).length },
  { id: 'tomorrow', label: 'Завтра', count: allTasks.value.filter(categoryFilter('tomorrow')).length },
  { id: 'week', label: 'На неделе', count: allTasks.value.filter(categoryFilter('week')).length },
  { id: 'overdue', label: 'Просрочено', count: allTasks.value.filter(categoryFilter('overdue')).length },
])

const activeLabel = computed(() => categories.value.find(c => c.id === activeCategory.value)?.label || '')
const filteredTasks = computed(() => allTasks.value.filter(categoryFilter(activeCategory.value)))

/* Task actions */
const toggleTask = async (task: Task) => {
  if (task.status === 'done') return
  await crmApi.patchActivity(task.id, { status: 'done' })
  await loadTasks()
}

const deleteTask = async (id: number) => {
  await crmApi.deleteActivity(id)
  await loadTasks()
}

/* New task form */
const showForm = ref(false)
const form = reactive({ title: '', body: '', due_date: '' })
const resetForm = () => { form.title = ''; form.body = ''; form.due_date = '' }

const createTask = async () => {
  if (!form.title.trim()) return
  await crmApi.createActivity({ activity_type: 'task', title: form.title.trim(), body: form.body.trim(), due_date: form.due_date || null, status: 'planned' })
  showForm.value = false
  resetForm()
  await loadTasks()
}

/* Display helpers */
const isOverdue = (t: Task) => t.due_date != null && t.due_date < todayStr() && t.status !== 'done'

const formatTaskTime = (t: Task) => {
  if (!t.due_date) return ''
  const [y, m, d] = t.due_date.split('-')
  return `${d}.${m}.${y}`
}

const priorityClass = (t: Task) => {
  if (isOverdue(t)) return 'high'
  if (!t.due_date) return 'low'
  return 'medium'
}

const priorityLabel = (t: Task) => {
  if (isOverdue(t)) return 'Просрочено'
  if (t.status === 'done') return 'Выполнено'
  return 'В работе'
}
</script>

<style scoped>
.view-gate,
:deep(.view-gate > div) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tasks-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tasks-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* Categories panel */
.categories-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cat-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 8px;
  padding: 0 4px;
}

.cat-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-family: 'Nunito Sans', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
  transition: all 0.15s;
  text-align: left;
}

.cat-btn:hover {
  background: var(--surface-alt);
  color: var(--text);
}

.cat-btn.active {
  background: var(--primary-lighter);
  color: var(--brand);
}

.cat-count {
  background: var(--surface-alt);
  border-radius: 99px;
  padding: 1px 8px;
  font-size: 12px;
  min-width: 20px;
  text-align: center;
}

.cat-count.overdue {
  background: #fef2f2;
  color: var(--danger);
}

/* Tasks list */
.tasks-list-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tasks-list-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.tasks-count {
  background: var(--surface-alt);
  border-radius: 99px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 700;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 8px;
  transition: background 0.15s;
}

.task-row:hover {
  background: var(--surface-alt);
}

.task-row.done {
  opacity: 0.6;
}

/* Checkbox */
.task-checkbox {
  width: 22px;
  height: 22px;
  min-width: 22px;
  border: 2px solid var(--line);
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: white;
  transition: all 0.15s;
}

.task-checkbox:hover {
  border-color: #22c55e;
}

.task-checkbox.checked {
  background: #22c55e;
  border-color: #22c55e;
}

.task-content {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.task-title.strikethrough {
  text-decoration: line-through;
  color: var(--text-muted);
}

.task-deal-tag {
  display: inline-block;
  background: var(--primary-lighter);
  color: var(--brand);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
  margin-top: 2px;
}

.task-time {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.task-time.overdue {
  color: var(--danger);
  font-weight: 700;
}

.row-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0;
  transition: all 0.15s;
}

.task-row:hover .row-btn {
  opacity: 1;
}

.row-btn-danger:hover {
  background: #fef2f2;
  color: var(--danger);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 24px;
  color: var(--text-muted);
  text-align: center;
}

/* Form */
.form-grid { display: grid; gap: 12px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
</style>
