const csrf = () => window.csrf_token || ''

const jsonHeaders = (extra = {}) => ({
  Accept: 'application/json',
  'Content-Type': 'application/json',
  'X-Frappe-CSRF-Token': csrf(),
  ...extra,
})

function errorMessage(payload, response) {
  if (payload?._server_messages) {
    try {
      const messages = JSON.parse(payload._server_messages)
      const first = messages[0]
      const parsed = typeof first === 'string' ? JSON.parse(first) : first
      return parsed?.message || parsed?.title || 'Request failed'
    } catch {
      // fall through
    }
  }
  return payload?.exception || payload?.message || response.statusText || 'Request failed'
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers: jsonHeaders(options.headers),
  })
  let payload = null
  try {
    payload = await response.json()
  } catch {
    // Empty body, e.g. a redirect to the login page.
  }
  if (!response.ok) {
    throw new Error(errorMessage(payload, response))
  }
  if (payload && Object.prototype.hasOwnProperty.call(payload, 'message')) return payload.message
  if (payload && Object.prototype.hasOwnProperty.call(payload, 'data')) return payload.data
  return payload
}

const resourceUrl = (doctype, name = '') =>
  `/api/resource/${encodeURIComponent(doctype)}${name ? `/${encodeURIComponent(name)}` : ''}`

export const api = {
  bootstrap: () => request('/api/method/fs_switch.api.get_bootstrap'),
  live: () => request('/api/method/fs_switch.api.get_live_data'),
  preview: (name) =>
    request(`/api/method/fs_switch.api.preview_dialplan?name=${encodeURIComponent(name)}`),
  action: (action, args = {}) =>
    request('/api/method/fs_switch.api.run_live_action', {
      method: 'POST',
      body: JSON.stringify({ action, ...args }),
    }),
  saveSettings: (settings) =>
    request('/api/method/fs_switch.api.save_settings', {
      method: 'POST',
      body: JSON.stringify(settings),
    }),
  list: (doctype, params = {}) => {
    const query = new URLSearchParams({
      limit_page_length: '200',
      fields: '["*"]',
      ...params,
    })
    return request(`${resourceUrl(doctype)}?${query}`)
  },
  get: (doctype, name) => request(resourceUrl(doctype, name)),
  create: (doctype, doc) =>
    request(resourceUrl(doctype), { method: 'POST', body: JSON.stringify(doc) }),
  update: (doctype, name, doc) =>
    request(resourceUrl(doctype, name), { method: 'PUT', body: JSON.stringify(doc) }),
  remove: (doctype, name) => request(resourceUrl(doctype, name), { method: 'DELETE' }),
}

export function parseGraph(graph) {
  if (!graph) return { nodes: [], edges: [] }
  if (typeof graph === 'object') return graph
  try {
    return JSON.parse(graph)
  } catch {
    return { nodes: [], edges: [] }
  }
}
