import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'

export function useAuth() {
  const auth = useAuthStore()
  const { user, loading } = storeToRefs(auth)

  const login = async (email: string, password: string) => auth.login(email, password)
  const logout = async () => auth.logout()

  return {
    auth,
    user,
    loading,
    login,
    logout
  }
}
