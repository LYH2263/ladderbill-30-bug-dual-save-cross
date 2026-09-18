<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
import TierLadder from '../components/TierLadder.vue'
import SegmentTable from '../components/SegmentTable.vue'
import DiffBar from '../components/DiffBar.vue'

const accounts = ref([])
const left = ref({ account_id: null, kwh: 220, peak: false })
const right = ref({ account_id: null, kwh: 400, peak: true })
const persist = ref(false)
const result = ref(null)
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  accounts.value = (await getJSON('/api/accounts')).items
  if (accounts.value[0]) left.value.account_id = accounts.value[0].id
  right.value.account_id = (accounts.value[1] || accounts.value[0])?.id ?? null
})

const sideTag = (s) => (s === 'left' ? '左侧' : s === 'right' ? '右侧' : '')
const fmtError = (raw) => {
  try {
    const d = JSON.parse(raw)?.detail
    if (d && !Array.isArray(d) && d.side) return `${sideTag(d.side)}：${d.message || d.error}`
    if (Array.isArray(d) && d[0]) return `${sideTag(d[0].loc?.[1])}：${d[0].msg}`
  } catch { /* 非 JSON 错误体，原样展示 */ }
  return raw
}

const run = async () => {
  error.value = ''
  result.value = null
  busy.value = true
  try {
    result.value = await postJSON('/api/bill/pair', {
      left: { account_id: left.value.account_id, kwh: left.value.kwh, peak: left.value.peak },
      right: { account_id: right.value.account_id, kwh: right.value.kwh, peak: right.value.peak },
      persist: persist.value,
    })
  } catch (e) {
    error.value = fmtError(e.message)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div class="page work">
    <h1>测算工作台 · 双户并列试算</h1>
    <div class="sides">
      <div class="panel side">
        <h3>左侧</h3>
        <label>户号
          <select v-model.number="left.account_id">
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}（#{{ a.id }}）</option>
          </select>
        </label>
        <label>电量(kWh) <input type="number" v-model.number="left.kwh" min="0" step="1" /></label>
        <label><input type="checkbox" v-model="left.peak" /> 尖峰系数</label>
      </div>
      <div class="panel side">
        <h3>右侧</h3>
        <label>户号
          <select v-model.number="right.account_id">
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}（#{{ a.id }}）</option>
          </select>
        </label>
        <label>电量(kWh) <input type="number" v-model.number="right.kwh" min="0" step="1" /></label>
        <label><input type="checkbox" v-model="right.peak" /> 尖峰系数</label>
      </div>
    </div>
    <div class="panel form-row">
      <label><input type="checkbox" v-model="persist" /> 写入测算记录（persist）</label>
      <button :disabled="busy" @click="run">{{ busy ? '试算中…' : '并列试算' }}</button>
      <span class="muted" v-if="!persist">默认只试算，不写运行记录</span>
    </div>
    <p v-if="error" class="panel error">{{ error }}</p>
    <template v-if="result">
      <div class="panel">
        <DiffBar
          :left-label="`左侧 · ${result.left.account_name}`"
          :right-label="`右侧 · ${result.right.account_name}`"
          :left-total="result.left.total"
          :right-total="result.right.total"
          :delta="result.delta"
        />
        <p v-if="result.left.run_id || result.right.run_id" class="muted saved">
          已写入两条记录：左侧 #{{ result.left.run_id }} · 右侧 #{{ result.right.run_id }}
          — <router-link to="/history">查看测算记录</router-link>
        </p>
      </div>
      <div class="sides">
        <div class="panel" v-for="side in ['left', 'right']" :key="side">
          <h3>{{ side === 'left' ? '左侧' : '右侧' }} · {{ result[side].account_name }}
            <span v-if="result[side].peak" class="tag">尖峰 ×{{ result[side].peak_factor }}</span>
          </h3>
          <p>合计 <span class="hero-num total">¥{{ result[side].total }}</span>
            <span v-if="result[side].run_id" class="muted">记录#{{ result[side].run_id }}</span>
          </p>
          <TierLadder :segments="result[side].segments" />
          <SegmentTable :rows="result[side].segments" />
        </div>
      </div>
    </template>
  </div>
</template>
<style scoped>
.sides { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.side h3 { margin-top: 0; }
.side label { display: block; margin-bottom: 0.6rem; }
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }
input[type=number] { width: 6rem; margin-left: 0.35rem; }
select { background: #0d1612; border: 1px solid var(--muted); color: var(--text); padding: 0.35rem 0.5rem; border-radius: 6px; margin-left: 0.35rem; }
.error { border: 1px solid #d95555; color: #f0a8a8; }
.total { font-size: 2rem; }
.tag { font-size: 0.8rem; color: #e0a23c; border: 1px solid #e0a23c; border-radius: 6px; padding: 0.1rem 0.4rem; margin-left: 0.4rem; }
.saved { margin-bottom: 0; }
@media (max-width: 800px) { .sides { grid-template-columns: 1fr; } }
</style>
