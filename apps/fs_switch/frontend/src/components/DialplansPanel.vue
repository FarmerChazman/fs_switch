<script setup>
import { onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Drawer from 'primevue/drawer'
import Tag from 'primevue/tag'

import { api } from '../api'
import { starterSemanticGraph } from '../flow'
import DialplanEditor from './DialplanEditor.vue'
import FlowDiffDrawer from './FlowDiffDrawer.vue'

const props = defineProps({
  isAdmin: Boolean,
  tenant: { type: String, default: '' },
  tenantContext: { type: String, default: 'default' },
  tenants: { type: Array, default: () => [] },
  notify: { type: Function, required: true },
})

const rows = ref([])
const loading = ref(false)
const editorDoc = ref(null)
const versionsVisible = ref(false)
const versionsLoading = ref(false)
const versions = ref([])
const versionsDoc = ref(null)
const diffVisible = ref(false)
const diffLoading = ref(false)
const diff = ref(null)
const publishing = ref(false)
const rollingBack = ref(false)
let versionsTrigger = null
let diffTrigger = null

async function load() {
  loading.value = true
  try {
    rows.value = await api.list('FS Dialplan', {
      order_by: 'priority asc',
      ...(props.tenant ? { tenant: props.tenant } : {}),
      fields: JSON.stringify([
        'name',
        'title',
        'tenant',
        'graph_format',
        'context',
        'extension_name',
        'destination_number',
        'priority',
        'enabled',
        'publish_status',
        'published_version',
      ]),
    })
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function newSemanticFlow() {
  editorDoc.value = {
    title: '',
    tenant: props.tenant || 'default',
    context: props.tenantContext || 'default',
    extension_name: '',
    destination_number: '^1000$',
    priority: 10,
    enabled: 0,
    description: '',
    graph_format: 'semantic',
    graph: JSON.stringify(starterSemanticGraph(), null, 2),
  }
}

function newDialplan() {
  editorDoc.value = {
    title: '',
    tenant: props.tenant || 'default',
    context: props.tenantContext || 'default',
    extension_name: '',
    destination_number: '^1000$',
    priority: 10,
    enabled: 0,
    description: '',
    graph_format: 'raw',
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

function publishStatusLabel(row) {
  if (row.publish_status !== 'Published') return 'Draft'
  return row.published_version ? `Published v${row.published_version}` : 'Published'
}

function isCurrentVersion(version) {
  return Number(version) === Number(versionsDoc.value?.published_version || 0)
}

async function openDiff(row, event) {
  diffTrigger = event?.currentTarget || document.activeElement
  diff.value = null
  diffVisible.value = true
  diffLoading.value = true
  try {
    diff.value = await api.flowDiff(row.name)
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    diffLoading.value = false
  }
}

function restoreDiffFocus() {
  diffTrigger?.focus?.()
  diffTrigger = null
}

async function publish(row) {
  if (!props.isAdmin || publishing.value) return
  publishing.value = true
  try {
    const result = await api.publishFlow(row.name)
    notifyPublish(result, `Published ${row.title} as version ${result.version}.`)
    await load()
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    publishing.value = false
  }
}

function notifyPublish(result, message) {
  if (result.reload && result.reload.ok === false) {
    props.notify(`${message} FreeSWITCH did not reload: ${result.reload.error}`, 'warn')
    return
  }
  props.notify(message)
}

async function openVersions(row, event) {
  versionsTrigger = event?.currentTarget || document.activeElement
  versionsDoc.value = row
  versions.value = []
  versionsVisible.value = true
  versionsLoading.value = true
  try {
    const result = await api.flowVersions(row.name)
    versionsDoc.value = { ...row, ...result }
    versions.value = result.versions || []
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    versionsLoading.value = false
  }
}

function restoreVersionsFocus() {
  versionsTrigger?.focus?.()
  versionsTrigger = null
}

async function rollback(row) {
  if (!props.isAdmin || !versionsDoc.value || rollingBack.value) return
  rollingBack.value = true
  try {
    const result = await api.rollbackFlow(versionsDoc.value.name, row.version)
    notifyPublish(
      result,
      `Rolled back ${versionsDoc.value.title} to version ${result.version}.`,
    )
    versionsVisible.value = false
    await load()
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    rollingBack.value = false
  }
}

onMounted(load)
watch(() => props.tenant, load)
</script>

<template>
  <DialplanEditor
    v-if="editorDoc"
    :key="editorDoc.name || 'new'"
    :doc="editorDoc"
    :notify="notify"
    :is-admin="isAdmin"
    :tenant="tenant"
    :tenant-context="tenantContext"
    :tenants="tenants"
    @saved="saved"
    @close="closeEditor"
  />

  <div v-else>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Dialplans</h2>
        <span>Visual call flows compiled to FreeSWITCH XML</span>
      </div>
      <div v-if="isAdmin" style="display: flex; gap: 8px">
        <Button
          label="New semantic flow"
          icon="pi pi-sitemap"
          size="small"
          @click="newSemanticFlow"
        />
        <Button
          label="Raw dialplan"
          icon="pi pi-code"
          size="small"
          severity="secondary"
          outlined
          @click="newDialplan"
        />
      </div>
    </div>

    <div class="fs-table-card">
      <DataTable :value="rows" :loading="loading" dataKey="name" paginator :rows="12" size="small">
        <template #empty>
          <div class="fs-empty">
            No dialplans yet. Create a semantic flow, or use a raw dialplan for a
            FreeSWITCH application chain.
          </div>
        </template>
        <Column field="title" header="Title" sortable />
        <Column field="tenant" header="Tenant" sortable />
        <Column field="publish_status" header="Publish" style="width: 150px">
          <template #body="{ data }">
            <Tag
              :value="publishStatusLabel(data)"
              :severity="data.publish_status === 'Published' ? 'success' : 'warning'"
            />
          </template>
        </Column>
        <Column field="graph_format" header="Format" style="width: 120px">
          <template #body="{ data }">
            <Tag
              :value="data.graph_format === 'semantic' ? 'Semantic' : 'Raw'"
              :severity="data.graph_format === 'semantic' ? 'info' : 'secondary'"
            />
          </template>
        </Column>
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
        <Column header="" style="width: 190px">
          <template #body="{ data }">
            <div style="display: flex; gap: 2px; justify-content: flex-end">
              <Button
                icon="pi pi-pencil"
                text
                rounded
                size="small"
                title="Edit Flow"
                aria-label="Edit Flow"
                @click="edit(data)"
              />
              <Button
                v-if="isAdmin"
                icon="pi pi-upload"
                text
                rounded
                size="small"
                severity="success"
                title="Publish saved Draft"
                aria-label="Publish saved Draft"
                :disabled="publishing || data.publish_status === 'Published'"
                @click="publish(data)"
              />
              <Button
                v-if="isAdmin"
                icon="pi pi-history"
                text
                rounded
                size="small"
                severity="secondary"
                title="Published versions"
                aria-label="Published versions"
                :disabled="!data.published_version"
                @click="openVersions(data, $event)"
              />
              <Button
                icon="pi pi-arrows-h"
                text
                rounded
                size="small"
                severity="info"
                title="Draft vs Published"
                aria-label="Draft vs Published"
                @click="openDiff(data, $event)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <Drawer
      v-model:visible="versionsVisible"
      header="Published versions"
      position="right"
      :style="{ width: 'min(560px, 100vw)' }"
      :pt="{ root: { 'aria-label': 'Published versions' }, content: { tabindex: '0' } }"
      @hide="restoreVersionsFocus"
    >
      <div v-if="versionsLoading" class="fs-empty">Loading versions...</div>
      <DataTable v-else :value="versions" dataKey="version" size="small">
        <template #empty>
          <div class="fs-empty">This Flow has not been published yet.</div>
        </template>
        <Column field="version" header="Version" style="width: 90px">
          <template #body="{ data }">
            <span class="fs-mono">v{{ data.version }}</span>
            <Tag
              v-if="isCurrentVersion(data.version)"
              value="Current"
              severity="success"
              style="margin-left: 6px"
            />
          </template>
        </Column>
        <Column field="published_on" header="Published" />
        <Column field="published_by" header="By" />
        <Column field="note" header="Note" />
        <Column header="" style="width: 100px">
          <template #body="{ data }">
            <Button
              label="Rollback"
              size="small"
              severity="warning"
              outlined
              :disabled="rollingBack || isCurrentVersion(data.version)"
              @click="rollback(data)"
            />
          </template>
        </Column>
      </DataTable>
    </Drawer>

    <FlowDiffDrawer
      v-model:visible="diffVisible"
      :diff="diff"
      :loading="diffLoading"
      @hide="restoreDiffFocus"
    />
  </div>
</template>
