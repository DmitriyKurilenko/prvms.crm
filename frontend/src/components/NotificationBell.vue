<template>
  <div class="bell" @click="open = !open">
    <i class="pi pi-bell" />
    <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>

    <div v-if="open" class="panel surface-card">
      <header>
        <h4>Уведомления</h4>
        <PButton size="small" label="Прочитать все" text @click.stop="readAll" />
      </header>
      <div v-if="items.length === 0" class="empty">Пока пусто</div>
      <button
        v-for="item in items.slice(0, 8)"
        :key="item.id"
        class="row"
        :class="{ unread: !item.is_read }"
        @click.stop="read(item.id)"
      >
        <strong>{{ item.title }}</strong>
        <small>{{ item.body }}</small>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useNotifications } from '@/composables/useNotifications'

const open = ref(false)
const { items, unreadCount, load, connect, read, readAll } = useNotifications()

onMounted(async () => {
  await load()
  connect()
})
</script>

<style scoped>
.bell {
  position: relative;
  cursor: pointer;
  width: 42px;
  height: 42px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface);
  display: grid;
  place-items: center;
}

.badge {
  position: absolute;
  top: -5px;
  right: -5px;
  min-width: 20px;
  height: 20px;
  border-radius: 999px;
  background: var(--danger);
  color: white;
  display: grid;
  place-items: center;
  font-size: 11px;
}

.panel {
  position: absolute;
  top: 50px;
  right: 0;
  width: min(420px, 90vw);
  padding: 12px;
  z-index: 20;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.row {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--surface-alt);
  border-radius: 10px;
  padding: 10px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.row.unread {
  border-color: #34d399;
}

.empty {
  color: var(--text-muted);
  padding: 10px;
}
</style>
