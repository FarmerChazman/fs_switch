<script setup>
import { computed } from 'vue'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Drawer from 'primevue/drawer'
import Tag from 'primevue/tag'

const visible = defineModel('visible', { type: Boolean, default: false })
const emit = defineEmits(['hide'])
const props = defineProps({
  diff: { type: Object, default: null },
  loading: Boolean,
})

const diffNodeRows = computed(() => {
  if (!props.diff) return []
  const rows = []
  for (const item of props.diff.nodes?.added || []) {
    rows.push({ ...item, change: 'Added', severity: 'success' })
  }
  for (const item of props.diff.nodes?.removed || []) {
    rows.push({ ...item, change: 'Removed', severity: 'danger' })
  }
  for (const item of props.diff.nodes?.changed || []) {
    rows.push({ ...item, change: 'Changed', severity: 'warning' })
  }
  return rows
})

const diffEdgeRows = computed(() => {
  if (!props.diff) return []
  const rows = []
  for (const item of props.diff.edges?.added || []) {
    rows.push({ ...item, change: 'Added', severity: 'success' })
  }
  for (const item of props.diff.edges?.removed || []) {
    rows.push({ ...item, change: 'Removed', severity: 'danger' })
  }
  return rows
})

function formatDiffValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function changeSummary(item) {
  if (!item.changes?.length) return ''
  return item.changes
    .map(
      (change) =>
        `${change.field}: ${formatDiffValue(change.published)} → ${formatDiffValue(change.draft)}`,
    )
    .join('; ')
}
</script>

<template>
  <Drawer
    v-model:visible="visible"
    header="Draft vs Published"
    position="right"
    :style="{ width: 'min(760px, 100vw)' }"
    :pt="{ root: { 'aria-label': 'Draft vs Published' }, content: { tabindex: '0' } }"
    @hide="emit('hide')"
  >
    <div v-if="loading" class="fs-empty">Comparing the Draft with the Published version...</div>
    <div v-else-if="diff" class="fs-stack">
      <div class="fs-diff-head">
        <div>
          <Tag
            :value="diff.has_changes ? 'Unpublished changes' : 'No changes'"
            :severity="diff.has_changes ? 'warning' : 'success'"
          />
          <span class="fs-muted" style="margin-left: 8px">{{ diff.title }}</span>
        </div>
        <span class="fs-muted">
          {{ diff.never_published ? 'Never published' : `Published v${diff.published_version}` }}
        </span>
      </div>

      <div v-if="diff.never_published" class="fs-settings-note">
        This Flow has not been published yet. Publishing will create version 1.
      </div>

      <ul v-if="diff.errors?.length" class="fs-simulation-errors">
        <li v-for="error in diff.errors" :key="error">{{ error }}</li>
      </ul>

      <div class="fs-table-card">
        <div class="fs-table-card-head">Settings</div>
        <DataTable :value="diff.settings" size="small">
          <Column field="field" header="Setting" />
          <Column header="Published">
            <template #body="{ data }">
              <span class="fs-mono">{{ formatDiffValue(data.published) }}</span>
            </template>
          </Column>
          <Column header="Draft">
            <template #body="{ data }">
              <span class="fs-mono">{{ formatDiffValue(data.draft) }}</span>
            </template>
          </Column>
          <Column header="" style="width: 100px">
            <template #body="{ data }">
              <Tag v-if="data.changed" value="Changed" severity="warning" />
            </template>
          </Column>
        </DataTable>
        <div class="fs-diff-note">{{ diff.settings_note }}</div>
      </div>

      <div class="fs-table-card">
        <div class="fs-table-card-head">Entry step</div>
        <div class="fs-diff-entry">
          <span>
            Published:
            <span class="fs-mono">{{ diff.entry.published || '—' }}</span>
          </span>
          <span>
            Draft:
            <span class="fs-mono">{{ diff.entry.draft || '—' }}</span>
          </span>
          <Tag v-if="diff.entry.changed" value="Changed" severity="warning" />
        </div>
      </div>

      <div class="fs-table-card">
        <div class="fs-table-card-head">Steps</div>
        <DataTable :value="diffNodeRows" size="small">
          <template #empty>
            <div class="fs-empty">No step changes.</div>
          </template>
          <Column header="Change" style="width: 110px">
            <template #body="{ data }">
              <Tag :value="data.change" :severity="data.severity" />
            </template>
          </Column>
          <Column header="Step">
            <template #body="{ data }">
              <strong>{{ data.label }}</strong>
              <span class="fs-mono" style="margin-left: 8px">{{ data.id }}</span>
            </template>
          </Column>
          <Column header="Type" style="width: 130px">
            <template #body="{ data }">
              <Tag :value="data.type" severity="secondary" />
            </template>
          </Column>
          <Column header="Detail">
            <template #body="{ data }">
              <span class="fs-muted">{{ changeSummary(data) || '—' }}</span>
            </template>
          </Column>
        </DataTable>
      </div>

      <div class="fs-table-card">
        <div class="fs-table-card-head">Connections</div>
        <DataTable :value="diffEdgeRows" size="small">
          <template #empty>
            <div class="fs-empty">No connection changes.</div>
          </template>
          <Column header="Change" style="width: 110px">
            <template #body="{ data }">
              <Tag :value="data.change" :severity="data.severity" />
            </template>
          </Column>
          <Column header="From">
            <template #body="{ data }">
              {{ data.source_label }}
              <span class="fs-mono" style="margin-left: 6px">{{ data.source_handle }}</span>
            </template>
          </Column>
          <Column header="To">
            <template #body="{ data }">{{ data.target_label }}</template>
          </Column>
        </DataTable>
      </div>

      <div class="fs-table-card">
        <div class="fs-table-card-head">XML</div>
        <div v-if="!diff.xml.changed" class="fs-diff-note">
          Compiled XML is identical.
        </div>
        <pre v-else-if="diff.xml.diff" class="fs-code fs-diff-code">{{ diff.xml.diff }}</pre>
        <div v-else class="fs-diff-note">
          {{ diff.xml.note || 'No XML diff available.' }}
        </div>
        <div v-if="diff.xml.truncated" class="fs-diff-note">
          Diff truncated to 2000 lines.
        </div>
      </div>
    </div>
  </Drawer>
</template>
