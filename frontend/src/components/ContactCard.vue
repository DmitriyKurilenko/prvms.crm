<template>
  <div class="surface-card card">
    <h4>{{ title }}</h4>
    <p>{{ subtitle }}</p>
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  subtitle: string
}>()
</script>

<style scoped>
.card {
  padding: 14px;
}

p {
  margin: 6px 0 0;
  color: var(--text-muted);
}
</style>
