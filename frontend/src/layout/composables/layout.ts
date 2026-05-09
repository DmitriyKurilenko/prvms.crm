import { computed, reactive } from 'vue'
import { useUiStore } from '@/stores/ui'

const layoutConfig = reactive({
  menuMode: 'static' as 'static' | 'overlay'
})

const layoutState = reactive({
  staticMenuInactive: false,
  overlayMenuActive: false,
  mobileMenuActive: false,
  menuHoverActive: false,
  activePath: null as string | null
})

export function useLayout() {
  const ui = useUiStore()

  const toggleDarkMode = () => {
    ui.toggleTheme()
  }

  const toggleMenu = () => {
    if (isDesktop()) {
      if (layoutConfig.menuMode === 'static') {
        layoutState.staticMenuInactive = !layoutState.staticMenuInactive
      } else {
        layoutState.overlayMenuActive = !layoutState.overlayMenuActive
      }
    } else {
      layoutState.mobileMenuActive = !layoutState.mobileMenuActive
    }
  }

  const hideMobileMenu = () => {
    layoutState.mobileMenuActive = false
  }

  const isDesktop = () => window.innerWidth > 991

  const isDarkTheme = computed(() => ui.darkMode)
  const hasOpenOverlay = computed(() => layoutState.overlayMenuActive)

  return {
    layoutConfig,
    layoutState,
    isDarkTheme,
    toggleDarkMode,
    toggleMenu,
    hideMobileMenu,
    isDesktop,
    hasOpenOverlay
  }
}
