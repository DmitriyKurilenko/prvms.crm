<template>
  <div class="surface-card player">
    <h4>Запись звонка</h4>
    <audio v-if="src" controls :src="src" style="width: 100%" />
    <p v-else>Запись не выбрана.</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{ src?: string | null }>()
</script>

<style scoped>
.player {
  padding: 14px;
}

p {
  color: var(--text-muted);
}
</style>
