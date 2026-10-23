<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

import {
  nodeAccent,
  nodeIcon,
  nodeSummary,
  outputLabel,
  outputsForNode,
} from '../flow'

const props = defineProps({
  data: { type: Object, required: true },
  selected: Boolean,
})

const config = computed(() => props.data.config || {})
const outputs = computed(() => outputsForNode(props.data.nodeType, config.value))
const label = computed(() => props.data.label || props.data.nodeType || 'Unnamed step')
const summary = computed(() => nodeSummary(props.data.nodeType, config.value))
const accent = computed(() => nodeAccent(props.data.category))
const icon = computed(() => nodeIcon(props.data.nodeType))
</script>

<template>
  <div
    class="fs-semantic-node"
    :class="{ 'is-selected': selected, 'is-simulated': data.isSimulated }"
    :style="{ '--fs-node-accent': accent }"
  >
    <Handle type="target" :position="Position.Left" class="fs-semantic-handle" />

    <div class="fs-semantic-node-head">
      <span class="fs-semantic-node-icon"><i :class="icon" /></span>
      <span class="fs-semantic-node-heading">
        <span class="fs-semantic-node-title">{{ label }}</span>
        <span class="fs-semantic-node-type">{{ data.nodeType }}</span>
      </span>
      <span v-if="data.isEntry" class="fs-entry-badge">Entry</span>
    </div>

    <div class="fs-semantic-node-summary">{{ summary }}</div>

    <div v-if="outputs.length" class="fs-semantic-node-outputs">
      <div v-for="handle in outputs" :key="handle" class="fs-semantic-port-row">
        <span class="fs-semantic-port-label">{{ outputLabel(handle) }}</span>
        <Handle
          type="source"
          :id="handle"
          :position="Position.Right"
          class="fs-semantic-handle"
        />
      </div>
    </div>
    <div v-else class="fs-semantic-terminal">Terminal step</div>
  </div>
</template>
