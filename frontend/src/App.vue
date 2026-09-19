<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">观</span>
        <div class="brand-text">
          <strong>观澜</strong>
          <small>日志分析系统</small>
        </div>
      </div>
      <nav class="nav">
        <RouterLink to="/dashboard" class="nav-item">
          <span class="nav-ico">▦</span> 控制台
        </RouterLink>
        <RouterLink to="/search" class="nav-item">
          <span class="nav-ico">⌕</span> 日志检索
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        Filebeat → Redis → ES
      </div>
    </aside>
    <main class="content">
      <RouterView v-slot="{ Component }">
        <component :is="Component" />
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 224px 1fr;
  min-height: 100vh;
}
.sidebar {
  background: var(--surface-2);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 22px;
}
.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--series-1), var(--series-1-700));
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  display: grid;
  place-items: center;
}
.brand-text { display: flex; flex-direction: column; line-height: 1.25; }
.brand-text strong { font-size: 17px; }
.brand-text small { color: var(--text-muted); font-size: 12px; }
.nav { display: flex; flex-direction: column; gap: 4px; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 9px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}
.nav-item .nav-ico { font-size: 15px; opacity: .8; }
.nav-item:hover { background: var(--surface-hover); color: var(--text-primary); }
.nav-item.router-link-active {
  background: var(--accent-soft);
  color: var(--series-1-700);
}
.sidebar-foot {
  margin-top: auto;
  font-size: 11px;
  color: var(--text-muted);
  padding: 8px 10px;
  letter-spacing: .02em;
}
.content { padding: 26px 30px 40px; min-width: 0; }

@media (max-width: 720px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { position: static; height: auto; flex-direction: row; align-items: center; }
  .brand { padding: 0 10px 0 0; }
  .nav { flex-direction: row; }
  .sidebar-foot { display: none; }
  .content { padding: 18px 14px 30px; }
}
</style>
