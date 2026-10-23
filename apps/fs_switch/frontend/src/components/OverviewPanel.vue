<script setup>
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const props = defineProps({
  bootstrap: { type: Object, default: null },
  live: { type: Object, default: null },
  isAdmin: Boolean,
  canWrite: Boolean,
  canSupervise: Boolean,
  navigate: { type: Function, default: null },
})

const counts = () => props.bootstrap?.counts || {}
const liveCount = (key) => (props.live?.[key] || []).length

function go(key) {
  props.navigate?.(key)
}
</script>

<template>
  <div class="fs-stack">
    <div class="fs-grid fs-grid-4">
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Extensions</span>
        <span class="fs-stat-value">{{ counts().extensions || 0 }}</span>
        <span class="fs-stat-note">Enabled SIP endpoints</span>
        <Button v-if="canWrite || canSupervise" label="Manage" text size="small" @click="go('extensions')" />
      </div>
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Gateways</span>
        <span class="fs-stat-value">{{ counts().gateways || 0 }}</span>
        <span class="fs-stat-note">Carrier connections</span>
        <Button v-if="canWrite" label="Manage" text size="small" @click="go('gateways')" />
      </div>
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Queues</span>
        <span class="fs-stat-value">{{ counts().queues || 0 }}</span>
        <span class="fs-stat-note">Call-center ring groups</span>
        <Button v-if="canWrite" label="Manage" text size="small" @click="go('queues')" />
      </div>
      <div class="fs-card fs-stat">
        <span class="fs-stat-label">Dialplans</span>
        <span class="fs-stat-value">{{ counts().dialplans || 0 }}</span>
        <span class="fs-stat-note">Enabled call flows</span>
        <Button v-if="canWrite" label="Manage" text size="small" @click="go('dialplans')" />
      </div>
    </div>

    <div class="fs-grid fs-grid-2">
      <div class="fs-card">
        <div class="fs-toolbar">
          <div class="fs-toolbar-title">
            <h2>Live state</h2>
            <span>Read from FreeSWITCH over ESL</span>
          </div>
          <Tag
            v-if="canSupervise"
            :value="live?.ok ? 'Connected' : 'Offline'"
            :severity="live?.ok ? 'success' : 'danger'"
          />
          <Tag v-else value="Restricted" severity="secondary" />
        </div>
        <div v-if="canSupervise" class="fs-grid fs-grid-2">
          <div class="fs-stat">
            <span class="fs-stat-label">Channels</span>
            <span class="fs-stat-value">{{ liveCount('channels') }}</span>
          </div>
          <div class="fs-stat">
            <span class="fs-stat-label">Registrations</span>
            <span class="fs-stat-value">{{ liveCount('registrations') }}</span>
          </div>
          <div class="fs-stat">
            <span class="fs-stat-label">Agents</span>
            <span class="fs-stat-value">{{ liveCount('agents') }}</span>
          </div>
          <div class="fs-stat">
            <span class="fs-stat-label">Queues</span>
            <span class="fs-stat-value">{{ liveCount('queues') }}</span>
          </div>
        </div>
        <p v-if="!canSupervise" class="fs-stat-note">
          Live state is available to Supervisors and Tenant Admins.
        </p>
        <p v-else-if="live && !live.ok" class="fs-mono">{{ live.error }}</p>
        <p v-else class="fs-stat-note">
          Live state arrives over Frappe realtime; a slow snapshot poll is the fallback.
        </p>
      </div>

      <div class="fs-card">
        <div class="fs-toolbar-title">
          <h2>How FS Switch works</h2>
          <span>One source of truth, compiled on demand</span>
        </div>
        <div class="fs-stack" style="gap: 14px; margin-top: 18px">
          <div>
            <strong style="font-size: 13px">1. Configure in Frappe</strong>
            <p style="margin: 4px 0 0">
              Extensions, gateways, queues and dialplans are ordinary documents with
              audit fields and role-based permissions.
            </p>
          </div>
          <div>
            <strong style="font-size: 13px">2. FreeSWITCH asks for XML</strong>
            <p style="margin: 4px 0 0">
              <span class="fs-mono">mod_xml_curl</span> fetches the directory, dialplan
              and <span class="fs-mono">callcenter.conf</span> from the app using a shared
              secret.
            </p>
          </div>
          <div>
            <strong style="font-size: 13px">3. The console shows live state</strong>
            <p style="margin: 4px 0 0">
              The ESL client reads channels, registrations and agents; the listener
              publishes call and queue events on Frappe realtime.
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="fs-card">
      <div class="fs-toolbar-title">
        <h2>Getting started</h2>
        <span>A clean install has a disabled demo dialplan; enable it after setting your DID.</span>
      </div>
      <div class="fs-grid fs-grid-4" style="margin-top: 16px">
        <div>
          <strong style="font-size: 13px">1. Set the site</strong>
          <p>Open Settings and set the SIP domain, WebRTC URL and main DID.</p>
        </div>
        <div>
          <strong style="font-size: 13px">2. Add an extension</strong>
          <p>Link it to a Frappe user and give it a SIP password.</p>
        </div>
        <div>
          <strong style="font-size: 13px">3. Point FreeSWITCH</strong>
          <p>Use the XML-curl URL and secret from the settings page.</p>
        </div>
        <div>
          <strong style="font-size: 13px">4. Build a flow</strong>
          <p>Create a dialplan, drag nodes, and check the XML preview.</p>
        </div>
      </div>
    </div>
  </div>
</template>
