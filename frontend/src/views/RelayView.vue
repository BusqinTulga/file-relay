<script setup lang="ts">
import { Download, Trash2, RefreshCw, ArrowRight } from 'lucide-vue-next'
import FileUploadArea from '@/components/common/FileUploadArea.vue'
import { useRelay } from '@/composables'
const {
  mode,
  session,
  passcode,
  files,
  requests,
  pendingRequest,
  queue,
  error,
  refreshState,
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
  cancel,
  refresh
} = useRelay()
const size = (n: number) =>
  n < 1000
    ? `${n} B`
    : n < 1e6
      ? `${(n / 1000).toFixed(1)} KB`
      : n < 1e9
        ? `${(n / 1e6).toFixed(1)} MB`
        : `${(n / 1e9).toFixed(2)} GB`
const time = (n: number) => new Date(n * 1000).toLocaleString()
</script>
<template>
  <main class="relay mx-auto max-w-4xl px-4 pb-12 pt-4 font-sans sm:px-8">
    <p
      v-if="error"
      role="alert"
      class="mb-5 rounded-xl border border-red-400/30 bg-red-500/10 p-4 text-sm"
    >
      {{ error }}
    </p>
    <section v-if="mode === 'loading'" class="panel p-8" aria-live="polite">
      正在恢复设备记忆…
    </section>
    <section v-else-if="mode === 'pair'" class="panel mx-auto max-w-lg p-7 sm:p-10">
      <h2 class="text-xl font-semibold">输入相同口令，即可接力</h2>
      <p class="mb-6 mt-3 text-sm leading-6 opacity-65">
        在两台设备上输入相同的 1 至 4 位数字。第三台及后续设备需要已加入设备确认。
      </p>
      <form @submit.prevent="pair">
        <label for="passcode" class="text-sm">配对口令</label>
        <input
          id="passcode"
          v-model="passcode"
          autofocus
          inputmode="numeric"
          pattern="[0-9]{1,4}"
          maxlength="4"
          autocomplete="off"
          required
          class="my-3 w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-transparent px-4 py-4 text-center text-3xl tracking-[.5em] outline-none focus:ring-2 focus:ring-zinc-400"
          placeholder="007"
        />
        <p class="mb-6 text-xs opacity-55">保留前导零，例如 007 与 7 是不同口令。</p>
        <button
          type="submit"
          :disabled="busy"
          class="primary flex w-full items-center justify-center gap-2"
        >
          {{ busy ? '正在配对…' : '开始接力' }}<ArrowRight :size="18" />
        </button>
      </form>
      <button
        v-if="session?.paired"
        :disabled="busy"
        class="mt-5 text-sm text-zinc-700 dark:text-zinc-300"
        @click="resume"
      >
        返回当前配对
      </button>
    </section>
    <section v-else-if="mode === 'waiting'" class="panel mx-auto max-w-lg p-8" aria-live="polite">
      <h2 class="text-xl font-semibold">等待已有设备确认</h2>
      <p class="my-4 text-sm leading-6 opacity-65">
        请在已配对的任意设备上同意本次加入。申请 10 分钟后过期，批准前无法访问目标文件。
      </p>
      <p v-if="pendingRequest" class="mb-4 text-sm">
        申请 {{ pendingRequest.request_id.slice(0, 8) }} · {{ time(pendingRequest.expires) }} 前有效
      </p>
      <button class="secondary" @click="repair">重新输入口令</button>
    </section>
    <template v-else>
      <section class="panel mb-5 flex flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <span class="text-sm opacity-60">当前口令</span
          ><strong class="ml-3 text-2xl tracking-widest">{{ session?.passcode }}</strong>
          <p class="mt-1 text-xs opacity-55">浏览器已记住配对</p>
        </div>
        <button class="secondary text-sm" @click="repair">重新输入口令</button>
      </section>
      <section v-if="requests.length" class="panel mb-5 p-5" aria-live="polite">
        <h2 class="mb-3 font-semibold">新设备请求加入</h2>
        <div
          v-for="request in requests"
          :key="request.id"
          class="flex flex-wrap items-center gap-3 border-t border-slate-400/15 py-3 text-sm"
        >
          <span class="flex-1"
            >申请 {{ request.id.slice(0, 8) }} · {{ time(request.expires) }} 前有效</span
          >
          <button class="primary" @click="decide(request.id, true)">同意</button
          ><button class="secondary" @click="decide(request.id, false)">拒绝</button>
        </div>
      </section>
      <section class="panel mb-5 overflow-hidden" aria-label="上传区域">
        <div class="px-5 py-5 sm:px-8">
          <h2 class="mb-3 text-lg font-semibold">文件发送</h2>
          <p class="mb-3 text-xs opacity-65" aria-live="polite">{{ policy ? (policy.open_upload ? `单文件上限 ${policy.upload_size / 1_000_000} MB` : '上传已暂停') : '正在读取上传限制，读取成功后才能上传' }}</p>
      <FileUploadArea
            class="payload-panel"
            placeholder="点击或拖放文件到此处上传"
            :description="policy?.open_upload ? `支持任意格式，单文件上限 ${size(policy.upload_size)}` : '上传暂不可用，请稍后重试'"
            @file-selected="addFiles([$event])"
            @files-selected="addFiles"
          />
          <p class="mt-3 text-center text-xs leading-5 text-slate-500 dark:text-zinc-400">
            点击选择、拖放到页面任意位置或粘贴文件，即可自动上传。
          </p>
        </div>
        <p class="section-footer px-5 py-2.5 text-center text-xs leading-5 sm:px-8">
          文件最多保留 24 小时，首次完整下载后保留 10 分钟供重试。
        </p>
        <section
          v-if="queue.length"
          class="border-t border-zinc-200/60 p-5 dark:border-zinc-800"
          aria-live="polite"
        >
          <h2 class="mb-3 font-semibold">上传队列</h2>
          <div v-for="item in queue" :key="item.key" class="border-t border-slate-400/15 py-4">
            <div class="flex items-center gap-3">
              <span class="min-w-0 flex-1 break-all text-sm">{{ item.file.name }}</span
              ><span class="text-xs opacity-60">{{ item.state }} {{ item.progress }}%</span>
              <button
                v-if="canRetry(item)"
                class="text-sm text-zinc-700 dark:text-zinc-300"
                @click="retry(item)"
              >
                重试
              </button>
              <button
                v-else-if="['等待上传', '校验文件', '上传中', '发布中'].includes(item.state)"
                class="text-sm opacity-60"
                @click="cancel(item)"
              >
                取消
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
      <section class="panel p-5 sm:p-8" aria-label="下载区域">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="font-semibold">
            <span class="inline-flex items-center gap-2"><Download :size="18" />文件下载</span>
            <span class="ml-1 text-sm font-normal opacity-50">{{ files.length }}</span>
          </h2>
          <button class="flex items-center gap-1 text-xs opacity-60" @click="refresh">
            <RefreshCw :size="13" />{{ refreshState }}
          </button>
        </div>
        <p v-if="!files.length" class="py-10 text-center text-sm opacity-50">
          {{
            refreshState.startsWith('连接失败')
              ? '暂时无法取得文件，请重试'
              : '还没有文件，上传后会自动出现在这里。'
          }}
        </p>
        <article
          v-for="file in files"
          :key="file.id"
          class="flex flex-wrap items-center gap-4 border-t border-slate-400/15 py-5"
        >
          <div class="min-w-0 flex-1 basis-52">
            <h3 class="break-all text-sm font-medium">{{ file.name }}</h3>
            <p class="mt-1 text-xs opacity-55">
              {{ size(file.size) }} · 上传于 {{ time(file.published) }}
            </p>
            <p class="mt-1 text-xs opacity-55">
              {{ file.first_sent ? '传输完成，将于' : '有效至' }} {{ time(file.expires) }} 清理
            </p>
          </div>
          <a
            :href="`/api/relay/files/${file.id}/download`"
            class="secondary inline-flex items-center gap-2 text-sm"
            ><Download :size="16" />下载</a
          >
          <button
            class="rounded-lg p-2 opacity-60 hover:text-red-500"
            :aria-label="`删除 ${file.name}`"
            @click="remove(file.id)"
          >
            <Trash2 :size="17" />
          </button>
        </article>
      </section>
    </template>
    <footer class="mt-8 text-center text-xs opacity-40">FileRelay · 文件接力</footer>
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
