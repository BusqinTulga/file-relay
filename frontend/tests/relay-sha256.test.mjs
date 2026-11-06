import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
const source = readFileSync(new URL('../src/utils/relay-sha256.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }
})
const { RelaySHA256, hashRelayFile } = await import(
  'data:text/javascript;base64,' + Buffer.from(outputText).toString('base64')
)
for (const size of [0, 1, 3, 55, 56, 63, 64, 65, 127, 128, 1000000]) {
  test(`incremental SHA256 matches node crypto at ${size} bytes`, async () => {
    const bytes = Buffer.alloc(size)
    for (let i = 0; i < size; i++) bytes[i] = (i * 137 + 17) % 256
    const expected = createHash('sha256').update(bytes).digest('hex')
    const hash = new RelaySHA256()
    for (let i = 0; i < size; i += 17) hash.update(bytes.subarray(i, i + 17))
    assert.equal(hash.hex(), expected)
    assert.equal(await hashRelayFile(new Blob([bytes])), expected)
  })
}
test('middle-only differences never reuse a sampled identity', async () => {
  const a = Buffer.alloc(12 * 1024 * 1024, 7),
    b = Buffer.from(a)
  b[6 * 1024 * 1024] = 8
  assert.notEqual(await hashRelayFile(new Blob([a])), await hashRelayFile(new Blob([b])))
})
test('aborted hashing stops before an upload starts', async () => {
  const c = new AbortController()
  c.abort()
  await assert.rejects(hashRelayFile(new Blob(['hello']), c.signal), { name: 'AbortError' })
})
