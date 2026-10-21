<script setup>
import CrudPanel from './CrudPanel.vue'

defineProps({
  isAdmin: Boolean,
  notify: { type: Function, required: true },
})

const columns = [
  { field: 'gateway_name', header: 'Gateway' },
  { field: 'proxy', header: 'Proxy' },
  { field: 'register', header: 'Register', type: 'bool' },
  { field: 'enabled', header: 'Enabled', type: 'bool' },
]

const fields = [
  { field: 'gateway_name', label: 'Gateway name', required: true, placeholder: 'carrier' },
  { field: 'proxy', label: 'Proxy', required: true, placeholder: 'sip.example.com:5060' },
  { field: 'register', label: 'Register', type: 'checkbox', default: 1, checkboxLabel: 'Register with the carrier' },
  { field: 'username', label: 'Username' },
  { field: 'password', label: 'Password', type: 'password' },
  { field: 'realm', label: 'Realm' },
  { field: 'from_domain', label: 'From domain' },
  { field: 'caller_id', label: 'Caller ID' },
  { field: 'context', label: 'Context', default: 'public' },
  { field: 'codec', label: 'Codec preferences', default: 'PCMU,PCMA' },
  { field: 'enabled', label: 'Enabled', type: 'checkbox', default: 1, checkboxLabel: 'Enabled' },
  { field: 'description', label: 'Description', type: 'textarea', span: 2 },
]
</script>

<template>
  <CrudPanel
    title="Gateways"
    doctype="FS Gateway"
    entity-label="Gateway"
    :columns="columns"
    :fields="fields"
    :is-admin="isAdmin"
    :notify="notify"
  />
</template>
