import { describe, it, expect, vi, afterEach } from 'vitest'

afterEach(() => { vi.unstubAllGlobals(); document.body.replaceChildren() })

describe('TCC instructor input contracts', () => {
  it('resolves a normal nested application property before matching input', async () => {
    vi.resetModules()
    const element = document.createElement('input')
    element.id = 'coverage-input'; element.value = 'Hello Juice Shop'
    document.body.append(element)
    const fetch = vi.fn().mockResolvedValue({ json: async () => ({ config: { application: { name: 'Juice Shop' } } }) })
    vi.stubGlobal('fetch', fetch)
    const { waitForInputToHaveValue } = await import('../hacking-instructor/helpers/helpers')
    await waitForInputToHaveValue('#coverage-input', 'Hello {{name}}', {
      ignoreCase: false, replacement: ['{{name}}', 'application.name']
    })()
    expect(fetch).toHaveBeenCalledWith('/rest/admin/application-configuration')
    expect(element.value).toBe('Hello Juice Shop')
  }, 2000)
})
