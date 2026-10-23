<script setup>
import { ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

import { api } from '../api'

const props = defineProps({
  bootstrap: { type: Object, default: null },
  live: { type: Object, default: null },
  isAdmin: Boolean,
  canSupervise: Boolean,
  tenant: { type: String, default: '' },
  tenantContext: { type: String, default: 'default' },
  notify: { type: Function, required: true },
  refreshLive: { type: Function, required: true },
})

const transferDialog = ref(false)
const selected = ref(null)
const destination = ref('')
const transferContext = ref('default')
const busy = ref(false)

const channels = () => props.live?.channels || []

function openTransfer(row) {
  selected.value = row
  destination.value = row.dest || ''
  transferContext.value = props.tenantContext || 'default'
  transferDialog.value = true
}

async function hangup(row) {
  if (!window.confirm(`Hang up channel ${row.uuid}?`)) return
  busy.value = true
  try {
    await api.action('hangup', { uuid: row.uuid, tenant: props.tenant })
    props.notify('Channel hung up.')
    await props.refreshLive(true)
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    busy.value = false
  }
}

async function transfer() {
  if (!destination.value.trim()) {
    props.notify('Destination is required.', 'error')
    return
  }
  busy.value = true
  try {
    await api.action('transfer', {
      uuid: selected.value.uuid,
      destination: destination.value.trim(),
      context: transferContext.value.trim() || 'default',
      tenant: props.tenant,
    })
    props.notify('Channel transferred.')
    transferDialog.value = false
    await props.refreshLive(true)
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Channels</h2>
        <span>{{ channels().length }} active channels over ESL</span>
      </div>
      <Tag
        :value="live?.ok ? 'Live' : 'Offline'"
        :severity="live?.ok ? 'success' : 'danger'"
      />
    </div>

    <div v-if="live && !live.ok" class="fs-settings-note" style="margin-bottom: 14px">
      {{ live.error }}
    </div>

    <div class="fs-table-card">
      <DataTable :value="channels()" dataKey="uuid" paginator :rows="15" size="small">
        <template #empty>
          <div class="fs-empty">No active channels.</div>
        </template>
        <Column field="uuid" header="UUID" style="width: 130px">
          <template #body="{ data }">
            <span class="fs-mono">{{ (data.uuid || '').slice(0, 8) }}</span>
          </template>
        </Column>
        <Column field="cid_num" header="Caller" />
        <Column field="cid_name" header="Caller name" />
        <Column field="dest" header="Destination" />
        <Column field="context" header="Context" />
        <Column field="callstate" header="State">
          <template #body="{ data }">
            <Tag :value="data.callstate || 'unknown'" severity="info" />
          </template>
        </Column>
        <Column header="Created" style="width: 130px">
          <template #body="{ data }">
            <span class="fs-mono">{{ data.created || '—' }}</span>
          </template>
        </Column>
        <Column v-if="canSupervise" header="" style="width: 160px">
          <template #body="{ data }">
            <div style="display: flex; gap: 2px; justify-content: flex-end">
              <Button
                icon="pi pi-arrow-right-arrow-left"
                text
                rounded
                size="small"
                title="Transfer"
                @click="openTransfer(data)"
              />
              <Button
                icon="pi pi-phone"
                text
                rounded
                severity="danger"
                size="small"
                title="Hang up"
                :disabled="busy"
                @click="hangup(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <Dialog v-model:visible="transferDialog" header="Transfer channel" modal :style="{ width: '440px' }">
      <div class="fs-stack" style="gap: 16px">
        <div class="fs-field">
          <label>Destination</label>
          <InputText v-model="destination" placeholder="1001" />
        </div>
        <div class="fs-field">
          <label>Context</label>
          <InputText v-model="transferContext" placeholder="default" />
        </div>
      </div>
      <div class="fs-dialog-actions">
        <Button label="Cancel" severity="secondary" text @click="transferDialog = false" />
        <Button label="Transfer" icon="pi pi-check" :loading="busy" @click="transfer" />
      </div>
    </Dialog>
  </div>
</template>
