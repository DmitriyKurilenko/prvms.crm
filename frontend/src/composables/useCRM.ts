import { ref } from 'vue'
import { api } from '@/api/http'

export function useCRM() {
  const loading = ref(false)
  const kanban = ref<Array<Record<string, unknown>>>([])

  const loadKanban = async (pipelineId: number) => {
    loading.value = true
    kanban.value = await api(`/crm/deals/kanban/${pipelineId}/`)
    loading.value = false
  }

  const moveDeal = async (dealId: number, stageId: number) => {
    await api(`/crm/deals/${dealId}/move/`, {
      method: 'PATCH',
      body: { stage_id: stageId }
    })
  }

  return {
    loading,
    kanban,
    loadKanban,
    moveDeal
  }
}
