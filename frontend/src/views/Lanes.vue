<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
const drafts = ref<Record<number, string>>({})
const errors = ref<Record<number, string>>({})

async function loadRefill() {
  refill.value = await api('/refills/run?location_id=1', { method: 'POST' })
}
async function saveDays(r: any) {
  const raw = (drafts.value[r.id] ?? '').trim()
  errors.value[r.id] = ''
  const days = raw === '' ? null : Number(raw)
  if (days !== null && (!Number.isInteger(days) || days <= 0)) {
    errors.value[r.id] = '天数需为正整数；留空不封顶'
    return
  }
  try {
    await api(`/lanes/${r.id}`, { method: 'PUT', body: JSON.stringify({ sellable_days: days }) })
    rows.value = await api('/lanes')
    await loadRefill()
  } catch (e: any) {
    // 天数 ≤0 被后端拒绝，三页保持改前
    let msg = '保存失败'
    try { msg = JSON.parse(e.message).detail ?? msg } catch { msg = e.message || msg }
    errors.value[r.id] = msg
  }
}
onMounted(async () => {
  rows.value = await api('/lanes')
  for (const r of rows.value) drafts.value[r.id] = r.sellable_days == null ? '' : String(r.sellable_days)
  await loadRefill()
})
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 可登记临期可售天数（留空=只按缺口补）· 右侧补货小票</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot">
        <div class="vf-slot-no">{{ r.slot_no }}</div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }}</div>
        <div class="vf-slot-meta" style="font-size:0.66rem">
          日均 {{ r.daily_avg.toFixed(2) }}
          <template v-if="r.sellable_days != null"> · 上限 {{ r.refill_cap }}</template>
        </div>
        <div style="display:flex;align-items:center;gap:0.3rem;margin-top:0.25rem">
          <input
            class="vf-input"
            type="number"
            min="1"
            placeholder="留空"
            v-model="drafts[r.id]"
            @keyup.enter="saveDays(r)"
          />
          <button class="vf-mini-btn" @click="saveDays(r)">保存天数</button>
        </div>
        <span v-if="errors[r.id]" class="vf-err">{{ errors[r.id] }}</span>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
