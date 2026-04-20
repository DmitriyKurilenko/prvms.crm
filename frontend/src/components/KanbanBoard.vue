<template>
  <div class="kanban">
    <section v-for="column in columns" :key="column.stage.id" class="surface-card col">
      <header>
        <h4>{{ column.stage.name }}</h4>
        <span>{{ column.deals.length }}</span>
      </header>
      <DealCard v-for="deal in column.deals" :key="deal.id" :deal="deal" @move="onMove(deal.id, $event)" />
    </section>
  </div>
</template>

<script setup lang="ts">
import DealCard from './DealCard.vue'

interface KanbanColumn {
  stage: { id: number; name: string }
  deals: Array<{ id: number; name: string; amount?: number | null; currency?: string }>
}

const props = defineProps<{ columns: KanbanColumn[] }>()
const emit = defineEmits<{ move: [dealId: number, stageId: number] }>()

const onMove = (dealId: number, stageId: number) => {
  emit('move', dealId, stageId)
}

void props
</script>

<style scoped>
.kanban {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.col {
  padding: 10px;
  min-height: 220px;
}

header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

@media (max-width: 1024px) {
  .kanban {
    grid-template-columns: 1fr;
  }
}
</style>
