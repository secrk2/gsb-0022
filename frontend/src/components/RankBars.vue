<script setup>
// 服务/来源 Top 排行：纯 HTML/CSS 横向条，单度量单轴；
// 条上不堆数字（避免噪声），右侧用文字给出计数与错误数（文字不走系列色）。
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Array, required: true }, // [{key,label,count,errors,colorIndex}]
  loading: Boolean,
  emptyText: { type: String, default: '暂无数据' },
})

const max = computed(() => Math.max(1, ...props.rows.map((r) => r.count || 0)))
function widthOf(count) {
  return `${Math.max(count ? 2 : 0, Math.round((count / max.value) * 100))}%`
}
function fmt(n) {
  return (n ?? 0).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="rank">
    <div v-if="loading" class="rank-loading"><span class="spinner" /></div>
    <template v-else-if="rows.length">
      <div v-for="row in rows" :key="row.key" class="rank-row">
        <div class="rank-head">
          <span class="rank-label" :title="row.label">{{ row.label }}</span>
          <span class="rank-num tnum">
            {{ fmt(row.count) }}
            <span v-if="row.errors" class="rank-err">· 错误 {{ fmt(row.errors) }}</span>
          </span>
        </div>
        <div class="rank-track">
          <div
            class="rank-bar"
            :class="`bar-${row.colorIndex || 1}`"
            :style="{ width: widthOf(row.count) }"
          />
        </div>
      </div>
    </template>
    <div v-else class="empty">{{ emptyText }}</div>
  </div>
</template>

<style scoped>
.rank { display: flex; flex-direction: column; gap: 14px; }
.rank-loading { display: grid; place-items: center; padding: 30px 0; }
.rank-row { display: flex; flex-direction: column; gap: 5px; }
.rank-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.rank-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rank-num { font-size: 13px; color: var(--text-primary); font-weight: 600; flex: none; }
.rank-err { color: var(--status-critical); font-weight: 550; font-size: 12px; }
.rank-track {
  height: 10px;
  border-radius: 5px;
  background: var(--gridline);
  overflow: hidden;
}
.rank-bar { height: 100%; border-radius: 5px; min-width: 2px; transition: width .4s ease; }
.bar-1 { background: var(--series-1); }
.bar-2 { background: var(--series-2); }
.bar-3 { background: var(--series-3); }
</style>
