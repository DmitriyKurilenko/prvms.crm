import type { Pinia } from 'pinia'
import type { Router } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useTenantStore } from '@/stores/tenant'
import { getAccessToken } from '@/api/http'
import { me } from '@/api/auth'

export function installGuards(router: Router, pinia: Pinia): void {
  router.beforeEach(async (to) => {
    const auth = useAuthStore(pinia)
    const tenant = useTenantStore(pinia)

    if (!auth.initialized) {
      await auth.initialize()
    }

    // If we have a valid token but no user (page refresh race),
    // try to fetch user data before redirecting to login.
    if (!auth.user && getAccessToken() && !to.meta.public) {
      try {
        auth.user = await me()
      } catch {
        // User data fetch failed — redirect to login
      }
    }

    if (to.meta.public) {
      if (auth.isAuthenticated && (to.name === 'login' || to.name === 'register' || to.name === 'landing')) {
        return { name: 'dashboard' }
      }
      return true
    }

    if (!auth.isAuthenticated) {
      return {
        name: 'login',
        query: { redirect: to.fullPath }
      }
    }

    if (!tenant.loaded) {
      try { await tenant.ensureLoaded() } catch { /* allow navigation if tenant fails */ }
    }

    // Trial expired → only allow subscription and settings pages
    const allowedWhenExpired = ['subscription', 'settings', 'upgrade']
    if (tenant.current?.trial_expired && !allowedWhenExpired.includes(to.name as string)) {
      return { name: 'subscription' }
    }

    // Onboarding incomplete → redirect owner/admin to onboarding wizard
    const allowedDuringOnboarding = ['onboarding', 'subscription', 'settings', 'upgrade']
    if (
      tenant.current &&
      (tenant.current.onboarding_step ?? 0) < 4 &&
      auth.user &&
      ['owner', 'admin'].includes(auth.user.role) &&
      !allowedDuringOnboarding.includes(to.name as string)
    ) {
      return { name: 'onboarding' }
    }

    const requiredRoles = to.meta.roles
    if (requiredRoles && auth.user && !requiredRoles.includes(auth.user.role)) {
      return { name: 'dashboard' }
    }

    if (to.meta.feature && !tenant.hasFeature(to.meta.feature as never)) {
      return {
        name: 'upgrade',
        query: { feature: to.meta.feature }
      }
    }

    return true
  })
}
