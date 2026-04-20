<template>
  <section>
    <h1 class="page-title brand-heading">Недоступная функция</h1>
    <div class="surface-card" style="padding: 16px; max-width: 700px">
      <p>
        Функция <strong>{{ feature }}</strong> не входит в ваш текущий план.
        Обратитесь к администратору платформы для смены тарифа.
      </p>
      <RouterLink to="/subscription">
        <PButton label="Открыть раздел Подписка" icon="pi pi-wallet" />
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const feature = computed(() => route.query.feature || 'unknown')
</script>
