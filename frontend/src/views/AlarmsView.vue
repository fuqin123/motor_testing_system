<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type { Alarm, AlarmList, PacketLossItem, PacketLossResponse } from '@/api/types'
import AlarmDetailDrawer from '@/components/AlarmDetailDrawer.vue'
import BaseModal from '@/components/BaseModal.vue'
import Icon from '@/components/Icon.vue'
import PagerBar from '@/components/PagerBar.vue'
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
const packetLossData = ref<PacketLossResponse | null>(null)
const lossLoading = ref(false)
const lossStatus = ref('all')
const lossQuery = ref('')
const lossPage = ref(1)
const lossPageSize = ref(5)
const expandedLoss = ref<Set<number>>(new Set())
const loading = ref(false)
const level = ref('all')
const status = ref('all')
const query = ref('')
const page = ref(1)
const pageSize = ref(50)
const selected = ref<Set<number>>(new Set())
const sortKey = ref<'time' | 'level'>('time')
const sortDir = ref<1 | -1>(-1)
const drawerOpen = ref(false)
const activeAlarmId = ref<number | null>(null)
const deleteTarget = ref<Alarm | null>(null)
const deleting = ref(false)
let searchTimer: number | null = null
let lossSearchTimer: number | null = null
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
const allChecked = computed(
  () =>
    sortedItems.value.length > 0 &&
    sortedItems.value.every((alarm) => selected.value.has(alarm.id)),
)

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const payload = await api.alarms({
      level: level.value,
      status: status.value,
      q: query.value.trim(),
      page: page.value,
      page_size: pageSize.value,
    })
    if (!payload.items.length && page.value > 1) {
      const lastPage = Math.max(1, Math.ceil(payload.total / pageSize.value))
      if (lastPage !== page.value) {
        page.value = lastPage
        await load(silent)
        return
      }
    }
    data.value = payload
  } catch (error) {
    ui.notify('err', '告警列表加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

async function loadPacketLosses(silent = false) {
  if (!silent) lossLoading.value = true
  try {
    const payload = await api.packetLosses({
      status: lossStatus.value,
      q: lossQuery.value.trim(),
      page: lossPage.value,
      page_size: lossPageSize.value,
    })
    if (!payload.items.length && lossPage.value > 1) {
      const lastPage = Math.max(1, Math.ceil(payload.total / lossPageSize.value))
      if (lastPage !== lossPage.value) {
        lossPage.value = lastPage
        await loadPacketLosses(silent)
        return
      }
    }
    packetLossData.value = payload
  } catch (error) {
    if (!silent) {
      ui.notify('err', '丢包补采记录加载失败', error instanceof Error ? error.message : '')
    }
  } finally {
    lossLoading.value = false
  }
}

const lossStats = computed(
  () => packetLossData.value?.stats ?? { pending: 0, failed: 0, recovered: 0 },
)
const lossFilters = computed(() => [
  {
    key: 'all',
    label: '全部',
    count: lossStats.value.pending + lossStats.value.failed + lossStats.value.recovered,
  },
  { key: 'pending', label: '待补采', count: lossStats.value.pending },
  { key: 'failed', label: '补采失败', count: lossStats.value.failed },
  { key: 'recovered', label: '已补回', count: lossStats.value.recovered },
])
const lossAllExpanded = computed(
  () =>
    (packetLossData.value?.items.length ?? 0) > 0 &&
    packetLossData.value!.items.every((item) => expandedLoss.value.has(item.id)),
)

function setLossStatus(value: string) {
  if (lossStatus.value === value) return
  lossStatus.value = value
  lossPage.value = 1
  expandedLoss.value = new Set()
  void loadPacketLosses()
}

function onLossSearch() {
  if (lossSearchTimer) window.clearTimeout(lossSearchTimer)
  lossSearchTimer = window.setTimeout(() => {
    lossPage.value = 1
    expandedLoss.value = new Set()
    void loadPacketLosses()
  }, 320)
}

function changeLossPage(next: number) {
  lossPage.value = next
  void loadPacketLosses()
}

function changeLossPageSize(size: number) {
  lossPageSize.value = size
  lossPage.value = 1
  void loadPacketLosses()
}

function toggleLoss(id: number) {
  const next = new Set(expandedLoss.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedLoss.value = next
}

function toggleAllLoss() {
  if (!packetLossData.value) return
  expandedLoss.value = lossAllExpanded.value
    ? new Set()
    : new Set(packetLossData.value.items.map((item) => item.id))
}

function isLossExpanded(item: PacketLossItem): boolean {
  return expandedLoss.value.has(item.id)
}

function attemptNoText(attemptNo: number): string {
  return attemptNo === 0 ? '初次采集' : `第 ${attemptNo} 次补采`
}

function lossReason(item: PacketLossItem): string {
  if (item.status === 'recovered') {
    const firstFailure = item.attempts_log.find((log) => !log.success)
    return `首次失败：${firstFailure?.error || item.error || '未返回错误信息'}`
  }
  return item.error || '未返回错误信息'
}

function changePageSize(size: number) {
  pageSize.value = size
  page.value = 1
  selected.value = new Set()
  void load()
}

function packetLossTone(status: string): 'ok' | 'warn' | 'crit' | 'mut' {
  if (status === 'recovered') return 'ok'
  if (status === 'failed') return 'crit'
  return 'warn'
}

function packetLossText(status: string): string {
  if (status === 'recovered') return '已补回'
  if (status === 'failed') return '补采失败'
  return '等待补采'
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
  void loadPacketLosses()
  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') {
      void load(true)
      void loadPacketLosses(true)
    }
  }, 30_000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (searchTimer) window.clearTimeout(searchTimer)
  if (lossSearchTimer) window.clearTimeout(lossSearchTimer)
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

    <div
      v-if="packetLossData && (packetLossData.total || lossStats.pending + lossStats.failed + lossStats.recovered)"
      class="card packet-loss-card"
    >
      <div class="card-head">
        <h3>丢包补采</h3>
        <div class="right">
          <span v-if="lossLoading" class="spinner" />
          <span class="micro"
            >待补 {{ lossStats.pending }} · 失败 {{ lossStats.failed }} · 已补回
            {{ lossStats.recovered }}</span
          >
          <button
            v-if="packetLossData.items.length > 1"
            class="btn btn-ghost btn-sm"
            @click="toggleAllLoss"
          >
            {{ lossAllExpanded ? '收起明细' : '展开明细' }}
          </button>
        </div>
        <div class="sub">
          丢包后每 {{ packetLossData.retry_delay_minutes }} 分钟补采一次，最多
          {{ packetLossData.items[0]?.max_attempts ?? 3 }} 次；点击任意记录可逐次查看补采时间与失败原因。
        </div>
      </div>

      <div class="pl-toolbar">
        <div class="pl-chips">
          <button
            v-for="filter in lossFilters"
            :key="filter.key"
            :class="['chip', lossStatus === filter.key ? 'active' : '']"
            @click="setLossStatus(filter.key)"
          >
            {{ filter.label }}<span class="cnt">{{ filter.count }}</span>
          </button>
        </div>
        <label class="search pl-search">
          <Icon name="search" :size="15" />
          <input
            v-model="lossQuery"
            placeholder="网关 / 采集点 / 电机 / 错误信息"
            @input="onLossSearch"
          />
        </label>
      </div>

      <div class="pl-scroll">
        <div class="pl-head-row">
          <span>状态</span>
          <span>采集点</span>
          <span>采集周期</span>
          <span>补采进度</span>
          <span>失败原因</span>
          <span>下次补采</span>
          <span />
        </div>
        <div
          v-for="item in packetLossData.items"
          :key="item.id"
          class="pl-item"
          :class="{ open: isLossExpanded(item) }"
        >
          <div
            class="pl-row"
            role="button"
            tabindex="0"
            :aria-expanded="isLossExpanded(item)"
            @click="toggleLoss(item.id)"
            @keydown.enter.prevent="toggleLoss(item.id)"
            @keydown.space.prevent="toggleLoss(item.id)"
          >
            <StateBadge :tone="packetLossTone(item.status)" :label="packetLossText(item.status)" />
            <div class="pl-point">
              <b>{{ item.gateway_code }}</b>
              <span>
                {{ item.sensor_code || '网关整体' }}
                <template v-if="item.motor_code"> · {{ item.motor_code }}</template>
              </span>
            </div>
            <span class="pl-cell num">{{ mmddhhmm(item.cycle_ts) }}</span>
            <span class="pl-progress">
              <span class="pl-bar">
                <i
                  :class="item.status"
                  :style="{
                    width: `${Math.min(100, (item.attempts / Math.max(1, item.max_attempts)) * 100)}%`,
                  }"
                />
              </span>
              <span class="num">{{ item.attempts }}/{{ item.max_attempts }}</span>
            </span>
            <span class="pl-reason" :title="lossReason(item)">{{ lossReason(item) }}</span>
            <span class="pl-cell num">{{
              item.next_attempt_at ? mmddhhmm(item.next_attempt_at) : '已停止'
            }}</span>
            <span class="pl-chev" :class="{ open: isLossExpanded(item) }">
              <Icon name="chevR" :size="14" />
            </span>
          </div>

          <div v-if="isLossExpanded(item)" class="pl-detail">
            <div class="pl-detail-head">
              <b>补采记录 · 共 {{ item.attempts_log.length }} 次</b>
              <span>
                采集周期 {{ mmddhhmm(item.cycle_ts) }} · 网关 {{ item.gateway_code }}
                <template v-if="item.sensor_code"> · 采集点 {{ item.sensor_code }}</template>
              </span>
            </div>
            <table class="pl-attempts">
              <thead>
                <tr>
                  <th style="width: 96px">尝试</th>
                  <th style="width: 132px">时间</th>
                  <th style="width: 80px">结果</th>
                  <th>失败原因</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(log, index) in item.attempts_log"
                  :key="`${item.id}-${log.attempt_no}-${index}`"
                >
                  <td>{{ attemptNoText(log.attempt_no) }}</td>
                  <td class="num">{{ mmddhhmm(log.attempted_at) }}</td>
                  <td>
                    <StateBadge
                      :tone="log.success ? 'ok' : 'crit'"
                      :label="log.success ? '成功' : '失败'"
                    />
                  </td>
                  <td class="pl-attempt-error">
                    {{ log.error || (log.success ? '该次补采成功，数据已回补' : '未返回错误信息') }}
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="pl-detail-foot">
              <span
                >重试间隔 {{ packetLossData.retry_delay_minutes }} 分钟 · 上限
                {{ item.max_attempts }} 次</span
              >
              <span v-if="item.recovered_at">补回时间 {{ mmddhhmm(item.recovered_at) }}</span>
              <span v-else-if="item.next_attempt_at"
                >下次补采 {{ mmddhhmm(item.next_attempt_at) }}</span
              >
              <span v-else>补采已停止</span>
            </div>
          </div>
        </div>
        <div v-if="!packetLossData.items.length" class="pl-empty">
          {{ lossStatus === 'all' ? '暂无丢包补采记录' : '当前筛选条件下没有补采记录' }}
        </div>
      </div>

      <PagerBar
        :total="packetLossData.total"
        :page="lossPage"
        :page-size="lossPageSize"
        :page-sizes="[5, 10, 20, 50]"
        unit="条补采记录"
        @update:page="changeLossPage"
        @update:page-size="changeLossPageSize"
      />
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
      <div v-if="!loading && data" class="alarm-pager">
        <PagerBar
          :total="data.total || 0"
          :page="page"
          :page-size="pageSize"
          :page-sizes="[20, 50, 100]"
          unit="条告警"
          @update:page="changePage"
          @update:page-size="changePageSize"
        />
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

<style scoped>
.packet-loss-card {
  margin-bottom: 16px;
}
.pl-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 20px 0;
}
.pl-chips {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.pl-search {
  width: 280px;
  margin-left: auto;
  padding: 6px 11px;
}
.pl-scroll {
  margin-top: 12px;
  border-top: 1px solid var(--line-soft);
  overflow-x: auto;
}
.pl-head-row,
.pl-row {
  display: grid;
  grid-template-columns: 88px minmax(140px, 1.1fr) 92px 108px minmax(180px, 1.8fr) 88px 18px;
  gap: 12px;
  align-items: center;
  min-width: 800px;
  padding: 0 20px;
}
.pl-head-row {
  height: 34px;
  background: rgba(17, 27, 48, 0.5);
  border-bottom: 1px solid var(--line-soft);
  color: var(--faint);
  font-size: 11px;
  letter-spacing: 0.06em;
}
.pl-item {
  border-bottom: 1px solid var(--line-soft);
}
.pl-row {
  min-height: 47px;
  cursor: pointer;
  transition: background 0.16s;
}
.pl-row:hover {
  background: rgba(45, 212, 238, 0.04);
}
.pl-row:focus-visible {
  outline: 1px solid rgba(45, 212, 238, 0.5);
  outline-offset: -2px;
}
.pl-item.open .pl-row {
  background: rgba(45, 212, 238, 0.05);
}
.pl-point {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}
.pl-point b {
  font-size: 12.5px;
  font-weight: 600;
}
.pl-point span {
  color: var(--faint);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pl-cell {
  color: var(--muted);
  font-size: 11.5px;
  white-space: nowrap;
}
.pl-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pl-bar {
  flex: 1;
  min-width: 40px;
  height: 5px;
  border-radius: 999px;
  background: rgba(148, 163, 204, 0.16);
  overflow: hidden;
}
.pl-bar i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--amber);
  transition: width 0.3s var(--ease);
}
.pl-bar i.failed {
  background: var(--red);
}
.pl-bar i.recovered {
  background: var(--green);
}
.pl-progress .num {
  color: var(--faint);
  font-size: 11px;
}
.pl-reason {
  color: var(--muted);
  font-size: 11.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pl-chev {
  display: inline-flex;
  color: var(--faint);
  transition: transform 0.18s var(--ease);
}
.pl-chev.open {
  transform: rotate(90deg);
  color: var(--cyan);
}
.pl-detail {
  padding: 2px 20px 16px 120px;
  background: rgba(6, 10, 19, 0.35);
}
.pl-detail-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  padding: 8px 0;
  font-size: 12px;
}
.pl-detail-head b {
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
}
.pl-detail-head span {
  color: var(--faint);
  font-size: 11.5px;
}
.pl-attempts {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--line-soft);
  background: rgba(17, 27, 48, 0.5);
}
.pl-attempts th {
  padding: 7px 10px;
  background: rgba(22, 34, 60, 0.6);
  border-bottom: 1px solid var(--line-soft);
  color: var(--faint);
  font-size: 11px;
  font-weight: 500;
  text-align: left;
}
.pl-attempts td {
  padding: 7px 10px;
  border-top: 1px solid var(--line-soft);
  font-size: 12px;
  vertical-align: top;
}
.pl-attempts tbody tr:first-child td {
  border-top: none;
}
.pl-attempts .num {
  color: var(--muted);
  font-size: 11.5px;
  white-space: nowrap;
}
.pl-attempt-error {
  color: var(--muted);
  line-height: 1.55;
  word-break: break-word;
}
.pl-detail-foot {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: var(--faint);
  font-size: 11px;
}
.pl-empty {
  padding: 26px;
  color: var(--faint);
  font-size: 12px;
  text-align: center;
}
.alarm-pager {
  padding: 0 20px 14px;
}
@media (max-width: 720px) {
  .pl-search {
    width: 100%;
    margin-left: 0;
  }
  .pl-detail {
    padding-left: 20px;
  }
}
</style>
