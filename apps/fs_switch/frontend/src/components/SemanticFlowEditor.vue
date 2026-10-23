<script setup>
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { ControlButton, Controls } from '@vue-flow/controls'

import { api, parseGraph } from '../api'
import {
  catalogMap,
  clone,
  edgeLabel,
  nodeIcon,
  normalizeNodeConfig,
  outputsForNode,
  specFor,
} from '../flow'
import FlowDiffDrawer from './FlowDiffDrawer.vue'
import SemanticNode from './SemanticNode.vue'

const props = defineProps({
  doc: { type: Object, required: true },
  notify: { type: Function, required: true },
  isAdmin: Boolean,
  tenant: { type: String, default: '' },
  tenantContext: { type: String, default: 'default' },
  tenants: { type: Array, default: () => [] },
})
const emit = defineEmits(['saved', 'close'])

const nodeTypes = markRaw({ 'semantic-node': SemanticNode })
const { fitView, screenToFlowCoordinate, updateNodeInternals, zoomIn, zoomOut } = useVueFlow()

const catalog = ref([])
const form = ref({})
const nodes = ref([])
const edges = ref([])
const entry = ref('')
const activeTab = ref('flow')
const drawer = ref(false)
const selectedNode = ref(null)
const saving = ref(false)
const publishing = ref(false)
const diffVisible = ref(false)
const diffLoading = ref(false)
const diff = ref(null)
const loading = ref(true)
const validating = ref(false)
const validationChecked = ref(false)
const previewXml = ref('')
const previewError = ref('')
const validation = ref({ valid: false, errors: [] })
const simulating = ref(false)
const simulation = ref(null)
const simDestination = ref('')
const simTime = ref('')
const simDigits = ref('')
let validationTimer = null
let validationRequest = 0
let applyingSimulation = false

const isNew = computed(() => !form.value.name)
const specs = computed(() => catalogMap(catalog.value))
const selectedSpec = computed(() =>
  selectedNode.value ? specs.value[selectedNode.value.data.nodeType] : null,
)
const entryOptions = computed(() =>
  nodes.value.map((node) => ({
    label: node.data.label || node.id,
    value: node.id,
  })),
)
const entryLabel = computed(
  () => entryOptions.value.find((option) => option.value === entry.value)?.label || 'not set',
)
const publishLabel = computed(() => {
  if (form.value.publish_status !== 'Published') return 'Draft'
  return form.value.published_version
    ? `Published v${form.value.published_version}`
    : 'Published'
})

const validationSummary = computed(() => {
  if (validating.value) return 'Checking flow...'
  if (!validationChecked.value) return 'Validation pending'
  if (validation.value.valid) return 'Flow is valid'
  const count = validation.value.errors.length
  return `${count} issue${count === 1 ? '' : 's'} found`
})
const paletteGroups = computed(() => {
  const groups = new Map()
  for (const item of catalog.value) {
    if (!groups.has(item.category)) groups.set(item.category, [])
    groups.get(item.category).push(item)
  }
  return [...groups.entries()].map(([category, items]) => ({ category, items }))
})
const simulationTag = computed(() => {
  if (!simulation.value) return { value: '', severity: 'secondary' }
  if (!simulation.value.valid) return { value: 'Invalid', severity: 'danger' }
  if (!simulation.value.matched) return { value: 'No match', severity: 'warn' }
  if (simulation.value.truncated) return { value: 'Loop', severity: 'warn' }
  return { value: 'Matched', severity: 'success' }
})
const endpointText = computed({
  get() {
    const endpoints = selectedNode.value?.data.config.endpoints
    return Array.isArray(endpoints) ? endpoints.join(', ') : endpoints || ''
  },
  set(value) {
    if (!selectedNode.value) return
    selectedNode.value.data.config.endpoints = String(value || '')
      .split(',')
      .map((endpoint) => endpoint.trim())
      .filter(Boolean)
  },
})

function selectTenant(tenant) {
  form.value.tenant = tenant
  const row = (props.tenants || []).find((item) => item.tenant === tenant)
  if (row?.default_context) form.value.context = row.default_context
}

function hydrate(doc) {
  form.value = {
    name: '',
    title: '',
    tenant: props.tenant || 'default',
    context: props.tenantContext || 'default',
    extension_name: '',
    destination_number: '^1000$',
    priority: 10,
    enabled: 1,
    description: '',
    graph_format: 'semantic',
    graph: '',
    compiled_xml: '',
    ...doc,
    graph_format: 'semantic',
  }

  const graph = parseGraph(form.value.graph)
  const sourceNodes = Array.isArray(graph.nodes) ? graph.nodes : []
  nodes.value = sourceNodes.map((node, index) => {
    const nodeType = String(node.type || '').trim()
    const spec = specs.value[nodeType] || specFor(catalog.value, nodeType)
    const nodeData = node.data && typeof node.data === 'object' ? node.data : {}
    return {
      id: String(node.id || `node_${index + 1}`),
      type: 'semantic-node',
      position:
        node.position && typeof node.position === 'object'
          ? { x: Number(node.position.x) || 0, y: Number(node.position.y) || 0 }
          : { x: 90, y: 80 + index * 150 },
      data: {
        nodeType,
        label: nodeData.label || spec?.label || nodeType || 'Step',
        category: spec?.category || '',
        config: normalizeNodeConfig(nodeType, nodeData, spec),
        isEntry: false,
      },
    }
  })

  edges.value = (Array.isArray(graph.edges) ? graph.edges : []).map((edge, index) => {
    const sourceHandle = String(edge.sourceHandle || 'next')
    return {
      id: String(edge.id || `edge_${index + 1}`),
      source: String(edge.source || ''),
      target: String(edge.target || ''),
      sourceHandle,
      label: edgeLabel(sourceHandle),
      type: 'smoothstep',
    }
  })

  entry.value = String(graph.entry || sourceNodes[0]?.id || '')
  markEntry()
  previewXml.value = form.value.compiled_xml || ''
  previewError.value = ''
}

