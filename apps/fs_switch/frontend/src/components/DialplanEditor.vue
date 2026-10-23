<script setup>
import { computed, markRaw, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Drawer from 'primevue/drawer'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'

import { api, parseGraph } from '../api'
import FSNode from './FSNode.vue'
import SemanticFlowEditor from './SemanticFlowEditor.vue'

const props = defineProps({
  doc: { type: Object, required: true },
  notify: { type: Function, required: true },
  isAdmin: Boolean,
  tenant: { type: String, default: '' },
  tenantContext: { type: String, default: 'default' },
  tenants: { type: Array, default: () => [] },
})
const emit = defineEmits(['saved', 'close'])

const nodeTypes = markRaw({ 'fs-node': FSNode })
const applications = [
  'answer',
  'playback',
  'sleep',
  'ivr',
  'callcenter',
  'bridge',
  'transfer',
  'set',
  'record',
  'park',
  'voicemail',
  'conference',
  'hangup',
]

const form = ref({ ...props.doc })
const nodes = ref([])
const edges = ref([])
const activeTab = ref('flow')
const drawer = ref(false)
const selectedNode = ref(null)
const saving = ref(false)
const publishing = ref(false)
const previewXml = ref('')
const previewError = ref('')

const isNew = computed(() => !form.value.name)
const isSemantic = computed(() => form.value.graph_format === 'semantic')
const publishLabel = computed(() => {
  if (form.value.publish_status !== 'Published') return 'Draft'
  return form.value.published_version
    ? `Published v${form.value.published_version}`
    : 'Published'
})
const selectedData = computed(() => selectedNode.value?.data || null)

function defaultGraph() {
  return {
    nodes: [
      {
        id: 'answer',
        type: 'fs-node',
        position: { x: 90, y: 80 },
        data: { label: 'Answer', application: 'answer', data: '' },
      },
      {
        id: 'hangup',
        type: 'fs-node',
        position: { x: 90, y: 250 },
        data: { label: 'Hang up', application: 'hangup', data: '' },
      },
    ],
    edges: [{ id: 'e-answer-hangup', source: 'answer', target: 'hangup' }],
  }
}

function selectTenant(tenant) {
  form.value.tenant = tenant
  const row = (props.tenants || []).find((item) => item.tenant === tenant)
  if (row?.default_context) form.value.context = row.default_context
}

function hydrate(doc) {
  form.value = {
    title: '',
    tenant: props.tenant || '',
    context: props.tenantContext || 'default',
    extension_name: '',
    destination_number: '^1000$',
    priority: 10,
    enabled: 1,
    description: '',
    graph_format: 'raw',
    graph: '',
    compiled_xml: '',
    ...doc,
  }
  const graph = parseGraph(form.value.graph)
  const fallback = defaultGraph()
  nodes.value = (graph.nodes?.length ? graph.nodes : fallback.nodes).map((node) => ({
    ...node,
    type: node.type || 'fs-node',
    data: { label: '', application: '', data: '', ...(node.data || {}) },
  }))
  edges.value = graph.edges?.length ? graph.edges : fallback.edges
  previewXml.value = form.value.compiled_xml || ''
  previewError.value = ''
}

function addNode() {
  const id = `node-${Date.now()}`
  nodes.value.push({
    id,
    type: 'fs-node',
    position: { x: 360, y: 80 + nodes.value.length * 35 },
    data: { label: 'New step', application: 'playback', data: '' },
  })
}

function removeNode(node) {
  nodes.value = nodes.value.filter((item) => item.id !== node.id)
  edges.value = edges.value.filter((edge) => edge.source !== node.id && edge.target !== node.id)
  if (selectedNode.value?.id === node.id) {
    drawer.value = false
    selectedNode.value = null
  }
}

function onNodeClick(event) {
  selectedNode.value = event.node
  drawer.value = true
}

function moveNode(index, direction) {
  const target = index + direction
  if (target < 0 || target >= nodes.value.length) return
  const copy = [...nodes.value]
  ;[copy[index], copy[target]] = [copy[target], copy[index]]
  nodes.value = copy
}

function graphPayload() {
  return JSON.stringify({ nodes: nodes.value, edges: edges.value }, null, 2)
}

async function save() {
  if (!form.value.title?.trim() || !form.value.extension_name?.trim()) {
    props.notify('Title and extension name are required.', 'error')
    return null
  }
  saving.value = true
  try {
    const payload = {
      tenant: form.value.tenant,
      title: String(form.value.title || '').trim(),
      context: String(form.value.context || 'default').trim() || 'default',
      extension_name: String(form.value.extension_name || '').trim(),
      destination_number:
        String(form.value.destination_number || '.*').trim() || '.*',
      priority: Number(form.value.priority || 0),
      enabled: form.value.enabled ? 1 : 0,
      description: String(form.value.description || ''),
      graph_format: 'raw',
      graph: graphPayload(),
    }
    const saved = form.value.name
      ? await api.update('FS Dialplan', form.value.name, payload)
      : await api.create('FS Dialplan', payload)
    form.value = { ...form.value, ...saved }
    props.notify('Dialplan saved.')
    emit('saved', saved)
    await loadPreview()
    return saved
  } catch (error) {
    props.notify(error.message, 'error')
    return null
  } finally {
    saving.value = false
  }
}

async function publish() {
  if (!props.isAdmin || publishing.value) return
  const saved = await save()
  if (!saved?.name) return
  publishing.value = true
  try {
    const result = await api.publishFlow(saved.name)
    const updated = result.dialplan || saved
    form.value = { ...form.value, ...updated }
    if (result.reload && result.reload.ok === false) {
      props.notify(
        `Published dialplan as version ${result.version}, but FreeSWITCH did not reload: ${result.reload.error}`,
        'warn',
      )
    } else {
      props.notify(`Published dialplan as version ${result.version}.`)
    }
    emit('saved', updated)
    await loadPreview()
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    publishing.value = false
  }
}

async function loadPreview() {
  previewError.value = ''
  if (!form.value.name) {
    previewXml.value = ''
    previewError.value = 'Save the dialplan to compile the XML.'
    return
  }
  try {
    const result = await api.preview(form.value.name)
    previewXml.value = result.xml
    form.value.compiled_xml = result.xml
  } catch (error) {
    previewError.value = error.message
  }
}

function onSemanticSaved(saved) {
  form.value = { ...form.value, ...saved }
  emit('saved', saved)
}

watch(activeTab, (tab) => {
  if (tab === 'xml') loadPreview()
})

onMounted(() => hydrate(props.doc))
</script>

<template>
  <SemanticFlowEditor
    v-if="isSemantic"
    :doc="form"
    :notify="notify"
    :is-admin="isAdmin"
    :tenant="tenant"
    :tenant-context="tenantContext"
    :tenants="tenants"
    @saved="onSemanticSaved"
    @close="emit('close')"
  />

  <div v-else class="fs-stack">
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>{{ isNew ? 'New dialplan' : form.title }}</h2>
        <span>{{ form.context }} · {{ form.destination_number }}</span>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <Tag
          :value="publishLabel"
          :severity="form.publish_status === 'Published' ? 'success' : 'warning'"
        />
        <Button label="Back" icon="pi pi-arrow-left" severity="secondary" text @click="emit('close')" />
        <Button
          label="Save"
          icon="pi pi-check"
          :loading="saving"
          :disabled="!isAdmin"
          @click="save"
        />
        <Button
          label="Publish"
          icon="pi pi-upload"
          severity="success"
          :loading="publishing"
          :disabled="!isAdmin || saving || form.publish_status === 'Published'"
          @click="publish"
        />
      </div>
    </div>

    <Tabs v-model:value="activeTab">
      <TabList>
        <Tab value="flow">Flow</Tab>
        <Tab value="table">Table</Tab>
        <Tab value="xml">XML</Tab>
        <Tab value="settings">Settings</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="flow">
          <div class="fs-preview-actions">
            <Button
              label="Add node"
              icon="pi pi-plus"
              size="small"
              severity="secondary"
              @click="addNode"
            />
            <span style="color: var(--fs-muted); font-size: 12px; align-self: center">
              Drag from a node's right handle to the next node's left handle.
            </span>
          </div>
          <div class="fs-flow-wrap">
            <VueFlow
              v-model:nodes="nodes"
              v-model:edges="edges"
              :node-types="nodeTypes"
              fit-view-on-init
              :min-zoom="0.3"
              :max-zoom="1.6"
              @node-click="onNodeClick"
            >
              <Background pattern-color="#cbd5e1" :gap="18" />
              <Controls />
            </VueFlow>
          </div>
        </TabPanel>

        <TabPanel value="table">
          <div class="fs-table-card">
            <DataTable :value="nodes" dataKey="id" size="small">
              <template #empty>
                <div class="fs-empty">Add a node to start building the flow.</div>
              </template>
              <Column header="Label">
                <template #body="{ data }">
                  <InputText v-model="data.data.label" size="small" />
                </template>
              </Column>
              <Column header="Application" style="width: 190px">
                <template #body="{ data }">
                  <Select
                    v-model="data.data.application"
                    :options="applications"
                    editable
                    size="small"
                  />
                </template>
              </Column>
              <Column header="Arguments">
                <template #body="{ data }">
                  <InputText v-model="data.data.data" size="small" placeholder="e.g. 1001 XML default" />
                </template>
              </Column>
              <Column header="" style="width: 170px">
                <template #body="{ data, index }">
                  <div style="display: flex; gap: 2px; justify-content: flex-end">
                    <Button icon="pi pi-arrow-up" text rounded size="small" @click="moveNode(index, -1)" />
                    <Button icon="pi pi-arrow-down" text rounded size="small" @click="moveNode(index, 1)" />
                    <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="removeNode(data)" />
                  </div>
                </template>
              </Column>
            </DataTable>
          </div>
        </TabPanel>

        <TabPanel value="xml">
          <div v-if="previewError" class="fs-settings-note">{{ previewError }}</div>
          <pre v-else class="fs-code">{{ previewXml || 'No compiled XML yet.' }}</pre>
        </TabPanel>

        <TabPanel value="settings">
          <div class="fs-card">
            <div class="fs-form-grid">
              <div class="fs-field">
                <label for="dp-title">Title</label>
                <InputText id="dp-title" v-model="form.title" />
              </div>
              <div class="fs-field">
                <label for="dp-tenant">Tenant</label>
                <Select
                  id="dp-tenant"
                  :model-value="form.tenant"
                  :options="tenants"
                  option-label="tenant_name"
                  option-value="tenant"
                  :disabled="!isNew"
                  placeholder="Tenant"
                  @update:model-value="selectTenant"
                />
              </div>
              <div class="fs-field">
                <label for="dp-context">Context</label>
                <InputText id="dp-context" v-model="form.context" disabled />
                <small>Matches the Tenant's default context.</small>
              </div>
              <div class="fs-field">
                <label for="dp-ext">Extension name</label>
                <InputText id="dp-ext" v-model="form.extension_name" placeholder="office_ivr" />
              </div>
              <div class="fs-field">
                <label for="dp-dest">Destination pattern</label>
                <InputText id="dp-dest" v-model="form.destination_number" placeholder="^1000$" />
              </div>
              <div class="fs-field">
                <label for="dp-priority">Priority</label>
                <InputNumber id="dp-priority" v-model="form.priority" :min="0" />
              </div>
              <div class="fs-field">
                <label>Enabled</label>
                <div style="padding-top: 5px">
                  <Checkbox v-model="form.enabled" :binary="true" inputId="dp-enabled" />
                  <label for="dp-enabled" style="margin-left: 8px; font-weight: 400">Enabled</label>
                </div>
              </div>
              <div class="fs-field fs-span-2">
                <label for="dp-desc">Description</label>
                <Textarea id="dp-desc" v-model="form.description" rows="2" />
              </div>
            </div>
            <div class="fs-settings-note" style="margin-top: 18px">
              The XML tab is generated by the same compiler FreeSWITCH uses. The raw format
              compiles a linear chain; use the table order or graph edges to set it. Semantic
              flows open in the semantic canvas instead of this editor.
            </div>
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <Drawer v-model:visible="drawer" header="Configure node" position="right" :style="{ width: '380px' }">
      <div v-if="selectedData" class="fs-stack" style="gap: 16px">
        <div class="fs-field">
          <label>Display label</label>
          <InputText v-model="selectedData.label" />
        </div>
        <div class="fs-field">
          <label>FreeSWITCH application</label>
          <Select v-model="selectedData.application" :options="applications" editable />
        </div>
        <div class="fs-field">
          <label>Arguments (data)</label>
          <InputText v-model="selectedData.data" placeholder="e.g. 1001 XML default" />
        </div>
        <div class="fs-settings-note">
          Examples: <span class="fs-mono">playback</span> with
          <span class="fs-mono">ivr/ivr-welcome_to_freeswitch.wav</span>,
          <span class="fs-mono">callcenter</span> with
          <span class="fs-mono">support@default</span>, or
          <span class="fs-mono">transfer</span> with
          <span class="fs-mono">1001 XML default</span>.
        </div>
        <Button
          label="Delete node"
          icon="pi pi-trash"
          severity="danger"
          outlined
          @click="removeNode(selectedNode)"
        />
      </div>
      <div v-else class="fs-empty">Select a node in the flow.</div>
    </Drawer>
  </div>
</template>
