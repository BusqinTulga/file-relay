<template>
  <TransitionGroup
    name="alert-fade"
    tag="div"
    class="pointer-events-none fixed inset-x-4 top-4 z-[70] mx-auto flex max-w-sm flex-col items-center gap-2"
  >
    <div
      v-for="alert in alerts"
      :key="alert.id"
      class="theme-surface-strong pointer-events-auto flex w-full items-start gap-3 rounded-2xl border p-3 shadow-lg shadow-black/10 backdrop-blur-xl"
    >
      <span
        :class="`alert-icon--${alert.type}`"
        class="alert-icon flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
      >
        <component :is="icons[alert.type]" class="h-4 w-4" aria-hidden="true" />
      </span>
      <p
        :role="alert.type === 'error' ? 'alert' : 'status'"
        class="theme-text-strong min-w-0 flex-1 break-words pt-1.5 text-sm font-medium"
      >
        {{ alert.message }}
      </p>
      <button
        type="button"
        class="theme-icon-button flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors"
        :aria-label="t('common.close')"
        @click="alertStore.removeAlert(alert.id)"
      >
        <XIcon class="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  </TransitionGroup>
</template>

<script setup lang="ts">
import { CircleAlertIcon, CircleCheckIcon, InfoIcon, TriangleAlertIcon, XIcon } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAlertStore } from '@/stores/alertStore'

const { locale, t } = useI18n()
const alertStore = useAlertStore()
const { alerts } = storeToRefs(alertStore)
watch(locale, () => alertStore.$reset())

const icons = {
  success: CircleCheckIcon,
  error: CircleAlertIcon,
  warning: TriangleAlertIcon,
  info: InfoIcon
}
</script>

<style scoped>
.alert-icon {
  --alert-tone: var(--color-text-muted);
  background: rgb(var(--alert-tone) / 0.12);
  color: rgb(var(--alert-tone));
}

.alert-icon--success {
  --alert-tone: var(--color-success);
}

.alert-icon--error {
  --alert-tone: var(--color-danger);
}

.alert-icon--warning {
  --alert-tone: var(--color-warning);
}

@media (prefers-reduced-motion: no-preference) {
  .alert-fade-enter-active,
  .alert-fade-leave-active {
    transition:
      opacity 0.2s ease,
      transform 0.2s ease;
  }

  .alert-fade-enter-from,
  .alert-fade-leave-to {
    opacity: 0;
    transform: translateY(-6px);
  }
}
</style>
