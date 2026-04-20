<template>
  <div class="surface-card builder">
    <h4>IVR Builder</h4>
    <PTextarea v-model="json" rows="7" />
    <small>JSON-конфигурация маршрутов IVR.</small>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const json = ref('[{"digit":"1","action":"queue:sales"}]')
</script>

<style scoped>
.builder {
  padding: 14px;
}

small {
  color: var(--text-muted);
}
</style>
