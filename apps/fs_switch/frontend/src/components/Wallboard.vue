<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Tag from 'primevue/tag'

const props = defineProps({
  live: { type: Object, default: null },
  tenant: { type: String, default: '' },
  refreshLive: { type: Function, required: true },
})

const summary = computed(
  () => props.live?.summary || { queues: [], calls: [], metrics: {} },
)
const metrics = computed(() => summary.value.metrics || {})
const queues = computed(() => summary.value.queues || [])
const calls = computed(() => summary.value.calls || [])

let refreshTimer = null

function formatDuration(seconds) {
  const value = Number(seconds) || 0
  if (value < 60) return `${value}s`
  const minutes = Math.floor(value / 60)
  const remainder = value % 60
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`
}

onMounted(() => {
  if (!props.live) props.refreshLive(true)
  refreshTimer = window.setInterval(() => props.refreshLive(true), 10000)
})

onUnmounted(() => {
  window.clearInterval(refreshTimer)
})
</script>

<template>
  <div class="fs-stack">
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Wallboard</h2>
        <span>
          {{ tenant }} · queue and call paths from the live FreeSWITCH snapshot
        </span>
      </div>
      <Tag
        :value="live?.ok ? 'Live' : 'Offline'"
        :severity="live?.ok ? 'success' : 'danger'"
      />
    </div>

    <div v-if="live && !live.ok" class="fs-settings-note">
      {{ live.error }}
    </div>

    <div class="fs-grid fs-grid-4">
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Waiting calls</span>
        <strong class="fs-stat-value">{{ metrics.waiting || 0 }}</strong>
        <span class="fs-stat-note">
          {{ queues.length }} {{ queues.length === 1 ? 'queue' : 'queues' }} · longest
          {{ formatDuration(metrics.longest_wait_seconds) }}
        </span>
      </div>
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Available agents</span>
        <strong class="fs-stat-value">{{ metrics.available_agents || 0 }}</strong>
        <span class="fs-stat-note">{{ metrics.busy_agents || 0 }} busy</span>
      </div>
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Active calls</span>
        <strong class="fs-stat-value">{{ metrics.active_calls || 0 }}</strong>
        <span class="fs-stat-note">{{ metrics.queue_calls || 0 }} in queue</span>
      </div>
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Answer rate</span>
        <strong class="fs-stat-value">{{ metrics.answer_rate || 0 }}%</strong>
        <span class="fs-stat-note">
          {{ metrics.answered || 0 }} answered · {{ metrics.abandoned || 0 }} abandoned
        </span>
      </div>
    </div>

    <div class="fs-grid fs-grid-2">
      <div class="fs-card">
        <div class="fs-toolbar-title" style="margin-bottom: 10px">
          <h2>Queues</h2>
          <span>Depth, configured wait and queue counters</span>
        </div>
        <div class="fs-table-card">
          <DataTable
            :value="queues"
            dataKey="name"
            size="small"
            :rows="8"
            :paginator="queues.length > 8"
          >
            <template #empty>
              <div class="fs-empty">No queues for this Tenant.</div>
            </template>
            <Column field="queue" header="Queue">
              <template #body="{ data }">
                <span>{{ data.queue }}</span>
                <span class="fs-muted"> · {{ data.context || 'default' }}</span>
              </template>
            </Column>
            <Column field="waiting" header="Waiting" style="width: 80px">
              <template #body="{ data }">
                <Tag
                  :value="String(data.waiting)"
                  :severity="data.waiting ? 'warn' : 'secondary'"
                />
              </template>
            </Column>
            <Column field="max_wait_seconds" header="Max wait" style="width: 100px">
              <template #body="{ data }">{{ formatDuration(data.max_wait_seconds) }}</template>
            </Column>
            <Column field="answered" header="Answered" style="width: 90px" />
            <Column field="abandoned" header="Abandoned" style="width: 100px" />
          </DataTable>
        </div>
      </div>

      <div class="fs-card">
        <div class="fs-toolbar-title" style="margin-bottom: 10px">
          <h2>Agents</h2>
          <span>Availability across the Tenant's call-center agents</span>
        </div>
        <div class="fs-grid fs-grid-2">
          <div class="fs-stat">
            <span class="fs-stat-label">Available</span>
            <strong class="fs-stat-value">{{ metrics.available_agents || 0 }}</strong>
          </div>
          <div class="fs-stat">
            <span class="fs-stat-label">Busy</span>
            <strong class="fs-stat-value">{{ metrics.busy_agents || 0 }}</strong>
          </div>
          <div class="fs-stat">
            <span class="fs-stat-label">On break</span>
            <strong class="fs-stat-value">{{ metrics.on_break || 0 }}</strong>
          </div>
          <div class="fs-stat">
            <span class="fs-stat-label">Logged out</span>
            <strong class="fs-stat-value">{{ metrics.logged_out || 0 }}</strong>
          </div>
        </div>
      </div>
    </div>

    <div class="fs-card">
      <div class="fs-toolbar-title" style="margin-bottom: 10px">
        <h2>Active call paths</h2>
        <span>Caller → queue or extension, with queue wait where available</span>
      </div>
      <div class="fs-table-card">
        <DataTable
          :value="calls"
          dataKey="uuid"
          size="small"
          :rows="10"
          :paginator="calls.length > 10"
        >
          <template #empty>
            <div class="fs-empty">No active calls.</div>
          </template>
          <Column field="path" header="Path">
            <template #body="{ data }">
              <span class="fs-mono">{{ data.path }}</span>
            </template>
          </Column>
          <Column field="state" header="State" style="width: 140px">
            <template #body="{ data }">
              <Tag :value="data.state || 'unknown'" severity="info" />
            </template>
          </Column>
          <Column field="wait_seconds" header="Wait" style="width: 100px">
            <template #body="{ data }">{{ formatDuration(data.wait_seconds) }}</template>
          </Column>
        </DataTable>
      </div>
    </div>
  </div>
</template>
