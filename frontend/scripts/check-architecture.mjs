import { readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { globSync } from 'glob'

const rootDir = new URL('..', import.meta.url).pathname
const srcDir = join(rootDir, 'src')

const rules = [
  { name: '页面与组件只通过 composable 调用业务', files: ['src/views/**/*.{ts,vue}', 'src/components/**/*.{ts,vue}'], patterns: [/from ['"]@\/services(?:\/[^'"]*)?['"]/] },
  { name: '页面层统一从 composables 入口导入', files: ['src/views/**/*.{ts,vue}', 'src/App.vue'], patterns: [/from ['"]@\/composables\/[^'"]+['"]/] },
  { name: 'composables 从 services 统一入口导入', files: ['src/composables/**/*.ts'], patterns: [/from ['"]@\/services\/[^'"]+['"]/] },
  { name: '请求客户端统一封装', files: ['src/**/*.{ts,vue}'], patterns: [/import\s+axios\b/], ignoreFiles: [/^src\/services\/client\.ts$/] },
  { name: '页面和组件不直接发 HTTP 请求', files: ['src/views/**/*.{ts,vue}', 'src/components/**/*.{ts,vue}'], patterns: [/\bfetch\(/, /\b(?:FileService|ConfigService|StatsService|AuthService)\./] },
  { name: '持久化通过 storage helper', files: ['src/**/*.{ts,vue}'], patterns: [/\blocalStorage\./], ignoreFiles: [/^src\/utils\/[a-z-]+-storage\.ts$/] },
  { name: '工具层不依赖 store', files: ['src/utils/**/*.ts'], patterns: [/from ['"]@\/stores\/[^'"]+['"]/] },
  { name: '概览加载时机由页面决定', files: ['src/composables/useDashboardStats.ts'], patterns: [/\bonMounted\(/] },
  { name: '系统设置不直接进行单位转换', files: ['src/views/manage/SystemSettingsView.vue'], patterns: [/from ['"]@\/utils\/config-form['"]/] },
]


const violations = []

for (const rule of rules) {
  const files = rule.files.flatMap((pattern) =>
    globSync(pattern, {
      cwd: rootDir,
      absolute: true,
      nodir: true,
      ignore: ['node_modules/**', 'dist/**'],
    })
  )

  for (const file of files) {
    const relativeFile = relative(rootDir, file)
    if (rule.ignoreFiles?.some((pattern) => pattern.test(relativeFile))) {
      continue
    }

    const source = readFileSync(file, 'utf8')
    const lines = source.split(/\r?\n/)

    lines.forEach((line, index) => {
      for (const pattern of rule.patterns) {
        if (pattern.test(line)) {
          violations.push({
            rule: rule.name,
            file: relativeFile,
            line: index + 1,
            text: line.trim(),
          })
        }
      }
    })
  }
}

if (violations.length > 0) {
  console.error('架构边界检查失败：')
  for (const violation of violations) {
    console.error(
      `- ${violation.rule}: ${violation.file}:${violation.line} ${violation.text}`
    )
  }
  process.exit(1)
}

console.log(`架构边界检查通过：${srcDir}`)
