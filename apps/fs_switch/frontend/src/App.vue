<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Tree from 'primevue/tree'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'

import { api } from './api'
import { createRealtime } from './realtime'
import OverviewPanel from './components/OverviewPanel.vue'
import ExtensionsPanel from './components/ExtensionsPanel.vue'
import GatewaysPanel from './components/GatewaysPanel.vue'
import QueuesPanel from './components/QueuesPanel.vue'
import DialplansPanel from './components/DialplansPanel.vue'
import DidsPanel from './components/DidsPanel.vue'
import LiveChannels from './components/LiveChannels.vue'
import LiveRegistrations from './components/LiveRegistrations.vue'
import LiveAgents from './components/LiveAgents.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import TenantsPanel from './components/TenantsPanel.vue'
import MyExtensionPanel from './components/MyExtensionPanel.vue'

const toast = useToast()
const bootstrap = ref(null)
const live = ref(null)
const loading = ref(true)
const switchingTenant = ref(false)
const selected = ref('overview')
const selectedKeys = ref({ overview: true })
const activeTenant = ref('')
const realtimeState = ref('offline')
const realtimeDetail = ref('')
let timer = null
let realtime = null

const panels = {
  overview: OverviewPanel,
  extensions: ExtensionsPanel,
  gateways: GatewaysPanel,
  queues: QueuesPanel,
  dialplans: DialplansPanel,
  dids: DidsPanel,
  channels: LiveChannels,
  registrations: LiveRegistrations,
  agents: LiveAgents,
  my_extension: MyExtensionPanel,
  tenants: TenantsPanel,
  settings: SettingsPanel,
}

const tenants = computed(() => bootstrap.value?.tenants || [])
const tenantOptions = computed(() =>
  tenants.value.map((tenant) => ({
    label: `${tenant.tenant_name} · ${tenant.role}`,
    value: tenant.tenant,
  })),
)
const activeTenantRow = computed(
  () => tenants.value.find((tenant) => tenant.tenant === activeTenant.value) || null,
)
const tenantContext = computed(
  () =>
    activeTenantRow.value?.default_context ||
    bootstrap.value?.settings?.default_context ||
    'default',
)
const canWrite = computed(() => Boolean(bootstrap.value?.can_write))
const canSupervise = computed(() => Boolean(bootstrap.value?.can_supervise))
const canManageTenants = computed(() => Boolean(bootstrap.value?.can_manage_tenants))
const userName = computed(() => bootstrap.value?.full_name || bootstrap.value?.user || '')
const siteName = computed(() => window.fs_switch?.site || '')
const markUrl = '/assets/fs_switch/images/fs-switch-mark.svg'

const tree = computed(() => {
  const nodes = [{ key: 'overview', label: 'Overview', icon: 'pi pi-home' }]
  if (activeTenant.value) {
    nodes.push({ key: 'my_extension', label: 'My extension', icon: 'pi pi-id-card' })
  }
  if (canWrite.value || canSupervise.value) {
    const children = [
      { key: 'extensions', label: 'Extensions', icon: 'pi pi-id-card' },
      { key: 'dids', label: 'DIDs', icon: 'pi pi-hashtag' },
    ]
    if (canWrite.value) {
      children.push(
        { key: 'gateways', label: 'Gateways', icon: 'pi pi-cloud' },
        { key: 'queues', label: 'Queues', icon: 'pi pi-users' },
        { key: 'dialplans', label: 'Dialplans', icon: 'pi pi-sitemap' },
      )
    }
    nodes.push({
      key: 'telephony',
      label: 'Telephony',
      icon: 'pi pi-phone',
      selectable: false,
      children,
    })
  }
  if (canSupervise.value) {
    nodes.push({
      key: 'live',
      label: 'Live',
      icon: 'pi pi-wave-pulse',
      selectable: false,
      children: [
        { key: 'channels', label: 'Channels', icon: 'pi pi-arrows-h' },
        { key: 'registrations', label: 'Registrations', icon: 'pi pi-sign-in' },
        { key: 'agents', label: 'Agents', icon: 'pi pi-headphones' },
      ],
    })
  }
  if (canManageTenants.value || canWrite.value) {
    nodes.push({
      key: 'administration',
      label: 'Administration',
      icon: 'pi pi-shield',
      selectable: false,
      children: [{ key: 'tenants', label: 'Tenants', icon: 'pi pi-building' }],
    })
  }
  if (canManageTenants.value) {
    nodes.push({ key: 'settings', label: 'Settings', icon: 'pi pi-cog' })
  }
  return nodes
})

