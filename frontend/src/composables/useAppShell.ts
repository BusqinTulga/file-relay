import { computed, onMounted, onUnmounted, provide } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AUTH_EVENTS } from '@/services'
import { ROUTES } from '@/constants'
import { useTheme } from './useTheme'
import { usePublicConfigBootstrap } from './usePublicConfigBootstrap'
import { useRouteLoading } from './useRouteLoading'
import { useAdminStore } from '@/stores/adminStore'

const selectionHighlightName = 'filerelay-selection'
const selectionHighlightClass = 'uses-text-selection-highlight'

export function useAppShell() {
  const route = useRoute()
  const router = useRouter()
  const { isDarkMode, toggleTheme, initTheme } = useTheme()
  const { isLoading, setupRouteLoading } = useRouteLoading(router)
  const { syncPublicConfig } = usePublicConfigBootstrap()
  const adminStore = useAdminStore()
  const showGlobalControls = computed(() => route.meta.showGlobalControls !== false)
  const routeTransitionName = computed(() => String(route.meta.routeTransition || 'fade'))
  const routeTransitionMode = computed(() => (route.meta.routeTransition ? undefined : 'out-in'))
  const routeViewKey = computed(() =>
    route.path === ROUTES.ADMIN || route.path.startsWith(`${ROUTES.ADMIN}/`)
      ? ROUTES.ADMIN
      : route.fullPath
  )

  let cleanupThemeListener: (() => void) | null = null
  let setupRedirecting = false

  const updateSelectionHighlight = () => {
    const selection = document.getSelection()
    if (!selection || selection.isCollapsed) {
      CSS.highlights.delete(selectionHighlightName)
      return
    }

    // Reuse native ranges so highlighting follows the selection without changing what is copied.
    const ranges = Array.from({ length: selection.rangeCount }, (_, index) =>
      selection.getRangeAt(index)
    )
    CSS.highlights.set(selectionHighlightName, new Highlight(...ranges))
  }

  const handleUnauthorized = () => {
    adminStore.logout()
    if (router.currentRoute.value.path !== ROUTES.LOGIN) {
      void router.push({
        path: ROUTES.LOGIN,
        query: {
          redirect: router.currentRoute.value.fullPath
        }
      })
    }
  }

  const handleSetupRequired = (event: Event) => {
    const setupPath =
      event instanceof CustomEvent && typeof event.detail?.setupPath === 'string'
        ? event.detail.setupPath
        : '/setup'

    if (
      !setupPath ||
      setupRedirecting ||
      window.location.pathname.replace(/\/+$/, '') === setupPath
    ) {
      return
    }

    setupRedirecting = true
    window.location.assign(setupPath)
  }

  onMounted(() => {
    cleanupThemeListener = initTheme()
    setupRouteLoading()
    if (
      typeof Highlight === 'function' &&
      CSS.highlights &&
      CSS.supports(`selector(::highlight(${selectionHighlightName}))`)
    ) {
      document.documentElement.classList.add(selectionHighlightClass)
      document.addEventListener('selectionchange', updateSelectionHighlight)
      updateSelectionHighlight()
    }
    window.addEventListener(AUTH_EVENTS.UNAUTHORIZED, handleUnauthorized)
    window.addEventListener(AUTH_EVENTS.SETUP_REQUIRED, handleSetupRequired)
    void syncPublicConfig()
  })

  onUnmounted(() => {
    cleanupThemeListener?.()
    document.documentElement.classList.remove(selectionHighlightClass)
    document.removeEventListener('selectionchange', updateSelectionHighlight)
    CSS.highlights?.delete(selectionHighlightName)
    window.removeEventListener(AUTH_EVENTS.UNAUTHORIZED, handleUnauthorized)
    window.removeEventListener(AUTH_EVENTS.SETUP_REQUIRED, handleSetupRequired)
  })

  provide('isDarkMode', isDarkMode)
  provide('toggleTheme', toggleTheme)
  provide('isLoading', isLoading)

  return {
    isDarkMode,
    isLoading,
    route,
    routeTransitionMode,
    routeTransitionName,
    routeViewKey,
    showGlobalControls
  }
}
