<template>
  <div class="layout-wrapper">
    <SidebarNav />

    <div class="layout-main-container">
      <TopBar />

      <div class="layout-main">
        <div v-if="trialBanner" class="trial-banner" :class="{ 'trial-expired': tenant?.trial_expired }">
          <template v-if="tenant?.trial_expired">
            <i class="pi pi-exclamation-triangle" />
            Пробный период истёк.
            <RouterLink to="/app/subscription">Оформите подписку</RouterLink>
          </template>
          <template v-else-if="tenant?.trial_active">
            <i class="pi pi-clock" />
            Пробный период: осталось {{ daysLeft }} дн.
            <RouterLink to="/app/subscription">Оформить подписку</RouterLink>
          </template>
        </div>

        <RouterView />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import SidebarNav from './SidebarNav.vue'
import TopBar from './TopBar.vue'
import { useTenantStore } from '@/stores/tenant'

const tenantStore = useTenantStore()
const tenant = computed(() => tenantStore.current)

const trialBanner = computed(() =>
  tenant.value ? (tenant.value.trial_active || tenant.value.trial_expired) : false
)

const daysLeft = computed(() => {
  if (!tenant.value?.trial_expires_at) return 0
  return Math.max(0, Math.ceil((new Date(tenant.value.trial_expires_at).getTime() - Date.now()) / 86400000))
})

onMounted(() => tenantStore.ensureLoaded())
</script>

<style scoped>
.trial-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 14px;
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
}
.trial-banner.trial-expired {
  background: #fef2f2;
  color: #991b1b;
  border-color: #fecaca;
}
.trial-banner a { font-weight: 700; text-decoration: underline; }
</style>
