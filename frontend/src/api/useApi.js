import { useCallback, useEffect, useRef, useState } from 'react'

// Loads data for a page and keeps it in state.
//
//   const { data, error, loading, reload } = useApi(() => api.get(`/courses/${id}`), [id])
//
// `reload()` fetches again (after a change) without showing "Loading"; `setData` updates
// the shown data at once. With `enabled: false` nothing is fetched until it turns true.
export default function useApi(load, deps = [], { enabled = true } = {}) {
  const key = JSON.stringify(deps)
  const [state, setState] = useState({ data: null, error: null, loading: enabled, key: null })
  const latest = useRef(0)
  const loadRef = useRef(load)
  loadRef.current = load

  const run = useCallback(
    async ({ quiet = false } = {}) => {
      const call = ++latest.current
      if (!quiet) setState((s) => ({ ...s, loading: true, error: null }))
      try {
        const data = await loadRef.current()
        if (call === latest.current) setState({ data, error: null, loading: false, key })
        return data
      } catch (error) {
        if (call === latest.current) setState((s) => ({ data: quiet ? s.data : null, error, loading: false, key }))
        return undefined
      }
    },
    [key],
  )

  useEffect(() => {
    if (enabled) run()
    return () => {
      latest.current += 1
    }
  }, [run, enabled])

  const setData = useCallback((update) => {
    setState((s) => ({ ...s, data: typeof update === 'function' ? update(s.data) : update }))
  }, [])

  // Until the first answer for the current inputs arrives, the data is still loading.
  const loading = enabled && (state.loading || state.key !== key)
  return { data: state.data, error: state.error, loading, reload: () => run({ quiet: true }), setData }
}
