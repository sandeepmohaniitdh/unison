// "Keep me signed in". The session cookie always lasts 7 days; when the box is not
// ticked, the app logs out the next time the browser is opened after being closed.
// sessionStorage is cleared when the browser closes, localStorage is not.

const EPHEMERAL = 'unison-ephemeral'
const ALIVE = 'unison-alive'

export function rememberChoice(keep) {
  try {
    if (keep) window.localStorage.removeItem(EPHEMERAL)
    else window.localStorage.setItem(EPHEMERAL, '1')
    window.sessionStorage.setItem(ALIVE, '1')
  } catch {
    // storage blocked: the session simply lasts its normal 7 days
  }
}

// True when the user asked not to stay signed in and the browser was closed since.
export function shouldEndSession() {
  try {
    const ephemeral = window.localStorage.getItem(EPHEMERAL) === '1'
    const alive = window.sessionStorage.getItem(ALIVE) === '1'
    window.sessionStorage.setItem(ALIVE, '1')
    return ephemeral && !alive
  } catch {
    return false
  }
}
