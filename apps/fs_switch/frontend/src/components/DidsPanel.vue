<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
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

const rows = ref([])
const flows = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({})

const flowOptions = computed(() =>
  flows.value.map((flow) => ({ label: flow.title || flow.name, value: flow.name })),
)
const flowLabels = computed(() =>
  Object.fromEntries(flowOptions.value.map((flow) => [flow.value, flow.label])),
)

function blankDid() {
  return {
    number: '',
    tenant: props.tenant || '',
    enabled: 1,
    flow: '',
    description: '',
  }
}

async function load() {
  loading.value = true
  try {
    const tenantFilter = props.tenant ? { tenant: props.tenant } : {}
    const [didRows, flowRows] = await Promise.all([
      api.list('FS DID', { order_by: 'number asc', ...tenantFilter }),
      api.list('FS Dialplan', {
        order_by: 'title asc',
        ...tenantFilter,
        fields: JSON.stringify(['name', 'title']),
      }),
    ])
    rows.value = didRows
    flows.value = flowRows
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function openNew() {
  editing.value = null
  form.value = blankDid()
  dialog.value = true
}

async function openEdit(row) {
  try {
    const doc = await api.get('FS DID', row.name)
    editing.value = row.name
    form.value = { ...blankDid(), ...doc }
    dialog.value = true
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

async function save() {
  if (!form.value.number?.trim()) {
    props.notify('A DID / inbound number is required.', 'error')
    return
  }
  const payload = {
    number: form.value.number.trim(),
    tenant: form.value.tenant,
    enabled: form.value.enabled ? 1 : 0,
    flow: form.value.flow || '',
    description: form.value.description || '',
  }
  saving.value = true
  try {
    if (editing.value) {
      await api.update('FS DID', editing.value, payload)
      props.notify('DID updated.')
    } else {
      await api.create('FS DID', payload)
      props.notify('DID created.')
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
  if (!window.confirm(`Delete DID "${row.number}"?`)) return
  try {
    await api.remove('FS DID', row.name)
    props.notify('DID deleted.')
    await load()
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

onMounted(load)
watch(() => props.tenant, load)
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>DIDs</h2>
        <span>Inbound numbers assigned to this Tenant and their intended Flow.</span>
      </div>
      <Button
        v-if="isAdmin"
        label="New DID"
        icon="pi pi-plus"
        size="small"
        @click="openNew"
      />
    </div>

    <div class="fs-table-card">
      <DataTable :value="rows" :loading="loading" dataKey="name" paginator :rows="15" size="small">
        <template #empty>
          <div class="fs-empty">No DIDs assigned to this Tenant yet.</div>
        </template>
        <Column field="number" header="DID / inbound number" sortable>
          <template #body="{ data }">
            <span class="fs-mono">{{ data.number }}</span>
          </template>
        </Column>
        <Column field="tenant" header="Tenant" sortable />
        <Column field="flow" header="Assigned Flow" sortable>
          <template #body="{ data }">
            {{ data.flow ? flowLabels[data.flow] || data.flow : '—' }}
          </template>
        </Column>
        <Column field="enabled" header="Enabled" sortable>
          <template #body="{ data }">
            <Tag
              :value="data.enabled ? 'Enabled' : 'Disabled'"
              :severity="data.enabled ? 'success' : 'danger'"
            />
          </template>
        </Column>
        <Column field="description" header="Description" />
        <Column v-if="isAdmin" header="" style="width: 120px">
          <template #body="{ data }">
            <div style="display: flex; gap: 2px; justify-content: flex-end">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(data)" />
              <Button
                icon="pi pi-trash"
                text
                rounded
                severity="danger"
                size="small"
                @click="remove(data)"
              />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <Dialog
      v-model:visible="dialog"
      :header="editing ? 'Edit DID' : 'New DID'"
      modal
      :style="{ width: '640px', maxWidth: '94vw' }"
    >
      <div class="fs-form-grid">
        <div class="fs-field">
          <label for="did-number">DID / inbound number</label>
          <InputText id="did-number" v-model="form.number" placeholder="+14155550100" />
        </div>
        <div class="fs-field">
          <label for="did-tenant">Tenant</label>
          <Select
            id="did-tenant"
            v-model="form.tenant"
            :options="tenants"
            option-label="tenant_name"
            option-value="tenant"
            :disabled="Boolean(editing)"
            placeholder="Tenant"
          />
        </div>
        <div class="fs-field">
          <label for="did-flow">Assigned Flow</label>
          <Select
            id="did-flow"
            v-model="form.flow"
            :options="flowOptions"
            option-label="label"
            option-value="value"
            placeholder="No Flow assigned"
            show-clear
          />
        </div>
        <div class="fs-field">
          <label>Enabled</label>
          <div style="padding-top: 5px">
            <Checkbox v-model="form.enabled" :binary="true" inputId="did-enabled" />
            <label for="did-enabled" style="margin-left: 8px; font-weight: 400">
              Enabled
            </label>
          </div>
        </div>
        <div class="fs-field fs-span-2">
          <label for="did-description">Description</label>
          <Textarea id="did-description" v-model="form.description" rows="2" />
        </div>
      </div>

      <div class="fs-dialog-actions">
        <Button label="Cancel" severity="secondary" text @click="dialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="saving" @click="save" />
      </div>
    </Dialog>
  </div>
</template>
