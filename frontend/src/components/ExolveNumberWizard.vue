<template>
  <div class="wizard">
    <div class="form-row-3">
      <div>
        <label class="lbl">Тип номера</label>
        <PSelect v-model="typeId" :options="typeOptions" option-label="label" option-value="value" class="w-full" />
      </div>
      <div>
        <label class="lbl">Регион (ID, необязательно)</label>
        <PInputText v-model="regionId" placeholder="например 10230" class="w-full" />
      </div>
      <div>
        <label class="lbl">Маска (необязательно)</label>
        <PInputText v-model="mask" placeholder="напр. 999" class="w-full" />
      </div>
    </div>
    <div class="wizard-actions">
      <PButton label="Найти номера" icon="pi pi-search" :loading="searching" @click="search" />
    </div>

    <p v-if="searchError" class="err">{{ searchError }}</p>

    <PDataTable v-if="numbers.length" :value="numbers" class="num-table" v-responsive-table>
      <PColumn field="number" header="Номер" />
      <PColumn field="price" header="Абон. плата" />
      <PColumn header="" style="width: 140px">
        <template #body="{ data }">
          <PButton label="Подключить" size="small" :loading="connectingCode === data.number_code"
                   @click="connect(data)" />
        </template>
      </PColumn>
    </PDataTable>
    <p v-else-if="searched && !searching" class="muted">По заданным параметрам свободных номеров не найдено.</p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { getAvailableNumbers, connectNumber } from '@/api/telephony'

interface FreeNumber { number: string; number_code: string; price: string }

const emit = defineEmits<{ connected: [number: string] }>()
const toast = useToast()

const typeOptions = [
  { label: 'Мобильный', value: 1104 },
  { label: 'Городской', value: 1105 },
  { label: '8-800', value: 1106 },
]
const typeId = ref(1104)
const regionId = ref('')
const mask = ref('')

const numbers = ref<FreeNumber[]>([])
const searching = ref(false)
const searched = ref(false)
const searchError = ref('')
const connectingCode = ref('')

function asArray(x: unknown): Record<string, unknown>[] {
  if (Array.isArray(x)) return x as Record<string, unknown>[]
  return []
}

function pick(it: Record<string, unknown>, keys: string[]): string {
  for (const k of keys) {
    const v = it[k]
    if (v !== undefined && v !== null && v !== '') return String(v)
  }
  return ''
}

function extractNumbers(resp: Record<string, unknown>): FreeNumber[] {
  // GetFree возвращает список свободных номеров; ключ контейнера нормализуем
  // защитно (numbers / free_numbers / result.numbers / сам массив).
  const result = resp['result']
  const container =
    asArray(resp['numbers']).length ? resp['numbers']
    : asArray(resp['free_numbers']).length ? resp['free_numbers']
    : (result && typeof result === 'object') ? (result as Record<string, unknown>)['numbers']
    : Array.isArray(resp) ? resp
    : []
  return asArray(container)
    .map((it) => ({
      number: pick(it, ['number', 'phone_number', 'number_code']),
      number_code: pick(it, ['number_code', 'number']),
      price: pick(it, ['subscription_fee', 'price', 'fee']),
    }))
    .filter((n) => n.number_code)
}

async function search() {
  searching.value = true
  searchError.value = ''
  searched.value = true
  try {
    const resp = await getAvailableNumbers({
      type_id: typeId.value,
      region_id: regionId.value ? Number(regionId.value) : undefined,
      mask: mask.value || undefined,
      limit: 30,
    })
    numbers.value = extractNumbers(resp)
  } catch (e) {
    searchError.value = e instanceof Error ? e.message : 'Не удалось получить список номеров'
  } finally {
    searching.value = false
  }
}

async function connect(item: FreeNumber) {
  connectingCode.value = item.number_code
  try {
    const res = await connectNumber({
      number_code: item.number_code,
      number: item.number,
      type_id: typeId.value,
      region_id: regionId.value ? Number(regionId.value) : undefined,
    })
    toast.add({ severity: 'success', summary: 'Номер подключён', detail: res.exolve_number, life: 4000 })
    emit('connected', res.exolve_number)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка подключения', detail: e instanceof Error ? e.message : '', life: 6000 })
  } finally {
    connectingCode.value = ''
  }
}
</script>

<style scoped>
.wizard { display: flex; flex-direction: column; gap: 14px; }
.lbl { display: block; font-size: 13px; color: var(--text-muted, #6b7280); margin-bottom: 4px; }
.wizard-actions { display: flex; gap: 10px; }
.num-table { margin-top: 6px; }
.err { color: #b91c1c; font-size: 13px; }
.muted { color: var(--text-muted, #6b7280); font-size: 13px; }
</style>
