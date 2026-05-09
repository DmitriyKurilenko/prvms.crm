import { defineStore } from 'pinia'

const THEME_KEY = 'crm.theme'
type ThemeMode = 'light' | 'dark'

function readStoredTheme(): ThemeMode | null {
  if (typeof localStorage === 'undefined') return null
  const value = localStorage.getItem(THEME_KEY)
  return value === 'dark' || value === 'light' ? value : null
}

function detectSystemTheme(): ThemeMode {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(mode: ThemeMode) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('app-dark', mode === 'dark')
}

export const useUiStore = defineStore('ui', {
  state: () => ({
    sidebarOpen: true,
    darkMode: false,
    themeInitialized: false
  }),
  actions: {
    initTheme() {
      if (this.themeInitialized) return
      const stored = readStoredTheme()
      const mode: ThemeMode = stored ?? detectSystemTheme()
      this.darkMode = mode === 'dark'
      applyTheme(mode)
      this.themeInitialized = true
    },
    setTheme(mode: ThemeMode) {
      this.darkMode = mode === 'dark'
      applyTheme(mode)
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(THEME_KEY, mode)
      }
    },
    toggleTheme() {
      this.setTheme(this.darkMode ? 'light' : 'dark')
    },
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen
    }
  }
})