function markEntry() {
  for (const node of nodes.value) {
    node.data.isEntry = node.id === entry.value
  }
}

function uniqueNodeId(type) {
  let counter = 1
  let candidate = `${type}_${counter}`
  while (nodes.value.some((node) => node.id === candidate)) {
    counter += 1
    candidate = `${type}_${counter}`
  }
  return candidate
}

function addNode(type, position = null) {
  if (!props.isAdmin) return
  const spec = specs.value[type]
  if (!spec) return
  const config = clone(spec.defaults || {})
  if (type === 'menu' && !config.options?.length) {
    config.options = [{ digit: '1', label: 'Option 1' }]
  }
  const id = uniqueNodeId(type)
  const node = {
    id,
    type: 'semantic-node',
    position: position || {
      x: 120 + (nodes.value.length % 3) * 280,
      y: 80 + Math.floor(nodes.value.length / 3) * 180,
    },
    data: {
      nodeType: type,
      label: spec.label,
      category: spec.category,
      config,
      isEntry: false,
    },
  }
  nodes.value.push(node)
  if (!entry.value) entry.value = id
  markEntry()
  selectedNode.value = nodes.value[nodes.value.length - 1]
  drawer.value = true
  nextTick(() => {
    updateNodeInternals(id)
    scheduleValidate()
  })
}

function removeNode(node) {
  if (!props.isAdmin || !node) return
  nodes.value = nodes.value.filter((item) => item.id !== node.id)
  edges.value = edges.value.filter(
    (edge) => edge.source !== node.id && edge.target !== node.id,
  )
  if (entry.value === node.id) entry.value = nodes.value[0]?.id || ''
  if (selectedNode.value?.id === node.id) {
    drawer.value = false
    selectedNode.value = null
  }
  markEntry()
  scheduleValidate()
}

function removeEdge(edge) {
  if (!props.isAdmin) return
  clearSimulation()
  edges.value = edges.value.filter((item) => item.id !== edge.id)
  scheduleValidate()
}

function onNodeClick(event) {
  selectedNode.value = nodes.value.find((node) => node.id === event.node.id) || event.node
  drawer.value = true
}

function onDragStart(event, type) {
  event.dataTransfer.setData('application/fs-semantic-node', type)
  event.dataTransfer.effectAllowed = 'move'
}

function onDrop(event) {
  const type = event.dataTransfer.getData('application/fs-semantic-node')
  if (!type) return
  addNode(type, screenToFlowCoordinate({ x: event.clientX, y: event.clientY }))
}

