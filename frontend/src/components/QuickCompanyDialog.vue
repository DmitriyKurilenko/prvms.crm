<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    header="Быстрое создание компании"
    :style="{ width: '400px', maxWidth: '95vw' }"
    modal
  >
    <div class="form-grid">
      <div><label class="field-label">Название *</label><PInputText v-model="form.name" placeholder="Название" class="w-full" /></div>
      <div class="form-row-2">
        <div><label class="field-label">ИНН</label><PInputText v-model="form.inn" placeholder="ИНН" maxlength="12" class="w-full" /></div>
        <div><label class="field-label">Телефон</label><PInputText v-model="form.phone" placeholder="+7..." class="w-full" /></div>
      </div>
      <PButton label="Создать" @click="submit" :disabled="!canCreate" />
    </div>
  </PDialog>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import * as crmApi from '@/api/crm'
import { useApiCall } from '@/composables/useApiCall'

const props = defineProps<{ visible: boolean; canCreate: boolean }>()
const emit = defineEmits<{ 'update:visible': [boolean]; created: [{ id: number }] }>()

const { call } = useApiCall()
const form = reactive({ name: '', inn: '', phone: '' })

const submit = async () => {
  if (!props.canCreate || !form.name) return
  const res = await call(() => crmApi.createCompany({ ...form }), 'Не удалось создать компанию.')
  if (res === undefined) return
  emit('created', res)
  Object.assign(form, { name: '', inn: '', phone: '' })
  emit('update:visible', false)
}
</script>

<style scoped>
/* .form-grid / .form-row-2 are global primitives (styles/main.css) — responsive there */
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
</style>