const currentPanel = computed(() => panels[selected.value] || OverviewPanel)
const selectedLabel = computed(() => findLabel(tree.value, selected.value) || 'Overview')
const realtimeLabel = computed(() => {
  if (!canSupervise.value) return 'Live unavailable'
  if (realtimeState.value === 'connected') return 'Live push'
  if (realtimeState.value === 'connecting') return 'Connecting'
  return 'Polling fallback'
})
const realtimeSeverity = computed(() => {
  if (!canSupervise.value) return 'secondary'
  if (realtimeState.value === 'connected') return 'success'
  if (realtimeState.value === 'connecting') return 'info'
  return 'warn'
})
const realtimeTitle = computed(() =>
  realtimeDetail.value ? `Socket.IO: ${realtimeDetail.value}` : 'Socket.IO status',
)

function findLabel(nodes, key) {
  for (const node of nodes) {
    if (node.key === key) return node.label
    if (node.children) {
      const found = findLabel(node.children, key)
      if (found) return found
    }
  }
  return ''
}

function onNodeSelect(node) {
  if (node.selectable === false) return
  selected.value = node.key
  selectedKeys.value = { [node.key]: true }
}

function navigate(key) {
  if (!panels[key] || !findLabel(tree.value, key)) return
  selected.value = key
  selectedKeys.value = { [key]: true }
}

function notify(detail, severity = 'success') {
  toast.add({ severity, summary: severity === 'error' ? 'Error' : 'FS Switch', detail, life: 4000 })
}

async function loadBootstrap(tenant = '') {
  try {
    const data = await api.bootstrap(tenant)
    bootstrap.value = data
    activeTenant.value = data.active_tenant || ''
    if (data.active_tenant) {
      window.localStorage.setItem('fs_switch_tenant', data.active_tenant)
    } else {
      window.localStorage.removeItem('fs_switch_tenant')
    }
  } catch (error) {
    if (tenant) {
      window.localStorage.removeItem('fs_switch_tenant')
      await loadBootstrap('')
      return
    }
    notify(error.message || 'Could not load the console.', 'error')
  }
}

async function refreshLive(silent = false) {
  if (!canSupervise.value) return
  try {
    live.value = await api.live(activeTenant.value)
    if (!silent && live.value?.ok) notify('Live state refreshed.')
  } catch (error) {
    live.value = {
      ok: false,
      channels: [],
      registrations: [],
      agents: [],
      queues: [],
      error: error.message || 'FreeSWITCH is unreachable.',
    }
    if (!silent) notify(live.value.error, 'error')
  }
}

function ensureLive() {
  if (!live.value) {
    live.value = { ok: true, channels: [], registrations: [], agents: [], queues: [], error: null }
  }
  if (!live.value.ok) {
    live.value = { ...live.value, ok: true, error: null }
  }
}

