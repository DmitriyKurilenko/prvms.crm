<template>
  <div ref="sidebarRef" class="layout-sidebar">
    <AppMenu />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useLayout } from './composables/layout'
import AppMenu from './AppMenu.vue'

const { layoutState, isDesktop, hasOpenOverlay } = useLayout()
const route = useRoute()
const sidebarRef = ref<HTMLElement | null>(null)
let outsideClickListener: ((e: MouseEvent) => void) | null = null

watch(
  () => route.path,
  () => {
    if (isDesktop()) layoutState.activePath = null
    layoutState.overlayMenuActive = false
    layoutState.mobileMenuActive = false
    layoutState.menuHoverActive = false
  }
)

watch(hasOpenOverlay, (newVal) => {
  if (isDesktop()) {
    if (newVal) bindOutsideClickListener()
    else unbindOutsideClickListener()
  }
})

const bindOutsideClickListener = () => {
  if (!outsideClickListener) {
    outsideClickListener = (event: MouseEvent) => {
      if (isOutsideClicked(event)) layoutState.overlayMenuActive = false
    }
    document.addEventListener('click', outsideClickListener)
  }
}

const unbindOutsideClickListener = () => {
  if (outsideClickListener) {
    document.removeEventListener('click', outsideClickListener)
    outsideClickListener = null
  }
}

const isOutsideClicked = (event: MouseEvent) => {
  const topbarBtn = document.querySelector('.layout-menu-button')
  const target = event.target as Node
  return !(
    sidebarRef.value?.isSameNode(target) ||
    sidebarRef.value?.contains(target) ||
    topbarBtn?.isSameNode(target) ||
    topbarBtn?.contains(target)
  )
}

onBeforeUnmount(() => unbindOutsideClickListener())
</script>
