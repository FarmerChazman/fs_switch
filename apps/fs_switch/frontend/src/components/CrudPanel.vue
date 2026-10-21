<script setup>
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

import { api } from '../api'

const props = defineProps({
  title: { type: String, required: true },
  doctype: { type: String, required: true },
  entityLabel: { type: String, default: 'Record' },
  columns: { type: Array, required: true },
  fields: { type: Array, required: true },
  isAdmin: Boolean,
  notify: { type: Function, required: true },
})

const rows = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const form = ref({})
const saving = ref(false)

function emptyForm() {
  const result = {}
  for (const field of props.fields) {
    result[field.field] = field.default ?? (field.type === 'checkbox' ? 0 : '')
  }
  return result
}

async function load() {
  loading.value = true
  try {
    rows.value = await api.list(props.doctype, { order_by: 'modified desc' })
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function openNew() {
  editing.value = null
  form.value = emptyForm()
  dialog.value = true
}

async function openEdit(row) {
  try {
    const doc = await api.get(props.doctype, row.name)
    editing.value = row.name
    form.value = { ...emptyForm(), ...doc }
    dialog.value = true
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

async function save() {
  for (const field of props.fields) {
    if (field.required && !String(form.value[field.field] ?? '').trim()) {
      props.notify(`${field.label} is required.`, 'error')
      return
    }
  }

  const payload = { ...form.value }
  for (const field of props.fields) {
    if (field.type === 'password' && editing.value && !payload[field.field]) {
      delete payload[field.field]
    }
    if (field.type === 'number' && payload[field.field] !== null && payload[field.field] !== '') {
      payload[field.field] = Number(payload[field.field])
    }
  }

  saving.value = true
  try {
    if (editing.value) {
      await api.update(props.doctype, editing.value, payload)
      props.notify(`${props.entityLabel} updated.`)
    } else {
      await api.create(props.doctype, payload)
      props.notify(`${props.entityLabel} created.`)
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
  if (!window.confirm(`Delete ${props.entityLabel.toLowerCase()} "${row.name}"?`)) return
  try {
    await api.remove(props.doctype, row.name)
    props.notify(`${props.entityLabel} deleted.`)
    await load()
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

function tagSeverity(value) {
  if (value === true || value === 1) return 'success'
  if (value === false || value === 0) return 'danger'
  const text = String(value || '').toLowerCase()
  if (['available', 'active', 'connected', 'enabled'].includes(text)) return 'success'
  if (['on break', 'wrap-up', 'warning'].includes(text)) return 'warn'
  if (['in call'].includes(text)) return 'info'
  if (['logged out', 'disabled', 'offline'].includes(text)) return 'secondary'
  return 'info'
}

function displayValue(row, column) {
  const value = row[column.field]
  if (column.type === 'bool') return value ? 'Enabled' : 'Disabled'
  if (value === null || value === undefined || value === '') return '—'
  return value
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>{{ title }}</h2>
        <span>{{ rows.length }} {{ rows.length === 1 ? entityLabel.toLowerCase() : `${entityLabel.toLowerCase()}s` }}</span>
      </div>
      <Button
        v-if="isAdmin"
        :label="`New ${entityLabel}`"
        icon="pi pi-plus"
        size="small"
        @click="openNew"
      />
    </div>

    <div class="fs-table-card">
      <DataTable :value="rows" :loading="loading" dataKey="name" paginator :rows="12" size="small">
        <template #empty>
          <div class="fs-empty">No {{ entityLabel.toLowerCase() }}s yet.</div>
        </template>
        <Column
          v-for="column in columns"
          :key="column.field"
          :field="column.field"
          :header="column.header"
          sortable
        >
          <template #body="{ data }">
            <Tag
              v-if="column.type === 'bool' || column.type === 'status'"
              :value="displayValue(data, column)"
              :severity="tagSeverity(column.type === 'bool' ? data[column.field] : data[column.field])"
            />
            <span v-else>{{ displayValue(data, column) }}</span>
          </template>
        </Column>
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
      :header="editing ? `Edit ${entityLabel}` : `New ${entityLabel}`"
      modal
      :style="{ width: '640px', maxWidth: '94vw' }"
    >
      <div class="fs-form-grid">
        <div
          v-for="field in fields"
          :key="field.field"
          class="fs-field"
          :class="{ 'fs-span-2': field.span === 2 || field.type === 'textarea' }"
        >
          <label v-if="field.type !== 'checkbox'" :for="`f-${field.field}`">{{ field.label }}</label>
          <InputText
            v-if="!field.type || field.type === 'text'"
            :id="`f-${field.field}`"
            v-model="form[field.field]"
            :placeholder="field.placeholder || ''"
          />
          <Password
            v-else-if="field.type === 'password'"
            :id="`f-${field.field}`"
            v-model="form[field.field]"
            :feedback="false"
            toggleMask
            :placeholder="editing ? 'Leave blank to keep the current value' : ''"
          />
          <InputNumber
            v-else-if="field.type === 'number'"
            :id="`f-${field.field}`"
            v-model="form[field.field]"
            :min="field.min ?? 0"
          />
          <Textarea
            v-else-if="field.type === 'textarea'"
            :id="`f-${field.field}`"
            v-model="form[field.field]"
            rows="3"
          />
          <Select
            v-else-if="field.type === 'select'"
            :id="`f-${field.field}`"
            v-model="form[field.field]"
            :options="field.options"
            :showClear="!field.required"
          />
          <div v-else-if="field.type === 'checkbox'" style="padding-top: 5px">
            <Checkbox v-model="form[field.field]" :binary="true" :inputId="`f-${field.field}`" />
            <label :for="`f-${field.field}`" style="margin-left: 8px; font-weight: 400">
              {{ field.checkboxLabel || field.label }}
            </label>
          </div>
          <small v-if="field.help">{{ field.help }}</small>
        </div>
      </div>
      <div class="fs-dialog-actions">
        <Button label="Cancel" severity="secondary" text @click="dialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="saving" @click="save" />
      </div>
    </Dialog>
  </div>
</template>
