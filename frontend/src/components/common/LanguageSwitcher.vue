<template>
  <div ref="switcherRef" class="relative">
    <button
      type="button"
      class="header-control gap-2 px-3 text-sm sm:px-4"
      :aria-expanded="isDropdownOpen"
      @click="toggleDropdown"
    >
      <GlobeIcon class="w-4 h-4" />
      <span class="text-sm font-medium">{{ currentLanguage.name }}</span>
      <ChevronDownIcon
        :class="['w-4 h-4 transition-transform duration-200', { 'rotate-180': isDropdownOpen }]"
      />
    </button>

    <transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="isDropdownOpen"
        :class="[
          'absolute right-0 z-50 mt-2 w-32 overflow-hidden rounded-xl border shadow-lg',
          isDarkMode
            ? 'border-zinc-800 bg-zinc-900 text-zinc-100'
            : 'border-slate-100 bg-white text-slate-700'
        ]"
      >
        <div class="py-1">
          <button
            v-for="language in availableLocales"
            :key="language.code"
            @click="switchLanguage(language.code)"
            :class="[
              'w-full text-left px-4 py-2 text-sm transition-colors duration-150',
              currentLocale === language.code
                ? isDarkMode
                  ? 'bg-white/10 text-zinc-100'
                  : 'bg-zinc-100 text-zinc-900'
                : isDarkMode
                  ? 'text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100'
                  : 'text-slate-600 hover:bg-slate-50'
            ]"
            :lang="language.code"
          >
            {{ language.name }}
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { GlobeIcon, ChevronDownIcon } from 'lucide-vue-next'
import { availableLocales, setLocale } from '@/i18n/index'

const { locale } = useI18n()
const isDarkMode = inject('isDarkMode')
const isDropdownOpen = ref(false)
const switcherRef = ref<HTMLElement | null>(null)

const currentLocale = computed(() => locale.value)
const currentLanguage = computed(() => {
  return (
    availableLocales.find(
      (lang: { code: string; name: string }) => lang.code === currentLocale.value
    ) || availableLocales[0]
  )
})

const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
}

const switchLanguage = (langCode: string) => {
  setLocale(langCode)
  isDropdownOpen.value = false
}

// 点击外部关闭下拉菜单
const handleClickOutside = (event: Event) => {
  const target = event.target as Node | null
  if (target && !switcherRef.value?.contains(target)) {
    isDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>
