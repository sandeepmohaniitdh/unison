import { describe, expect, it } from 'vitest'
import { rememberChoice, shouldEndSession } from '../auth/session'
import { notificationIcon, notificationLink } from './notifications'
import { applyTheme, savedTheme, toggleTheme } from './theme'

describe('notifications', () => {
  it('picks an icon per event', () => {
    expect(notificationIcon('marks_released')).toBe('star')
    expect(notificationIcon('unknown_event')).toBe('bell')
  })

  it('keeps links inside the site', () => {
    expect(notificationLink('/teams/12')).toBe('/teams/12')
    expect(notificationLink('//evil.example.com')).toBe('/notifications')
    expect(notificationLink('https://evil.example.com')).toBe('/notifications')
    expect(notificationLink(null)).toBe('/notifications')
  })
})

describe('keep me signed in', () => {
  it('ends the session after the browser was closed when not ticked', () => {
    rememberChoice(false)
    expect(shouldEndSession()).toBe(false) // same browser session
    window.sessionStorage.clear() // the browser was closed and opened again
    expect(shouldEndSession()).toBe(true)
  })

  it('keeps the session when ticked', () => {
    rememberChoice(true)
    window.sessionStorage.clear()
    expect(shouldEndSession()).toBe(false)
  })
})

describe('theme', () => {
  it('switches between light and dark and remembers it', () => {
    applyTheme('light')
    expect(document.documentElement.getAttribute('data-theme')).not.toBe('dark')
    const next = toggleTheme()
    expect(next).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(savedTheme()).toBe('dark')
  })
})