function onConnect(connection) {
  if (!props.isAdmin) return
  if (!connection.source || !connection.target) return
  const source = nodes.value.find((node) => node.id === connection.source)
  if (!source) return
  const handle = connection.sourceHandle || 'next'
  const validOutputs = outputsForNode(source.data.nodeType, source.data.config)
  if (!validOutputs.includes(handle)) return
  edges.value = edges.value.filter(
    (edge) => !(edge.source === connection.source && (edge.sourceHandle || 'next') === handle),
  )
  clearSimulation()
  edges.value.push({
    id: `e-${connection.source}-${handle}-${Date.now()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: handle,
    label: edgeLabel(handle),
    type: 'smoothstep',
  })
  scheduleValidate()
}

function addOption() {
  if (!props.isAdmin) return
  const config = selectedNode.value?.data.config
  if (!config) return
  if (!Array.isArray(config.options)) config.options = []
  const used = new Set(config.options.map((option) => option.digit))
  const digit = '1234567890'.split('').find((candidate) => !used.has(candidate)) || '1'
  config.options.push({ digit, label: '' })
  nextTick(refreshHandles)
}

function removeOption(index) {
  if (!props.isAdmin) return
  selectedNode.value?.data.config.options?.splice(index, 1)
  nextTick(refreshHandles)
}

function refreshHandles() {
  for (const node of nodes.value) updateNodeInternals(node.id)
}

function nodeLabel(nodeId) {
  return nodes.value.find((node) => node.id === nodeId)?.data.label || nodeId
}

function graphObject() {
  return {
    schema: 1,
    entry: entry.value || nodes.value[0]?.id || '',
    nodes: nodes.value.map((node) => ({
      id: node.id,
      type: node.data.nodeType,
      position: {
        x: Math.round(Number(node.position?.x) || 0),
        y: Math.round(Number(node.position?.y) || 0),
      },
      data: clone(node.data.config || {}),
    })),
    edges: edges.value.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle || 'next',
    })),
  }
}

function graphPayload() {
  return JSON.stringify(graphObject(), null, 2)
}

function clearSimulation() {
  simulation.value = null
  for (const node of nodes.value) {
    if (node.data.isSimulated) node.data.isSimulated = false
  }
}

async function runSimulation() {
  if (simulating.value) return
  if (!nodes.value.length) {
    props.notify('Add at least one step before simulating.', 'error')
    return
  }
  simulating.value = true
  try {
    const result = await api.simulateRoute(graphPayload(), {
      destination: simDestination.value,
      at: simTime.value,
      digits: simDigits.value,
      destinationNumber: form.value.destination_number || '',
    })
    simulation.value = result
    applyingSimulation = true
    const ids = new Set((result.path || []).map((step) => step.node))
    for (const node of nodes.value) node.data.isSimulated = ids.has(node.id)
    await nextTick()
    applyingSimulation = false
    if (!result.valid) {
      props.notify('The simulation could not run. See the errors below.', 'error')
    } else if (!result.matched) {
      props.notify('Destination does not match this Flow.', 'warn')
    }
  } catch (error) {
    simulation.value = null
    props.notify(error.message, 'error')
  } finally {
    simulating.value = false
  }
}

function scheduleValidate() {
  // Simulation highlights also mutate nodes. Clear the result only from the
  // graph-edit watchers below, never from a validation pass.
  window.clearTimeout(validationTimer)
  validationTimer = null
  validationRequest += 1
  validationChecked.value = false
  validation.value = { valid: false, errors: [] }
  validationTimer = window.setTimeout(validateNow, 450)
}

async function validateNow() {
  window.clearTimeout(validationTimer)
  validationTimer = null
  const graph = graphObject()
  if (!graph.nodes.length) {
    validationRequest += 1
    validating.value = false
    validationChecked.value = true
    validation.value = { valid: false, errors: ['Add at least one step to the flow.'] }
    return
  }
  validating.value = true
  const requestId = ++validationRequest
  try {
    const result = await api.validateFlow(JSON.stringify(graph))
    if (requestId !== validationRequest) return
    validationChecked.value = true
    validation.value = {
      valid: Boolean(result?.valid),
      errors: Array.isArray(result?.errors) ? result.errors : [],
    }
  } catch (error) {
    if (requestId !== validationRequest) return
    validationChecked.value = true
    validation.value = { valid: false, errors: [error.message] }
  } finally {
    if (requestId === validationRequest) validating.value = false
  }
}

async function save() {
  if (!props.isAdmin) return null
  if (!form.value.title?.trim() || !form.value.extension_name?.trim()) {
    props.notify('Title and extension name are required.', 'error')
    activeTab.value = 'settings'
    return null
  }
  await validateNow()
  if (!validation.value.valid) {
    props.notify('Fix the validation issues before saving this flow.', 'error')
    activeTab.value = 'flow'
    return null
  }
  saving.value = true
  try {
    const priority = form.value.priority
    const numericPriority = Number(priority)
    const payload = {
      tenant: form.value.tenant,
      title: String(form.value.title || '').trim(),
      context: String(form.value.context || 'default').trim() || 'default',
      extension_name: String(form.value.extension_name || '').trim(),
      destination_number:
        String(form.value.destination_number || '^1000$').trim() || '^1000$',
      priority:
        priority === '' || priority === null || priority === undefined
          ? 10
          : Number.isFinite(numericPriority)
            ? numericPriority
            : 10,
      enabled: form.value.enabled ? 1 : 0,
      description: String(form.value.description || ''),
      graph_format: 'semantic',
      graph: graphPayload(),
    }
    const saved = form.value.name
      ? await api.update('FS Dialplan', form.value.name, payload)
      : await api.create('FS Dialplan', payload)
    form.value = { ...form.value, ...saved }
    previewXml.value = saved.compiled_xml || previewXml.value
    props.notify('Semantic flow saved.')
    emit('saved', saved)
    return saved
  } catch (error) {
    props.notify(error.message, 'error')
    return null
  } finally {
    saving.value = false
  }
}

async function openDiff() {
  if (!form.value.name) {
    props.notify('Save the Flow before comparing it with the Published version.', 'warn')
    return
  }
  diff.value = null
  diffVisible.value = true
  diffLoading.value = true
  try {
    diff.value = await api.flowDiff(form.value.name)
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    diffLoading.value = false
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
    previewXml.value = updated.published_xml || previewXml.value
    props.notify(`Published semantic flow as version ${result.version}.`)
    emit('saved', updated)
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    publishing.value = false
  }
}

async function loadPreview() {
  previewError.value = ''
  try {
    const result = await api.previewGraph(graphPayload(), {
      graphFormat: 'semantic',
      extensionName: form.value.extension_name || 'preview',
      context: form.value.context || 'default',
      destinationNumber: form.value.destination_number || '^1000$',
    })
    previewXml.value = result.xml
  } catch (error) {
    previewError.value = error.message
  }
}

watch(
  () => nodes.value.map((node) => ({
    id: node.id,
    type: node.data.nodeType,
    config: node.data.config,
  })),
  () => {
    if (applyingSimulation) return
    clearSimulation()
    scheduleValidate()
    nextTick(refreshHandles)
  },
  { deep: true },
)
watch(entry, () => {
  markEntry()
  clearSimulation()
  scheduleValidate()
})
watch(activeTab, (tab) => {
  if (tab === 'xml') loadPreview()
})

onMounted(async () => {
  try {
    const result = await api.flowCatalog()
    catalog.value = result?.nodes || []
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    hydrate(props.doc)
    loading.value = false
    scheduleValidate()
  }
})

onBeforeUnmount(() => {
  window.clearTimeout(validationTimer)
  validationTimer = null
})
</script>

<template>
  <div v-if="loading" class="fs-card fs-empty">Loading semantic flow editor...</div>

  <div v-else class="fs-stack fs-semantic-editor">
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>{{ isNew ? 'New semantic flow' : form.title }}</h2>
        <span>{{ form.context }} · {{ form.destination_number }} · semantic graph</span>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <Tag value="Semantic" severity="info" />
        <Tag
          :value="publishLabel"
          :severity="form.publish_status === 'Published' ? 'success' : 'warning'"
        />
        <Button
          label="Back"
          icon="pi pi-arrow-left"
          severity="secondary"
          text
          @click="emit('close')"
        />
        <Button
          label="Validate"
          icon="pi pi-check-circle"
          severity="secondary"
          outlined
          :loading="validating"
          @click="validateNow"
        />
        <Button
          label="Save"
          icon="pi pi-check"
          :loading="saving"
          :disabled="!isAdmin"
          @click="save"
        />
        <Button
          label="Draft vs Published"
          icon="pi pi-history"
          severity="info"
          text
          :disabled="isNew || saving || publishing"
          @click="openDiff"
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

    <div
      class="fs-semantic-status"
      :class="{
        'is-valid': validation.valid,
        'is-invalid': !validation.valid && validation.errors.length,
      }"
    >
      <i
        :class="
          validation.valid
            ? 'pi pi-check-circle'
            : 'pi pi-exclamation-triangle'
        "
      />
      <div>
        <strong>{{ validationSummary }}</strong>
        <span>
          {{
            validation.valid
              ? 'Every required output is connected and the flow compiles cleanly.'
              : 'Connect every required output before saving. Validation runs against the same compiler FreeSWITCH uses.'
          }}
        </span>
      </div>
    </div>

    <Tabs v-model:value="activeTab">
      <TabList>
        <Tab value="flow">Flow</Tab>
        <Tab value="table">Table</Tab>
        <Tab value="simulate">Simulate</Tab>
        <Tab value="xml">XML</Tab>
        <Tab value="settings">Settings</Tab>
      </TabList>
      <TabPanels>
        <TabPanel value="flow">
          <div class="fs-semantic-layout">
            <aside
              class="fs-semantic-palette"
              tabindex="0"
              aria-label="Semantic node palette"
            >
              <div class="fs-palette-title">Semantic palette</div>
              <div class="fs-palette-hint">Drag a step onto the canvas, or click to add it.</div>
              <div v-if="!paletteGroups.length" class="fs-empty">Palette unavailable.</div>
              <div v-for="group in paletteGroups" :key="group.category" class="fs-palette-group">
                <div class="fs-palette-category">{{ group.category }}</div>
                <div
                  v-for="item in group.items"
                  :key="item.type"
                  class="fs-palette-item"
                  :class="{ 'is-disabled': !isAdmin }"
                  draggable="true"
                  @dragstart="onDragStart($event, item.type)"
                  @click="addNode(item.type)"
                >
                  <i :class="nodeIcon(item.type)" />
                  <span>
                    <strong>{{ item.label }}</strong>
                    <small>
                      {{
                        item.terminal
                          ? 'Terminal step'
                          : item.type === 'menu'
                            ? 'Digit branches'
                            : `${item.outputs.length} output${item.outputs.length === 1 ? '' : 's'}`
                      }}
                    </small>
                  </span>
                </div>
              </div>
            </aside>

            <section class="fs-semantic-canvas">
              <div class="fs-semantic-canvas-toolbar">
                <span>
                  Entry: <strong>{{ entryLabel }}</strong> · Drag from an output port to connect
                  steps.
                </span>
                <Button
                  label="Fit view"
                  icon="pi pi-expand"
                  size="small"
                  severity="secondary"
                  text
                  @click="fitView({ padding: 0.2 })"
                />
              </div>

              <div class="fs-flow-wrap fs-semantic-flow" @dragover.prevent @drop="onDrop">
                <VueFlow
                  v-model:nodes="nodes"
                  v-model:edges="edges"
                  :node-types="nodeTypes"
                  fit-view-on-init
                  :min-zoom="0.2"
                  :max-zoom="1.6"
                  :snap-to-grid="true"
                  :snap-grid="[20, 20]"
                  delete-key-code="Delete"
                  @connect="onConnect"
                  @node-click="onNodeClick"
                  @nodes-initialized="fitView({ padding: 0.2 })"
                >
                  <Background pattern-color="#cbd5e1" :gap="18" />
                  <Controls :show-interactive="false">
                    <template #control-zoom-in>
                      <ControlButton
                        class="vue-flow__controls-zoomin"
                        aria-label="Zoom in"
                        @click="zoomIn"
                      >
                        <i class="pi pi-plus" />
                      </ControlButton>
                    </template>
                    <template #control-zoom-out>
                      <ControlButton
                        class="vue-flow__controls-zoomout"
                        aria-label="Zoom out"
                        @click="zoomOut"
                      >
                        <i class="pi pi-minus" />
                      </ControlButton>
                    </template>
                    <template #control-fit-view>
                      <ControlButton
                        class="vue-flow__controls-fitview"
                        aria-label="Fit flow to view"
                        @click="fitView({ padding: 0.2 })"
                      >
                        <i class="pi pi-window-maximize" />
                      </ControlButton>
                    </template>
                  </Controls>
                </VueFlow>
              </div>

              <div
                class="fs-validation-panel"
                :class="{ 'is-valid': validation.valid, 'is-invalid': !validation.valid }"
              >
                <div class="fs-validation-head">
                  <strong>Validation</strong>
                  <span v-if="validating">Checking...</span>
                  <span v-else-if="!validationChecked">Pending</span>
                  <span v-else-if="validation.valid">No issues</span>
                  <span v-else>{{ validation.errors.length }} issue(s)</span>
                </div>
                <div v-if="validating" class="fs-validation-empty">Checking the flow...</div>
                <div v-else-if="!validationChecked" class="fs-validation-empty">
                  Validation will run automatically as the flow changes.
                </div>
                <ul v-else-if="validation.errors.length">
                  <li v-for="error in validation.errors" :key="error">{{ error }}</li>
                </ul>
                <div v-else class="fs-validation-empty">
                  The flow is structurally complete and compiles cleanly.
                </div>
              </div>
            </section>
          </div>
        </TabPanel>

        <TabPanel value="table">
          <div class="fs-stack">
            <div class="fs-table-card">
              <DataTable :value="nodes" dataKey="id" size="small">
                <template #empty>
                  <div class="fs-empty">Add a step to start building the flow.</div>
                </template>
                <Column header="Label">
                  <template #body="{ data }">
                    <InputText
                      v-model="data.data.label"
                      :aria-label="`Step label for ${data.id}`"
                      size="small"
                    />
                  </template>
                </Column>
                <Column header="Type" style="width: 170px">
                  <template #body="{ data }">
                    <Tag :value="data.data.nodeType" severity="secondary" />
                  </template>
                </Column>
                <Column header="Outputs">
                  <template #body="{ data }">
                    <span
                      v-for="handle in outputsForNode(data.data.nodeType, data.data.config)"
                      :key="handle"
                      class="fs-port-chip"
                    >
                      {{ edgeLabel(handle) }}
                    </span>
                    <span
                      v-if="!outputsForNode(data.data.nodeType, data.data.config).length"
                      class="fs-muted"
                    >
                      Terminal
                    </span>
                  </template>
                </Column>
                <Column header="Entry" style="width: 110px">
                  <template #body="{ data }">
                    <Tag v-if="entry === data.id" value="Entry" severity="success" />
                    <Button
                      v-else
                      label="Set entry"
                      size="small"
                      text
                      @click="entry = data.id"
                    />
                  </template>
                </Column>
                <Column header="" style="width: 60px">
                  <template #body="{ data }">
                    <Button
                      icon="pi pi-trash"
                      text
                      rounded
                      severity="danger"
                      size="small"
                      :aria-label="`Delete step ${data.data.label || data.id}`"
                      @click="removeNode(data)"
                    />
                  </template>
                </Column>
              </DataTable>
            </div>

            <div class="fs-table-card">
              <div class="fs-table-card-head">Connections</div>
              <DataTable :value="edges" dataKey="id" size="small">
                <template #empty>
                  <div class="fs-empty">Connect two steps by dragging from an output port.</div>
                </template>
                <Column header="From">
                  <template #body="{ data }">
                    <span>{{ nodeLabel(data.source) }}</span>
                    <span class="fs-mono" style="margin-left: 8px">
                      {{ edgeLabel(data.sourceHandle) }}
                    </span>
                  </template>
                </Column>
                <Column header="To">
                  <template #body="{ data }">{{ nodeLabel(data.target) }}</template>
                </Column>
                <Column header="" style="width: 60px">
                  <template #body="{ data }">
                    <Button
                      icon="pi pi-trash"
                      text
                      rounded
                      severity="danger"
                      size="small"
                      :aria-label="`Delete connection ${data.id}`"
                      @click="removeEdge(data)"
                    />
                  </template>
                </Column>
              </DataTable>
            </div>
          </div>
        </TabPanel>

        <TabPanel value="simulate">
          <div class="fs-stack">
            <div class="fs-card">
              <div class="fs-form-grid">
                <div class="fs-field">
                  <label for="sim-destination">Destination</label>
                  <InputText
                    id="sim-destination"
                    v-model="simDestination"
                    placeholder="1000"
                  />
                </div>
                <div class="fs-field">
                  <label for="sim-time">Time</label>
                  <InputText
                    id="sim-time"
                    v-model="simTime"
                    placeholder="2026-10-23T14:30 or 1430"
                  />
                </div>
                <div class="fs-field">
                  <label for="sim-digits">Digits</label>
                  <InputText id="sim-digits" v-model="simDigits" placeholder="1" />
                </div>
              </div>
              <div class="fs-preview-actions" style="margin-top: 14px">
                <Button
                  label="Run simulation"
                  icon="pi pi-play"
                  size="small"
                  :loading="simulating"
                  @click="runSimulation"
                />
                <span class="fs-muted" style="align-self: center; font-size: 12px">
                  Walks the Flow graph, never the XML. Time defaults to now; digits feed
                  menus in order.
                </span>
              </div>
            </div>

            <div v-if="simulation" class="fs-card fs-simulation">
              <div class="fs-simulation-head">
                <div>
                  <Tag
                    :value="simulationTag.value"
                    :severity="simulationTag.severity"
                  />
                  <span
                    v-if="simulation.matched && simulation.terminal"
                    class="fs-muted"
                  >
                    Ends at <strong>{{ simulation.outcome }}</strong>
                    <span class="fs-mono">({{ simulation.terminal }})</span>
                  </span>
                  <span v-else-if="simulation.matched" class="fs-muted">
                    No terminal step reached.
                  </span>
                </div>
                <span class="fs-muted fs-mono">{{ simulation.at }}</span>
              </div>

              <ul v-if="simulation.errors?.length" class="fs-simulation-errors">
                <li v-for="error in simulation.errors" :key="error">{{ error }}</li>
              </ul>
              <ul v-if="simulation.warnings?.length" class="fs-simulation-warnings">
                <li v-for="warning in simulation.warnings" :key="warning">
                  {{ warning }}
                </li>
              </ul>

              <div
                v-if="Object.keys(simulation.variables || {}).length"
                class="fs-simulation-variables"
              >
                <strong>Variables</strong>
                <span
                  v-for="(value, key) in simulation.variables"
                  :key="key"
                  class="fs-port-chip"
                >
                  {{ key }}={{ value }}
                </span>
              </div>

              <DataTable :value="simulation.path" size="small" stripedRows>
                <template #empty>
                  <div class="fs-empty">No path to show.</div>
                </template>
                <Column header="#" style="width: 48px">
                  <template #body="{ index }">{{ index + 1 }}</template>
                </Column>
                <Column header="Step">
                  <template #body="{ data }">
                    <strong>{{ data.label }}</strong>
                    <span class="fs-mono" style="margin-left: 8px">
                      {{ data.node }}
                    </span>
                  </template>
                </Column>
                <Column header="Type" style="width: 130px">
                  <template #body="{ data }">
                    <Tag :value="data.type" severity="secondary" />
                  </template>
                </Column>
                <Column header="Output" style="width: 130px">
                  <template #body="{ data }">
                    <span v-if="data.port" class="fs-port-chip">
                      {{ edgeLabel(data.port) }}
                    </span>
                    <span v-else class="fs-muted">Terminal</span>
                  </template>
                </Column>
                <Column header="Detail">
                  <template #body="{ data }">
                    <span class="fs-muted">{{ data.note || '—' }}</span>
                  </template>
                </Column>
              </DataTable>
            </div>

            <div v-else class="fs-card fs-empty">
              Run a simulation to see the path a call takes through this Flow.
            </div>
          </div>
        </TabPanel>

        <TabPanel value="xml">
          <div class="fs-preview-actions">
            <Button
              label="Refresh XML"
              icon="pi pi-refresh"
              size="small"
              severity="secondary"
              @click="loadPreview"
            />
            <span class="fs-muted" style="align-self: center; font-size: 12px">
              This is the exact XML block the semantic compiler will publish.
            </span>
          </div>
          <div v-if="previewError" class="fs-settings-note">{{ previewError }}</div>
          <pre v-else class="fs-code">{{ previewXml || 'No compiled XML yet.' }}</pre>
        </TabPanel>

        <TabPanel value="settings">
          <div class="fs-card">
            <div class="fs-form-grid">
              <div class="fs-field">
                <label for="sf-title">Title</label>
                <InputText id="sf-title" v-model="form.title" />
              </div>
              <div class="fs-field">
                <label for="sf-tenant">Tenant</label>
                <Select
                  id="sf-tenant"
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
                <label for="sf-context">Context</label>
                <InputText id="sf-context" v-model="form.context" disabled />
                <small>Matches the Tenant's default context.</small>
              </div>
              <div class="fs-field">
                <label for="sf-ext">Extension name</label>
                <InputText id="sf-ext" v-model="form.extension_name" placeholder="office_ivr" />
              </div>
              <div class="fs-field">
                <label for="sf-dest">Destination pattern</label>
                <InputText id="sf-dest" v-model="form.destination_number" placeholder="^1000$" />
              </div>
              <div class="fs-field">
                <label for="sf-priority">Priority</label>
                <InputNumber id="sf-priority" v-model="form.priority" :min="0" />
              </div>
              <div class="fs-field">
                <label for="sf-entry">Entry step</label>
                <Select
                  id="sf-entry"
                  v-model="entry"
                  :options="entryOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Select the first step"
                />
              </div>
              <div class="fs-field">
                <label>Enabled</label>
                <div style="padding-top: 5px">
                  <Checkbox v-model="form.enabled" :binary="true" inputId="sf-enabled" />
                  <label for="sf-enabled" style="margin-left: 8px; font-weight: 400">Enabled</label>
                </div>
              </div>
              <div class="fs-field fs-span-2">
                <label for="sf-desc">Description</label>
                <Textarea id="sf-desc" v-model="form.description" rows="2" />
              </div>
            </div>
            <div class="fs-settings-note" style="margin-top: 18px">
              Semantic steps are compiled into deterministic named FreeSWITCH extensions.
              The entry extension matches <span class="fs-mono">{{ form.destination_number }}</span>
              and transfers into the flow. The XML tab shows the result before publishing.
            </div>
          </div>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <Drawer
      v-model:visible="drawer"
      header="Configure step"
      position="right"
      :style="{ width: 'min(430px, 100vw)' }"
      :pt="{ root: { 'aria-label': 'Configure step' }, content: { tabindex: '0' } }"
    >
      <div v-if="selectedNode" class="fs-stack" style="gap: 16px">
        <div class="fs-field">
          <label>Display label</label>
          <InputText v-model="selectedNode.data.label" aria-label="Display label" />
        </div>
        <div class="fs-field">
          <label>Step type</label>
          <div>
            <Tag :value="selectedNode.data.nodeType" severity="secondary" />
            <span v-if="selectedSpec" class="fs-muted" style="margin-left: 8px; font-size: 12px">
              {{ selectedSpec.category }}
            </span>
          </div>
        </div>

        <template v-if="selectedNode.data.nodeType === 'play'">
          <div class="fs-field">
            <label>Prompt</label>
            <InputText
              v-model="selectedNode.data.config.prompt"
              aria-label="Prompt"
              placeholder="ivr/welcome.wav"
            />
            <small>A sound path or phrase understood by FreeSWITCH playback.</small>
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'menu'">
          <div class="fs-field">
            <label>Prompt</label>
            <InputText
              v-model="selectedNode.data.config.prompt"
              aria-label="Prompt"
              placeholder="ivr/main_menu.wav"
            />
          </div>
          <div class="fs-field">
            <label>Invalid-entry prompt</label>
            <InputText
              v-model="selectedNode.data.config.invalid_prompt"
              aria-label="Invalid-entry prompt"
            />
          </div>
          <div class="fs-field">
            <label>Variable</label>
            <InputText
              v-model="selectedNode.data.config.variable"
              aria-label="Variable"
              placeholder="menu_digit"
            />
          </div>
          <div class="fs-form-grid">
            <div class="fs-field">
              <label>Minimum digits</label>
              <InputNumber
                v-model="selectedNode.data.config.min_digits"
                aria-label="Minimum digits"
                :min="1"
                :max="1"
              />
            </div>
            <div class="fs-field">
              <label>Maximum digits</label>
              <InputNumber
                v-model="selectedNode.data.config.max_digits"
                aria-label="Maximum digits"
                :min="1"
                :max="1"
              />
              <small>Digit menus collect exactly one digit.</small>
            </div>
            <div class="fs-field">
              <label>Tries</label>
              <InputNumber
                v-model="selectedNode.data.config.tries"
                aria-label="Tries"
                :min="1"
              />
            </div>
            <div class="fs-field">
              <label>Timeout (ms)</label>
              <InputNumber
                v-model="selectedNode.data.config.timeout_ms"
                aria-label="Timeout milliseconds"
                :min="1"
              />
            </div>
          </div>
          <div class="fs-field">
            <label>Terminators</label>
            <InputText
              v-model="selectedNode.data.config.terminators"
              aria-label="Terminators"
            />
          </div>
          <div class="fs-field">
            <label>Options</label>
            <div class="fs-option-list">
              <div
                v-for="(option, index) in selectedNode.data.config.options"
                :key="index"
                class="fs-option-row"
              >
                <InputText
                  v-model="option.digit"
                  :aria-label="`Option ${index + 1} digit`"
                  maxlength="1"
                  placeholder="1"
                  class="fs-option-digit"
                />
                <InputText
                  v-model="option.label"
                  :aria-label="`Option ${index + 1} label`"
                  placeholder="Sales"
                />
                <Button
                  icon="pi pi-trash"
                  text
                  rounded
                  severity="danger"
                  size="small"
                  :aria-label="`Remove option ${index + 1}`"
                  @click="removeOption(index)"
                />
              </div>
              <Button
                label="Add option"
                icon="pi pi-plus"
                size="small"
                severity="secondary"
                outlined
                @click="addOption"
              />
            </div>
            <small>Each digit creates its own output port. The timeout port is always present.</small>
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'time'">
          <div class="fs-field">
            <label>Field</label>
            <InputText
              v-model="selectedNode.data.config.field"
              aria-label="Time field"
              placeholder="${strftime(%H%M)}"
            />
          </div>
          <div class="fs-field">
            <label>Expression</label>
            <InputText
              v-model="selectedNode.data.config.expression"
              aria-label="Time expression"
              placeholder="^(09|10|11|12|13|14|15|16|17)"
            />
            <small>A FreeSWITCH regular expression evaluated against the field.</small>
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'ring_group'">
          <div class="fs-field">
            <label>Endpoints</label>
            <Textarea
              v-model="endpointText"
              aria-label="Ring group endpoints"
              rows="3"
              placeholder="1001, 1002, user/1003@${domain_name}"
            />
            <small>Comma-separated extensions or full FreeSWITCH endpoints.</small>
          </div>
          <div class="fs-field">
            <label>Timeout (seconds)</label>
            <InputNumber
              v-model="selectedNode.data.config.timeout_seconds"
              aria-label="Ring group timeout seconds"
              :min="0"
            />
            <small>Set to 0 to omit the global leg timeout.</small>
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'queue'">
          <div class="fs-field">
            <label>Queue</label>
            <InputText
              v-model="selectedNode.data.config.queue"
              aria-label="Queue"
              placeholder="support"
            />
            <small>Use queue@context when the queue lives outside this dialplan's context.</small>
          </div>
          <div class="fs-field">
            <label>Context (optional)</label>
            <InputText
              v-model="selectedNode.data.config.context"
              aria-label="Context"
              placeholder="default"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'voicemail'">
          <div class="fs-field">
            <label>Mailbox</label>
            <InputText
              v-model="selectedNode.data.config.mailbox"
              aria-label="Mailbox"
              placeholder="1001"
            />
          </div>
          <div class="fs-field">
            <label>Profile</label>
            <InputText
              v-model="selectedNode.data.config.profile"
              aria-label="Profile"
              placeholder="default"
            />
          </div>
          <div class="fs-field">
            <label>Domain</label>
            <InputText
              v-model="selectedNode.data.config.domain"
              aria-label="Domain"
              placeholder="${domain_name}"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'transfer'">
          <div class="fs-field">
            <label>Destination</label>
            <InputText
              v-model="selectedNode.data.config.destination"
              aria-label="Transfer destination"
              placeholder="1001"
            />
          </div>
          <div class="fs-field">
            <label>Dialplan</label>
            <InputText
              v-model="selectedNode.data.config.dialplan"
              aria-label="Transfer dialplan"
              placeholder="XML"
            />
          </div>
          <div class="fs-field">
            <label>Context (optional)</label>
            <InputText
              v-model="selectedNode.data.config.context"
              aria-label="Context"
              placeholder="default"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'conference'">
          <div class="fs-field">
            <label>Room</label>
            <InputText
              v-model="selectedNode.data.config.room"
              aria-label="Conference room"
              placeholder="sales"
            />
          </div>
          <div class="fs-field">
            <label>Profile</label>
            <InputText
              v-model="selectedNode.data.config.profile"
              aria-label="Profile"
              placeholder="default"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'set'">
          <div class="fs-field">
            <label>Variable</label>
            <InputText
              v-model="selectedNode.data.config.variable"
              aria-label="Variable name"
              placeholder="route"
            />
          </div>
          <div class="fs-field">
            <label>Value</label>
            <InputText
              v-model="selectedNode.data.config.value"
              aria-label="Variable value"
              placeholder="sales"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'sleep'">
          <div class="fs-field">
            <label>Milliseconds</label>
            <InputNumber
              v-model="selectedNode.data.config.milliseconds"
              aria-label="Sleep milliseconds"
              :min="1"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'record'">
          <div class="fs-field">
            <label>Recording path</label>
            <InputText
              v-model="selectedNode.data.config.path"
              aria-label="Recording path"
              placeholder="$${recordings_dir}/call.wav"
            />
          </div>
        </template>

        <template v-else-if="selectedNode.data.nodeType === 'hangup'">
          <div class="fs-field">
            <label>Cause (optional)</label>
            <InputText
              v-model="selectedNode.data.config.cause"
              aria-label="Hangup cause"
              placeholder="NORMAL_CLEARING"
            />
          </div>
        </template>

        <div v-else class="fs-settings-note">
          This step has no configuration. It compiles directly to a FreeSWITCH action.
        </div>

        <div class="fs-drawer-actions">
          <Button
            v-if="entry !== selectedNode.id"
            label="Set as entry"
            icon="pi pi-sign-in"
            size="small"
            severity="secondary"
            outlined
            @click="entry = selectedNode.id"
          />
          <Button
            label="Delete step"
            icon="pi pi-trash"
            severity="danger"
            outlined
            size="small"
            @click="removeNode(selectedNode)"
          />
        </div>
      </div>
      <div v-else class="fs-empty">Select a step in the flow.</div>
    </Drawer>

    <FlowDiffDrawer v-model:visible="diffVisible" :diff="diff" :loading="diffLoading" />
  </div>
</template>
