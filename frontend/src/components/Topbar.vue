<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'
import Icon from './Icon.vue'

const app = useAppStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const clock = ref('--:--:--')
const searchInput = ref<HTMLInputElement | null>(null)
let clockTimer: number | null = null

const title = computed(() => String(route.meta.title || '监测总览'))
const crumb = computed(() => String(route.meta.crumb || '监测中心 / 监测总览'))
const feishuReady = computed(() => app.meta?.feishu.configured ?? false)

function tick() {
  const date = new Date()
  clock.value = [date.getHours(), date.getMinutes(), date.getSeconds()]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')
}

function handleKey(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    if (route.path !== '/overview') {
      void router.push('/overview')
      window.setTimeout(() => searchInput.value?.focus(), 80)
    } else {
      searchInput.value?.focus()
    }
  }
}

function submitSearch() {
  if (route.path !== '/overview') {
    void router.push('/overview')
  }
}

onMounted(() => {
  tick()
  clockTimer = window.setInterval(tick, 1000)
  window.addEventListener('keydown', handleKey)
})

onBeforeUnmount(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  window.removeEventListener('keydown', handleKey)
})
</script>

<template>
  <header class="topbar">
    <button class="hamburger" aria-label="打开导航" @click="ui.toggleSidebar()">
      <Icon name="menu" />
    </button>
    <div class="page-title">
      <h1>{{ title }}</h1>
      <p>{{ crumb }}</p>
    </div>
    <div class="topbar-right">
      <label class="search">
        <Icon name="search" />
        <input
          ref="searchInput"
          v-model="app.searchQuery"
          type="text"
          placeholder="搜索电机 / 编号 / 位置…"
          autocomplete="off"
          @keydown.enter="submitSearch"
        />
        <kbd>Ctrl K</kbd>
      </label>
      <div class="pill hide-m">
        <span class="dot live" />
        <span class="num">{{ clock }}</span>
        <span style="color: var(--faint)">采集周期 {{ app.intervalMinutes }} 分钟</span>
      </div>
      <div class="pill hide-m" :title="feishuReady ? '飞书机器人已配置' : '未配置飞书 Webhook'">
        <span
          class="dot"
          :style="{
            background: feishuReady ? 'var(--green)' : 'var(--faint)',
            boxShadow: feishuReady ? '0 0 8px rgba(46,211,163,.9)' : 'none',
          }"
        />
        {{ feishuReady ? '飞书机器人在线' : '飞书未配置' }}
      </div>
      <button class="icon-btn" aria-label="查看告警" @click="router.push('/alarms')">
        <Icon name="bell" />
        <span v-if="app.alarmCount > 0" class="badge">{{ app.alarmCount }}</span>
      </button>
      <div class="avatar" :title="`${app.user.name} · ${app.user.role}`">
        {{ app.user.name.slice(0, 1) }}
      </div>
    </div>
  </header>
</template>
