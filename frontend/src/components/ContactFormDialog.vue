<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="form.id ? 'Редактировать контакт' : 'Новый контакт'"
    :style="{ width: '500px', maxWidth: '95vw' }"
    modal
  >
    <div class="form-grid">
      <div class="form-row-2">
        <div>
          <label class="field-label">Имя *</label>
          <PInputText v-model="form.first_name" placeholder="Имя" class="w-full" />
        </div>
        <div>
          <label class="field-label">Фамилия</label>
          <PInputText v-model="form.last_name" placeholder="Фамилия" class="w-full" />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Телефон</label>
          <PInputText v-model="form.phone" placeholder="+7 (___) ___-__-__" class="w-full" />
        </div>
        <div>
          <label class="field-label">Email</label>
          <PInputText v-model="form.email" placeholder="email@example.com" class="w-full" />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Должность</label>
          <PInputText v-model="form.position" placeholder="Менеджер, директор..." class="w-full" />
        </div>
        <div>
          <label class="field-label">Компания</label>
          <PSelect
            v-model="form.company_id"
            :options="companyOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="— не выбрана —"
            showClear
            filter
            filterPlaceholder="Поиск…"
            class="w-full"
          />
        </div>
      </div>
      <div class="form-row-2">
        <div>
          <label class="field-label">Мессенджер</label>
          <PInputText v-model="form.messenger_id" placeholder="Telegram, WhatsApp..." class="w-full" />
        </div>
        <div>
          <label class="field-label">Источник</label>
          <PSelect
            v-model="form.source"
            :options="sourceOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="— не указан —"
            showClear
            class="w-full"
          />
        </div>
      </div>
      <div>
        <label class="field-label">Ответственный</label>
        <PSelect
          v-model="form.responsible_id"
          :options="managerOptions"
          optionLabel="label"
          optionValue="value"
          placeholder="— не выбран —"
          showClear
          class="w-full"
        />
      </div>
      <PButton
        :label="form.id ? 'Сохранить' : 'Создать'"
        :disabled="!form.first_name"
        @click="$emit('submit')"
      />
    </div>
  </PDialog>
</template>

<script setup lang="ts">
/**
 * Презентационный диалог формы контакта. Состояние формы (реактивный объект)
 * и логика submit/load остаются в родителе (ContactsView) — как в
 * DealFormDialog. Перенос 1:1.
 */
interface ContactForm {
  id: number | null
  first_name: string
  last_name: string
  phone: string
  email: string
  position: string
  company_id: number | null
  messenger_id: string
  source: string
  responsible_id: number | null
}

defineProps<{
  visible: boolean
  form: ContactForm
  companyOptions: { value: number; label: string }[]
  sourceOptions: { value: string; label: string }[]
  managerOptions: { value: number; label: string }[]
}>()

defineEmits<{
  'update:visible': [boolean]
  submit: []
}>()
</script>

<style scoped>
/* .form-grid / .form-row-2 — глобальные примитивы (styles/main.css), адаптив там. */
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: var(--text); }
.w-full { width: 100%; }
</style>
