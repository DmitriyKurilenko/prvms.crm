<template>
  <div class="layout-topbar">
    <!-- Breadcrumb -->
    <div class="topbar-breadcrumb">
      <span class="breadcrumb-root">CRM</span>
      <i class="pi pi-angle-right" style="font-size:11px; color:var(--p-text-muted-color)" />
      <span class="breadcrumb-page">{{ title }}</span>
    </div>

    <!-- Center search -->
    <div class="topbar-search">
      <span class="p-input-icon-left" style="width:100%">
        <i class="pi pi-search" />
        <PInputText
          v-model="searchQuery"
          placeholder="Поиск..."
          class="w-full"
          style="padding-left: 2.2rem"
        />
      </span>
    </div>

    <div class="topbar-end">
      <!-- Org switcher -->
      <PSelect
        v-if="organizationOptions.length > 1"
        :model-value="selectedTenantSlug"
        :options="organizationOptions"
        option-label="label"
        option-value="value"
        :disabled="auth.loading"
        style="min-width:180px; font-size:13px"
        @update:model-value="switchOrganization"
      />

      <NotificationBell />

      <PButton
        :icon="ui.darkMode ? 'pi pi-sun' : 'pi pi-moon'"
        text
        rounded
        severity="secondary"
        title="Тема"
        @click="ui.toggleTheme"
      />

      <PButton
        icon="pi pi-sign-out"
        text
        rounded
        severity="danger"
        title="Выйти"
        @click="doLogout"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NotificationBell from '@/components/NotificationBell.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const route  = useRoute()
const router = useRouter()
const auth   = useAuthStore()
const ui     = useUiStore()

const searchQuery = ref('')

const title = computed(() => String(route.meta.title || route.name || 'Dashboard'))

const selectedTenantSlug = computed(() => auth.user?.tenant_slug || null)
const organizationOptions = computed(() =>
  auth.organizations.map(o => ({ value: o.tenant_slug, label: `${o.tenant_name} (${o.role})` }))
)

const doLogout = async () => {
  await auth.logout()
  await router.push('/login')
}

const switchOrganization = async (slug: string | null) => {
  if (!slug) return
  await auth.switchOrganization(slug)
  await router.push('/app')
}
</script>

<style scoped>
.layout-topbar { /* defined globally in main.css */ }

.topbar-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.breadcrumb-root {
  font-size: 13px;
  font-weight: 500;
  color: var(--p-text-muted-color);
}

.breadcrumb-page {
  font-size: 14px;
  font-weight: 700;
  color: var(--p-text-color);
}

.topbar-search {
  flex: 1;
  max-width: 380px;
  margin: 0 auto;
}

.topbar-search :deep(.p-inputtext) { width: 100%; }

.topbar-end {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  flex-shrink: 0;
}

.w-full { width: 100%; }
</style>
