<template>
  <div class="layout-menu-container">
    <ul class="layout-menu">
      <template v-for="(group, gi) in groups" :key="gi">
        <li v-if="gi > 0" class="layout-menu-separator" />
        <li
          v-for="item in group"
          :key="item.to"
          class="layout-menuitem"
          :class="{ 'layout-menuitem-locked': item.locked }"
        >
          <RouterLink
            v-if="!item.locked"
            :to="item.to"
            class="layout-menuitem-link"
            :active-class="item.to === '/app' ? '' : 'layout-menuitem-active'"
            :exact-active-class="'layout-menuitem-active'"
            :title="item.label"
          >
            <i :class="['layout-menuitem-icon', item.icon]" />
            <span class="layout-menuitem-text">{{ item.label }}</span>
          </RouterLink>
          <span v-else class="layout-menuitem-link" :title="item.label">
            <i :class="['layout-menuitem-icon', item.icon]" />
            <span class="layout-menuitem-text">{{ item.label }}</span>
            <i class="pi pi-lock layout-menuitem-lock-icon" />
          </span>
        </li>
      </template>
    </ul>

    <div v-if="auth.user" class="layout-menu-footer">
      <div class="layout-menu-user-avatar">{{ userInitials }}</div>
      <div class="layout-menu-user-info">
        <div class="layout-menu-user-name">{{ auth.user.username }}</div>
        <div class="layout-menu-user-role">{{ roleLabel }}</div>
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

const planReady = computed(() => tenantStore.planLoaded)

interface NavItem { to: string; label: string; icon: string; feature?: string | null; locked?: boolean }

function withLock(items: NavItem[]) {
  if (!planReady.value) {
    return items.map(i => ({ ...i, locked: false }))
  }
  return items.map(i => {
    if (i.locked) return i
    return { ...i, locked: i.feature ? !tenantStore.hasFeature(i.feature as never) : false }
  })
}

const groups = computed(() => [
  withLock([
    { to: '/app',          label: 'Дашборд',       icon: 'pi pi-home',          feature: null },
    { to: '/app/contacts', label: 'Контакты',      icon: 'pi pi-users',         feature: 'crm_builtin' },
    { to: '/app/companies',label: 'Компании',      icon: 'pi pi-building',      feature: 'crm_builtin' },
    { to: '/app/products', label: 'Товары',        icon: 'pi pi-box',           feature: 'crm_builtin' },
    { to: '/app/webforms', label: 'Веб-формы',     icon: 'pi pi-id-card',       feature: 'crm_builtin' },
    { to: '/app/deals',    label: 'Сделки',        icon: 'pi pi-chart-bar',     feature: 'crm_builtin' },
    { to: '/app/tags',     label: 'Теги',          icon: 'pi pi-tags',          feature: 'crm_builtin' },
    { to: '/app/automation', label: 'Автоматизации', icon: 'pi pi-bolt',        feature: 'crm_builtin' },
    { to: '/app/tasks',    label: 'Задачи',        icon: 'pi pi-check-square',  feature: 'crm_builtin' },
  ]),
  withLock([
    { to: '/app/chats',       label: 'Чаты',         icon: 'pi pi-send',     feature: 'messenger_channels' },
    { to: '/app/documents',   label: 'Документы',    icon: 'pi pi-file',     feature: 'documents' },
    { to: '/app/telephony',   label: 'Телефония',    icon: 'pi pi-phone',    feature: 'telephony' },
  ]),
  withLock([
    { to: '/app/integrations',  label: 'Интеграции',  icon: 'pi pi-plug',            feature: null, locked: true },
    { to: '/app/team',          label: 'Команда',     icon: 'pi pi-users',           feature: null },
    { to: '/app/assistant',     label: 'AI Ассистент', icon: 'pi pi-comment',         feature: null },
    { to: '/app/audit',         label: 'Аудит',       icon: 'pi pi-list-check',      feature: null },
    { to: '/app/settings',      label: 'Настройки',   icon: 'pi pi-cog',             feature: null },
    { to: '/app/subscription',  label: 'Подписка',    icon: 'pi pi-wallet',          feature: null },
    { to: '/app/help',          label: 'Помощь',      icon: 'pi pi-question-circle', feature: null },
  ]),
])

const userInitials = computed(() =>
  (auth.user?.username || auth.user?.email || 'U')[0].toUpperCase()
)
const roleLabels: Record<string, string> = {
  owner: 'Владелец', admin: 'Администратор', manager: 'Менеджер', viewer: 'Наблюдатель',
}
const roleLabel = computed(() => roleLabels[auth.user?.role || ''] || auth.user?.role || '')
</script>
