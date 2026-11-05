import { describe, expect, it } from 'vitest'
import {
  capitalise,
  deadlineBadge,
  emailUser,
  fileKind,
  fileSize,
  formatTerm,
  percentOf,
  plural,
  points,
  shortName,
  stateBadge,
} from './format'

describe('text helpers', () => {
  it('writes terms with an en dash', () => {
    expect(formatTerm('Jul-Nov 2026')).toBe('Jul–Nov 2026')
    expect(formatTerm()).toBe('')
  })

  it('writes file sizes and kinds', () => {
    expect(fileSize(512)).toBe('512 B')
    expect(fileSize(340000)).toBe('332 KB')
    expect(fileSize(2400000)).toBe('2.3 MB')
    expect(fileSize(null)).toBe('')
    expect(fileKind('report.pdf')).toBe('PDF')
    expect(fileKind('README', 'text/plain')).toBe('PLAIN')
    expect(fileKind(null, null)).toBe('File')
  })

  it('shortens names for greetings and chips', () => {
    expect(shortName('Dr. Kavya Menon')).toBe('Dr. Menon')
    expect(shortName('Prof Ravi Kumar')).toBe('Prof. Kumar')
    expect(shortName('Sandeep M')).toBe('Sandeep')
    expect(emailUser('cs26mt001@iitdh.ac.in')).toBe('cs26mt001')
  })

  it('counts and formats numbers', () => {
    expect(plural(1, 'team')).toBe('1 team')
    expect(plural(3, 'team')).toBe('3 teams')
    expect(plural(2, 'person', 'people')).toBe('2 people')
    expect(points('42.0')).toBe('42')
    expect(points('24.5')).toBe('24.5')
    expect(points(null)).toBe('')
    expect(percentOf(21, 30)).toBe(70)
    expect(percentOf(5, 0)).toBe(0)
    expect(capitalise('group')).toBe('Group')
  })

  it('maps submission states to badges', () => {
    expect(stateBadge('final_submitted')).toEqual(['Final submitted', 'green'])
    expect(stateBadge('something_new')).toEqual(['something_new', 'grey'])
    expect(deadlineBadge('final_submitted')).toEqual(['Final in', 'green'])
    expect(deadlineBadge('drafts')).toEqual(['Draft only', 'amber'])
  })
})
