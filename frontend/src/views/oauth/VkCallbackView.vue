<template>
  <div class="vk-callback flex flex-col items-center justify-center min-h-screen p-6">
    <PProgressSpinner v-if="loading" />
    <div v-else-if="error" class="error text-center">
      <h2 class="text-xl font-semibold text-red-600 mb-2">Ошибка подключения</h2>
      <p class="text-gray-700 mb-4">{{ error }}</p>
      <PButton label="Назад к мессенджерам" @click="goBack" />
    </div>
    <div v-else class="text-center">
      <h2 class="text-xl font-semibold mb-2">ВКонтакте подключён</h2>
      <p class="text-gray-700 mb-2">Создано каналов: {{ result.created.length }}</p>
      <ul v-if="result.failed.length" class="text-left text-red-600 mb-4">
        <li v-for="f in result.failed" :key="f.group_id">{{ f.group_id }}: {{ f.error }}</li>
      </ul>
      <PButton label="К мессенджерам" @click="goBack" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { completeVkOauth } from '@/api/channels'

const router = useRouter()
const toast = useToast()

const loading = ref(true)
const error = ref('')
const result = ref<{ created: any[]; failed: any[] }>({ created: [], failed: [] })

const goBack = () => {
  router.push('/app/settings?tab=channels')
}

onMounted(async () => {
  try {
    const hash = window.location.hash.slice(1)
    const params = new URLSearchParams(hash)

    const tokens: Array<{ group_id: number; access_token: string }> = []
    for (const [key, value] of params.entries()) {
      if (key.startsWith('access_token_')) {
        const groupId = key.replace('access_token_', '')
        if (groupId && value) {
          tokens.push({ group_id: Number(groupId), access_token: value })
        }
      }
    }

    const state = sessionStorage.getItem('vk_oauth_state')
    if (!state) {
      error.value = 'Отсутствует state. Попробуйте подключить ВКонтакте заново.'
      loading.value = false
      return
    }

    const response = await completeVkOauth({ state, tokens })
    result.value = response
    loading.value = false

    setTimeout(() => {
      goBack()
    }, 2500)
  } catch (e: any) {
    loading.value = false
    error.value = e?.message || 'Не удалось подключить ВКонтакте'
    toast.add({ severity: 'error', summary: 'Ошибка', detail: error.value, life: 5000 })
  }
})
</script>
