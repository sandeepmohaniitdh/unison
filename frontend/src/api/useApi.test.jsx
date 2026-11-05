import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import useApi from './useApi'

describe('useApi', () => {
  it('loads, then reloads quietly', async () => {
    let n = 0
    const load = vi.fn(async () => ({ n: ++n }))
    const { result } = renderHook(() => useApi(load, []))
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.data).toEqual({ n: 1 }))
    expect(result.current.loading).toBe(false)
    await act(() => result.current.reload())
    expect(result.current.data).toEqual({ n: 2 })
  })

  it('keeps the error and loads again when the inputs change', async () => {
    const load = vi.fn(async (id) => {
      if (id === 1) throw new Error('nope')
      return { id }
    })
    const { result, rerender } = renderHook(({ id }) => useApi(() => load(id), [id]), { initialProps: { id: 1 } })
    await waitFor(() => expect(result.current.error?.message).toBe('nope'))
    rerender({ id: 2 })
    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.data).toEqual({ id: 2 }))
    expect(result.current.error).toBeNull()
  })

  it('waits while disabled and lets the page change the data', async () => {
    const load = vi.fn(async () => [1])
    const { result, rerender } = renderHook(({ on }) => useApi(load, [], { enabled: on }), { initialProps: { on: false } })
    expect(result.current.loading).toBe(false)
    expect(load).not.toHaveBeenCalled()
    rerender({ on: true })
    await waitFor(() => expect(result.current.data).toEqual([1]))
    act(() => result.current.setData((d) => [...d, 2]))
    expect(result.current.data).toEqual([1, 2])
  })
})
