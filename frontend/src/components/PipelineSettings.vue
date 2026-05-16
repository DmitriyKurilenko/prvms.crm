<template>
  <div class="surface-card block">
    <h4>Настройка воронки</h4>
    <PDataTable v-responsive-table :value="stages" size="small">
      <PColumn field="name" header="Стадия" />
      <PColumn field="stage_type" header="Тип" />
      <PColumn field="sort_order" header="Порядок" />
    </PDataTable>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  stages: Array<{ id: number; name: string; stage_type: string; sort_order: number }>
}>()
</script>

<style scoped>
.block {
  padding: 14px;
}
</style>
