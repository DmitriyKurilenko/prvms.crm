<template>
  <div>
    <slot v-if="isAllowed" />
    <slot v-else name="locked">
      <div class="locked surface-card">
        <i class="pi pi-lock" />
        <div>
          <h3>Функция недоступна</h3>
          <p>Раздел доступен после расширения тарифа.</p>
        </div>
        <RouterLink to="/subscription">
          <PButton label="Перейти к подписке" />
        </RouterLink>
      </div>
    </slot>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFeatureGate } from '@/composables/useFeatureGate'
import type { FeatureCode } from '@/types'

const props = defineProps<{
  feature: FeatureCode
}>()

const { hasFeature } = useFeatureGate()
const isAllowed = computed(() => hasFeature(props.feature))
</script>

<style scoped>
.locked {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.locked p {
  margin: 4px 0 0;
  color: var(--text-muted);
}
</style>
