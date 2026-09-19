<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { getMeta, searchLogs } from '../api.js'
import {
  formatInTz, localInputToIso, nowLocalInput,
  shiftLocalInput, todayStartLocalInput, TZ_LABEL,
} from '../util/time.js'

const meta = ref(null)
const metaErr = ref('')

const filters = reactive({
  q: '',
  levels: [],
  services: [],
  sources: [],
  start: '',
  end: '',
  tz: 'Asia/Shanghai',
})

// 结果与分页（search_after 游标，绝不下发全量）
const items = ref([])
const cursor = ref(null)
const hasMore = ref(false)
const total = ref(null)
const pageSize = 30
const loading = ref(false)
const loadingMore = ref(false)
const err = ref('')
const searched = ref(false)
const expanded = reactive({}) // event_id -> bool

// ---- 元数据驱动的可选项 ----------------------------------------------------
const serviceOptions = computed(() => meta.value?.services || [])
const allLevels = computed(() => meta.value?.levels || [])
// 来源随所选服务联动；未选服务时列出全部
const sourceOptions = computed(() => {
  const svcs = meta.value?.services || []
  return svcs
    .filter((s) => !filters.services.length || filters.services.includes(s.service))
    .flatMap((s) => s.sources.map((src) => ({
      source: src.source,
      service: s.service,
      label: `${s.label} · ${src.label}`,
    })))
})
// 可选级别取所选服务来源的并集
const levelOptions = computed(() => {
  const svcs = meta.value?.services || []
  if (!svcs.length) return []
  const picked = svcs.filter((s) => filters.services.includes(s.service))
  const pool = picked.length ? picked : svcs
  const set = new Set()
  for (const s of pool) for (const src of s.sources) src.levels.forEach((l) => set.add(l))
  return [...set].sort()
})

// 时间输入解释时区：只选了一个服务时跟随该服务，否则用手选时区
const effectiveTz = computed(() => {
  // 时间快捷范围统一按页面上选的时区解释（未跟随所选服务的时区）
  return filters.tz
})

function toggle(arr, value) {
  const i = arr.indexOf(value)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(value)
}

function onServiceToggle() {
  // 已选来源若不再属于所选服务，剔除
  const valid = new Set(sourceOptions.value.map((s) => `${s.service}/${s.source}`))
  filters.sources = filters.sources.filter((x) => valid.has(x))
  const validLevels = new Set(levelOptions.value)
  filters.levels = filters.levels.filter((l) => validLevels.has(l))
}

function toggleSource(src) {
  const key = `${src.service}/${src.source}`
  toggle(filters.sources, key)
}

function isSourceChecked(src) {
  return filters.sources.includes(`${src.service}/${src.source}`)
}

// 后端 source 只收来源名；两个服务来源名不同（nginx-access / spring-app），
// 转成 CSV 时同时按所选服务约束即可。
function sourceNamesForQuery() {
  return filters.sources.map((x) => x.split('/')[1])
}

// ---- 时间快捷范围（墙上时间按 effectiveTz） --------------------------------
function applyPreset(kind) {
  const tz = effectiveTz.value
  const now = nowLocalInput(tz)
  if (kind === '15m') {
    filters.start = shiftLocalInput(now, tz, -15 * 60000); filters.end = now
  } else if (kind === '1h') {
    filters.start = shiftLocalInput(now, tz, -3600 * 1000); filters.end = now
  } else if (kind === '3h') {
    filters.start = shiftLocalInput(now, tz, -3 * 3600 * 1000); filters.end = now
  } else if (kind === 'today') {
    filters.start = todayStartLocalInput(tz); filters.end = now
  }
}

function buildParams(useCursor) {
  const p = { page_size: pageSize }
  if (filters.q.trim()) p.q = filters.q.trim()
  if (filters.levels.length) p.level = filters.levels.join(',')
  if (filters.services.length) p.service = filters.services.join(',')
  const srcNames = sourceNamesForQuery()
  if (srcNames.length) p.source = [...new Set(srcNames)].join(',')
  if (filters.start) p.start = localInputToIso(filters.start, effectiveTz.value)
  if (filters.end) p.end = localInputToIso(filters.end, effectiveTz.value)
  if (useCursor && cursor.value) p.cursor = cursor.value
  return p
}

