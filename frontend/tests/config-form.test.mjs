import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
const source = readFileSync(new URL('../src/utils/config-form.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } })
const form = await import('data:text/javascript;base64,' + Buffer.from(outputText).toString('base64'))
test('legacy byte limits survive decimal display and resubmission exactly', () => {
  for (const value of [1, 1001, 10_485_760, 999_999_999, 1_000_000_000, 5_000_000_000, 500_000_000_000]) {
    const { value: amount, unit } = form.bytesToFileSizeForm(value)
    assert.equal(form.fileSizeFormToBytes(amount, unit), value)
    const other = form.bytesToFileSizeForm(value, unit === 'GB' ? 'MB' : 'GB')
    assert.equal(form.fileSizeFormToBytes(other.value, other.unit), value)
  }
  assert.equal(form.fileSizeFormToBytes(10, 'MB'), 10_000_000)
  assert.equal(form.fileSizeFormToBytes(0.000001, 'MB'), 1)
})
test('zero, nonfinite values and fractional bytes cannot become valid limits', () => {
  for (const value of [0, -1, NaN, Infinity, 1.0000000001, 0.0000001])
    assert.throws(() => form.fileSizeFormToBytes(value, 'MB'))
})
