<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Download, Trash2, ArrowRight } from 'lucide-vue-next'
import FileUploadArea from '@/components/common/FileUploadArea.vue'
import { useRelay } from '@/composables'
import { formatFileSize, formatSizeLimit } from '@/utils/common'
const { t, locale } = useI18n()
const {
  mode,
  session,
  passcode,
  files,
  requests,
  pendingRequest,
  queue,
  error,
  busy,
  policy,
  pair,
  repair,
  resume,
  decide,
  remove,
  addFiles,
  retry,
  canRetry,
  cancel
} = useRelay()
const time = (n: number) => new Date(n * 1000).toLocaleString(locale.value)
</script>
<template>
  <main class="relay mx-auto w-full max-w-4xl px-4 py-4 font-sans sm:px-8">
    <p
      v-if="error"
      role="alert"
      class="mb-5 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm"
    >
      {{ error }}
    </p>
    <section v-if="mode === 'loading'" class="panel p-8" aria-live="polite">
      {{ t('relay.loading') }}
    </section>
    <section v-else-if="mode === 'pair'" class="panel mx-auto max-w-lg p-7 sm:p-10">
      <h2 class="mb-6 text-xl font-semibold">{{ t('relay.pairTitle') }}</h2>
      <form novalidate @submit.prevent="pair">
        <span id="passcode-label" class="text-sm">{{ t('relay.passcode') }}</span>
        <input
          id="passcode"
          aria-labelledby="passcode-label"
          v-model="passcode"
          inputmode="numeric"
          pattern="[0-9]{1,4}"
          maxlength="4"
          autocomplete="off"
          required
          class="my-3 w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-transparent px-4 py-4 text-center text-3xl tracking-[.5em] caret-transparent outline-none focus:ring-2 focus:ring-zinc-400"
          placeholder="0317"
        />
        <button
          type="submit"
          :disabled="busy"
          class="primary flex w-full items-center justify-center gap-2"
        >
          {{ t(busy ? 'relay.pairing' : 'relay.start') }}<ArrowRight :size="18" />
        </button>
      </form>
      <button
        v-if="session?.paired"
        :disabled="busy"
        class="mt-5 text-sm text-zinc-700 dark:text-zinc-300"
        @click="resume"
      >
        {{ t('relay.resume') }}
      </button>
    </section>
    <section v-else-if="mode === 'waiting'" class="panel mx-auto max-w-lg p-8" aria-live="polite">
      <h2 class="text-xl font-semibold">{{ t('relay.waitingTitle') }}</h2>
      <p class="my-4 text-sm leading-6 opacity-65">
        {{ t('relay.waitingHint') }}
      </p>
      <p v-if="pendingRequest" class="mb-4 text-sm">
        {{ t('relay.requestExpires', { id: pendingRequest.request_id.slice(0, 8), time: time(pendingRequest.expires) }) }}
      </p>
      <button class="secondary" @click="repair">{{ t('relay.repair') }}</button>
    </section>
    <template v-else>
      <section class="panel mb-5 flex flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <span class="text-sm opacity-60">{{ t('relay.currentCode') }}</span
          ><strong class="ml-3 text-2xl tracking-widest">{{ session?.passcode }}</strong>
          <p class="mt-1 text-xs opacity-55">{{ t('relay.pairRemembered') }}</p>
        </div>
        <button class="secondary text-sm" @click="repair">{{ t('relay.repair') }}</button>
      </section>
      <section v-if="requests.length" class="panel mb-5 p-5" aria-live="polite">
        <h2 class="mb-3 font-semibold">{{ t('relay.joinRequests') }}</h2>
        <div
          v-for="request in requests"
          :key="request.id"
          class="flex flex-wrap items-center gap-3 border-t border-slate-400/15 py-3 text-sm"
        >
          <span class="flex-1"
            >{{ t('relay.requestExpires', { id: request.id.slice(0, 8), time: time(request.expires) }) }}</span
          >
          <button class="primary" @click="decide(request.id, true)">{{ t('relay.approve') }}</button
          ><button class="secondary" @click="decide(request.id, false)">{{ t('relay.reject') }}</button>
        </div>
      </section>
      <section class="panel mb-5 overflow-hidden" :aria-label="t('relay.uploadRegion')">
        <div class="px-5 py-5 sm:px-8">
          <h2 class="mb-3 text-lg font-semibold">{{ t('relay.uploadTitle') }}</h2>
          <p v-if="!policy?.open_upload" class="mb-3 text-xs opacity-65" aria-live="polite">
            {{ t(policy ? 'relay.uploadPaused' : 'relay.loadingPolicy') }}
          </p>
          <FileUploadArea
            class="payload-panel"
            :placeholder="t('relay.dropFiles')"
            :description="policy?.open_upload ? t('relay.uploadFormats', { limit: formatSizeLimit(policy.upload_size) }) : t('relay.uploadUnavailable')"
            @file-selected="addFiles([$event])"
            @files-selected="addFiles"
          />
        </div>
        <p class="section-footer px-5 py-2.5 text-center text-xs leading-5 sm:px-8">
          {{ t('relay.retention') }}
        </p>
        <section
          v-if="queue.length"
          class="border-t border-zinc-200/60 p-5 dark:border-zinc-800"
          aria-live="polite"
        >
          <h2 class="mb-3 font-semibold">{{ t('relay.queue') }}</h2>
          <div v-for="item in queue" :key="item.key" class="border-t border-slate-400/15 py-4">
            <div class="flex items-center gap-3">
              <span class="min-w-0 flex-1 break-all text-sm">{{ item.file.name }}</span
              ><span class="text-xs opacity-60">
                {{ t('relay.' + item.state) }}
                <template v-if="item.state !== 'alreadyUploaded'">{{ item.progress }}%</template>
              </span>
              <button
                v-if="canRetry(item)"
                class="text-sm text-zinc-700 dark:text-zinc-300"
                @click="retry(item)"
              >
                {{ t('send.uploadArea.retry') }}
              </button>
              <button
                v-else-if="['queued', 'hashing', 'uploading', 'publishing'].includes(item.state)"
                class="text-sm opacity-60"
                @click="cancel(item)"
              >
                {{ t('relay.stop') }}
              </button>
            </div>
            <progress
              :value="item.progress"
              max="100"
              class="mt-3 h-1.5 w-full accent-zinc-800 dark:accent-zinc-200"
            />
            <p v-if="item.error" class="mt-1 text-xs text-red-500">{{ item.error }}</p>
          </div>
        </section>
      </section>
      <section class="panel p-5 sm:p-8" :aria-label="t('relay.downloadRegion')">
        <div class="mb-3">
          <h2 class="flex items-center gap-3 font-semibold">
            <span class="inline-flex items-center gap-2"><Download :size="18" />{{ t('relay.downloadTitle') }}</span>
            <span
              class="inline-flex min-w-6 items-center justify-center rounded-full bg-slate-500/10 px-2 py-0.5 text-xs font-medium leading-5 tabular-nums text-slate-500 dark:text-slate-400"
              :aria-label="t('relay.fileCount', { count: files.length })"
            >
              {{ files.length }}
            </span>
          </h2>
        </div>
        <p v-if="!files.length" class="py-10 text-center text-sm opacity-50">
          {{ t('relay.empty') }}
        </p>
        <article
          v-for="file in files"
          :key="file.id"
          class="flex flex-wrap items-center gap-4 border-t border-slate-400/15 py-5"
        >
          <div class="min-w-0 flex-1 basis-52">
            <h3 class="break-all text-sm font-medium">{{ file.name }}</h3>
            <p class="mt-1 text-xs opacity-55">
              {{ formatFileSize(file.size) }} · {{ t('relay.publishedAt', { time: time(file.published) }) }}
            </p>
            <p class="mt-1 text-xs opacity-55">
              {{ t(file.first_sent ? 'relay.cleanupAt' : 'relay.availableUntil', { time: time(file.expires) }) }}
            </p>
          </div>
          <a
            :href="`/api/relay/files/${file.id}/download?lang=${locale}`"
            class="secondary inline-flex items-center gap-2 text-sm"
            ><Download :size="16" />{{ t('simple.download') }}</a
          >
          <button
            class="rounded-lg p-2 opacity-60 hover:text-red-500"
            :aria-label="t('relay.deleteFile', { name: file.name })"
            @click="remove(file.id)"
          >
            <Trash2 :size="17" />
          </button>
        </article>
      </section>
    </template>
  </main>
