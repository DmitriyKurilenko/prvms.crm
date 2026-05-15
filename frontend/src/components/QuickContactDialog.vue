<template>
  <PDialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    header="Быстрое создание контакта"
    :style="{ width: '400px', maxWidth: '95vw' }"
    modal
  >
    <div class="form-grid">
      <div class="form-row-2">
        <div><label class="field-label">Имя *</label><PInputText v-model="form.first_name" placeholder="Имя" class="w-full" /></div>
        <div><label class="field-label">Фамилия</label><PInputText v-model="form.last_name" placeholder="Фамилия" class="w-full" /></div>
      </div>
      <div class="form-row-2">
        <div><label class="field-label">Телефон</label><PInputText v-model="form.phone" placeholder="+7..." class="w-full" /></div>
        <div><label class="field-label">Email</label><PInputText v-model="form.email" placeholder="email@..." class="w-full" /></div>
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
const form = reactive({ first_name: '', last_name: '', phone: '', email: '' })

const submit = async () => {
  if (!props.canCreate || !form.first_name) return
  const res = await call(() => crmApi.createContact({ ...form }), 'Не удалось создать контакт.')
  if (res === undefined) return
  emit('created', res)
  Object.assign(form, { first_name: '', last_name: '', phone: '', email: '' })
  emit('update:visible', false)
}
</script>

<style scoped>
.form-grid { display: grid; gap: 12px; }
.form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.field-label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.w-full { width: 100%; }
</style>
