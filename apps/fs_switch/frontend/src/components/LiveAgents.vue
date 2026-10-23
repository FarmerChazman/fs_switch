<script setup>
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import { api } from '../api'

const props = defineProps({
  live: { type: Object, default: null },
  isAdmin: Boolean,
  canSupervise: Boolean,
  tenant: { type: String, default: '' },
  notify: { type: Function, required: true },
  refreshLive: { type: Function, required: true },
})

const rows = ref([])
const busy = ref('')

watch(
  () => props.live?.agents,
  (agents) => {
    rows.value = (agents || []).map((agent) => ({
      ...agent,
      _status: ['Available', 'On Break', 'Logged Out'].includes(agent.status)
        ? agent.status
        : 'Logged Out',
    }))
  },
  { immediate: true },
)

async function setStatus(row) {
  busy.value = row.name
  try {
    await api.action('agent_status', {
      agent: row.name,
      status: row._status,
      tenant: props.tenant,
    })
    props.notify(`Agent ${row.name} set to ${row._status}.`)
    await props.refreshLive(true)
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    busy.value = ''
  }
}

function severity(status) {
  if (status === 'Available') return 'success'
  if (status === 'On Break') return 'warn'
  return 'secondary'
}
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Agents</h2>
        <span>{{ rows.length }} call-center agents</span>
      </div>
      <Tag :value="live?.ok ? 'Live' : 'Offline'" :severity="live?.ok ? 'success' : 'danger'" />
    </div>

    <div v-if="live && !live.ok" class="fs-settings-note" style="margin-bottom: 14px">
      {{ live.error }}
    </div>

    <div class="fs-table-card">
      <DataTable :value="rows" dataKey="name" paginator :rows="15" size="small">
        <template #empty>
          <div class="fs-empty">No agents. Add extensions to a queue first.</div>
        </template>
        <Column field="name" header="Agent">
          <template #body="{ data }">
            <span class="fs-mono">{{ data.name }}</span>
          </template>
        </Column>
        <Column field="status" header="Status" style="width: 140px">
          <template #body="{ data }">
            <Tag :value="data.status || 'Unknown'" :severity="severity(data.status)" />
          </template>
        </Column>
        <Column field="state" header="State" style="width: 140px" />
        <Column v-if="canSupervise" header="Set status" style="width: 270px">
          <template #body="{ data }">
            <div style="display: flex; gap: 6px">
              <Select
                v-model="data._status"
                :options="['Available', 'On Break', 'Logged Out']"
                size="small"
                style="min-width: 130px"
              />
              <Button
                label="Apply"
                size="small"
                severity="secondary"
                :loading="busy === data.name"
                @click="setStatus(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>
