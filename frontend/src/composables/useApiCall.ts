/**
 * useApiCall — single enforcement point for the DEC-031 invariant:
 * every `await api(...)` must surface failures via a PrimeVue error toast.
 *
 * Replaces the hand-rolled `try { await … } catch { toast.add(…) }` block
 * duplicated across views. The success path stays at the call site:
 *
 *   const deal = await call(() => crmApi.getDeal(id), 'Не удалось открыть сделку.')
 *   if (deal !== undefined) { dealDetail.value = deal; showDealDetail.value = true }
 *
 * On error a toast is shown and `undefined` is returned (unless `rethrow`).
 * `onFinally` covers the loading-flag `finally {}` pattern.
 */
import { useToast } from 'primevue/usetoast'

export interface ApiCallOptions {
  /** Toast detail text shown on error. */
  errorDetail?: string
  /** Toast summary; defaults to «Ошибка». */
  errorSummary?: string
  /** Re-throw after toasting (caller needs the rejection). */
  rethrow?: boolean
  /** Always runs after success or error (loading flags etc.). */
  onFinally?: () => void
}

export function useApiCall() {
  const toast = useToast()

  async function call<T>(
    fn: () => Promise<T>,
    errorDetail?: string,
    options: ApiCallOptions = {},
  ): Promise<T | undefined> {
    try {
      return await fn()
    } catch (e) {
      toast.add({
        severity: 'error',
        summary: options.errorSummary ?? 'Ошибка',
        detail: errorDetail ?? options.errorDetail ?? 'Не удалось выполнить операцию.',
        life: 5000,
      })
      if (options.rethrow) throw e
      return undefined
    } finally {
      options.onFinally?.()
    }
  }

  return { call }
}
