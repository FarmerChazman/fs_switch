import { io } from 'socket.io-client'

const EVENTS = [
  'fs_switch_call',
  'fs_switch_agent',
  'fs_switch_registration',
]

/**
 * Connect to Frappe's Socket.IO server for the current site.
 *
 * Frappe namespaces the socket by site, and authenticates the connection with
 * the existing session cookie. The console still keeps a slow snapshot poll as
 * a fallback for a stopped ESL listener or a blocked socket.
 */
export function createRealtime({ url, site, onEvent, onStatus }) {
  if (!url) return null
  const origin = String(url).replace(/\/+$/, '')
  const namespace = site ? `/${site}` : '/'
  let socket = null

  function emitStatus(state, detail = '') {
    onStatus?.({ state, detail })
  }

  function connect() {
    if (socket) return socket
    emitStatus('connecting')
    socket = io(`${origin}${namespace}`, {
      withCredentials: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      timeout: 10000,
    })
    socket.on('connect', () => emitStatus('connected'))
    socket.on('disconnect', (reason) => emitStatus('disconnected', reason))
    socket.on('connect_error', (error) => emitStatus('error', error?.message || 'Socket unavailable'))
    for (const event of EVENTS) {
      socket.on(event, (payload) => onEvent?.(event, payload))
    }
    return socket
  }

  function disconnect() {
    if (!socket) return
    socket.removeAllListeners()
    socket.disconnect()
    socket = null
    emitStatus('disconnected', 'Console closed')
  }

  return { connect, disconnect }
}
