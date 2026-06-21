<template>
  <FeatureGate feature="crm_builtin">
    <section class="tags-page animate-fade">
      <div class="section-header">
        <h1 class="page-title">Теги</h1>
      </div>

      <div v-if="!canView" class="surface-card" style="padding: 14px;">
        У вас нет прав для просмотра тегов.
      </div>

      <template v-else>
        <div class="surface-card" style="padding: 16px; margin-bottom: 12px;">
          <div class="create-row">
            <PInputText v-model="newName" placeholder="Название тега" @keyup.enter="create" />
            <input v-model="newColor" type="color" class="color-input" />
            <PButton v-if="canEdit" label="Добавить" icon="pi pi-plus" size="small" :disabled="!newName.trim()" @click="create" />
          </div>
        </div>

        <div class="surface-card" style="padding: 12px;">
          <PDataTable v-responsive-table :value="tags" size="small" stripedRows :paginator="true" :rows="20">
            <PColumn header="Тег">
              <template #body="{ data }">
                <span class="tag-chip" :style="{ background: data.color }">{{ data.name }}</span>
              </template>
            </PColumn>
            <PColumn field="color" header="Цвет" />
            <PColumn header="" style="width: 70px">
              <template #body="{ data }">
                <PButton v-if="canEdit" icon="pi pi-trash" text size="small" severity="danger" @click="remove(data.id)" />
              </template>
            </PColumn>
            <template #empty>
              <div class="empty-state">Тегов пока нет</div>
            </template>
          </PDataTable>
        </div>
      </template>
    </section>

    <template #locked>
      <div class="locked-feature">CRM встроенный недоступен в текущем тарифе.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import type { CrmTag } from '@/api/crm'
import { useAuthStore } from '@/stores/auth'
import { createLogger } from '@/utils/logger'
import { normalizeCrmPermissions } from '@/utils/crmPermissions'

const log = createLogger('tags')
const toast = useToast()
const authStore = useAuthStore()
const perms = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canView = computed(() => perms.value.contacts.can_view)
const canEdit = computed(() => perms.value.contacts.can_update)

const tags = ref<CrmTag[]>([])
const newName = ref('')
const newColor = ref('#6366F1')

async function load() {
  if (!canView.value) { tags.value = []; return }
  try {
    tags.value = await crmApi.listTags()
  } catch (err) {
    log.error('Failed to load tags', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось загрузить теги', life: 5000 })
  }
}

async function create() {
  if (!newName.value.trim() || !canEdit.value) return
  try {
    await crmApi.createTag({ name: newName.value.trim(), color: newColor.value })
    newName.value = ''
    newColor.value = '#6366F1'
    await load()
  } catch (err) {
    log.error('Failed to create tag', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось создать тег (возможно, имя занято)', life: 5000 })
  }
}

async function remove(id: number) {
  if (!canEdit.value) return
  try {
    await crmApi.deleteTag(id)
    await load()
  } catch (err) {
    log.error('Failed to delete tag', err)
    toast.add({ severity: 'error', summary: 'Ошибка', detail: 'Не удалось удалить тег', life: 5000 })
  }
}

onMounted(load)
</script>

<style scoped>
.tags-page { padding: 14px; }
.section-header { margin-bottom: 12px; }
.create-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.color-input { width: 40px; height: 36px; border: 1px solid var(--line); border-radius: 6px; cursor: pointer; background: none; }
.tag-chip { display: inline-block; padding: 2px 10px; border-radius: 12px; color: #fff; font-size: 12px; font-weight: 600; }
.empty-state { padding: 18px; text-align: center; color: var(--p-text-muted-color); }
.locked-feature { padding: 24px; text-align: center; color: var(--p-text-muted-color); }
</style>
