<template>
  <section>
    <h1 class="page-title brand-heading">Настройка организации</h1>
    <OnboardingWizard @done="onDone" />
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import OnboardingWizard from '@/components/OnboardingWizard.vue'

const router = useRouter()

const onDone = () => {
  router.push({ name: 'dashboard' })
}
</script>
