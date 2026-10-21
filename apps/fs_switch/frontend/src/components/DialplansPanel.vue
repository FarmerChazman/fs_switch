<script setup>
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'

import { api } from '../api'
import DialplanEditor from './DialplanEditor.vue'

const props = defineProps({
  isAdmin: Boolean,
  notify: { type: Function, required: true },
})

const rows = ref([])
const loading = ref(false)
const editorDoc = ref(null)

async function load() {
  loading.value = true
  try {
    rows.value = await api.list('FS Dialplan', { order_by: 'priority asc' })
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function newDialplan() {
  editorDoc.value = {
    title: '',
    context: 'default',
    extension_name: '',
    destination_number: '^1000$',
    priority: 10,
    enabled: 0,
    description: '',
    graph: '',
  }
}

async function edit(row) {
  try {
    editorDoc.value = await api.get('FS Dialplan', row.name)
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

function closeEditor() {
  editorDoc.value = null
}

async function saved() {
  await load()
}

onMounted(load)
</script>

<template>
  <DialplanEditor
    v-if="editorDoc"
    :key="editorDoc.name || 'new'"
    :doc="editorDoc"
    :notify="notify"
    :is-admin="isAdmin"
    @saved="saved"
    @close="closeEditor"
  />

  <div v-else>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Dialplans</h2>
        <span>Visual call flows compiled to FreeSWITCH XML</span>
      </div>
      <Button v-if="isAdmin" label="New Dialplan" icon="pi pi-plus" size="small" @click="newDialplan" />
    </div>

    <div class="fs-table-card">
      <DataTable :value="rows" :loading="loading" dataKey="name" paginator :rows="12" size="small">
        <template #empty>
          <div class="fs-empty">
            No dialplans yet. Create one and add answer, playback, queue or transfer nodes.
          </div>
        </template>
        <Column field="title" header="Title" sortable />
        <Column field="context" header="Context" sortable />
        <Column field="extension_name" header="Extension" sortable />
        <Column field="destination_number" header="Destination" sortable>
          <template #body="{ data }">
            <span class="fs-mono">{{ data.destination_number }}</span>
          </template>
        </Column>
        <Column field="priority" header="Priority" sortable />
        <Column field="enabled" header="Enabled" sortable>
          <template #body="{ data }">
            <Tag :value="data.enabled ? 'Enabled' : 'Disabled'" :severity="data.enabled ? 'success' : 'danger'" />
          </template>
        </Column>
        <Column v-if="isAdmin" header="" style="width: 90px">
          <template #body="{ data }">
            <Button icon="pi pi-pencil" text rounded size="small" @click="edit(data)" />
          </template>
        </Column>
      </DataTable>
    </div>
  </div>
</template>
