<template>
  <div class="layout-topbar">
    <div class="layout-topbar-logo-container">
      <button class="layout-menu-button layout-topbar-action" @click="toggleMenu" type="button">
        <i class="pi pi-bars" />
      </button>
      <RouterLink to="/app" class="layout-topbar-logo">
        <i class="pi pi-th-large" />
        <span>CRM</span>
      </RouterLink>
    </div>

    <div class="layout-topbar-actions">
      <PSelect
        v-if="organizationOptions.length > 1"
        :model-value="selectedTenantSlug"
        :options="organizationOptions"
        option-label="label"
        option-value="value"
        :disabled="auth.loading"
        class="topbar-org-select"
        @update:model-value="switchOrganization"
      />

      <NotificationBell />

      <button type="button" class="layout-topbar-action" :title="isDarkTheme ? 'Светлая тема' : 'Тёмная тема'" @click="toggleDarkMode">
        <i :class="isDarkTheme ? 'pi pi-sun' : 'pi pi-moon'" />
      </button>

      <button type="button" class="layout-topbar-action layout-topbar-action-danger" title="Выйти" @click="doLogout">
        <i class="pi pi-sign-out" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useLayout } from './composables/layout'
import { useAuthStore } from '@/stores/auth'
import NotificationBell from '@/components/NotificationBell.vue'

const { toggleMenu, toggleDarkMode, isDarkTheme } = useLayout()
const router = useRouter()
const auth = useAuthStore()

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
