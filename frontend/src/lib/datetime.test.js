import { describe, expect, it } from 'vitest'
import {
  dateTile,
  daysUntil,
  formatDate,
  formatDay,
  formatDayMonth,
  formatDeadline,
  formatDeadlineLong,
  formatShort,
  formatTime,
  fromIstInput,
  greeting,
  isPast,
  isWithinDays,
  parseTime,
  toIstInput,
} from './datetime'

// 5 Nov 2026, 23:59:59 IST
const DUE = '2026-11-05T23:59:59+05:30'

describe('IST formatting', () => {
  it('shows deadlines as in the design', () => {
    expect(formatDeadline(DUE)).toBe('Thu 5 Nov, 23:59 IST')
    expect(formatDeadlineLong(DUE)).toBe('Thu 5 Nov 2026, 23:59')
    expect(formatShort(DUE)).toBe('5 Nov, 23:59 IST')
    expect(formatDay(DUE)).toBe('Thu 5 Nov')
    expect(formatDayMonth(DUE)).toBe('5 Nov')
    expect(formatDate(DUE)).toBe('5 Nov 2026')
    expect(formatTime(DUE)).toBe('23:59 IST')
    expect(dateTile(DUE)).toEqual({ day: '05', month: 'NOV' })
  })

  it('reads a time without a zone as UTC and converts it to IST', () => {
    expect(parseTime('2026-11-05T18:29:59').toISOString()).toBe('2026-11-05T18:29:59.000Z')
    expect(formatTime('2026-11-05T04:30:00')).toBe('10:00 IST')
  })

  it('writes September with three letters', () => {
    expect(formatDayMonth('2026-09-10T10:00:00+05:30')).toBe('10 Sep')
  })
})

describe('datetime-local inputs', () => {
  it('round-trips an IST deadline', () => {
    expect(toIstInput(DUE)).toBe('2026-11-05T23:59')
    expect(fromIstInput('2026-11-05T23:59')).toBe('2026-11-05T23:59:59+05:30')
    expect(fromIstInput('2026-11-05T17:00')).toBe('2026-11-05T17:00:00+05:30')
  })

  it('treats empty values as no time', () => {
    expect(toIstInput(null)).toBe('')
    expect(fromIstInput('')).toBeNull()
  })
})

describe('relative times', () => {
  const now = new Date('2026-11-02T04:30:00Z') // Mon 2 Nov, 10:00 IST

  it('greets by the time of day in IST', () => {
    expect(greeting(now)).toBe('Good morning')
    expect(greeting(new Date('2026-11-02T09:30:00Z'))).toBe('Good afternoon')
    expect(greeting(new Date('2026-11-02T13:30:00Z'))).toBe('Good evening')
  })

  it('knows past and upcoming deadlines', () => {
    expect(isPast('2026-11-01T10:00:00+05:30', now)).toBe(true)
    expect(isPast(DUE, now)).toBe(false)
    expect(isWithinDays(DUE, 7, now)).toBe(true)
    expect(isWithinDays(DUE, 2, now)).toBe(false)
    expect(daysUntil(DUE, now)).toBe(4)
    expect(daysUntil('2026-10-01T00:00:00Z', now)).toBe(0)
  })
})
