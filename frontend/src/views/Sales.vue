<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const lanes = ref<any[]>([])
const fmtAvg = (v: number) => Number(v).toFixed(2)
onMounted(async () => {
  const data = await api('/sales')
  rows.value = data.rows
  lanes.value = data.lanes
})
</script>
<template>
  <h1>销量</h1>
  <p class="sub">近七日日均销量与可补上限（日均 = 近七日合计 ÷ 7，上限 = min(缺口, ⌊日均 × 可售天数⌋)）</p>
  <div class="card">
    <table>
      <thead>
        <tr><th>货道</th><th>商品</th><th>近7日销量</th><th>日均</th><th>可售天数</th><th>缺口</th><th>可补上限</th></tr>
      </thead>
      <tbody>
        <tr v-for="l in lanes" :key="l.lane_id">
          <td>{{ l.slot_no }}</td>
          <td>{{ l.sku_name }}</td>
          <td>{{ l.sold_7d }}</td>
          <td>{{ fmtAvg(l.daily_avg) }}</td>
          <td>{{ l.sellable_days == null ? '未启用' : l.sellable_days }}</td>
          <td>{{ l.gap }}</td>
          <td>
            <strong :style="{ color: l.sellable_days != null && l.refill_cap < l.gap ? 'var(--vf-amber)' : 'var(--vf-led)' }">
              {{ l.refill_cap }}
            </strong>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="sub">近期出货记录</p>
  <div class="card">
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>数量</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)"><td>{{ r.slot_no }}</td><td>{{ r.sku_name }}</td><td>{{ r.qty }}</td><td>{{ r.sold_at }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
