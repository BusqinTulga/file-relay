<template>
  <transition-group
    name="alert-fade"
    tag="div"
    class="fixed left-1/2 top-5 z-50 flex w-max max-w-[calc(100vw-2rem)] -translate-x-1/2 flex-col items-center gap-2"
    aria-live="polite"
  >
    <div
      v-for="alert in alerts"
      :key="alert.id"
      class="max-w-full"
    >
      <p
        :role="alert.type === 'error' ? 'alert' : 'status'"
        :class="[
          'mx-auto w-fit max-w-full break-words rounded-full px-5 py-2.5 text-center text-sm font-medium shadow-lg shadow-black/10 ring-1 backdrop-blur',
          messageToneClass(alert.type)
        ]"
      >
        {{ alert.message }}
      </p>
    </div>
  </transition-group>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useAlertStore } from '@/stores/alertStore'
import { useInjectedDarkMode } from '@/composables'

const isDarkMode = useInjectedDarkMode()

const alertStore = useAlertStore()
const { alerts } = storeToRefs(alertStore)

type AlertType = 'success' | 'error' | 'warning' | 'info'

const messageToneClass = (type: AlertType) => {
  const darkClasses: Record<AlertType, string> = {
    success: 'bg-emerald-950/90 text-emerald-200 ring-emerald-400/30',
    error: 'bg-rose-950/90 text-rose-200 ring-rose-400/30',
    warning: 'bg-amber-950/90 text-amber-200 ring-amber-400/30',
    info: 'bg-sky-950/90 text-sky-200 ring-sky-400/30'
  }
  const lightClasses: Record<AlertType, string> = {
    success: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
    error: 'bg-rose-50 text-rose-800 ring-rose-200',
    warning: 'bg-amber-50 text-amber-900 ring-amber-200',
    info: 'bg-sky-50 text-sky-800 ring-sky-200'
  }

  return isDarkMode.value ? darkClasses[type] : lightClasses[type]
}
</script>

<style scoped>
.alert-fade-enter-active,
.alert-fade-leave-active {
  transition:
    opacity 0.24s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.alert-fade-enter-from,
.alert-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.98);
}
</style>
