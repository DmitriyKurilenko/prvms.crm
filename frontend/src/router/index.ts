import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import AppLayout from '@/layouts/AppLayout.vue'
import LandingView from '@/views/LandingView.vue'
import LoginView from '@/views/LoginView.vue'
import RegisterView from '@/views/RegisterView.vue'
import DashboardView from '@/views/DashboardView.vue'
import TeamView from '@/views/TeamView.vue'
import SettingsView from '@/views/SettingsView.vue'
import SubscriptionView from '@/views/SubscriptionView.vue'
import NotificationsView from '@/views/NotificationsView.vue'
import AuditView from '@/views/AuditView.vue'
import IntegrationsView from '@/views/IntegrationsView.vue'
import CRMView from '@/views/CRMView.vue'
import ContactsView from '@/views/ContactsView.vue'
import DealsView from '@/views/DealsView.vue'
import TasksView from '@/views/TasksView.vue'
import DistributionView from '@/views/DistributionView.vue'
import ContractsView from '@/views/ContractsView.vue'
import TelephonyView from '@/views/TelephonyView.vue'
import ChannelsView from '@/views/ChannelsView.vue'
import OnboardingView from '@/views/OnboardingView.vue'
import UpgradeView from '@/views/UpgradeView.vue'
import AcceptInviteView from '@/views/AcceptInviteView.vue'
import HelpView from '@/views/HelpView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import AssistantView from '@/views/AssistantView.vue'

export interface AppRouteMeta {
  public?: boolean
  roles?: Array<'owner' | 'admin' | 'manager' | 'viewer'>
  feature?: string
  title?: string
}

declare module 'vue-router' {
  interface RouteMeta extends AppRouteMeta {}
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'landing',
    component: LandingView,
    meta: { public: true }
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true }
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterView,
    meta: { public: true }
  },
  {
    path: '/invite/accept',
    name: 'accept-invite',
    component: AcceptInviteView,
    meta: { public: true }
  },
  {
    path: '/app',
    component: AppLayout,
    children: [
      {
        path: '',
        name: 'dashboard',
        component: DashboardView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], title: 'Дашборд' }
      },
      {
        path: 'contacts',
        name: 'contacts',
        component: ContactsView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], feature: 'crm_builtin', title: 'Контакты' }
      },
      {
        path: 'deals',
        name: 'deals',
        component: DealsView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], feature: 'crm_builtin', title: 'Сделки' }
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: TasksView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], feature: 'crm_builtin', title: 'Задачи' }
      },
      {
        path: 'crm',
        name: 'crm',
        component: CRMView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], feature: 'crm_builtin', title: 'CRM' }
      },
      {
        path: 'integrations',
        name: 'integrations',
        component: IntegrationsView,
        meta: { roles: ['owner', 'admin'], title: 'Интеграции' }
      },
      {
        path: 'channels',
        name: 'channels',
        component: ChannelsView,
        meta: { roles: ['owner', 'admin', 'manager'], feature: 'messenger_channels', title: 'Мессенджеры' }
      },
      {
        path: 'telephony',
        name: 'telephony',
        component: TelephonyView,
        meta: { roles: ['owner', 'admin'], feature: 'telephony', title: 'Телефония' }
      },
      {
        path: 'team',
        name: 'team',
        component: TeamView,
        meta: { roles: ['owner', 'admin'], title: 'Команда' }
      },
      {
        path: 'distribution',
        name: 'distribution',
        component: DistributionView,
        meta: { roles: ['owner', 'admin'], feature: 'distribution', title: 'Распределение' }
      },
      {
        path: 'contracts',
        name: 'contracts',
        component: ContractsView,
        meta: { roles: ['owner', 'admin', 'manager'], feature: 'contracts', title: 'Договоры' }
      },
      {
        path: 'notifications',
        name: 'notifications',
        component: NotificationsView,
        meta: { roles: ['owner', 'admin'], title: 'Уведомления' }
      },
      {
        path: 'audit',
        name: 'audit',
        component: AuditView,
        meta: { roles: ['owner', 'admin'], title: 'Аудит' }
      },
      {
        path: 'settings',
        name: 'settings',
        component: SettingsView,
        meta: { roles: ['owner'], title: 'Настройки' }
      },
      {
        path: 'subscription',
        name: 'subscription',
        component: SubscriptionView,
        meta: { roles: ['owner'], title: 'Подписка' }
      },
      {
        path: 'onboarding',
        name: 'onboarding',
        component: OnboardingView,
        meta: { roles: ['owner', 'admin'], title: 'Настройка' }
      },
      {
        path: 'upgrade',
        name: 'upgrade',
        component: UpgradeView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], title: 'Обновление' }
      },
      {
        path: 'help',
        name: 'help',
        component: HelpView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], title: 'Помощь' }
      },
      {
        path: 'assistant',
        name: 'assistant',
        component: AssistantView,
        meta: { roles: ['owner', 'admin', 'manager', 'viewer'], title: 'AI Ассистент' }
      }
    ]
  },
  {
    path: '/crm',
    redirect: '/app/crm'
  },
  {
    path: '/integrations',
    redirect: '/app/integrations'
  },
  {
    path: '/channels',
    redirect: '/app/channels'
  },
  {
    path: '/telephony',
    redirect: '/app/telephony'
  },
  {
    path: '/team',
    redirect: '/app/team'
  },
  {
    path: '/distribution',
    redirect: '/app/distribution'
  },
  {
    path: '/contracts',
    redirect: '/app/contracts'
  },
  {
    path: '/notifications',
    redirect: '/app/notifications'
  },
  {
    path: '/audit',
    redirect: '/app/audit'
  },
  {
    path: '/settings',
    redirect: '/app/settings'
  },
  {
    path: '/subscription',
    redirect: '/app/subscription'
  },
  {
    path: '/onboarding',
    redirect: '/app/onboarding'
  },
  {
    path: '/upgrade',
    redirect: '/app/upgrade'
  },
  {
    path: '/help',
    redirect: '/app/help'
  },
  {
    path: '/:pathMatch(.*)*',
    name: '404',
    component: NotFoundView,
    meta: { public: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
