<template>
  <div class="surface-card timeline">
    <h4>Таймлайн сделки</h4>
    <div v-for="item in items" :key="item.id" class="row">
      <strong>{{ item.title }}</strong>
      <small>{{ item.status }} · {{ item.created_at }}</small>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  items: Array<{ id: number; title: string; status: string; created_at: string }>
}>()
</script>

<style scoped>
.timeline {
  padding: 14px;
}

.row {
  border-left: 3px solid #10b981;
  padding: 8px 10px;
  margin-top: 8px;
  background: #f3fbf7;
}

small {
  color: var(--text-muted);
}
</style>
