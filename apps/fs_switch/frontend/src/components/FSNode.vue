<script setup>
import { Handle, Position } from '@vue-flow/core'

defineProps({
  data: { type: Object, required: true },
  selected: Boolean,
})
</script>

<template>
  <div class="fs-flow-node" :style="selected ? { borderColor: '#0f766e' } : {}">
    <Handle type="target" :position="Position.Left" />
    <div class="fs-flow-node-title">{{ data.label || 'Unnamed step' }}</div>
    <span class="fs-flow-node-app">{{ data.application || 'no application' }}</span>
    <div class="fs-flow-node-data">{{ data.data || 'no arguments' }}</div>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
