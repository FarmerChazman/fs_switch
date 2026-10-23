<script setup>
import { computed, onMounted, ref } from 'vue'
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
  bootstrap: { type: Object, default: null },
  isAdmin: Boolean,
  canManageTenants: Boolean,
  notify: { type: Function, required: true },
})
const emit = defineEmits(['changed'])

const roles = ['Admin', 'Supervisor', 'Agent']
const defaultTenant = computed(() => props.bootstrap?.settings?.default_tenant || 'default')
const rows = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({})

function blankTenant() {
  return {
    tenant_name: '',
    slug: '',
    enabled: 1,
    sip_domain: '',
    default_context: '',
    outbound_caller_id: '',
    hold_music_file: '',
    description: '',
    members: [],
  }
}

async function load() {
  loading.value = true
  try {
    rows.value = await api.list('FS Tenant', { order_by: 'tenant_name asc' })
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function openNew() {
  if (!props.canManageTenants) return
  editing.value = null
  form.value = blankTenant()
  dialog.value = true
}

async function openEdit(row) {
  try {
    const doc = await api.get('FS Tenant', row.name)
    editing.value = row.name
    form.value = {
      ...blankTenant(),
      ...doc,
      members: (doc.members || []).map((member) => ({
        user: member.user,
        role: member.role || 'Agent',
        enabled: member.enabled ?? 1,
      })),
    }
    dialog.value = true
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

function addMember() {
  form.value.members.push({ user: '', role: 'Agent', enabled: 1 })
}

function removeMember(index) {
  form.value.members.splice(index, 1)
}

async function save() {
  if (!form.value.tenant_name?.trim() || !form.value.slug?.trim()) {
    props.notify('Tenant name and slug are required.', 'error')
    return
  }
  if (!form.value.default_context?.trim()) {
    props.notify('Default context is required.', 'error')
    return
  }
  const members = (form.value.members || [])
    .filter((member) => member.user?.trim())
    .map((member) => ({
      doctype: 'FS Tenant Member',
      user: member.user.trim(),
      role: member.role || 'Agent',
      enabled: member.enabled ? 1 : 0,
    }))
  const payload = {
    tenant_name: form.value.tenant_name.trim(),
    slug: form.value.slug.trim().toLowerCase(),
    enabled: form.value.enabled ? 1 : 0,
    sip_domain: (form.value.sip_domain || '').trim().toLowerCase(),
    default_context: form.value.default_context.trim().toLowerCase(),
    outbound_caller_id: (form.value.outbound_caller_id || '').trim(),
    hold_music_file: (form.value.hold_music_file || '').trim(),
    description: form.value.description || '',
    members,
  }
  saving.value = true
  try {
    if (editing.value) {
      await api.update('FS Tenant', editing.value, payload)
      props.notify('Tenant updated.')
    } else {
      await api.create('FS Tenant', payload)
      props.notify('Tenant created.')
    }
    dialog.value = false
    await load()
    emit('changed')
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!props.canManageTenants) return
  if (!window.confirm(`Delete Tenant "${row.tenant_name}"? This cannot be undone.`)) return
  try {
    await api.remove('FS Tenant', row.name)
    props.notify('Tenant deleted.')
    await load()
    emit('changed')
  } catch (error) {
    props.notify(error.message, 'error')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Tenants</h2>
        <span>
          SIP domain and context routing, plus tenant-scoped membership.
        </span>
      </div>
      <Button
        v-if="canManageTenants"
        label="New Tenant"
        icon="pi pi-plus"
        size="small"
        @click="openNew"
      />
    </div>

    <div class="fs-table-card">
      <DataTable :value="rows" :loading="loading" dataKey="name" paginator :rows="12" size="small">
        <template #empty>
          <div class="fs-empty">
            No Tenants are visible to your account. A System Manager can add you as a member.
          </div>
        </template>
        <Column field="tenant_name" header="Tenant" sortable />
        <Column field="slug" header="Slug" sortable>
          <template #body="{ data }">
            <span class="fs-mono">{{ data.slug }}</span>
          </template>
        </Column>
        <Column field="sip_domain" header="SIP domain" sortable>
          <template #body="{ data }">
            <span class="fs-mono">{{ data.sip_domain || '—' }}</span>
          </template>
        </Column>
        <Column field="default_context" header="Context" sortable>
          <template #body="{ data }">
            <span class="fs-mono">{{ data.default_context }}</span>
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
        <Column header="" style="width: 120px">
          <template #body="{ data }">
            <div style="display: flex; gap: 2px; justify-content: flex-end">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEdit(data)" />
              <Button
                v-if="canManageTenants && data.name !== defaultTenant"
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
      :header="editing ? 'Edit Tenant' : 'New Tenant'"
      modal
      :style="{ width: '780px', maxWidth: '95vw' }"
    >
      <div class="fs-form-grid">
        <div class="fs-field">
          <label for="tenant-name">Tenant name</label>
          <InputText id="tenant-name" v-model="form.tenant_name" placeholder="Acme" />
        </div>
        <div class="fs-field">
          <label for="tenant-slug">Slug</label>
          <InputText
            id="tenant-slug"
            v-model="form.slug"
            placeholder="acme"
            :disabled="Boolean(editing)"
          />
        </div>
        <div class="fs-field">
          <label for="tenant-domain">SIP domain</label>
          <InputText id="tenant-domain" v-model="form.sip_domain" placeholder="acme.example.com" />
        </div>
        <div class="fs-field">
          <label for="tenant-context">Default context</label>
          <InputText id="tenant-context" v-model="form.default_context" placeholder="acme" />
        </div>
        <div class="fs-field">
          <label for="tenant-caller-id">Outbound caller ID</label>
          <InputText
            id="tenant-caller-id"
            v-model="form.outbound_caller_id"
            placeholder="+14155550100"
          />
        </div>
        <div class="fs-field">
          <label for="tenant-moh">Music on hold</label>
          <InputText
            id="tenant-moh"
            v-model="form.hold_music_file"
            placeholder="local_stream://moh"
          />
        </div>
        <div class="fs-field">
          <label>Enabled</label>
          <div style="padding-top: 5px">
            <Checkbox
              v-model="form.enabled"
              :binary="true"
              inputId="tenant-enabled"
              :disabled="editing === defaultTenant"
            />
            <label for="tenant-enabled" style="margin-left: 8px; font-weight: 400">
              Enabled
            </label>
          </div>
        </div>
        <div class="fs-field fs-span-2">
          <label for="tenant-desc">Description</label>
          <Textarea id="tenant-desc" v-model="form.description" rows="2" />
        </div>
      </div>

      <div class="fs-toolbar" style="margin-top: 22px">
        <div class="fs-toolbar-title">
          <h2 style="font-size: 14px">Members</h2>
          <span>Admin manages config; Supervisor runs live operations; Agent sees their own extension.</span>
        </div>
        <Button label="Add member" icon="pi pi-plus" size="small" severity="secondary" @click="addMember" />
      </div>

      <div v-if="!form.members?.length" class="fs-empty">No members yet.</div>
      <div v-for="(member, index) in form.members" :key="index" class="fs-agent-row">
        <InputText v-model="member.user" placeholder="user@example.com" />
        <Select v-model="member.role" :options="roles" placeholder="Role" />
        <Checkbox v-model="member.enabled" :binary="true" inputId="member-enabled" />
        <Button
          icon="pi pi-trash"
          text
          rounded
          severity="danger"
          size="small"
          @click="removeMember(index)"
        />
      </div>

      <div class="fs-dialog-actions">
        <Button label="Cancel" severity="secondary" text @click="dialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="saving" @click="save" />
      </div>
    </Dialog>
  </div>
</template>
