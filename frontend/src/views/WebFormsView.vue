<template>
  <FeatureGate feature="crm_builtin">
    <section class="webforms-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Веб-формы</h1>
      </div>

      <div v-if="!canView" class="surface-card" style="padding: 14px;">
        У вас нет прав для просмотра веб-форм.
      </div>

      <template v-else>
        <div class="toolbar">
          <PButton v-if="canCreate" label="Новая форма" icon="pi pi-plus" size="small" @click="openCreate" />
        </div>

        <div class="surface-card" style="padding: 12px; margin-top: 12px;">
          <PDataTable v-responsive-table :value="forms" size="small" stripedRows :paginator="true" :rows="20">
            <PColumn field="name" header="Название" />
            <PColumn header="Заявок">
              <template #body="{ data }">{{ data.submissions_count }}</template>
            </PColumn>
            <PColumn header="Активна">
              <template #body="{ data }">
                <PTag :value="data.is_active ? 'Да' : 'Нет'" :severity="data.is_active ? 'success' : 'secondary'" />
              </template>
            </PColumn>
            <PColumn header="" style="width: 150px">
              <template #body="{ data }">
                <PButton icon="pi pi-code" text size="small" title="Код для вставки" @click="showSnippet(data)" />
                <PButton v-if="canDelete" icon="pi pi-trash" text size="small" severity="danger" @click="remove(data.id)" />
              </template>
            </PColumn>
            <template #empty>
              <div class="empty-state">Форм пока нет</div>
            </template>
          </PDataTable>
        </div>
      </template>

      <!-- Create dialog -->
      <PDialog v-model:visible="dialogVisible" header="Новая веб-форма" :style="{ width: '560px' }" modal>
        <div class="form-grid">
          <PInputText v-model="form.name" placeholder="Название формы" />
          <div class="form-row-2">
            <PSelect v-model="form.pipeline_id" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Воронка" @change="onPipelineChange" />
            <PSelect v-model="form.stage_id" :options="stages" optionLabel="name" optionValue="id" placeholder="Первая стадия" />
          </div>
          <PInputText v-model="form.success_message" placeholder="Сообщение после отправки" />

          <div class="fields-block">
            <div class="fields-head">
              <strong>Поля формы</strong>
              <PButton label="Добавить поле" icon="pi pi-plus" text size="small" @click="addField" />
            </div>
            <div v-for="(f, i) in form.fields_schema" :key="i" class="field-row">
              <PInputText v-model="f.key" placeholder="ключ (phone)" style="width: 130px" />
              <PInputText v-model="f.label" placeholder="Подпись" style="flex: 1" />
              <PSelect v-model="f.type" :options="fieldTypes" optionLabel="label" optionValue="value" style="width: 130px" />
              <label class="req"><input type="checkbox" v-model="f.required" /> обяз.</label>
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="form.fields_schema.splice(i, 1)" />
              <PInputText
                v-if="f.type === 'select'"
                :modelValue="(f.options || []).join(', ')"
                placeholder="Варианты через запятую: A, B, C"
                style="flex: 1 1 100%"
                @update:modelValue="(v: string) => (f.options = String(v).split(',').map((s) => s.trim()).filter(Boolean))"
              />
            </div>
          </div>

          <PButton :label="'Создать'" :disabled="!form.name || !form.pipeline_id || !form.stage_id" @click="submit" />
        </div>
      </PDialog>

      <!-- Snippet dialog -->
      <PDialog v-model:visible="snippetVisible" header="Код для вставки на сайт" :style="{ width: '600px' }" modal>
        <p class="hint">Вставьте этот код на страницу вашего сайта — форма появится на месте вставки.</p>
        <pre class="snippet">{{ currentSnippet }}</pre>
        <PButton label="Скопировать" icon="pi pi-copy" size="small" @click="copySnippet" />
      </PDialog>
    </section>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmWebForm, CrmWebFormField, CrmPipeline, CrmStage } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('webforms')
