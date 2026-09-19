<script setup>
defineProps({
  label: String,
  value: [Number, String],
  sub: String,
  tone: { type: String, default: 'default' }, // default | error
  loading: Boolean,
})
</script>

<template>
  <div class="card stat" :class="`tone-${tone}`">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value tnum">
      <span v-if="loading" class="spinner" />
      <template v-else>
        <slot name="value">{{ value }}</slot>
      </template>
    </div>
    <div v-if="sub || $slots.sub" class="stat-sub">
      <slot name="sub">{{ sub }}</slot>
    </div>
  </div>
</template>

<style scoped>
.stat-label { color: var(--text-secondary); font-size: 13px; font-weight: 550; }
.stat-value {
  font-size: 34px;
  font-weight: 700;
  line-height: 1.15;
  margin-top: 8px;
  letter-spacing: -0.01em;
}
.stat-sub { margin-top: 8px; font-size: 12px; color: var(--text-muted); }
.tone-error .stat-value { color: var(--status-critical); }
</style>
