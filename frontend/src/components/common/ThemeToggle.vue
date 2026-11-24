<script setup lang="ts">
import { inject } from 'vue'
import { SunIcon, MoonIcon } from 'lucide-vue-next'

const isDarkMode = inject('isDarkMode') as { value: boolean }
const toggleTheme = inject('toggleTheme') as () => void

const toggleColorMode = () => {
  toggleTheme()
}
</script>

<template>
  <button
    type="button"
    @click="toggleColorMode"
    class="header-control aspect-square"
    :aria-label="$t('shell.theme')"
  >
    <SunIcon v-if="isDarkMode" class="h-5 w-5" />
    <MoonIcon v-else class="h-5 w-5" />
  </button>
</template>