async function doSearch() {
  loading.value = true
  err.value = ''
  searched.value = true
  try {
    const res = await searchLogs(buildParams(false))
    items.value = res.items
    cursor.value = res.next_cursor
    hasMore.value = res.has_more
    total.value = res.total
    Object.keys(expanded).forEach((k) => delete expanded[k])
  } catch (e) {
    err.value = e.message
    items.value = []
    total.value = null
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!hasMore.value || loadingMore.value) return
  loadingMore.value = true
  try {
    const res = await searchLogs(buildParams(true))
    // 游标翻页可能跨刷新出现重复 event_id，去重后追加
    const known = new Set(items.value.map((x) => x.event_id))
    items.value = items.value.concat(res.items.filter((x) => !known.has(x.event_id)))
    cursor.value = res.next_cursor
    hasMore.value = res.has_more
  } catch (e) {
    err.value = e.message
  } finally {
    loadingMore.value = false
  }
}

function resetFilters() {
  filters.q = ''
  filters.levels = []
  filters.services = []
  filters.sources = []
  filters.start = ''
  filters.end = ''
}

function rowTz(item) {
  return item.tz || effectiveTz.value
}
function svcLabel(key) {
  return serviceOptions.value.find((s) => s.service === key)?.label || key
}
function srcLabel(item) {
  const svc = serviceOptions.value.find((s) => s.service === item.service)
  return svc?.sources.find((x) => x.source === item.source)?.label || item.source
}
function isMultiline(item) {
  return item.is_exception || (item.message || '').includes('\n')
}
function preview(msg) {
  const line = (msg || '').split('\n')[0]
  return line.length > 220 ? `${line.slice(0, 220)}…` : line
}
function totalText() {
  if (!total.value) return ''
  const { value, relation } = total.value
  return relation === 'gte' ? `命中 ${value.toLocaleString('zh-CN')}+ 条` : `命中 ${value.toLocaleString('zh-CN')} 条`
}

function onEnterSearch(e) {
  if (e.key === 'Enter') doSearch()
}

onMounted(async () => {
  try {
    meta.value = await getMeta()
    // 打开即有数据：默认近 15 分钟并自动查询一次
    applyPreset('15m')
    await doSearch()
  } catch (e) {
    metaErr.value = e.message
  }
})
</script>

