<script setup>
import { onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import { api } from '../api'

const props = defineProps({
  isAdmin: Boolean,
  tenant: { type: String, default: '' },
  tenants: { type: Array, default: () => [] },
  notify: { type: Function, required: true },
})

const queues = ref([])
const extensions = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({})

const strategies = [
  'longest-idle-agent',
  'round-robin',
  'agent-with-least-talk-time',
  'agent-with-fewest-calls',
  'ring-all',
]

const extensionOptions = ref([])
const backupOptions = ref([])

function blankQueue() {
  return {
    queue_name: '',
    tenant: props.tenant || '',
    display_name: '',
    enabled: 1,
    strategy: 'longest-idle-agent',
    max_wait_seconds: 180,
    music_on_hold: 'local_stream://moh',
    backup_queue: '',
    agents: [],
    description: '',
  }
}

async function load() {
  loading.value = true
  try {
    const tenantFilter = props.tenant ? { tenant: props.tenant } : {}
    const [queueRows, extensionRows] = await Promise.all([
      api.list('FS Queue', { order_by: 'queue_name asc', ...tenantFilter }),
      api.list('FS Extension', { order_by: 'extension asc', ...tenantFilter }),
    ])
    // A list query does not include child tables, so load the queue docs to
    // show an accurate agent count in the table.
    queues.value = await Promise.all(
      queueRows.map(async (row) => {
        const doc = await api.get('FS Queue', row.name)
        return { ...row, agents: doc.agents || [] }
      }),
    )
    extensions.value = extensionRows
    extensionOptions.value = extensionRows.map((row) => ({
      label: `${row.extension}${row.display_name ? ` — ${row.display_name}` : ''}`,
      value: row.name,
    }))
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function refreshBackupOptions() {
  backupOptions.value = queues.value
    .filter((queue) => queue.name !== editing.value)
    .map((queue) => ({ label: queue.queue_name, value: queue.name }))
}

function openNew() {
  editing.value = null
  form.value = blankQueue()
  refreshBackupOptions()
  dialog.value = true
}

async function openEdit(row) {
  try {
    const doc = await api.get('FS Queue', row.name)
    editing.value = row.name
    form.value = {
      ...blankQueue(),
      ...doc,
      agents: (doc.agents || []).map((agent) => ({
        extension: agent.extension,
        level: agent.level || 1,
        position: agent.position || 0,
      })),
    }
    refreshBackupOptions()
    dialog.value = true
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

function addAgent() {
  form.value.agents.push({
    extension: '',
    level: 1,
    position: form.value.agents.length + 1,
  })
}

function removeAgent(index) {
  form.value.agents.splice(index, 1)
}

async function save() {
  if (!form.value.queue_name?.trim()) {
    props.notify('Queue name is required.', 'error')
    return
  }
  const payload = {
    queue_name: form.value.queue_name.trim(),
    tenant: form.value.tenant,
    display_name: form.value.display_name || '',
    enabled: form.value.enabled ? 1 : 0,
    strategy: form.value.strategy || 'longest-idle-agent',
    max_wait_seconds: Number(form.value.max_wait_seconds || 180),
    music_on_hold: form.value.music_on_hold || 'local_stream://moh',
    backup_queue: form.value.backup_queue || '',
    description: form.value.description || '',
    agents: (form.value.agents || [])
      .filter((agent) => agent.extension)
      .map((agent, index) => ({
        doctype: 'FS Queue Agent',
        extension: agent.extension,
        level: Number(agent.level || 1),
        position: Number(agent.position || index + 1),
      })),
  }
  saving.value = true
  try {
    if (editing.value) {
      await api.update('FS Queue', editing.value, payload)
      props.notify('Queue updated.')
    } else {
      await api.create('FS Queue', payload)
      props.notify('Queue created.')
    }
    dialog.value = false
    await load()
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!window.confirm(`Delete queue "${row.queue_name}"?`)) return
  try {
    await api.remove('FS Queue', row.name)
    props.notify('Queue deleted.')
    await load()
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

function agentCount(row) {
  return (row.agents || []).length
}

onMounted(load)
watch(() => props.tenant, load)
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Queues</h2>
        <span>{{ queues.length }} call-center queues</span>
      </div>
      <Button v-if="isAdmin" label="New Queue" icon="pi pi-plus" size="small" @click="openNew" />
    </div>

    <div class="fs-table-card">
      <DataTable :value="queues" :loading="loading" dataKey="name" paginator :rows="12" size="small">
        <template #empty>
          <div class="fs-empty">No queues yet. Create one, then add extensions as agents.</div>
        </template>
        <Column field="queue_name" header="Queue" sortable />
        <Column field="tenant" header="Tenant" sortable />
        <Column field="display_name" header="Name" sortable />
        <Column field="strategy" header="Strategy" sortable />
        <Column header="Agents">
          <template #body="{ data }">
            <Tag :value="String(agentCount(data))" severity="info" />
          </template>
        </Column>
        <Column field="enabled" header="Enabled" sortable>
          <template #body="{ data }">
            <Tag :value="data.enabled ? 'Enabled' : 'Disabled'" :severity="data.enabled ? 'success' : 'danger'" />
          </template>
        </Column>
        <Column v-if="isAdmin" header="" style="width: 120px">
          <template #body="{ data }">
            <div style="display: flex; gap: 2px; justify-content: flex-end">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(data)" />
              <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="remove(data)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <Dialog
      v-model:visible="dialog"
      :header="editing ? 'Edit Queue' : 'New Queue'"
      modal
      :style="{ width: '760px', maxWidth: '95vw' }"
    >
      <div class="fs-form-grid">
        <div class="fs-field">
          <label for="queue-tenant">Tenant</label>
          <Select
            id="queue-tenant"
            v-model="form.tenant"
            :options="tenants"
            option-label="tenant_name"
            option-value="tenant"
            :disabled="Boolean(editing)"
            placeholder="Tenant"
          />
        </div>
        <div class="fs-field">
          <label for="queue-name">Queue name</label>
          <InputText id="queue-name" v-model="form.queue_name" placeholder="support" :disabled="Boolean(editing)" />
        </div>
        <div class="fs-field">
          <label for="queue-display">Display name</label>
          <InputText id="queue-display" v-model="form.display_name" placeholder="Support" />
        </div>
        <div class="fs-field">
          <label for="queue-strategy">Strategy</label>
          <Select id="queue-strategy" v-model="form.strategy" :options="strategies" />
        </div>
        <div class="fs-field">
          <label for="queue-wait">Maximum wait (seconds)</label>
          <InputNumber id="queue-wait" v-model="form.max_wait_seconds" :min="0" />
        </div>
        <div class="fs-field">
          <label for="queue-moh">Music on hold</label>
          <InputText id="queue-moh" v-model="form.music_on_hold" placeholder="local_stream://moh" />
        </div>
        <div class="fs-field">
          <label for="queue-backup">Backup queue</label>
          <Select
            id="queue-backup"
            v-model="form.backup_queue"
            :options="backupOptions"
            showClear
            placeholder="None"
          />
        </div>
        <div class="fs-field">
          <label>Enabled</label>
          <div style="padding-top: 5px">
            <Checkbox v-model="form.enabled" :binary="true" inputId="queue-enabled" />
            <label for="queue-enabled" style="margin-left: 8px; font-weight: 400">Enabled</label>
          </div>
        </div>
        <div class="fs-field fs-span-2">
          <label for="queue-desc">Description</label>
          <Textarea id="queue-desc" v-model="form.description" rows="2" />
        </div>
      </div>

      <div class="fs-toolbar" style="margin-top: 22px">
        <div class="fs-toolbar-title">
          <h2 style="font-size: 14px">Agents</h2>
          <span>Level 1 is primary; level 2 is a backup tier.</span>
        </div>
        <Button label="Add agent" icon="pi pi-plus" size="small" severity="secondary" @click="addAgent" />
      </div>

      <div v-if="!form.agents?.length" class="fs-empty">No agents in this queue yet.</div>
      <div v-for="(agent, index) in form.agents" :key="index" class="fs-agent-row">
        <Select v-model="agent.extension" :options="extensionOptions" placeholder="Extension" filter />
        <Select v-model="agent.level" :options="[1, 2]" placeholder="Level" />
        <InputNumber v-model="agent.position" :min="0" placeholder="Position" />
        <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="removeAgent(index)" />
      </div>

      <div class="fs-dialog-actions">
        <Button label="Cancel" severity="secondary" text @click="dialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="saving" @click="save" />
      </div>
    </Dialog>
  </div>
</template>
