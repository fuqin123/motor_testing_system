<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type { Alarm, AlarmList } from '@/api/types'
import AlarmDetailDrawer from '@/components/AlarmDetailDrawer.vue'
import BaseModal from '@/components/BaseModal.vue'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useUiStore } from '@/stores/ui'
import { downloadBlob } from '@/utils/download'
import {
  ALARM_STATUS_TEXT,
  LEVEL_TEXT,
  NOTIFICATION_TEXT,
  fmt,
  mmddhhmm,
  timeAgo,
} from '@/utils/format'

const ui = useUiStore()

const data = ref<AlarmList | null>(null)
const loading = ref(false)
const level = ref('all')
const status = ref('all')
const query = ref('')
const page = ref(1)
const pageSize = 50
const selected = ref<Set<number>>(new Set())
const sortKey = ref<'time' | 'level'>('time')
const sortDir = ref<1 | -1>(-1)
const drawerOpen = ref(false)
const activeAlarmId = ref<number | null>(null)
const deleteTarget = ref<Alarm | null>(null)
const deleting = ref(false)
let searchTimer: number | null = null
let refreshTimer: number | null = null

const levelFilters = [
  { key: 'all', label: '全部级别' },
  { key: 'crit', label: '严重' },
  { key: 'warn', label: '警告' },
  { key: 'info', label: '提示' },
]
const statusFilters = [
  { key: 'all', label: '全部状态' },
  { key: 'open', label: '未处理' },
  { key: 'ack', label: '处理中' },
  { key: 'closed', label: '已闭环' },
]

const sortedItems = computed(() => {
  const items = [...(data.value?.items || [])]
  const levelRank: Record<string, number> = { crit: 3, warn: 2, info: 1 }
  items.sort((a, b) => {
    if (sortKey.value === 'level') {
      return (levelRank[a.level] - levelRank[b.level]) * sortDir.value
    }
    return (new Date(a.triggered_at).getTime() - new Date(b.triggered_at).getTime()) * sortDir.value
  })
  return items
})
const totalPages = computed(() => Math.max(1, Math.ceil((data.value?.total || 0) / pageSize)))
const allChecked = computed(
  () =>
    sortedItems.value.length > 0 &&
    sortedItems.value.every((alarm) => selected.value.has(alarm.id)),
)

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    data.value = await api.alarms({
      level: level.value,
      status: status.value,
      q: query.value.trim(),
      page: page.value,
      page_size: pageSize,
    })
  } catch (error) {
    ui.notify('err', '告警列表加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  selected.value = new Set()
  void load()
}

function onSearch() {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(applyFilters, 320)
}

function setLevel(value: string) {
  level.value = value
  applyFilters()
}

function setStatus(value: string) {
  status.value = value
  applyFilters()
}

function sortBy(key: 'time' | 'level') {
  if (sortKey.value === key) sortDir.value = sortDir.value === 1 ? -1 : 1
  else {
    sortKey.value = key
    sortDir.value = -1
  }
}

function toggleAll() {
  if (allChecked.value) {
    selected.value = new Set()
  } else {
    selected.value = new Set(sortedItems.value.map((alarm) => alarm.id))
  }
}

function clearSelection() {
  selected.value = new Set()
}

function toggleOne(id: number) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function openAlarm(id: number) {
  activeAlarmId.value = id
  drawerOpen.value = true
}

async function bulkClose() {
  if (!selected.value.size) return
  try {
    const result = await api.bulkClose([...selected.value], '批量闭环：已现场确认处理。')
    ui.notify('ok', `已批量闭环 ${result.closed} 条告警`, '处理结果已写入审计记录')
    selected.value = new Set()
    await load()
  } catch (error) {
    ui.notify('err', '批量闭环失败', error instanceof Error ? error.message : '')
  }
}

function askDelete(alarm: Alarm) {
  deleteTarget.value = alarm
}

async function confirmDelete() {
  if (!deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    await api.deleteAlarm(deleteTarget.value.id)
    ui.notify('ok', `${deleteTarget.value.code} 已删除`, '仅删除已闭环的历史记录')
    deleteTarget.value = null
    selected.value = new Set()
    await load()
  } catch (error) {
    ui.notify('err', '删除失败', error instanceof Error ? error.message : '')
  } finally {
    deleting.value = false
  }
}

async function exportCsv() {
  try {
    const blob = await api.alarmExport({
      level: level.value,
      status: status.value,
      q: query.value.trim(),
    })
    const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    downloadBlob(blob, `告警记录_${stamp}.csv`)
    ui.notify('ok', '已导出告警记录', 'CSV 含 UTF-8 BOM，Excel 直接打开不乱码')
  } catch (error) {
    ui.notify('err', '导出失败', error instanceof Error ? error.message : '')
  }
}

async function onUpdated() {
  await load(true)
}

function changePage(next: number) {
  page.value = next
  selected.value = new Set()
  void load()
}

onMounted(() => {
  void load()
  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void load(true)
  }, 30_000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (searchTimer) window.clearTimeout(searchTimer)
})
</script>