<template>
  <div>
    <header class="page-head">
      <div>
        <h1 class="page-title">日志检索</h1>
        <div class="page-sub">组合筛选 · 时间倒序 · 按每条日志所属服务的时区显示时间</div>
      </div>
    </header>

    <div v-if="metaErr" class="error-banner">元数据加载失败：{{ metaErr }}</div>

    <!-- 筛选区 -->
    <section class="card filter-card">
      <div class="filter-row">
        <div class="filter-grow">
          <label class="f-label">关键字</label>
          <input
            v-model="filters.q"
            class="input"
            type="search"
            placeholder="搜索日志内容、路径、异常类…（空格为“与”）"
            @keydown="onEnterSearch"
          />
        </div>
        <button class="btn btn-primary search-btn" :disabled="loading" @click="doSearch">
          {{ loading ? '查询中…' : '查询' }}
        </button>
        <button class="btn" @click="resetFilters">重置</button>
      </div>

      <div class="filter-block">
        <span class="f-label">服务</span>
        <div class="chips">
          <button
            v-for="s in serviceOptions"
            :key="s.service"
            class="chip"
            :class="{ active: filters.services.includes(s.service) }"
            @click="toggle(filters.services, s.service); onServiceToggle()"
          >
            <span class="chip-dot" :data-svc="s.service" />
            {{ s.label }}
            <small class="chip-tz">{{ TZ_LABEL[s.timezone] || s.timezone }}</small>
          </button>
        </div>
      </div>

      <div class="filter-block">
        <span class="f-label">来源</span>
        <div class="chips">
          <button
            v-for="src in sourceOptions"
            :key="`${src.service}/${src.source}`"
            class="chip"
            :class="{ active: isSourceChecked(src) }"
            @click="toggleSource(src)"
          >
            {{ src.label }}
          </button>
          <span v-if="!sourceOptions.length" class="muted">无可用来源</span>
        </div>
      </div>

      <div class="filter-block">
        <span class="f-label">级别</span>
        <div class="chips">
          <button
            v-for="lvl in levelOptions.length ? levelOptions : allLevels"
            :key="lvl"
            class="chip chip-level"
            :class="[`lvl-${lvl}`, { active: filters.levels.includes(lvl) }]"
            @click="toggle(filters.levels, lvl)"
          >
            {{ lvl }}
          </button>
        </div>
      </div>

      <div class="filter-block time-block">
        <span class="f-label">时间范围</span>
        <div class="time-inputs">
          <input v-model="filters.start" class="input" type="datetime-local" step="1" />
          <span class="muted">至</span>
          <input v-model="filters.end" class="input" type="datetime-local" step="1" />
          <span class="tz-hint">按 {{ TZ_LABEL[effectiveTz] || effectiveTz }} 解释</span>
        </div>
        <div class="chips presets">
          <button class="chip" @click="applyPreset('15m')">近15分钟</button>
          <button class="chip" @click="applyPreset('1h')">近1小时</button>
          <button class="chip" @click="applyPreset('3h')">近3小时</button>
          <button class="chip" @click="applyPreset('today')">今天</button>
        </div>
        <select v-if="filters.services.length !== 1" v-model="filters.tz" class="input tz-select">
          <option value="Asia/Shanghai">北京时间</option>
          <option value="Europe/London">伦敦时间</option>
          <option value="UTC">UTC</option>
        </select>
      </div>
    </section>

    <div v-if="err" class="error-banner">{{ err }}</div>

    <!-- 结果区 -->
    <section v-if="searched" class="result-meta">
      <span class="muted">{{ totalText() }}</span>
      <span class="muted">每页 {{ pageSize }} 条，时间倒序，向下游标翻页</span>
    </section>

    <section class="card result-card">
      <div v-if="loading" class="empty"><span class="spinner" /></div>
      <div v-else-if="!items.length" class="empty">
        {{ searched ? '没有符合条件的日志，试试放宽筛选或扩大时间范围' : '设置筛选条件后点击查询' }}
      </div>
      <ul v-else class="log-list">
        <li v-for="item in items" :key="item.event_id" class="log-row-wrap">
          <div
            class="log-row"
            :class="{ expandable: isMultiline(item), expanded: expanded[item.event_id] }"
            @click="isMultiline(item) && (expanded[item.event_id] = !expanded[item.event_id])"
          >
            <div class="col-time tnum">
              <div>{{ formatInTz(item['@timestamp'], rowTz(item)) }}</div>
              <div class="col-tz">{{ rowTz(item) }}</div>
            </div>
            <div class="col-tags">
              <span class="badge badge-svc">{{ svcLabel(item.service) }}</span>
              <span class="badge badge-src">{{ srcLabel(item) }}</span>
            </div>
            <div class="col-level">
              <span class="badge badge-level" :class="`lvl-${item.level}`">{{ item.level }}</span>
              <span v-if="item.status_code" class="http-status tnum" :class="`st-${Math.floor(item.status_code / 100)}`">
                {{ item.method }} {{ item.status_code }}
              </span>
            </div>
            <div class="col-msg">
              <pre v-if="expanded[item.event_id]" class="msg-full">{{ item.message }}</pre>
              <template v-else>
                <code class="msg-preview">{{ preview(item.message) }}</code>
                <span v-if="isMultiline(item)" class="stack-toggle">展开堆栈 ▾</span>
              </template>
              <div v-if="expanded[item.event_id]" class="msg-fields">
                <template v-if="item.service === 'nginx-demo'">
                  <span>路径 <code>{{ item.method }} {{ item.path }}</code></span>
                  <span>来源 IP <code>{{ item.remote_ip }}</code></span>
                  <span>字节 <code>{{ item.bytes_sent }}</code></span>
                </template>
                <template v-else>
                  <span v-if="item.logger">logger <code>{{ item.logger }}</code></span>
                  <span v-if="item.thread">线程 <code>{{ item.thread }}</code></span>
                  <span v-if="item.exception_class">异常 <code>{{ item.exception_class }}</code></span>
                </template>
                <span>采集延迟 <code>{{ item.latency_ms }} ms</code></span>
              </div>
            </div>
          </div>
        </li>
      </ul>

      <div v-if="items.length && hasMore" class="load-more">
        <button class="btn" :disabled="loadingMore" @click="loadMore">
          <span v-if="loadingMore" class="spinner btn-spin" />
          {{ loadingMore ? '加载中…' : `加载更多（已加载 ${items.length} 条）` }}
        </button>
      </div>
      <div v-else-if="items.length" class="muted no-more">— 已到末尾 —</div>
    </section>
  </div>
