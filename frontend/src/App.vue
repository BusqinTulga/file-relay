<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink, RouterView } from 'vue-router'
import { LogInIcon, ShieldCheckIcon, SendIcon } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import ThemeToggle from './components/common/ThemeToggle.vue'
import LanguageSwitcher from './components/common/LanguageSwitcher.vue'
import AlertComponent from '@/components/common/AlertComponent.vue'
import SiteFooter from '@/components/common/SiteFooter.vue'
import { useAdminSession, useAppShell } from '@/composables'
import { ROUTES } from '@/constants'
import { useConfigStore } from '@/stores/configStore'
import { useAdminStore } from '@/stores/adminStore'

const {
  route,
  isDarkMode,
  isLoading,
  routeTransitionMode,
  routeTransitionName,
  routeViewKey,
  showGlobalControls
} = useAppShell()

const configStore = useConfigStore()
const { config } = storeToRefs(configStore)
const adminStore = useAdminStore()
const { t } = useI18n()
const { verifySession } = useAdminSession()
const showAdminAddress = computed(() => config.value.show_admin_addr === 1)
const adminEntryLabel = computed(() =>
  t(adminStore.isAuthenticated ? 'admin.session.loggedIn' : 'admin.session.loggedOut')
)

watch(() => configStore.siteName, (name) => { document.title = name }, { immediate: true })

onMounted(() => {
  if (adminStore.hasToken) void verifySession()
})
</script>

<template>
  <div :class="['app-container', isDarkMode ? 'dark' : 'light']">
    <header
      v-if="!route.meta.requiresAuth"
      class="app-header relative z-[60] flex shrink-0 flex-wrap items-center justify-between gap-3 px-4 py-4 font-sans sm:px-6 sm:py-6"
    >
      <RouterLink to="/" class="flex items-center gap-3" :aria-label="t('shell.home')">
        <span
          class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border sm:h-12 sm:w-12"
          :class="
            isDarkMode
              ? 'border-white/10 bg-white/10 text-zinc-100'
              : 'border-white/80 bg-zinc-100 text-zinc-900 shadow-sm'
          "
        >
          <SendIcon class="h-6 w-6" :stroke-width="1.5" />
        </span>
        <span>
          <span class="block text-base font-semibold tracking-tight sm:text-lg"
            >{{ configStore.siteName }}</span
          >
          <span class="theme-text-muted mt-0.5 block text-xs">{{ configStore.siteDescription }}</span>
        </span>
      </RouterLink>
      <div v-if="showGlobalControls" class="ml-auto flex items-center gap-2 sm:gap-3">
        <RouterLink
          v-if="showAdminAddress"
          :to="ROUTES.ADMIN"
          class="header-control aspect-square"
          :aria-label="adminEntryLabel"
          :title="adminEntryLabel"
        >
          <ShieldCheckIcon v-if="adminStore.isAuthenticated" class="h-5 w-5" />
          <LogInIcon v-else class="h-5 w-5" />
        </RouterLink>
        <LanguageSwitcher />
        <ThemeToggle v-model="isDarkMode" />
      </div>
    </header>
    <div v-if="isLoading" class="loading-overlay">
      <div class="loading-spinner"></div>
    </div>
    <RouterView v-slot="{ Component }">
      <transition :name="routeTransitionName" :mode="routeTransitionMode">
        <component :is="Component" :key="routeViewKey" />
      </transition>
    </RouterView>

    <SiteFooter v-if="!route.meta.requiresAuth" />
    <AlertComponent />
  </div>
</template>

<style>
.app-header {
  min-height: 8rem;
}
@media (min-width: 640px) {
  .app-header {
    min-height: 6rem;
  }
}
.app-container {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  width: 100%;
  transition: background-color 0.5s ease;
}

.light {
  background-color: rgb(var(--color-page));
  color: rgb(var(--color-text));
}

.dark {
  background-color: rgb(var(--color-page));
  color: rgb(var(--color-text));
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.transfer-fade-enter-active,
.transfer-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.transfer-fade-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.transfer-fade-leave-active {
  position: absolute;
  inset: 0;
  width: 100%;
  pointer-events: none;
}

.transfer-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgb(var(--color-overlay) / var(--loading-overlay-opacity));
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.loading-spinner {
  width: var(--spinner-size);
  height: var(--spinner-size);
  border: var(--spinner-border-width) solid rgb(var(--color-accent-contrast));
  border-top-color: rgb(var(--color-accent));
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}
</style>
