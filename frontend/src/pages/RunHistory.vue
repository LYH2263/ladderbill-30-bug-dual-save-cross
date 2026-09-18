<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const items = ref([])
onMounted(async () => { items.value = (await getJSON('/api/history')).items })
const summary = (row) => {
  try { const r = JSON.parse(row.result_json); return r.total != null ? `¥${r.total}` : `平${r.plain_total}/尖${r.peak_total}` } catch { return '—' }
}
const sideTag = (row) => {
  try { const s = JSON.parse(row.input_json).side; return s === 'left' ? '左' : s === 'right' ? '右' : '' } catch { return '' }
}
</script>
<template>
  <div class="page">
    <h1>测算记录</h1>
    <table>
      <thead><tr><th>#</th><th>类型</th><th>户号</th><th>结果摘要</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="h in items" :key="h.id">
          <td>{{ h.id }}</td><td>{{ h.kind }}<span v-if="sideTag(h)" class="side-tag">{{ sideTag(h) }}</span></td><td>{{ h.account_id ?? '—' }}</td>
          <td>{{ summary(h) }}</td><td class="muted">{{ h.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<style scoped>
.side-tag { font-size: 0.75rem; color: var(--accent); border: 1px solid var(--accent); border-radius: 4px; padding: 0 0.25rem; margin-left: 0.35rem; }
</style>
