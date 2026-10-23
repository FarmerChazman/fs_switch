<script setup>
import { onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

import { api } from '../api'

const props = defineProps({
  tenant: { type: String, default: '' },
  notify: { type: Function, required: true },
})

const statuses = ['Logged Out', 'Available', 'On Break']
const config = ref(null)
const loading = ref(false)
const reveal = ref(false)
const status = ref('Logged Out')
const savingStatus = ref(false)

async function load() {
  loading.value = true
  reveal.value = false
  try {
    config.value = await api.softphoneConfig(props.tenant)
    status.value = config.value?.agent_status || 'Logged Out'
  } catch (error) {
    config.value = null
    props.notify(error.message, 'error')
  } finally {
    loading.value = false
  }
}

function statusSeverity(status) {
  if (status === 'Available') return 'success'
  if (status === 'On Break') return 'warn'
  return 'secondary'
}

async function setStatus() {
  savingStatus.value = true
  try {
    const result = await api.setMyAgentStatus(status.value, props.tenant)
    config.value = { ...config.value, agent_status: status.value }
    if (result?.esl_ok === false) {
      props.notify(`Status saved; live update failed: ${result.error || 'ESL unavailable'}`, 'warn')
    } else {
      props.notify(`Agent status set to ${status.value}.`)
    }
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    savingStatus.value = false
  }
}

onMounted(load)
watch(() => props.tenant, load)
</script>

<template>
  <div class="fs-stack">
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>My extension</h2>
        <span>Your own SIP endpoint and browser softphone settings.</span>
      </div>
      <Tag
        v-if="config?.enabled"
        :value="config.agent_status"
        :severity="statusSeverity(config.agent_status)"
      />
    </div>

    <div v-if="loading" class="fs-empty">Loading your extension…</div>

    <div v-else-if="!config?.enabled" class="fs-card">
      <div class="fs-empty">
        No extension is assigned to your account in this Tenant. Ask a Tenant Admin to add one.
      </div>
    </div>

    <div v-else class="fs-grid fs-grid-2">
      <div class="fs-card">
        <div class="fs-toolbar-title">
          <h2>Endpoint</h2>
          <span>Read-only details from the Tenant directory.</span>
        </div>
        <div class="fs-form-grid" style="margin-top: 18px">
          <div class="fs-field">
            <label>Extension</label>
            <span class="fs-mono">{{ config.extension }}</span>
          </div>
          <div class="fs-field">
            <label>Display name</label>
            <span>{{ config.display_name }}</span>
          </div>
          <div class="fs-field">
            <label>Tenant</label>
            <span class="fs-mono">{{ config.tenant }}</span>
          </div>
          <div class="fs-field">
            <label>Context</label>
            <span class="fs-mono">{{ config.context }}</span>
          </div>
          <div class="fs-field">
            <label>SIP domain</label>
            <span class="fs-mono">{{ config.domain || '—' }}</span>
          </div>
          <div class="fs-field">
            <label>Agent status</label>
            <span>{{ config.agent_status }}</span>
          </div>
          <div class="fs-field fs-span-2">
            <label for="my-agent-status">Change my status</label>
            <div style="display: flex; gap: 8px; align-items: center">
              <Select
                id="my-agent-status"
                v-model="status"
                :options="statuses"
                style="flex: 1"
              />
              <Button
                label="Apply"
                icon="pi pi-check"
                size="small"
                :loading="savingStatus"
                @click="setStatus"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="fs-card">
        <div class="fs-toolbar-title">
          <h2>Softphone</h2>
          <span>Credentials are returned only to the extension owner.</span>
        </div>
        <div class="fs-stack" style="margin-top: 18px">
          <div class="fs-field">
            <label>WebSocket URL</label>
            <span class="fs-mono">{{ config.ws_url || '—' }}</span>
          </div>
          <div class="fs-field">
            <label>SIP password</label>
            <div style="display: flex; gap: 8px; align-items: center">
              <span class="fs-mono" style="flex: 1">
                {{ reveal ? config.password : '••••••••••••' }}
              </span>
              <Button
                :label="reveal ? 'Hide' : 'Reveal'"
                :icon="reveal ? 'pi pi-eye-slash' : 'pi pi-eye'"
                size="small"
                severity="secondary"
                @click="reveal = !reveal"
              />
            </div>
          </div>
          <p class="fs-settings-note" style="margin: 0">
            Use these values in a WebRTC softphone. Do not share the password.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
