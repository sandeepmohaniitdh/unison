import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

// Every test sees the same "now" as the recorded fixtures: Thu 29 Oct 2026, 19:30 IST.
// Only Date is faked, so promises and timers still run normally.
export const NOW = new Date('2026-10-29T14:00:00Z')

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  window.localStorage.clear()
  window.sessionStorage.clear()
  document.documentElement.removeAttribute('data-theme')
})

// jsdom has no matchMedia, scrollTo or showPicker.
window.matchMedia ??= () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
window.scrollTo = () => {}