</template>

<style scoped>
.filter-card { display: flex; flex-direction: column; gap: 14px; margin-bottom: 14px; }
.filter-row { display: flex; gap: 10px; align-items: flex-end; }
.filter-grow { flex: 1; }
.filter-grow .input { width: 100%; }
.search-btn { min-width: 92px; }
.f-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.filter-block .f-label { display: inline-block; margin-bottom: 0; margin-right: 10px; min-width: 32px; }
.filter-block { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12.5px;
  cursor: pointer;
  font-family: inherit;
}
.chip:hover { background: var(--surface-hover); }
.chip.active {
  border-color: var(--series-1);
  background: var(--series-1-soft);
  color: var(--series-1-700);
  font-weight: 600;
}
.chip-tz { color: var(--text-muted); font-size: 10.5px; }
.chip-dot { width: 8px; height: 8px; border-radius: 50%; }
.chip-dot[data-svc="nginx-demo"] { background: var(--series-1); }
.chip-dot[data-svc="spring-demo"] { background: var(--series-2); }
.chip-level.lvl-ERROR.active { border-color: var(--level-ERROR); background: rgba(208,59,59,.12); color: var(--level-ERROR); }
.chip-level.lvl-WARN.active { border-color: var(--level-WARN); background: rgba(250,178,25,.14); color: var(--level-WARN); }
.chip-level.lvl-INFO.active { border-color: var(--level-INFO); background: var(--series-1-soft); color: var(--level-INFO); }
.chip-level.lvl-DEBUG.active { border-color: var(--level-DEBUG); background: var(--surface-hover); color: var(--text-secondary); }

.time-block { align-items: flex-end; }
.time-inputs { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tz-hint { font-size: 11.5px; color: var(--text-muted); }
.presets { margin-left: 0; }
.tz-select { padding: 6px 8px; font-size: 12px; }

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 4px 2px 10px;
  font-size: 12.5px;
}
.result-card { padding: 0; overflow: hidden; }
.log-list { list-style: none; margin: 0; padding: 0; }
.log-row-wrap + .log-row-wrap { border-top: 1px solid var(--gridline); }
.log-row {
  display: grid;
  grid-template-columns: 196px 172px 132px 1fr;
  gap: 12px;
  padding: 11px 16px;
  align-items: start;
  font-size: 13px;
}
.log-row.expandable { cursor: pointer; }
.log-row.expandable:hover { background: var(--surface-hover); }
.log-row.expanded { background: var(--surface-hover); }
.col-time { font-size: 12.5px; color: var(--text-secondary); line-height: 1.4; }
.col-tz { font-size: 10.5px; color: var(--text-muted); }
.col-tags { display: flex; flex-direction: column; gap: 4px; align-items: flex-start; }
.col-level { display: flex; flex-direction: column; gap: 5px; align-items: flex-start; }
.lvl-INFO { color: var(--level-INFO); }
.lvl-DEBUG { color: var(--level-DEBUG); }
.lvl-WARN { color: var(--level-WARN); }
.lvl-ERROR { color: var(--level-ERROR); }
.http-status { font-size: 11.5px; font-weight: 600; }
.st-4 { color: var(--level-WARN); }
.st-5 { color: var(--level-ERROR); }
.col-msg { min-width: 0; }
.msg-preview {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  color: var(--text-primary);
  word-break: break-all;
  white-space: normal;
}
.msg-full {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.55;
  margin: 0 0 8px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
.stack-toggle {
  margin-left: 8px;
  color: var(--series-1);
  font-size: 12px;
  white-space: nowrap;
}
.msg-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
  font-size: 11.5px;
  color: var(--text-muted);
}
.msg-fields code {
  font-family: ui-monospace, Menlo, Consolas, monospace;
  color: var(--text-secondary);
}
.load-more { display: grid; place-items: center; padding: 16px; border-top: 1px solid var(--gridline); }
.no-more { text-align: center; padding: 16px; font-size: 12px; }
.btn-spin { margin-right: 6px; vertical-align: -3px; }

@media (max-width: 1080px) {
  .log-row { grid-template-columns: 1fr; gap: 6px; }
  .col-tags, .col-level { flex-direction: row; }
}
</style>
