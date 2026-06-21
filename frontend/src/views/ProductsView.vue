<template>
  <FeatureGate feature="crm_builtin">
    <section class="products-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Товары</h1>
      </div>

      <div v-if="!canViewProducts" class="surface-card" style="padding: 14px;">
        У вас нет прав для просмотра каталога.
      </div>

      <template v-else>
        <div class="toolbar">
          <PInputText v-model="search" placeholder="Поиск по названию" @keyup.enter="load" />
          <PButton v-if="canCreateProduct" label="Новый товар" icon="pi pi-plus" size="small" @click="openCreate" />
        </div>

        <div class="surface-card" style="padding: 12px; margin-top: 12px;">
          <PDataTable v-responsive-table
            :value="products"
            size="small"
            stripedRows
            :paginator="true"
            :rows="20"
            :rowsPerPageOptions="[10, 20, 50]"
          >
            <PColumn field="name" header="Название" />
            <PColumn field="sku" header="Артикул" />
            <PColumn header="Цена">
              <template #body="{ data }">{{ data.price }} {{ data.currency }}</template>
            </PColumn>
            <PColumn header="НДС">
              <template #body="{ data }">{{ data.vat_rate }}%</template>
            </PColumn>
            <PColumn field="unit" header="Ед." />
            <PColumn header="Статус">
              <template #body="{ data }">
                <PTag :value="data.is_active ? 'Активен' : 'Архив'" :severity="data.is_active ? 'success' : 'secondary'" />
              </template>
            </PColumn>
            <PColumn header="" style="width: 110px">
              <template #body="{ data }">
                <PButton v-if="canUpdateProduct" icon="pi pi-pencil" text size="small" @click="openEdit(data)" />
                <PButton v-if="canDeleteProduct" icon="pi pi-trash" text size="small" severity="danger" @click="remove(data.id)" />
              </template>
            </PColumn>
            <template #empty>
              <div class="empty-state">Нет товаров</div>
            </template>
          </PDataTable>
        </div>
      </template>

      <PDialog v-model:visible="dialogVisible" :header="form.id ? 'Редактирование товара' : 'Новый товар'" :style="{ width: '480px' }" modal>
        <div class="form-grid">
          <PInputText v-model="form.name" placeholder="Название" />
          <PInputText v-model="form.sku" placeholder="Артикул" />
          <div class="form-row-2">
            <PInputNumber v-model="form.price" placeholder="Цена" :minFractionDigits="2" :maxFractionDigits="2" mode="decimal" />
            <PSelect v-model="form.currency" :options="currencies" optionLabel="label" optionValue="value" />
          </div>
          <div class="form-row-2">
            <PInputNumber v-model="form.vat_rate" placeholder="Ставка НДС, %" :min="0" :max="100" />
            <PSelect v-model="form.unit" :options="units" optionLabel="label" optionValue="value" />
          </div>
          <PTextarea v-model="form.description" placeholder="Описание" rows="2" autoResize />
          <PButton
            :label="form.id ? 'Сохранить' : 'Создать'"
            :disabled="!form.name || (form.id ? !canUpdateProduct : !canCreateProduct)"
            @click="submit"
          />
        </div>
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
import type { CrmProduct } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('products')
const toast = useToast()
const authStore = useAuthStore()
const crmPermissions = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canViewProducts = computed(() => crmPermissions.value.products.can_view)
const canCreateProduct = computed(() => crmPermissions.value.products.can_create)
const canUpdateProduct = computed(() => crmPermissions.value.products.can_update)
const canDeleteProduct = computed(() => crmPermissions.value.products.can_delete)

const currencies = [{ label: 'RUB', value: 'RUB' }, { label: 'USD', value: 'USD' }, { label: 'EUR', value: 'EUR' }]
const units = [
  { label: 'шт', value: 'pcs' }, { label: 'час', value: 'hour' }, { label: 'усл', value: 'service' },
  { label: 'кг', value: 'kg' }, { label: 'мес', value: 'month' }, { label: 'лиц', value: 'license' },
]

const products = ref<CrmProduct[]>([])
const search = ref('')
const dialogVisible = ref(false)
const form = reactive({
  id: null as number | null,
  name: '',
  sku: '',
  price: 0,
  currency: 'RUB',
  vat_rate: 20,
  unit: 'pcs',
  description: '',
})

function resetForm() {
  form.id = null
  form.name = ''
  form.sku = ''
  form.price = 0
  form.currency = 'RUB'
  form.vat_rate = 20
  form.unit = 'pcs'
  form.description = ''
}

async function load() {
  if (!canViewProducts.value) {
    products.value = []
    return
  }
  try {
    products.value = await crmApi.listProducts(search.value || undefined)
  } catch (err) {
    log.error('Failed to load products', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить каталог', life: 5000 })
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(p: CrmProduct) {
  form.id = p.id
  form.name = p.name
  form.sku = p.sku
  form.price = p.price
  form.currency = p.currency
  form.vat_rate = p.vat_rate
  form.unit = p.unit
  form.description = p.description
  dialogVisible.value = true
}

async function submit() {
  if (!form.name) return
  const allowed = form.id ? canUpdateProduct.value : canCreateProduct.value
  if (!allowed) return
  const payload = {
    name: form.name, sku: form.sku, price: form.price, currency: form.currency,
    vat_rate: form.vat_rate, unit: form.unit, description: form.description,
  }
  try {
    if (form.id) {
      await crmApi.patchProduct(form.id, payload)
    } else {
      await crmApi.createProduct(payload)
    }
    dialogVisible.value = false
    resetForm()
    await load()
  } catch (err) {
    log.error('Failed to save product', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось сохранить товар', life: 5000 })
  }
}

async function remove(id: number) {
  if (!canDeleteProduct.value) return
  try {
    await crmApi.deleteProduct(id)
    await load()
  } catch (err) {
    log.error('Failed to delete product', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить товар', life: 5000 })
  }
}

onMounted(load)
</script>

<style scoped>
.products-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.toolbar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.form-grid { display: flex; flex-direction: column; gap: 10px; }
.empty-state { padding: 18px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
