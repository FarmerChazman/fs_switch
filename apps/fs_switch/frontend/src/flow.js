const TERMINAL_TYPES = new Set(['voicemail', 'transfer', 'conference', 'park', 'hangup'])

const NODE_ICONS = {
  answer: 'pi pi-phone',
  play: 'pi pi-volume-up',
  menu: 'pi pi-list',
  time: 'pi pi-clock',
  ring_group: 'pi pi-users',
  queue: 'pi pi-headphones',
  voicemail: 'pi pi-inbox',
  transfer: 'pi pi-arrow-right',
  conference: 'pi pi-microphone',
  park: 'pi pi-pause',
  hangup: 'pi pi-phone-slash',
  set: 'pi pi-pencil',
  sleep: 'pi pi-hourglass',
  record: 'pi pi-circle',
}

const CATEGORY_COLORS = {
  'Call control': '#6b7280',
  Routing: '#2490ef',
  Media: '#8b5cf6',
  Variables: '#d97706',
}

const SERVER_MANAGED_FIELDS = [
  'compiled_xml',
  'versions',
  'publish_status',
  'published_version',
  'published_on',
  'published_by',
  'published_xml',
  'published_graph',
  'published_graph_format',
  'published_context',
  'published_tenant',
  'published_priority',
]

export function clone(value) {
  if (value === null || value === undefined) return value
  return JSON.parse(JSON.stringify(value))
}

export function stripPublishState(payload) {
  const draft = { ...payload }
  for (const field of SERVER_MANAGED_FIELDS) delete draft[field]
  return draft
}

export function catalogMap(catalog) {
  return Object.fromEntries((catalog || []).map((item) => [item.type, item]))
}

export function specFor(catalog, type) {
  return (catalog || []).find((item) => item.type === type) || null
}

export function normalizeMenuOptions(options) {
  return (Array.isArray(options) ? options : [])
    .map((option) => {
      if (typeof option === 'string') return { digit: option.trim(), label: '' }
      return {
        ...option,
        digit: String(option?.digit ?? '').trim(),
        label: String(option?.label ?? ''),
      }
    })
    .filter((option) => option.digit || option.label)
}

export function normalizeNodeConfig(type, data, spec) {
  const config = {
    ...clone(spec?.defaults || {}),
    ...clone(data || {}),
  }
  delete config.label
  if (type === 'menu') {
    config.options = normalizeMenuOptions(config.options)
    for (const key of ['min_digits', 'max_digits', 'tries', 'timeout_ms']) {
      if (config[key] !== undefined && config[key] !== null && config[key] !== '') {
        config[key] = Number(config[key])
      }
    }
  }
  if (type === 'ring_group') {
    if (typeof config.endpoints === 'string') {
      config.endpoints = config.endpoints
        .split(',')
        .map((endpoint) => endpoint.trim())
        .filter(Boolean)
    }
    if (!Array.isArray(config.endpoints)) config.endpoints = []
    if (
      config.timeout_seconds !== undefined &&
      config.timeout_seconds !== null &&
      config.timeout_seconds !== ''
    ) {
      config.timeout_seconds = Number(config.timeout_seconds)
    }
  }
  if (
    type === 'sleep' &&
    config.milliseconds !== undefined &&
    config.milliseconds !== null &&
    config.milliseconds !== ''
  ) {
    config.milliseconds = Number(config.milliseconds)
  }
  return config
}

export function outputsForNode(type, config = {}) {
  if (type === 'menu') {
    const digits = []
    for (const option of Array.isArray(config.options) ? config.options : []) {
      const digit = String((typeof option === 'string' ? option : option?.digit) ?? '').trim()
      if (/^[0-9]$/.test(digit) && !digits.includes(digit)) digits.push(digit)
    }
    return [...digits.map((digit) => `digit:${digit}`), 'timeout']
  }
  if (type === 'time') return ['match', 'no_match']
  if (TERMINAL_TYPES.has(type)) return []
  return ['next']
}

export function isTerminalType(type) {
  return TERMINAL_TYPES.has(type)
}

export function outputLabel(handle) {
  if (handle?.startsWith('digit:')) return `Press ${handle.slice(6)}`
  const labels = {
    next: 'Next',
    timeout: 'Timeout',
    match: 'Match',
    no_match: 'No match',
  }
  return labels[handle] || handle || 'Output'
}

export function edgeLabel(handle) {
  if (handle?.startsWith('digit:')) return handle.slice(6)
  return outputLabel(handle)
}

export function nodeSummary(type, config = {}) {
  switch (type) {
    case 'answer':
      return 'Answer the call'
    case 'play':
      return config.prompt ? `Play ${config.prompt}` : 'Choose a prompt'
    case 'menu': {
      const count = outputsForNode('menu', config).filter((handle) => handle !== 'timeout').length
      const prompt = config.prompt ? ` · ${config.prompt}` : ''
      return `${count} option${count === 1 ? '' : 's'}${prompt}`
    }
    case 'time':
      return `${config.field || '${strftime(%H%M)}'} ${config.expression || 'needs a condition'}`
    case 'ring_group': {
      const endpoints = Array.isArray(config.endpoints) ? config.endpoints : []
      return endpoints.length ? `Ring ${endpoints.join(', ')}` : 'Choose at least one endpoint'
    }
    case 'queue':
      return config.queue ? `Queue ${config.queue}` : 'Choose a queue'
    case 'voicemail':
      return config.mailbox ? `Mailbox ${config.mailbox}` : 'Choose a mailbox'
    case 'transfer':
      return config.destination ? `Transfer to ${config.destination}` : 'Choose a destination'
    case 'conference':
      return config.room ? `Conference ${config.room}` : 'Choose a room'
    case 'park':
      return 'Park the call'
    case 'hangup':
      return config.cause ? `Hang up (${config.cause})` : 'Hang up'
    case 'set':
      return config.variable ? `${config.variable} = ${config.value || ''}` : 'Choose a variable'
    case 'sleep':
      return `${config.milliseconds ?? 1000} ms`
    case 'record':
      return config.path ? `Record to ${config.path}` : 'Choose a recording path'
    default:
      return ''
  }
}

export function nodeIcon(type) {
  return NODE_ICONS[type] || 'pi pi-box'
}

export function nodeAccent(category) {
  return CATEGORY_COLORS[category] || '#64748b'
}

export function starterSemanticGraph() {
  return {
    schema: 1,
    entry: 'answer',
    nodes: [
      {
        id: 'answer',
        type: 'answer',
        position: { x: 90, y: 80 },
        data: {},
      },
      {
        id: 'hangup',
        type: 'hangup',
        position: { x: 90, y: 250 },
        data: {},
      },
    ],
    edges: [
      {
        id: 'e-answer-hangup',
        source: 'answer',
        target: 'hangup',
        sourceHandle: 'next',
      },
    ],
  }
}
