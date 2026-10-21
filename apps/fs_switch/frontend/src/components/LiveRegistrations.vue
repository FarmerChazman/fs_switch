<script setup>
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'

const props = defineProps({
  live: { type: Object, default: null },
})

const registrations = () => props.live?.registrations || []
</script>

<template>
  <div>
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Registrations</h2>
        <span>{{ registrations().length }} SIP contacts registered</span>
      </div>
      <Tag :value="live?.ok ? 'Live' : 'Offline'" :severity="live?.ok ? 'success' : 'danger'" />
    </div>

    <div v-if="live && !live.ok" class="fs-settings-note" style="margin-bottom: 14px">
      {{ live.error }}
    </div>

    <div class="fs-table-card">
      <DataTable :value="registrations()" dataKey="contact" paginator :rows="15" size="small">
        <template #empty>
          <div class="fs-empty">No registrations. Check the extension password and WebSocket URL.</div>
        </template>
        <Column field="user" header="User" />
        <Column field="realm" header="Realm" />
        <Column field="contact" header="Contact">
          <template #body="{ data }">
            <span class="fs-mono">{{ data.contact }}</span>
          </template>
        </Column>
        <Column field="network_ip" header="Network IP" />
        <Column field="network_port" header="Port" style="width: 90px" />
        <Column field="expires" header="Expires" style="width: 110px" />
      </DataTable>
    </div>
  </div>
</template>
