<script setup>
import CrudPanel from './CrudPanel.vue'

defineProps({
  isAdmin: Boolean,
  notify: { type: Function, required: true },
})

const columns = [
  { field: 'extension', header: 'Extension' },
  { field: 'display_name', header: 'Name' },
  { field: 'user', header: 'User' },
  { field: 'agent_status', header: 'Agent status', type: 'status' },
  { field: 'enabled', header: 'Enabled', type: 'bool' },
]

const fields = [
  { field: 'extension', label: 'Extension', required: true, placeholder: '1001' },
  { field: 'display_name', label: 'Display name', placeholder: 'Front desk' },
  { field: 'user', label: 'Frappe user', placeholder: 'agent@example.com' },
  { field: 'sip_password', label: 'SIP password', type: 'password', required: true },
  { field: 'context', label: 'Context', help: 'Leave blank to use the site default.' },
  { field: 'caller_id_name', label: 'Caller ID name' },
  { field: 'caller_id_number', label: 'Caller ID number' },
  { field: 'outbound_caller_id', label: 'Outbound caller ID' },
  {
    field: 'agent_status',
    label: 'Agent status',
    type: 'select',
    options: ['Logged Out', 'Available', 'On Break'],
    default: 'Logged Out',
  },
  { field: 'enabled', label: 'Enabled', type: 'checkbox', default: 1, checkboxLabel: 'Enabled' },
  {
    field: 'voicemail_enabled',
    label: 'Voicemail',
    type: 'checkbox',
    default: 1,
    checkboxLabel: 'Voicemail enabled',
  },
  { field: 'notes', label: 'Notes', type: 'textarea', span: 2 },
]
</script>

<template>
  <CrudPanel
    title="Extensions"
    doctype="FS Extension"
    entity-label="Extension"
    :columns="columns"
    :fields="fields"
    :is-admin="isAdmin"
    :notify="notify"
  />
</template>
