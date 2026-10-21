<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Tree from 'primevue/tree'
import Toast from 'primevue/toast'
import { useToast } from 'primevue/usetoast'

import { api } from './api'
import OverviewPanel from './components/OverviewPanel.vue'
import ExtensionsPanel from './components/ExtensionsPanel.vue'
import GatewaysPanel from './components/GatewaysPanel.vue'
import QueuesPanel from './components/QueuesPanel.vue'
import DialplansPanel from './components/DialplansPanel.vue'
import LiveChannels from './components/LiveChannels.vue'
import LiveRegistrations from './components/LiveRegistrations.vue'
import LiveAgents from './components/LiveAgents.vue'
import SettingsPanel from './components/SettingsPanel.vue'

const toast = useToast()
const bootstrap = ref(null)
const live = ref(null)
const loading = ref(true)
const selected = ref('overview')
const selectedKeys = ref({ overview: true })
let timer = null

const tree = [
  { key: 'overview', label: 'Overview', icon: 'pi pi-home' },
  {
    key: 'telephony',
    label: 'Telephony',
    icon: 'pi pi-phone',
    selectable: false,
    children: [
      { key: 'extensions', label: 'Extensions', icon: 'pi pi-id-card' },
      { key: 'gateways', label: 'Gateways', icon: 'pi pi-cloud' },
      { key: 'queues', label: 'Queues', icon: 'pi pi-users' },
      { key: 'dialplans', label: 'Dialplans', icon: 'pi pi-sitemap' },
    ],
  },
  {
    key: 'live',
    label: 'Live',
    icon: 'pi pi-wave-pulse',
    selectable: false,
    children: [
      { key: 'channels', label: 'Channels', icon: 'pi pi-arrows-h' },
      { key: 'registrations', label: 'Registrations', icon: 'pi pi-sign-in' },
      { key: 'agents', label: 'Agents', icon: 'pi pi-headphones' },
    ],
  },
  { key: 'settings', label: 'Settings', icon: 'pi pi-cog' },
]

const panels = {
  overview: OverviewPanel,
  extensions: ExtensionsPanel,
  gateways: GatewaysPanel,
  queues: QueuesPanel,
  dialplans: DialplansPanel,
  channels: LiveChannels,
  registrations: LiveRegistrations,
  agents: LiveAgents,
  settings: SettingsPanel,
}

const currentPanel = computed(() => panels[selected.value] || OverviewPanel)
const selectedLabel = computed(() => findLabel(tree, selected.value) || 'Overview')
const isAdmin = computed(() => Boolean(bootstrap.value?.is_admin))
const userName = computed(() => bootstrap.value?.full_name || bootstrap.value?.user || '')
const siteName = computed(() => window.fs_switch?.site || '')
const markUrl = '/assets/fs_switch/images/fs-switch-mark.svg'

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
  if (!panels[key]) return
  selected.value = key
  selectedKeys.value = { [key]: true }
}

function notify(detail, severity = 'success') {
  toast.add({ severity, summary: severity === 'error' ? 'Error' : 'FS Switch', detail, life: 4000 })
}

async function loadBootstrap() {
  try {
    bootstrap.value = await api.bootstrap()
  } catch (error) {
    notify(error.message || 'Could not load the console.', 'error')
  }
}

async function refreshLive(silent = false) {
  if (!isAdmin.value) return
  try {
    live.value = await api.live()
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

onMounted(async () => {
  loading.value = true
  await loadBootstrap()
  await refreshLive(true)
  loading.value = false
  timer = window.setInterval(() => refreshLive(true), 5000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
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
          <div class="fs-eyebrow">{{ siteName }}</div>
          <h1>{{ selectedLabel }}</h1>
        </div>
        <div class="fs-topbar-actions">
          <Tag
            :value="live?.ok ? 'FreeSWITCH connected' : 'FreeSWITCH offline'"
            :severity="live?.ok ? 'success' : 'danger'"
            class="fs-connection"
          />
          <Button
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
        <div v-if="bootstrap && !isAdmin" class="fs-readonly-banner">
          <i class="pi pi-lock" />
          This console is read-only for your account. Ask a System Manager for access.
        </div>
        <component
          :is="currentPanel"
          :bootstrap="bootstrap"
          :live="live"
          :is-admin="isAdmin"
          :refresh-live="refreshLive"
          :notify="notify"
          :navigate="navigate"
        />
      </main>
    </div>
  </div>
</template>
