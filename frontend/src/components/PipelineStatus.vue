<script setup>
// 采集链路健康：每服务一个状态行，断流/延迟用「圆点 + 文字」双通道表达，
// 不仅靠颜色（dataviz 状态色规则）。
import { computed } from 'vue'
import { formatInTz, formatRelative } from '../util/time.js'

const props = defineProps({
  pipeline: { type: Object, required: false },
  loading: Boolean,
})

const svcRows = computed(() => {
  if (!props.pipeline) return []
  return Object.entries(props.pipeline.services).map(([key, s]) => ({
    key,
    ...s,
    status: s.stale ? 'stale' : s.latency_alert ? 'slow' : 'ok',
  }))
})

function latencyText(ms) {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(2)} s`
}
</script>

<template>
  <div class="pipe">
    <div v-if="loading" class="empty"><span class="spinner" /></div>
    <template v-else-if="svcRows.length">
      <!-- 总状态条 -->
      <div
        class="overall"
        :class="pipeline.healthy ? 'is-ok' : 'is-bad'"
        role="status"
      >
        <span class="dot" :class="pipeline.healthy ? 'dot-good' : 'dot-crit'" />
        <strong>{{ pipeline.healthy ? '采集正常' : '采集异常' }}</strong>
        <span class="overall-detail">
          <template v-if="pipeline.redis_ok">
            队列积压 {{ pipeline.queue_len ?? '—' }} 条
          </template>
          <template v-else>Redis 不可用</template>
        </span>
      </div>

      <div v-for="s in svcRows" :key="s.key" class="svc">
        <div class="svc-top">
          <span class="dot" :class="{
            'dot-good': s.status === 'ok',
            'dot-warn': s.status === 'slow',
            'dot-crit': s.status === 'stale',
          }" />
          <span class="svc-name">{{ s.label }}</span>
          <span class="svc-tz">{{ s.timezone }}</span>
          <span class="svc-state" :class="`state-${s.status}`">
            <template v-if="s.status === 'ok'">正常</template>
            <template v-else-if="s.status === 'slow'">延迟偏高</template>
            <template v-else>断流</template>
          </span>
        </div>
        <div class="svc-meta">
          <span>最新事件：
            <template v-if="s.last_event_at">
              {{ formatInTz(s.last_event_at, s.timezone) }}
              <em class="muted">（{{ formatRelative(s.last_event_at) }}）</em>
            </template>
            <template v-else><em>从未收到</em></template>
          </span>
          <span>断流阈值 {{ pipeline.stale_gap_seconds }}s ·
            当前间隔 {{ s.gap_seconds === null ? '—' : `${s.gap_seconds}s` }}</span>
          <span>最近延迟
            <strong :class="{ 'text-warn': s.latency_alert }">{{ latencyText(s.latest_latency_ms) }}</strong>
            <template v-if="s.avg_latency_ms !== null">（均值 {{ latencyText(s.avg_latency_ms) }}）</template>
          </span>
        </div>
      </div>
    </template>
    <div v-else class="empty">暂无链路数据</div>
  </div>
</template>

<style scoped>
.overall {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 12px;
  border-radius: 9px;
  margin-bottom: 14px;
  font-size: 13px;
}
.overall.is-ok { background: rgba(12, 163, 12, 0.10); }
.overall.is-bad { background: var(--status-critical-soft); }
.overall-detail { color: var(--text-secondary); font-weight: 400; margin-left: 2px; }
.svc { padding: 11px 0; border-top: 1px solid var(--gridline); }
.svc:first-of-type { border-top: none; }
.svc-top { display: flex; align-items: center; gap: 9px; margin-bottom: 5px; }
.svc-name { font-weight: 600; font-size: 13px; }
.svc-tz { color: var(--text-muted); font-size: 11px; }
.svc-state {
  margin-left: auto;
  font-size: 12px;
  font-weight: 650;
  padding: 1px 9px;
  border-radius: 999px;
}
.state-ok { color: var(--status-good-text); background: rgba(12, 163, 12, 0.10); }
.state-slow { color: var(--status-warn); background: rgba(250, 178, 25, 0.14); }
.state-stale { color: var(--status-critical); background: var(--status-critical-soft); }
.svc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 22px;
  padding-left: 18px;
  font-size: 12px;
  color: var(--text-secondary);
}
.svc-meta em { font-style: normal; }
.text-warn { color: var(--status-warn); }
</style>
