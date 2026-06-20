<template>
  <div class="kanban-board">
    <div
      v-for="col in columns"
      :key="col.stage.id"
      class="kanban-col surface-card"
      @dragover.prevent
      @drop="$emit('drop', $event, col.stage.id)"
    >
      <div class="col-header">
        <span class="stage-dot" :style="{ background: col.stage.color }" />
        <span class="col-name">{{ col.stage.name }}</span>
        <span class="col-count">{{ col.deals.length }}</span>
      </div>
      <div class="col-amount">{{ colTotal(col) }}</div>
      <div class="col-body">
        <div
          v-for="deal in col.deals"
          :key="deal.id"
          class="deal-card surface-card"
          :draggable="canUpdateDeal"
          @dragstart="canUpdateDeal && $emit('dragstart', $event, deal.id)"
          @click="$emit('openDeal', deal.id)"
        >
          <div class="deal-name">{{ deal.name }}</div>
          <div v-if="deal.amount" class="deal-amount">{{ deal.amount.toLocaleString('ru') }} {{ deal.currency }}</div>
          <div class="deal-meta">
            <span v-if="deal.contact_id" class="deal-contact">{{ contactLabel(deal.contact_id) }}</span>
          </div>
        </div>
      </div>
      <button v-if="canCreateDeal" class="add-deal-btn" @click="$emit('addForStage', col.stage.id)">
        <i class="pi pi-plus" /> Добавить
      </button>
    </div>
    <div v-if="showEmpty" class="empty-state">Выберите воронку</div>
  </div>
</template>

<script setup lang="ts">
import type { KanbanColumn } from '@/api/crm'

/**
 * Презентационная Kanban-доска сделок. Drag-состояние (dragDealId) и обработчики
 * перемещения/загрузки остаются в родителе (DealsView): дочерний компонент лишь
 * прокидывает нативные события dragstart/drop вверх — перенос 1:1.
 */
defineProps<{
  columns: KanbanColumn[]
  canCreateDeal: boolean
  canUpdateDeal: boolean
  showEmpty: boolean
  contactLabel: (id: number | null | undefined) => string
  colTotal: (col: KanbanColumn) => string
}>()

defineEmits<{
  dragstart: [e: DragEvent, dealId: number]
  drop: [e: DragEvent, stageId: number]
  openDeal: [dealId: number]
  addForStage: [stageId: number]
}>()
</script>

<style scoped>
.kanban-board {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  flex: 1;
  min-height: 0;
}

.kanban-col {
  min-width: 260px;
  max-width: 300px;
  flex: 0 0 auto;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.col-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.stage-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.col-name {
  font-weight: 700;
  font-size: 13px;
  flex: 1;
}

.col-count {
  background: var(--surface-alt);
  border-radius: 99px;
  padding: 1px 8px;
  font-size: 12px;
  font-weight: 600;
}

.col-amount {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 600;
  min-height: 16px;
}

.col-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.deal-card {
  padding: 12px;
  cursor: grab;
  border: 1px solid var(--line);
  transition: box-shadow 0.15s, transform 0.1s;
}

.deal-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
  border-color: var(--brand);
}

.deal-name {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 4px;
}

.deal-amount {
  font-size: 13px;
  color: var(--brand);
  font-weight: 700;
}

.deal-meta {
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-muted);
}

.add-deal-btn {
  width: 100%;
  padding: 8px;
  border: 1.5px dashed var(--line);
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  font-family: 'Nunito Sans', sans-serif;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.15s;
  flex-shrink: 0;
}

.add-deal-btn:hover {
  background: var(--surface-alt);
  border-color: var(--brand);
  color: var(--brand);
}

.empty-state {
  color: var(--text-muted);
  padding: 24px;
  text-align: center;
}
</style>
