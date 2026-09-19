<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getDashboard } from '../api.js'
import { formatInTz } from '../util/time.js'
import StatCard from '../components/StatCard.vue'
import RankBars from '../components/RankBars.vue'
import PipelineStatus from '../components/PipelineStatus.vue'

const data = ref(null)
const loading = ref(true)
const error = ref('')
const lastUpdated = ref(null)
const AUTO_REFRESH_MS = 5000
let timer = null

// 服务按目录固定上色：nginx=blue(1)，spring=orange(2)
const SVC_COLOR = { 'nginx-demo': 1, 'spring-demo': 2 }

const serviceRows = computed(() =>
  (data.value?.top_services || []).map((s) => ({
    key: s.service,
    label: s.label,
    count: s.count,
    errors: s.errors,
    colorIndex: SVC_COLOR[s.service] || 1,
  })),
)
const sourceRows = computed(() =>
  (data.value?.top_sources || []).map((r) => ({
    key: `${r.service}/${r.source}`,
    label: r.label,
    count: r.count,
    errors: r.errors,
    colorIndex: SVC_COLOR[r.service] || 1,
  })),
)

const errorRatePct = computed(() => {
  const r = data.value?.totals?.error_rate
  return r === undefined ? '—' : `${(r * 100).toFixed(2)}%`
})

async function load(showSpinner = false) {
  if (showSpinner) loading.value = true
  error.value = ''
  try {
    data.value = await getDashboard()
    lastUpdated.value = new Date()
  } catch (e) {
    error.value = e.message || '控制台数据加载失败'
  } finally {
    loading.value = false
  }
}

function refreshLabel() {
  if (!lastUpdated.value) return ''
  return `更新于 ${formatInTz(lastUpdated.value.toISOString(), 'Asia/Shanghai', false)} · 每 ${AUTO_REFRESH_MS / 1000}s 自动刷新`
}

onMounted(() => {
  load(true)
  timer = setInterval(() => load(false), AUTO_REFRESH_MS)
})
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <div>
    <header class="page-head">
      <div>
        <h1 class="page-title">控制台</h1>
        <div class="page-sub">今日各服务日志概览与采集链路健康（按各服务所在时区统计当日）</div>
      </div>
      <div class="head-actions">
        <span class="muted update-hint">{{ refreshLabel() }}</span>
        <button class="btn" :disabled="loading" @click="load(true)">
          {{ loading ? '刷新中…' : '手动刷新' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <section class="kpi-grid">
      <StatCard
        label="今日日志总量"
        :value="(data?.totals.today_total ?? 0).toLocaleString('zh-CN')"
        :loading="loading && !data"
        sub="跨全部已接入服务"
      />
      <StatCard
        label="今日错误数"
        tone="error"
        :value="(data?.totals.today_errors ?? 0).toLocaleString('zh-CN')"
        :loading="loading && !data"
        :sub="`错误率 ${errorRatePct}`"
      />
      <StatCard label="接入服务数" :value="serviceRows.length" :loading="loading && !data" sub="持续写入中">
        <template #value>
          <span class="svc-pills">
            <span v-for="s in serviceRows" :key="s.key" class="svc-pill">{{ s.label }}</span>
          </span>
        </template>
      </StatCard>
      <StatCard label="队列积压" :loading="loading && !data">
        <template #value>
          {{ data?.pipeline.queue_len ?? '—' }}
        </template>
        <template #sub>
          <span :class="data?.pipeline.healthy ? 'ok-text' : 'bad-text'">
            {{ data?.pipeline.healthy ? '链路正常' : '链路异常，请查看下方状态' }}
          </span>
        </template>
      </StatCard>
    </section>

    <section class="grid-2">
      <div class="card">
        <div class="card-title">服务 Top 排行 <span class="muted font-normal">（今日事件量）</span></div>
        <RankBars :rows="serviceRows" :loading="loading && !data" empty-text="今天还没有日志" />
      </div>
      <div class="card">
        <div class="card-title">来源 Top 排行 <span class="muted font-normal">（今日事件量）</span></div>
        <RankBars :rows="sourceRows" :loading="loading && !data" empty-text="今天还没有日志" />
      </div>
    </section>

    <section class="card pipeline-card">
      <div class="card-title">
        采集延迟与断流
        <span
          class="pulse-dot"
          :class="data?.pipeline.healthy ? 'dot-good' : 'dot-crit'"
          :title="data?.pipeline.healthy ? '正常' : '异常'"
        />
      </div>
      <PipelineStatus :pipeline="data?.pipeline" :loading="loading && !data" />
    </section>
  </div>
</template>

<style scoped>
.head-actions { display: flex; align-items: center; gap: 12px; }
.update-hint { font-size: 12px; }
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.pipeline-card .card-title { justify-content: space-between; }
.pulse-dot {
  width: 11px; height: 11px; border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 transparent; }
  50% { box-shadow: 0 0 0 5px rgba(208, 59, 59, 0.08); }
}
.svc-pills { display: flex; flex-wrap: wrap; gap: 6px; font-size: 13px; font-weight: 600; }
.svc-pill {
  background: var(--series-1-soft);
  color: var(--series-1-700);
  border-radius: 7px;
  padding: 3px 10px;
}
.font-normal { font-weight: 400; font-size: 12px; }
.ok-text { color: var(--status-good-text); }
.bad-text { color: var(--status-critical); }

@media (max-width: 1080px) {
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
