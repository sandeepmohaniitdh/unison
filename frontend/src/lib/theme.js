// Dark mode: the sidebar's "Dark mode" item switches the colour tokens (styles/tokens.css).
// The choice is remembered in this browser only.

const KEY = 'unison-theme'

export function savedTheme() {
  try {
    return window.localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  try {
    window.localStorage.setItem(KEY, theme)
  } catch {
    // private window: the choice lasts until the page is closed
  }
}

export function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
  applyTheme(next)
  return next
}