<template>
  <section class="view" id="view-alarms">
    <div v-if="data" class="alarm-stats">
      <div class="card alarm-stat">
        <div class="kpi-ic" style="--accent: #ff8296; width: 38px; height: 38px">
          <Icon name="alert" :size="19" />
        </div>
        <div>
          <div class="v num" style="color: #ff8296">{{ data.stats.open }}</div>
          <div class="l">未处理</div>
        </div>
      </div>
      <div class="card alarm-stat">
        <div class="kpi-ic" style="--accent: #ffc65c; width: 38px; height: 38px">
          <Icon name="bell" :size="19" />
        </div>
        <div>
          <div class="v num" style="color: #ffc65c">{{ data.stats.today }}</div>
          <div class="l">24h 新增</div>
        </div>
      </div>
      <div class="card alarm-stat">
        <div class="kpi-ic" style="--accent: #5fe3bb; width: 38px; height: 38px">
          <Icon name="checkc" :size="19" />
        </div>
        <div>
          <div class="v num" style="color: #5fe3bb">{{ data.stats.closed }}</div>
          <div class="l">已闭环</div>
        </div>
      </div>
      <div class="card alarm-stat">
        <div class="kpi-ic" style="--accent: #8fb6ff; width: 38px; height: 38px">
          <Icon name="clock" :size="19" />
        </div>
        <div>
          <div class="v num" style="color: #8fb6ff">
            {{
              data.stats.avg_response_min === null
                ? '—'
                : `${Math.round(data.stats.avg_response_min)} min`
            }}
          </div>
          <div class="l">平均响应时长</div>
        </div>
      </div>
    </div>

    <div class="alarm-filter-bar">
      <div style="display: flex; gap: 7px; flex-wrap: wrap">
        <button
          v-for="filter in levelFilters"
          :key="filter.key"
          :class="['chip', level === filter.key ? 'active' : '']"
          @click="setLevel(filter.key)"
        >
          {{ filter.label }}
        </button>
      </div>
      <div class="alarm-filter-divider" />
      <div style="display: flex; gap: 7px; flex-wrap: wrap">
        <button
          v-for="filter in statusFilters"
          :key="filter.key"
          :class="['chip', status === filter.key ? 'active' : '']"
          @click="setStatus(filter.key)"
        >
          {{ filter.label }}
        </button>
      </div>
      <div class="alarm-filter-right">
        <label class="search" style="display: flex">
          <Icon name="search" />
          <input v-model="query" placeholder="搜索告警…" @input="onSearch" />
        </label>
        <button class="btn btn-ghost btn-sm" @click="exportCsv">
          <Icon name="download" :size="15" /> 导出 CSV
        </button>
      </div>
    </div>

    <div class="card">
      <div v-if="loading" class="loading-block"><span class="spinner" />加载告警…</div>
      <div v-else class="table-wrap">
        <table id="alarmTable">
          <thead>
            <tr>
              <th style="width: 36px">
                <input
                  type="checkbox"
                  class="table-check"
                  :checked="allChecked"
                  aria-label="全选"
                  @change="toggleAll"
                />
              </th>
              <th class="sortable" @click="sortBy('level')">级别 ⇅</th>
              <th>告警内容</th>
              <th>电机 / 设备</th>
              <th>触发值 / 阈值</th>
              <th class="sortable" @click="sortBy('time')">时间 ⇅</th>
              <th>飞书通知</th>
              <th>状态</th>
              <th style="text-align: right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="alarm in sortedItems"
              :key="alarm.id"
              class="clickable-row"
              @click="openAlarm(alarm.id)"
            >
              <td @click.stop>
                <input
                  type="checkbox"
                  class="table-check"
                  :checked="selected.has(alarm.id)"
                  :aria-label="`选择 ${alarm.code}`"
                  @change="toggleOne(alarm.id)"
                />
              </td>
              <td><StateBadge :tone="alarm.level" :label="LEVEL_TEXT[alarm.level]" /></td>
              <td>
                <b style="font-size: 12.5px">{{ alarm.title }}</b>
                <div class="sub">{{ alarm.code }} · {{ alarm.description.slice(0, 30) }}…</div>
              </td>
              <td>
                <b style="font-size: 12.5px">{{ alarm.motor_code || alarm.device_code }}</b>
                <div class="sub">{{ alarm.motor_name || '链路设备' }}</div>
              </td>
              <td class="num" style="font-size: 12.5px">
                <b
                  :style="{
                    color:
                      alarm.level === 'crit' ? '#FF8296' : alarm.level === 'warn' ? '#FFC65C' : '',
                  }"
                >
                  {{ alarm.value === null ? '—' : `${fmt(alarm.value)} ${alarm.unit}` }}
                </b>
                <div class="sub">
                  阈值
                  {{ alarm.threshold === null ? '—' : `${fmt(alarm.threshold)} ${alarm.unit}` }}
                </div>
              </td>
              <td class="num" style="font-size: 12px">
                {{ mmddhhmm(alarm.triggered_at) }}
                <div class="sub">{{ timeAgo(alarm.triggered_at) }}</div>
              </td>
              <td>
                <span :class="['feishu-tag', alarm.notification_status === 'skipped' ? 'off' : '']">
                  <Icon name="send" :size="13" />
                  {{ NOTIFICATION_TEXT[alarm.notification_status] }} ·
                  {{ alarm.notification_to || alarm.owner }}
                </span>
              </td>
              <td>
                <StateBadge
                  :tone="
                    alarm.status === 'closed' ? 'ok' : alarm.status === 'ack' ? 'info' : 'crit'
                  "
                  :label="ALARM_STATUS_TEXT[alarm.status]"
                />
              </td>
              <td @click.stop>
                <div class="row-actions">
                  <button
                    v-if="alarm.status !== 'closed'"
                    class="mini-btn primary"
                    @click="openAlarm(alarm.id)"
                  >
                    处理
                  </button>
                  <button v-else class="mini-btn danger" @click="askDelete(alarm)">删除</button>
                  <button class="mini-btn" @click="openAlarm(alarm.id)">详情</button>
                </div>
              </td>
            </tr>
            <tr v-if="!sortedItems.length">
              <td colspan="9" style="text-align: center; padding: 34px; color: var(--muted)">
                没有匹配的告警记录 —— 调整筛选或搜索关键词试试。
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!loading && (data?.total || 0) > pageSize" class="pager">
        <span>共 {{ data?.total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
        <button :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
        <button :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
      </div>
    </div>

    <div v-if="selected.size" class="bulk-bar">
      <span
        >已选 <b class="num">{{ selected.size }}</b> 项</span
      >
      <button class="btn btn-primary btn-sm" @click="bulkClose">批量闭环</button>
      <button class="btn btn-ghost btn-sm" @click="clearSelection()">取消选择</button>
    </div>

    <AlarmDetailDrawer
      :open="drawerOpen"
      :alarm-id="activeAlarmId"
      @close="drawerOpen = false"
      @updated="onUpdated"
    />
    <BaseModal
      :open="deleteTarget !== null"
      title="删除告警记录"
      subtitle="仅允许删除已闭环的历史记录，操作会写入审计日志"
      @close="deleteTarget = null"
    >
      <p style="font-size: 13px; color: var(--muted)">
        确认删除
        <b style="color: var(--text)">{{ deleteTarget?.code }} · {{ deleteTarget?.title }}</b
        >？
      </p>
      <div class="report-actions">
        <button class="btn btn-ghost" @click="deleteTarget = null">取消</button>
        <button class="btn btn-danger" :disabled="deleting" @click="confirmDelete">
          {{ deleting ? '删除中…' : '确认删除' }}
        </button>
      </div>
    </BaseModal>
  </section>
</template>
