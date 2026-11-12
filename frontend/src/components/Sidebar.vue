<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'
import Icon from './Icon.vue'

const app = useAppStore()
const ui = useUiStore()

const pilotScopeCount = computed(() => {
  const scope = app.pilot?.scope || ''
  return scope.split('/').filter((item) => item.trim()).length || 0
})

const navItems = [
  { to: '/overview', label: '监测总览', icon: 'grid', group: '监测中心' },
  { to: '/analysis', label: '对比分析', icon: 'compare', group: '监测中心' },
  { to: '/alarms', label: '告警中心', icon: 'bell', group: '监测中心' },
  { to: '/topology', label: '设备与链路', icon: 'radio', group: '系统管理' },
  { to: '/settings', label: '阈值与通知', icon: 'sliders', group: '系统管理' },
]
</script>

<template>
  <aside class="sidebar" :class="{ open: ui.sidebarOpen }">
    <div class="brand">
      <div class="brand-mark">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="#04121C"
          stroke-width="2.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M2.5 12h4l2.5-7 4 14 3-10 1.8 3h3.7" />
        </svg>
      </div>
      <div>
        <div class="brand-name">Motor<em>Pulse</em></div>
        <div class="brand-sub">大电机风险监测平台</div>
      </div>
    </div>

    <nav class="nav">
      <template v-for="(group, groupIndex) in ['监测中心', '系统管理']" :key="group">
        <div v-if="groupIndex > 0" style="height: 6px" />
        <div class="nav-group">{{ group }}</div>
        <RouterLink
          v-for="item in navItems.filter((entry) => entry.group === group)"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          active-class="active"
          @click="ui.closeSidebar()"
        >
          <span class="ic"><Icon :name="item.icon" /></span>
          <span>{{ item.label }}</span>
          <span v-if="item.to === '/alarms' && app.alarmCount > 0" class="nav-badge">{{
            app.alarmCount
          }}</span>
        </RouterLink>
      </template>
    </nav>

    <div class="side-foot">
      <div v-if="app.pilot" class="pilot-card">
        <h5>
          试点运行
          <span>第 {{ app.pilot.current_day }} / {{ app.pilot.days }} 天</span>
        </h5>
        <div class="progress"><i :style="{ width: `${app.pilot.progress_pct}%` }" /></div>
        <p>{{ pilotScopeCount }} 台关键电机 · 验收倒计时 {{ app.pilot.remaining_days }} 天</p>
      </div>
      <div class="user-card">
        <div class="avatar">{{ app.user.name.slice(0, 1) }}</div>
        <div>
          <b>{{ app.user.name }}</b>
          <span>{{ app.user.role }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>
