<script setup lang="ts">
import { ref } from 'vue'
import { UploadCloud, Download, Trash2, RefreshCw, Link2, ArrowRight } from 'lucide-vue-next'
import { useRelay } from '@/composables'
const {
  mode,
  session,
  passcode,
  files,
  requests,
  queue,
  error,
  refreshState,
  busy,
  pair,
  repair,
  resume,
  decide,
  remove,
  addFiles,
  retry,
  cancel,
  refresh
} = useRelay()
const picker = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const size = (n: number) =>
  n < 1000
    ? `${n} B`
    : n < 1e6
      ? `${(n / 1000).toFixed(1)} KB`
      : n < 1e9
        ? `${(n / 1e6).toFixed(1)} MB`
        : `${(n / 1e9).toFixed(2)} GB`
const time = (n: number) => new Date(n * 1000).toLocaleString()
const select = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files) addFiles(input.files)
  input.value = ''
}
const drop = (event: DragEvent) => {
  dragging.value = false
  if (event.dataTransfer?.files) addFiles(event.dataTransfer.files)
}
</script>
<template>
  <main class="relay mx-auto max-w-4xl px-5 pb-16 pt-24 sm:px-8">
    <header class="mb-8 flex items-center gap-3">
      <div class="rounded-2xl bg-indigo-500/10 p-3 text-indigo-500"><Link2 :size="28" /></div>
      <div>
        <h1 class="text-2xl font-bold tracking-tight">
          FileRelay <span class="text-base font-normal opacity-60">文件接力</span>
        </h1>
        <p class="mt-1 text-sm opacity-60">在你的设备之间，轻松传递文件</p>
      </div>
    </header>
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
          class="my-3 w-full rounded-xl border border-indigo-400/30 bg-transparent px-4 py-4 text-center text-3xl tracking-[.5em] outline-none focus:ring-2 focus:ring-indigo-400"
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
      <button v-if="session?.paired" class="mt-5 text-sm text-indigo-500" @click="resume">
        返回当前配对
      </button>
    </section>
    <section v-else-if="mode === 'waiting'" class="panel mx-auto max-w-lg p-8" aria-live="polite">
      <h2 class="text-xl font-semibold">等待已有设备确认</h2>
      <p class="my-4 text-sm leading-6 opacity-65">
        请在已配对的任意设备上同意本次加入。申请 10 分钟后过期，批准前无法访问目标文件。
      </p>
      <button class="secondary" @click="repair">重新输入口令</button>
    </section>
    <template v-else>
      <section class="panel mb-5 flex flex-wrap items-center justify-between gap-3 p-5">
        <div>
          <span class="text-sm opacity-60">当前口令</span
          ><strong class="ml-3 font-mono text-2xl tracking-widest">{{ session?.passcode }}</strong>
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
      <section
        class="panel mb-5 border-dashed p-8 text-center transition-colors"
        :class="dragging ? 'bg-indigo-500/10' : ''"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="drop"
      >
        <UploadCloud class="mx-auto mb-3 text-indigo-500" :size="34" />
        <h2 class="text-lg font-semibold">发送文件</h2>
        <p class="mb-5 mt-2 text-sm opacity-60">
          选择、拖入或粘贴文件 · 每个文件独立上传 · 单文件最多 1 GB
        </p>
        <input
          ref="picker"
          type="file"
          multiple
          class="sr-only"
          aria-label="选择要上传的文件"
          @change="select"
        />
        <button class="primary" @click="picker?.click()">选择照片或文件</button>
        <p class="mt-5 text-xs opacity-50">
          发布后最多保留 24 小时，首次完整发送后保留 10 分钟供重试。
        </p>
      </section>
      <section v-if="queue.length" class="panel mb-5 p-5" aria-live="polite">
        <h2 class="mb-3 font-semibold">上传队列</h2>
        <div v-for="item in queue" :key="item.key" class="border-t border-slate-400/15 py-4">
          <div class="flex items-center gap-3">
            <span class="min-w-0 flex-1 break-all text-sm">{{ item.file.name }}</span
            ><span class="text-xs opacity-60">{{ item.state }} {{ item.progress }}%</span>
            <button
              v-if="['失败', '已取消'].includes(item.state)"
              class="text-sm text-indigo-500"
              @click="retry(item)"
            >
              重试
            </button>
            <button
              v-else-if="item.state !== '已完成'"
              class="text-sm opacity-60"
              @click="cancel(item)"
            >
              取消
            </button>
          </div>
          <progress :value="item.progress" max="100" class="mt-3 h-1.5 w-full accent-indigo-500" />
          <p v-if="item.error" class="mt-1 text-xs text-red-500">{{ item.error }}</p>
        </div>
      </section>
      <section class="panel p-5">
        <div class="mb-3 flex items-center justify-between gap-3">
          <h2 class="font-semibold">
            共享文件 <span class="ml-1 text-sm font-normal opacity-50">{{ files.length }}</span>
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
  border: 1px solid rgb(148 163 184 / 0.2);
  border-radius: 1.25rem;
  background: rgb(var(--color-surface) / 0.5);
  box-shadow: 0 4px 24px rgb(0 0 0 / 0.025);
}
.primary {
  border-radius: 0.75rem;
  background: #6366f1;
  color: white;
  padding: 0.7rem 1.2rem;
  font-weight: 500;
}
.primary:hover {
  background: #4f46e5;
}
.primary:disabled {
  opacity: 0.5;
}
.secondary {
  border: 1px solid rgb(148 163 184 / 0.3);
  border-radius: 0.75rem;
  padding: 0.6rem 1rem;
}
button,
a {
  transition: background-color 0.15s;
}
button:focus-visible,
a:focus-visible {
  outline: 2px solid #818cf8;
  outline-offset: 3px;
}
</style>
