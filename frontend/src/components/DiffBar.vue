<script setup>
import { computed } from 'vue'
const props = defineProps({
  leftLabel: { type: String, default: '左侧' },
  rightLabel: { type: String, default: '右侧' },
  leftTotal: { type: Number, required: true },
  rightTotal: { type: Number, required: true },
  delta: { type: Number, required: true },
})
const max = computed(() => Math.max(props.leftTotal, props.rightTotal, 1e-9))
const leftPct = computed(() => (props.leftTotal / max.value) * 100)
const rightPct = computed(() => (props.rightTotal / max.value) * 100)
const verdict = computed(() => {
  if (Math.abs(props.delta) < 0.005) return '两侧持平'
  return props.delta > 0 ? `右侧高 ¥${props.delta.toFixed(2)}` : `左侧高 ¥${(-props.delta).toFixed(2)}`
})
</script>
<template>
  <div class="diffbar">
    <div class="row">
      <span class="lab">{{ leftLabel }}</span>
      <div class="track"><div class="fill left" :style="{ width: leftPct + '%' }"></div></div>
      <span class="val">¥{{ leftTotal.toFixed(2) }}</span>
    </div>
    <div class="row">
      <span class="lab">{{ rightLabel }}</span>
      <div class="track"><div class="fill right" :style="{ width: rightPct + '%' }"></div></div>
      <span class="val">¥{{ rightTotal.toFixed(2) }}</span>
    </div>
    <p class="verdict">差值（右 − 左）¥{{ delta.toFixed(2) }} · {{ verdict }}</p>
  </div>
</template>
<style scoped>
.diffbar { display: flex; flex-direction: column; gap: 0.5rem; }
.row { display: grid; grid-template-columns: 4rem 1fr 6rem; align-items: center; gap: 0.6rem; }
.lab { color: var(--muted); font-size: 0.9rem; }
.track { background: #0d1612; border-radius: 6px; height: 14px; overflow: hidden; }
.fill { height: 100%; border-radius: 6px; transition: width 0.25s ease; }
.fill.left { background: var(--accent); }
.fill.right { background: #e0a23c; }
.val { text-align: right; font-variant-numeric: tabular-nums; }
.verdict { margin: 0.25rem 0 0; font-weight: 600; }
</style>
