<template>
  <article class="deal">
    <h5>{{ deal.name }}</h5>
    <p v-if="deal.amount">{{ deal.amount }} {{ deal.currency || 'RUB' }}</p>
    <div class="actions">
      <PButton text size="small" icon="pi pi-arrow-right" label="Далее" @click="moveNext" />
    </div>
  </article>
</template>

<script setup lang="ts">
const props = defineProps<{
  deal: {
    id: number
    name: string
    amount?: number | null
    currency?: string
  }
}>()

const emit = defineEmits<{ move: [stageId: number] }>()

const moveNext = () => {
  emit('move', -1)
}

void props
</script>

<style scoped>
.deal {
  background: #f3fbf7;
  border: 1px solid #dceee5;
  border-radius: 12px;
  padding: 10px;
  margin-bottom: 8px;
}

.deal h5,
.deal p {
  margin: 0;
}

.actions {
  margin-top: 6px;
}
</style>