const toast = useToast()
const authStore = useAuthStore()
const perms = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canView = computed(() => perms.value.webforms.can_view)
const canCreate = computed(() => perms.value.webforms.can_create)
const canDelete = computed(() => perms.value.webforms.can_delete)

const fieldTypes = [
  { label: 'Текст', value: 'text' }, { label: 'Телефон', value: 'phone' },
  { label: 'Email', value: 'email' }, { label: 'Многострочное', value: 'textarea' },
  { label: 'Список', value: 'select' }, { label: 'Чекбокс', value: 'checkbox' },
]

const forms = ref<CrmWebForm[]>([])
const pipelines = ref<CrmPipeline[]>([])
const stages = ref<CrmStage[]>([])
const dialogVisible = ref(false)
const snippetVisible = ref(false)
const currentSnippet = ref('')

const defaultFields = (): CrmWebFormField[] => [
  { key: 'name', label: 'Имя', type: 'text', required: true },
  { key: 'phone', label: 'Телефон', type: 'phone', required: true },
  { key: 'email', label: 'Email', type: 'email', required: false },
]

const form = reactive({
  name: '',
  pipeline_id: null as number | null,
  stage_id: null as number | null,
  success_message: 'Спасибо! Мы свяжемся с вами.',
  fields_schema: defaultFields(),
})

function addField() {
  form.fields_schema.push({ key: '', label: '', type: 'text', required: false })
}

async function load() {
  if (!canView.value) { forms.value = []; return }
  try {
    forms.value = await crmApi.listWebForms()
    pipelines.value = await crmApi.listPipelines()
  } catch (err) {
    log.error('Failed to load web forms', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить веб-формы', life: 5000 })
  }
}

async function onPipelineChange() {
  form.stage_id = null
  if (form.pipeline_id) {
    stages.value = await crmApi.listStages(form.pipeline_id)
    if (stages.value.length) form.stage_id = stages.value[0].id
  }
}

async function openCreate() {
  form.name = ''
  form.success_message = 'Спасибо! Мы свяжемся с вами.'
  form.fields_schema = defaultFields()
  if (!pipelines.value.length) pipelines.value = await crmApi.listPipelines()
  form.pipeline_id = pipelines.value[0]?.id ?? null
  await onPipelineChange()
  dialogVisible.value = true
}

async function submit() {
  if (!form.name || !form.pipeline_id || !form.stage_id) return
  try {
    const created = await crmApi.createWebForm({
      name: form.name,
      pipeline_id: form.pipeline_id,
      stage_id: form.stage_id,
      success_message: form.success_message,
      fields_schema: form.fields_schema,
    })
    dialogVisible.value = false
    await load()
    showSnippet(created)
  } catch (err) {
    log.error('Failed to create web form', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать форму', life: 5000 })
  }
}

function showSnippet(f: CrmWebForm) {
  currentSnippet.value = f.embed_snippet
  snippetVisible.value = true
}

function copySnippet() {
  navigator.clipboard?.writeText(currentSnippet.value)
  toast.add({ severity: 'success', summary: 'Скопировано', life: 2500 })
}

async function remove(id: number) {
  if (!canDelete.value) return
  try {
    await crmApi.deleteWebForm(id)
    await load()
  } catch (err) {
    log.error('Failed to delete web form', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить форму', life: 5000 })
  }
}

onMounted(load)
</script>

<style scoped>
.webforms-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { display: flex; gap: 8px; align-items: center; }
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.fields-block { border: 1px solid var(--line); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.fields-head { display: flex; justify-content: space-between; align-items: center; }
.field-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.req { display: flex; align-items: center; gap: 4px; font-size: 12px; white-space: nowrap; }
.snippet { background: var(--surface-alt, #f3f4f6); padding: 12px; border-radius: 8px; font-size: 12px; white-space: pre-wrap; word-break: break-all; }
.hint { color: var(--text-muted); font-size: 13px; }
.empty-state { padding: 18px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
