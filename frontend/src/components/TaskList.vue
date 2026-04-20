<template>
  <div class="surface-card task-list">
    <h4>Задачи</h4>
    <ul>
      <li v-for="task in tasks" :key="task.id">
        <strong>{{ task.title }}</strong>
        <small>{{ task.status }}</small>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  tasks: Array<{ id: number; title: string; status: string }>
}>()
</script>

<style scoped>
.task-list {
  padding: 14px;
}

ul {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
}

li {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 10px;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
}

small {
  color: var(--text-muted);
}
</style>
