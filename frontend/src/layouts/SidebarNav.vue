<template>
  <div class="layout-sidebar">
    <!-- Logo -->
    <div class="sidebar-logo">
      <div class="logo-icon">
        <img v-if="logoUrl" :src="logoUrl" :alt="tenantName" class="logo-img" />
        <span v-else>{{ logoInitials }}</span>
      </div>
      <div class="logo-text">
        <div class="logo-name">{{ tenantName }}</div>
        <div class="logo-sub">CRM Platform</div>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="sidebar-menu">
      <template v-for="(group, gi) in groups" :key="gi">
        <div v-if="gi > 0" class="menu-divider" />
        <RouterLink
          v-for="item in group"
          :key="item.to"
          :to="item.to"
          class="menu-item"
          :class="{ locked: item.locked }"
          :title="item.label"
          :active-class="item.to === '/app' ? '' : 'menu-item-active'"
          :exact-active-class="'menu-item-active'"
        >
          <i :class="item.icon" />
          <span>{{ item.label }}</span>
          <i v-if="item.locked" class="pi pi-lock lock-icon" />
        </RouterLink>
      </template>
    </nav>

    <div class="sidebar-spacer" />

    <!-- User -->
    <div v-if="auth.user" class="sidebar-user">
      <div class="user-avatar avatar avatar-sm">{{ userInitials }}</div>
      <div class="user-info">
        <div class="user-name">{{ auth.user.username }}</div>
        <div class="user-role">{{ roleLabel }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTenantStore } from '@/stores/tenant'
import { useAuthStore } from '@/stores/auth'

const tenantStore = useTenantStore()
const auth = useAuthStore()

const tenantName = computed(() => tenantStore.current?.name || auth.user?.tenant_name || 'Organization')
const logoUrl    = computed(() => tenantStore.current?.logo_url || '')
const logoInitials = computed(() =>
  tenantName.value.trim().split(/\s+/).slice(0, 2).map(p => p[0].toUpperCase()).join('')
)
const userInitials = computed(() =>
  (auth.user?.username || auth.user?.email || 'U')[0].toUpperCase()
)

const roleLabels: Record<string, string> = {
  owner: 'Владелец', admin: 'Администратор', manager: 'Менеджер', viewer: 'Наблюдатель',
}
const roleLabel = computed(() => roleLabels[auth.user?.role || ''] || auth.user?.role || '')

interface NavItem { to: string; label: string; icon: string; feature?: string | null; locked?: boolean }

function withLock(items: NavItem[]) {
  return items.map(i => ({ ...i, locked: i.feature ? !tenantStore.hasFeature(i.feature as never) : false }))
}

const groups = computed(() => [
  withLock([
    { to: '/app',            label: 'Дашборд',       icon: 'pi pi-home',         feature: null },
    { to: '/app/contacts',   label: 'Контакты',      icon: 'pi pi-users',        feature: 'crm_builtin' },
    { to: '/app/companies',  label: 'Компании',      icon: 'pi pi-building',     feature: 'crm_builtin' },
    { to: '/app/deals',      label: 'Сделки',        icon: 'pi pi-chart-bar',    feature: 'crm_builtin' },
    { to: '/app/tasks',      label: 'Задачи',        icon: 'pi pi-check-square', feature: 'crm_builtin' },
    { to: '/app/pipelines',  label: 'Воронки',       icon: 'pi pi-sitemap',      feature: 'crm_builtin' },
    { to: '/app/stats',      label: 'Аналитика CRM', icon: 'pi pi-chart-line',   feature: 'crm_builtin' },
  ]),
  withLock([
    { to: '/app/channels',      label: 'Мессенджеры',  icon: 'pi pi-send',     feature: 'messenger_channels' },
    { to: '/app/documents',     label: 'Документы',    icon: 'pi pi-file',     feature: 'documents' },
    { to: '/app/telephony',     label: 'Телефония',    icon: 'pi pi-phone',    feature: 'telephony' },
    { to: '/app/distribution',  label: 'Распределение',icon: 'pi pi-sitemap',  feature: 'distribution' },
  ]),
  withLock([
    { to: '/app/integrations',  label: 'Интеграции',   icon: 'pi pi-plug',           feature: null },
    { to: '/app/team',          label: 'Команда',      icon: 'pi pi-users',          feature: null },
    { to: '/app/audit',         label: 'Аудит',        icon: 'pi pi-list-check',     feature: null },
    { to: '/app/notifications', label: 'Уведомления',  icon: 'pi pi-bell',           feature: null },
    { to: '/app/settings',      label: 'Настройки',    icon: 'pi pi-cog',            feature: null },
    { to: '/app/subscription',  label: 'Подписка',     icon: 'pi pi-wallet',         feature: null },
    { to: '/app/help',          label: 'Помощь',       icon: 'pi pi-question-circle',feature: null },
  ]),
])
</script>

<style scoped>
.layout-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Logo */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 14px;
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}

.logo-icon {
  width: 36px;
  height: 36px;
  min-width: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--p-primary-color);
  color: #fff;
  font-weight: 800;
  font-size: 14px;
  overflow: hidden;
  flex-shrink: 0;
}

.logo-img { width: 100%; height: 100%; object-fit: contain; }

.logo-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--p-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logo-sub { font-size: 11px; color: var(--p-text-muted-color); }

/* Menu */
.sidebar-menu {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 8px;
}

.menu-divider {
  height: 1px;
  background: var(--p-content-border-color);
  margin: 6px 8px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 6px;
  color: var(--p-text-muted-color);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
}

.menu-item:hover {
  background: var(--p-surface-hover);
  color: var(--p-text-color);
}

.menu-item-active,
.menu-item.menu-item-active {
  background: var(--p-primary-50);
  color: var(--p-primary-color);
  font-weight: 600;
}

.menu-item.locked { opacity: 0.55; }

.menu-item i { font-size: 15px; flex-shrink: 0; }

.lock-icon { margin-left: auto; font-size: 11px !important; opacity: 0.7; }

/* Spacer */
.sidebar-spacer { flex: 1; }

/* User area */
.sidebar-user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-top: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}

.user-name { font-size: 13px; font-weight: 600; color: var(--p-text-color); }
.user-role { font-size: 11px; color: var(--p-text-muted-color); }
</style>
