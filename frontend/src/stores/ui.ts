import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    sidebarOpen: true,
    darkMode: false
  }),
  actions: {
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen
    },
    toggleTheme() {
      this.darkMode = !this.darkMode
      document.documentElement.classList.toggle('app-dark', this.darkMode)
    }
  }
})