</template>
<style scoped>
.panel {
  border: 1px solid rgb(255 255 255 / 0.7);
  border-radius: 2rem;
  background: rgb(255 255 255 / 0.8);
  box-shadow: 0 24px 70px -28px rgb(24 24 27 / 0.18);
  backdrop-filter: blur(64px);
}
.primary {
  border-radius: 0.75rem;
  background: #27272a;
  color: white;
  padding: 0.7rem 1.2rem;
  font-weight: 500;
}
.primary:hover {
  background: #18181b;
}
.primary:disabled {
  opacity: 0.5;
}
.secondary {
  border: 1px solid rgb(var(--color-border));
  border-radius: 0.75rem;
  padding: 0.6rem 1rem;
}
button,
a {
  transition: background-color 0.15s;
}
button:focus-visible,
a:focus-visible {
  outline: 2px solid rgb(var(--color-focus-ring));
  outline-offset: 3px;
}

:global(.dark .relay .panel) {
  border-color: rgb(255 255 255 / 0.1);
  background: rgb(24 24 27 / 0.75);
  box-shadow: 0 24px 80px -32px rgb(255 255 255 / 0.18);
}
:global(.dark .relay .primary) {
  background: #e4e4e7;
  color: #09090b;
}
:global(.dark .relay .primary:hover) {
  background: white;
}
.secondary:hover {
  background: rgb(var(--color-accent) / 0.06);
}
.section-footer {
  border-top: 1px solid rgb(241 245 249);
  background: rgb(248 250 252 / 0.5);
  color: rgb(100 116 139);
}
:global(.dark .relay .section-footer) {
  border-color: rgb(39 39 42 / 0.6);
  background: rgb(24 24 27 / 0.4);
  color: rgb(161 161 170);
}
:deep(.payload-panel) {
  height: 7rem;
  min-height: 7rem;
  padding: 0.75rem;
}
:deep(.payload-panel > svg) {
  width: 2.5rem;
  height: 2.5rem;
}
:deep(.payload-panel > p) {
  margin-top: 0.25rem;
}
@media (min-width: 640px) {
  .panel {
    border-radius: 2.5rem;
  }
  :deep(.payload-panel) {
    height: 8rem;
    min-height: 8rem;
  }
}
progress {
  appearance: none;
  overflow: hidden;
  border: 0;
  border-radius: 9999px;
  background: rgb(var(--color-border));
  color: rgb(var(--color-accent));
}
progress::-webkit-progress-bar {
  background: rgb(var(--color-border));
}
progress::-webkit-progress-value {
  background: rgb(var(--color-accent));
}
progress::-moz-progress-bar {
  background: rgb(var(--color-accent));
}
</style>