function upsert(rows, key, row) {
  const clean = Object.fromEntries(
    Object.entries(row).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
  const index = rows.findIndex((item) => item[key] && item[key] === clean[key])
  if (index === -1) rows.push(clean)
  else rows[index] = { ...rows[index], ...clean }
}

function applyCallEvent(payload) {
  ensureLive()
  const uuid = payload.uuid
  if (!uuid) return
  if (payload.event === 'CHANNEL_HANGUP_COMPLETE') {
    live.value.channels = live.value.channels.filter((channel) => channel.uuid !== uuid)
    return
  }
  upsert(live.value.channels, 'uuid', {
    uuid,
    name: payload.name || '',
    cid_name: payload.from_name || '',
    cid_num: payload.from || '',
    dest: payload.to || '',
    context: payload.context || '',
    callstate:
      payload.callstate || (payload.event === 'CHANNEL_ANSWER' ? 'Answered' : 'Ringing'),
    created: payload.created || '',
    tenant: payload.tenant || '',
  })
}

function applyAgentEvent(payload) {
  ensureLive()
  const name = payload.agent
  if (!name) return
  upsert(live.value.agents, 'name', {
    name,
    status: payload.status || 'Logged Out',
    state: payload.state || '',
    queue: payload.queue || '',
    tenant: payload.tenant || '',
  })
}

function applyRegistrationEvent(payload) {
  ensureLive()
  const registration = payload.registration || {}
  const contact = registration.contact || payload.contact
  if (!contact) return
  if (payload.action === 'unregister') {
    live.value.registrations = live.value.registrations.filter(
      (row) => row.contact !== contact,
    )
    return
  }
  upsert(live.value.registrations, 'contact', { ...registration, tenant: payload.tenant || '' })
}

function handleRealtimeEvent(event, payload) {
  if (!payload || typeof payload !== 'object') return
  const tenant = payload.tenant || payload.registration?.tenant
  if (activeTenant.value && tenant && tenant !== activeTenant.value) return
  if (event === 'fs_switch_call') applyCallEvent(payload)
  else if (event === 'fs_switch_agent') applyAgentEvent(payload)
  else if (event === 'fs_switch_registration') applyRegistrationEvent(payload)
}

function handleRealtimeStatus({ state, detail }) {
  realtimeState.value = state
  realtimeDetail.value = detail || ''
  if (state === 'connected') refreshLive(true)
}

function connectRealtime() {
  realtime?.disconnect()
  const config = bootstrap.value?.realtime
  realtime = createRealtime({
    url: config?.url,
    site: config?.site,
    onEvent: handleRealtimeEvent,
    onStatus: handleRealtimeStatus,
  })
  realtime?.connect()
}

async function switchTenant(tenant) {
  if (!tenant || tenant === activeTenant.value || switchingTenant.value) return
  switchingTenant.value = true
  activeTenant.value = tenant
  live.value = null
  try {
    await loadBootstrap(tenant)
    if (!findLabel(tree.value, selected.value)) navigate('overview')
    await refreshLive(true)
  } finally {
    switchingTenant.value = false
  }
}

async function afterTenantChange() {
  await loadBootstrap(activeTenant.value)
  if (!findLabel(tree.value, selected.value)) navigate('overview')
  await refreshLive(true)
}

onMounted(async () => {
  loading.value = true
  const saved = window.localStorage.getItem('fs_switch_tenant') || ''
  await loadBootstrap(saved)
  await refreshLive(true)
  loading.value = false
  connectRealtime()
  // Snapshot polling is a fallback, not the primary live path.
  timer = window.setInterval(() => {
    if (realtimeState.value !== 'connected') refreshLive(true)
  }, 30000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  realtime?.disconnect()
})
</script>

<template>
  <div class="fs-shell">
    <Toast position="bottom-right" />
    <aside class="fs-sidebar">
      <div class="fs-brand">
        <img :src="markUrl" alt="" class="fs-brand-mark" />
        <div>
          <div class="fs-brand-name">FS Switch</div>
          <div class="fs-brand-sub">FreeSWITCH control plane</div>
        </div>
      </div>

      <Tree
        v-model:selectionKeys="selectedKeys"
        :value="tree"
        selectionMode="single"
        class="fs-tree"
        @node-select="onNodeSelect"
      />

      <div class="fs-sidebar-foot">
        <a href="/app" class="fs-desk-link"><i class="pi pi-desktop" /> Open Desk</a>
        <div class="fs-version">v{{ bootstrap?.version || '0.1.0' }}</div>
      </div>
    </aside>

    <div class="fs-main">
      <header class="fs-topbar">
        <div>
          <div class="fs-eyebrow">
            {{ siteName }}
            <template v-if="activeTenantRow"> · {{ activeTenantRow.tenant_name }}</template>
          </div>
          <h1>{{ selectedLabel }}</h1>
        </div>
        <div class="fs-topbar-actions">
          <Select
            v-if="tenantOptions.length"
            :model-value="activeTenant"
            :options="tenantOptions"
            option-label="label"
            option-value="value"
            size="small"
            class="fs-tenant-select"
            :disabled="switchingTenant"
            aria-label="Active Tenant"
            @update:model-value="switchTenant"
          />
          <Tag
            v-if="canSupervise"
            :value="realtimeLabel"
            :severity="realtimeSeverity"
            :title="realtimeTitle"
            class="fs-connection"
          />
          <Tag
            v-if="canSupervise"
            :value="live?.ok ? 'FreeSWITCH connected' : 'FreeSWITCH offline'"
            :severity="live?.ok ? 'success' : 'danger'"
            class="fs-connection"
          />
          <Button
            v-if="canSupervise"
            label="Refresh"
            icon="pi pi-refresh"
            size="small"
            severity="secondary"
            :loading="loading"
            @click="refreshLive()"
          />
          <div class="fs-user">
            <span class="fs-avatar">{{ (userName || '?').slice(0, 1).toUpperCase() }}</span>
            <span class="fs-user-name">{{ userName }}</span>
          </div>
        </div>
      </header>

      <main class="fs-content">
        <div v-if="bootstrap && !canWrite" class="fs-readonly-banner">
          <i class="pi pi-lock" />
          <template v-if="!tenants.length">
            No Tenant membership for this account. Ask a System Manager or a Tenant Admin
            to add you.
          </template>
          <template v-else-if="canSupervise">
            Live operations only for this Tenant. Configuration and publishing need the
            Tenant Admin role.
          </template>
          <template v-else-if="activeTenantRow?.role === 'Agent'">
            Agent access for this Tenant. Your own extension stays read-only.
          </template>
          <template v-else>
            This Tenant is read-only for your account.
          </template>
        </div>
        <component
          :is="currentPanel"
          :bootstrap="bootstrap"
          :live="live"
          :is-admin="canWrite"
          :can-write="canWrite"
          :can-supervise="canSupervise"
          :can-manage-tenants="canManageTenants"
          :tenant="activeTenant"
          :tenants="tenants"
          :tenant-context="tenantContext"
          :refresh-live="refreshLive"
          :notify="notify"
          :navigate="navigate"
          @changed="afterTenantChange"
        />
      </main>
    </div>
  </div>
</template>
