<script setup>
import { onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'

import { api } from '../api'

const props = defineProps({
  bootstrap: { type: Object, default: null },
  isAdmin: Boolean,
  notify: { type: Function, required: true },
})

const form = ref({})
const gateways = ref([])
const saving = ref(false)

function hydrate() {
  const settings = props.bootstrap?.settings || {}
  form.value = {
    main_did: settings.main_did || '',
    default_context: settings.default_context || 'default',
    sip_domain: settings.sip_domain || 'localhost',
    webrtc_url: settings.webrtc_url || 'ws://localhost:5066',
    public_ip: settings.public_ip || '127.0.0.1',
    esl_host: settings.esl_host || '127.0.0.1',
    esl_port: settings.esl_port || 8021,
    ivr_prompt_file: settings.ivr_prompt_file || 'ivr/ivr-welcome_to_freeswitch.wav',
    hold_music_file: settings.hold_music_file || 'local_stream://moh',
    voicemail_path: settings.voicemail_path || '/var/lib/freeswitch/voicemail',
    recording_path: settings.recording_path || '/var/lib/freeswitch/recordings',
    default_gateway: settings.default_gateway || '',
    outbound_caller_id: settings.outbound_caller_id || '',
    recording_enabled: settings.recording_enabled || 0,
    allow_internal_calls: settings.allow_internal_calls ?? 1,
    xml_curl_secret: '',
    esl_password: '',
  }
}

async function save() {
  if (!form.value.default_context?.trim()) {
    props.notify('Default context is required.', 'error')
    return
  }
  saving.value = true
  try {
    await api.saveSettings(form.value)
    props.notify('Settings saved.')
    form.value.xml_curl_secret = ''
    form.value.esl_password = ''
  } catch (error) {
    props.notify(error.message, 'error')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  hydrate()
  try {
    const rows = await api.list('FS Gateway', { order_by: 'gateway_name asc' })
    gateways.value = rows.map((row) => ({ label: row.gateway_name, value: row.name }))
  } catch {
    gateways.value = []
  }
})

watch(() => props.bootstrap?.settings, hydrate)
</script>

<template>
  <div class="fs-stack">
    <div class="fs-toolbar">
      <div class="fs-toolbar-title">
        <h2>Settings</h2>
        <span>The values shared by Frappe, FreeSWITCH and browser softphones</span>
      </div>
      <Button
        label="Save settings"
        icon="pi pi-check"
        :loading="saving"
        :disabled="!isAdmin"
        @click="save"
      />
    </div>

    <div class="fs-card">
      <div class="fs-form-grid">
        <div class="fs-field">
          <label for="set-did">Main inbound number (DID)</label>
          <InputText id="set-did" v-model="form.main_did" placeholder="1000" />
          <small>Local placeholder; replace with your carrier number.</small>
        </div>
        <div class="fs-field">
          <label for="set-context">Default context</label>
          <InputText id="set-context" v-model="form.default_context" placeholder="default" />
        </div>
        <div class="fs-field">
          <label for="set-sip">SIP domain</label>
          <InputText id="set-sip" v-model="form.sip_domain" placeholder="localhost" />
        </div>
        <div class="fs-field">
          <label for="set-ws">WebRTC WebSocket URL</label>
          <InputText id="set-ws" v-model="form.webrtc_url" placeholder="wss://voice.example.com" />
        </div>
        <div class="fs-field">
          <label for="set-ip">Public media IP</label>
          <InputText id="set-ip" v-model="form.public_ip" placeholder="203.0.113.10" />
        </div>
        <div class="fs-field">
          <label>Allow internal calls</label>
          <div style="padding-top: 5px">
            <Checkbox v-model="form.allow_internal_calls" :binary="true" inputId="set-internal" />
            <label for="set-internal" style="margin-left: 8px; font-weight: 400">
              Extension-to-extension dialing
            </label>
          </div>
        </div>
      </div>
    </div>

    <div class="fs-card">
      <div class="fs-toolbar-title" style="margin-bottom: 18px">
        <h2>Event Socket</h2>
        <span>Used by the console and the realtime listener</span>
      </div>
      <div class="fs-form-grid">
        <div class="fs-field">
          <label for="set-esl-host">ESL host</label>
          <InputText id="set-esl-host" v-model="form.esl_host" placeholder="freeswitch" />
        </div>
        <div class="fs-field">
          <label for="set-esl-port">ESL port</label>
          <InputNumber id="set-esl-port" v-model="form.esl_port" :min="1" :max="65535" />
        </div>
        <div class="fs-field fs-span-2">
          <label for="set-esl-pass">ESL password</label>
          <Password
            id="set-esl-pass"
            v-model="form.esl_password"
            :feedback="false"
            toggleMask
            placeholder="Leave blank to keep the current value"
          />
        </div>
      </div>
    </div>

    <div class="fs-card">
      <div class="fs-toolbar-title" style="margin-bottom: 18px">
        <h2>XML-curl</h2>
        <span>FreeSWITCH calls this endpoint for its directory, dialplan and call center config</span>
      </div>
      <div class="fs-settings-note" style="margin-bottom: 16px">
        Point all three bindings at
        <span class="fs-mono">https://&lt;your-site&gt;/api/method/fs_switch.api.xml_curl?secret=&lt;secret&gt;</span>.
        Keep the secret out of tickets and screenshots.
      </div>
      <div class="fs-form-grid">
        <div class="fs-field fs-span-2">
          <label for="set-xml-secret">XML-curl shared secret</label>
          <Password
            id="set-xml-secret"
            v-model="form.xml_curl_secret"
            :feedback="false"
            toggleMask
            placeholder="Leave blank to keep the current value"
          />
        </div>
      </div>
    </div>

    <div class="fs-card">
      <div class="fs-toolbar-title" style="margin-bottom: 18px">
        <h2>Media and outbound</h2>
        <span>Prompts, recordings and the default carrier gateway</span>
      </div>
      <div class="fs-form-grid">
        <div class="fs-field">
          <label for="set-ivr">Default IVR prompt</label>
          <InputText id="set-ivr" v-model="form.ivr_prompt_file" />
        </div>
        <div class="fs-field">
          <label for="set-moh">Queue hold music</label>
          <InputText id="set-moh" v-model="form.hold_music_file" />
        </div>
        <div class="fs-field">
          <label for="set-vm">Voicemail path</label>
          <InputText id="set-vm" v-model="form.voicemail_path" />
        </div>
        <div class="fs-field">
          <label for="set-rec">Recording path</label>
          <InputText id="set-rec" v-model="form.recording_path" />
        </div>
        <div class="fs-field">
          <label for="set-gw">Default gateway</label>
          <Select id="set-gw" v-model="form.default_gateway" :options="gateways" showClear placeholder="None" />
        </div>
        <div class="fs-field">
          <label for="set-cid">Outbound caller ID</label>
          <InputText id="set-cid" v-model="form.outbound_caller_id" />
        </div>
        <div class="fs-field">
          <label>Record calls</label>
          <div style="padding-top: 5px">
            <Checkbox v-model="form.recording_enabled" :binary="true" inputId="set-record" />
            <label for="set-record" style="margin-left: 8px; font-weight: 400">Enable recording</label>
          </div>
        </div>
      </div>
    </div>

    <div class="fs-settings-note">
      Some settings also exist in the FreeSWITCH config. On the Docker stack the entrypoint
      writes the matching values from <span class="fs-mono">.env</span>. On a manual install,
      keep this page and <span class="fs-mono">xml_curl.conf.xml</span> in sync.
    </div>
  </div>
</template>
