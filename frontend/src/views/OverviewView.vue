<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api/client'
import type { MotorStatus, Overview, QuadrantAnalysis, SeriesPoint } from '@/api/types'
import AlarmDetailDrawer from '@/components/AlarmDetailDrawer.vue'
import DatePicker from '@/components/DatePicker.vue'
import Icon from '@/components/Icon.vue'
import LineChart from '@/components/LineChart.vue'
import MotorDetailDrawer from '@/components/MotorDetailDrawer.vue'
import QuadrantChart from '@/components/QuadrantChart.vue'
import Sparkline from '@/components/Sparkline.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'
import {
  NOTIFICATION_TEXT,
  STATUS_TEXT,
  average,
  fmt,
  hhmm,
  pointLabel,
  signed,
  statusClass,
  timeAgo,
} from '@/utils/format'

const app = useAppStore()
const ui = useUiStore()
const router = useRouter()

function todayText(): string {
  const date = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const today = todayText()
const selectedDate = ref(today)
const isHistorical = computed(() => selectedDate.value !== today)
const historicalOverview = ref<Overview | null>(null)
const pageLoading = ref(false)

const trendRange = ref('24h')
const trendMotor = ref<string | null>(null)
const trendPoints = ref<SeriesPoint[]>([])
const trendLoading = ref(false)
const quadrant = ref<QuadrantAnalysis | null>(null)
const motorFilter = ref<'all' | MotorStatus>('all')
const motorDrawerOpen = ref(false)
const activeMotorCode = ref<string | null>(null)
const alarmDrawerOpen = ref(false)
const activeAlarmId = ref<number | null>(null)

const pageOverview = computed<Overview | null>(() =>
  isHistorical.value ? historicalOverview.value : app.overview,
)
const motors = computed(() => pageOverview.value?.motors || [])
const visibleMotors = computed(() =>
  motors.value.filter((motor) => {
    if (motorFilter.value !== 'all' && motor.status !== motorFilter.value) return false
    const query = app.searchQuery.trim().toLowerCase()
    return (
      !query ||
      `${motor.code} ${motor.name} ${motor.location} ${motor.group}`.toLowerCase().includes(query)
    )
  }),
)
const selectedMotor = computed(
  () => motors.value.find((motor) => motor.code === trendMotor.value) || null,
)
const onlineCount = computed(() => motors.value.filter((motor) => motor.online).length)
const pilotCount = computed(() => motors.value.filter((motor) => motor.pilot).length)
const periodLabel = computed(() => (isHistorical.value ? selectedDate.value : '今日'))

function averageSparks(arrays: number[][]): number[] {
  const length = Math.max(0, ...arrays.map((array) => array.length))
  const output: number[] = []
  for (let index = 0; index < length; index += 1) {
    const values = arrays
      .map((array) => array[array.length - length + index])
      .filter((value): value is number => typeof value === 'number')
    const value = average(values)
    if (value !== null) output.push(Number(value.toFixed(2)))
  }
  return output
}

const tempSpark = computed(() => averageSparks(motors.value.map((motor) => motor.spark_temp)))
const currentSpark = computed(() => averageSparks(motors.value.map((motor) => motor.spark_current)))
const avgCurrent = computed(() => {
  const values = motors.value
    .map((motor) => motor.current_avg_a)
    .filter((value): value is number => value !== null)
  const value = average(values)
  return value === null ? null : value
})

const kpiRows = computed(() => {
  const kpi = pageOverview.value?.kpis
  if (!kpi) return []
  return [
    {
      icon: 'motor',
      color: '#2DD4EE',
      label: '在线电机',
      value: String(kpi.online_motors),
      unit: `/ ${kpi.total_motors} 台`,
      delta: `试点 ${pilotCount.value} 台 · ${kpi.online_motors === kpi.total_motors ? '全部在线' : '部分离线'}`,
      spark: motors.value.map((motor) => (motor.online ? 1 : 0)),
      deltaClass: kpi.online_motors === kpi.total_motors ? 'down' : 'up',
    },
    {
      icon: 'bell',
      color: '#FF4D6D',
      label: isHistorical.value ? '当日告警' : '活跃告警',
      value: String(kpi.active_alarms),
      unit: '条',
      delta: `严重 ${kpi.critical_alarms} · 警告 ${kpi.warning_alarms}`,
      spark: [] as number[],
      deltaClass: kpi.critical_alarms > 0 ? 'up' : 'flat',
    },
    {
      icon: 'thermo',
      color: '#FFB224',
      label: '平均外壳温度',
      value: fmt(kpi.avg_temperature_c),
      unit: '°C',
      delta: isHistorical.value
        ? `${periodLabel.value} 历史快照`
        : `每 ${app.intervalMinutes} 分钟采集一次`,
      spark: tempSpark.value,
      deltaClass: 'flat',
    },
    {
      icon: 'zap',
      color: '#4F8CFF',
      label: '平均负载率',
      value: fmt(kpi.avg_load_pct),
      unit: '%',
      delta: `电流均值 ${fmt(avgCurrent.value, 0)} A`,
      spark: currentSpark.value,
      deltaClass: 'flat',
    },
    {
      icon: 'radio',
      color: '#9D7CFF',
      label: '链路完好率',
      value: fmt(kpi.link_availability_pct),
      unit: '%',
      delta: `丢包 ${fmt(kpi.packet_loss_pct, 2)}% · 延迟 ${Math.round(kpi.avg_latency_ms)}ms`,
      spark: [kpi.link_availability_pct],
      deltaClass: kpi.link_availability_pct >= 99 ? 'down' : 'up',
    },
  ]
})

const trendLabels = computed(() =>
  trendPoints.value.map((point) => pointLabel(point.ts, trendRange.value)),
)
const trendTemp = computed(() => trendPoints.value.map((point) => point.temperature_c))
const trendCurrent = computed(() => trendPoints.value.map((point) => point.current_avg_a))
const tempThreshold = computed(() => selectedMotor.value?.temp_limit_c ?? 85)
const trendSummary = computed(() => {
  const points = trendPoints.value
  const temps = points
    .map((point) => point.temperature_c)
    .filter((value): value is number => value !== null)
  const currents = points
    .map((point) => point.current_avg_a)
    .filter((value): value is number => value !== null)
  const lastTemp =
    [...points].reverse().find((point) => point.temperature_c !== null)?.temperature_c ?? null
  const lastCurrent =
    [...points].reverse().find((point) => point.current_avg_a !== null)?.current_avg_a ?? null
  return [
    { label: '温度末值', value: fmt(lastTemp), unit: '°C', color: '#FFC65C' },
    {
      label: '最高温度',
      value: fmt(temps.length ? Math.max(...temps) : null),
      unit: '°C',
      color: '#FF8296',
    },
    {
      label: '最低温度',
      value: fmt(temps.length ? Math.min(...temps) : null),
      unit: '°C',
      color: '#7FE7F7',
    },
    { label: '电流末值', value: fmt(lastCurrent, 0), unit: 'A', color: '#7FE7F7' },
    {
      label: '平均电流',
      value: fmt(currents.length ? average(currents) : null, 0),
      unit: 'A',
      color: '#8FB6FF',
    },
  ]
})

const linkStats = computed(() => {
  const link = pageOverview.value?.link
  if (!link) return []
  return [
    {
      value: `${link.gateways_online} / ${link.gateways_total}`,
      label: '网关在线',
      color: '#5FE3BB',
    },
    { value: `${link.nodes_online} / ${link.nodes_total}`, label: '节点在线', color: '#5FE3BB' },
    {
      value: link.avg_rssi_dbm === null ? '—' : `${link.avg_rssi_dbm} dBm`,
      label: '平均信号强度',
      color: '#C9B3FF',
    },
    {
      value: link.packets_today.toLocaleString(),
      label: isHistorical.value ? '当日数据包' : '今日数据包',
      color: '#7FE7F7',
    },
  ]
})

const quadrantInsight = computed(() => {
  const points = quadrant.value?.points || []
  const tempRisk = points.find(
    (point) => point.temp_deviation_pct >= 8 && point.current_deviation_pct < 10,
  )
  if (tempRisk) {
    return `${tempRisk.code} ${tempRisk.name} 落入「温度高 · 电流正常」象限 —— 电流正常但温度偏高，疑似散热、轴承或润滑问题，建议优先检查。`
  }
  const currentRisk = points.find(
    (point) => point.current_deviation_pct >= 10 && point.temp_deviation_pct < 8,
  )
  if (currentRisk) {
    return `${currentRisk.code} ${currentRisk.name} 落入「温度正常 · 电流异常」象限 —— 疑似负载或电气侧波动，建议检查变频器输出与负载。`
  }
  return '当前全部电机处于双正常区间，温度与电流均未明显偏离自身基线。'
})

function riskScore(point: { temp_deviation_pct: number; current_deviation_pct: number }): number {
  return (
    Math.max(0, point.temp_deviation_pct - 8) + Math.max(0, point.current_deviation_pct - 10) * 1.1
  )
}

const riskPoints = computed(() =>
  [...(quadrant.value?.points || [])].sort((a, b) => riskScore(b) - riskScore(a)).slice(0, 3),
)

const statusFilters = [
  { key: 'all' as const, label: '全部' },
  { key: 'crit' as const, label: '严重' },
  { key: 'warn' as const, label: '警告' },
  { key: 'ok' as const, label: '正常' },
]

async function loadHistorical(date: string) {
  pageLoading.value = true
  try {
    historicalOverview.value = await api.overview(date)
  } catch (error) {
    historicalOverview.value = null
    ui.notify('err', '历史数据加载失败', error instanceof Error ? error.message : '')
  } finally {
    pageLoading.value = false
  }
}

async function loadTrend() {
  trendLoading.value = true
  try {
    const data = await api.dashboardTrend(
      trendRange.value,
      trendMotor.value,
      isHistorical.value ? selectedDate.value : undefined,
    )
    trendPoints.value = data.points
  } catch (error) {
    ui.notify('err', '趋势数据加载失败', error instanceof Error ? error.message : '')
  } finally {
    trendLoading.value = false
  }
}

async function loadQuadrant() {
  try {
    quadrant.value = await api.quadrant(isHistorical.value ? selectedDate.value : undefined)
  } catch (error) {
    ui.notify('err', '四象限数据加载失败', error instanceof Error ? error.message : '')
  }
}

function setRange(range: string) {
  trendRange.value = range
  void loadTrend()
}

function setTrendMotor(code: string | null) {
  trendMotor.value = code
  void loadTrend()
}

function openMotor(code: string) {
  activeMotorCode.value = code
  motorDrawerOpen.value = true
}

function openAlarm(id: number) {
  activeAlarmId.value = id
  alarmDrawerOpen.value = true
}

async function onAlarmUpdated() {
  if (!isHistorical.value) {
    await app.refresh()
    await loadQuadrant()
  }
}

function goAnalysis(motorCode?: string | null) {
  const query: Record<string, string> = {}
  if (motorCode) query.motor = motorCode
  if (isHistorical.value) query.date = selectedDate.value
  void router.push({ path: '/analysis', query })
}

async function onDateChange(date: string) {
  selectedDate.value = date
  if (date === today) {
    historicalOverview.value = null
    await app.fetchOverview(true)
  } else {
    await loadHistorical(date)
  }
  await Promise.all([loadTrend(), loadQuadrant()])
}

watch(
  () => app.overview?.sampling.last_poll_at,
  (value, oldValue) => {
    if (!isHistorical.value && value && oldValue && value !== oldValue) {
      void loadTrend()
      void loadQuadrant()
    }
  },
)

onMounted(() => {
  void loadTrend()
  void loadQuadrant()
})
</script>

<template>
  <section class="view" id="view-overview">
    <div class="overview-toolbar">
      <div class="ov-mode">
        <span class="pill">
          <span :class="['dot', isHistorical ? 'ok' : 'live']" />
          {{ isHistorical ? '历史回看' : '实时监测' }}
        </span>
        <span class="micro">{{
          isHistorical ? `数据日期 ${selectedDate}` : `每 ${app.intervalMinutes} 分钟采集`
        }}</span>
        <span v-if="isHistorical" class="badge info">只读快照 · 告警为当日告警</span>
      </div>
      <div class="right">
        <span class="micro">数据日期</span>
        <DatePicker :model-value="selectedDate" :max="today" @update:model-value="onDateChange" />
        <button v-if="isHistorical" class="mini-btn" @click="onDateChange(today)">回到今天</button>
      </div>
    </div>

    <div v-if="pageLoading" class="loading-block">
      <span class="spinner" />正在加载 {{ selectedDate }} 历史数据…
    </div>
    <div v-else-if="!pageOverview" class="empty-state card">
      <b>暂无监测数据</b>
      请确认采集器已启动，或执行演示数据初始化。
    </div>
    <template v-else>
      <div class="kpi-grid-5" id="kpiRow">
        <div
          v-for="(kpi, index) in kpiRows"
          :key="kpi.label"
          class="card kpi reveal in"
          :style="{ '--accent': kpi.color, '--d': `${index * 0.06}s` }"
        >
          <div class="kpi-top">
            <div class="kpi-ic"><Icon :name="kpi.icon" /></div>
            <span class="kpi-label">{{ kpi.label }}</span>
          </div>
          <div class="kpi-val num">
            {{ kpi.value }}<small>{{ kpi.unit }}</small>
          </div>
          <div class="kpi-foot">
            <span :class="['kpi-delta', kpi.deltaClass]">{{ kpi.delta }}</span>
            <div class="kpi-spark">
              <Sparkline
                v-if="kpi.spark.length > 1"
                :data="kpi.spark"
                :color="kpi.color"
                :width="86"
                :height="30"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="card trend-card reveal in" style="--d: 0.08s">
        <div class="card-head">
          <h3>温度 · 电流实时趋势</h3>
          <div class="right">
            <div class="seg" id="trendRange">
              <button
                v-for="range in ['24h', '7d', '30d']"
                :key="range"
                :class="{ active: trendRange === range }"
                @click="setRange(range)"
              >
                {{ range === '24h' ? '24 小时' : range === '7d' ? '7 天' : '30 天' }}
              </button>
            </div>
          </div>
          <div
            class="sub"
            style="display: flex; align-items: center; gap: 10px; width: 100%; margin-top: 2px"
          >
            <span :class="['dot', isHistorical ? 'ok' : 'live']" />
            <span v-if="isHistorical">历史回看 · {{ selectedDate }} · 按 15 分钟粒度还原</span>
            <span v-else>每 {{ app.intervalMinutes }} 分钟上报一次 · LoRa 无线回传</span>
          </div>
        </div>

        <div class="chart-summary">
          <div v-for="item in trendSummary" :key="item.label" class="chart-summary-item">
            <span>{{ item.label }}</span>
            <b class="num" :style="{ color: item.color }"
              >{{ item.value }} <small>{{ item.unit }}</small></b
            >
          </div>
        </div>

        <div style="padding: 12px 20px 0; display: flex; gap: 7px; flex-wrap: wrap" id="trendChips">
          <button
            :class="['chip', trendMotor === null ? 'active' : '']"
            @click="setTrendMotor(null)"
          >
            全部均值
          </button>
          <button
            v-for="motor in motors"
            :key="motor.code"
            :class="['chip', trendMotor === motor.code ? 'active' : '']"
            @click="setTrendMotor(motor.code)"
          >
            {{ motor.code }}
          </button>
        </div>

        <div class="chart-wrap">
          <div v-if="trendLoading" class="loading-block" style="min-height: 320px">
            <span class="spinner" />加载趋势…
          </div>
          <LineChart
            v-else-if="trendPoints.length"
            :labels="trendLabels"
            :series="[
              { name: '外壳温度', color: '#FFB224', data: trendTemp, unit: '°C', area: true },
              { name: '运行电流', color: '#2DD4EE', data: trendCurrent, unit: 'A', yAxisIndex: 1 },
            ]"
            :thresholds="[
              { value: tempThreshold, label: `温度上限 ${tempThreshold}°C`, color: '#FF4D6D' },
            ]"
            :height="320"
            y2
          />
          <div v-else class="chart-empty" style="height: 304px">该日期暂无趋势数据</div>
        </div>
        <div class="legend" style="padding: 0 22px 16px">
          <span><i style="background: #ffb224" />外壳温度 °C（左轴）</span>
          <span><i style="background: #2dd4ee" />运行电流 A（右轴）</span>
          <span style="margin-left: auto; color: var(--faint)">
            {{ selectedMotor ? `${selectedMotor.code} · ${selectedMotor.name}` : '全部电机均值' }} ·
            {{ trendRange === '24h' ? '15 分钟' : trendRange === '7d' ? '1 小时' : '6 小时' }}粒度
          </span>
        </div>
      </div>

      <div class="card link-strip-card reveal in" style="--d: 0.12s">
        <div class="card-head">
          <h3>LoRa 链路状态</h3>
          <div class="right">
            <StateBadge
              :tone="pageOverview.link.gateways_online > 0 ? 'ok' : 'warn'"
              :label="pageOverview.link.gateways_online > 0 ? '网关在线' : '网关离线'"
            />
            <span class="micro">{{
              isHistorical ? `${selectedDate} 当日链路统计` : '实时链路'
            }}</span>
          </div>
        </div>
        <div class="link-strip">
          <div class="link-strip-stats">
            <div v-for="stat in linkStats" :key="stat.label" class="link-stat">
              <div class="v num" :style="{ color: stat.color }">{{ stat.value }}</div>
              <div class="l">{{ stat.label }}</div>
            </div>
          </div>
          <div class="link-flow">
            <div class="hop">
              <b>采集点 ×{{ motors.length }}</b
              >RS485
            </div>
            <span class="arr"><Icon name="chevR" :size="14" /></span>
            <div class="hop">
              <b>LoRa 网关 ×{{ pageOverview.link.gateways_total }}</b
              >470MHz
            </div>
            <span class="arr"><Icon name="chevR" :size="14" /></span>
            <div class="hop"><b>后台服务</b>厂区网口</div>
          </div>
        </div>
      </div>

      <div class="ov-row">
        <div class="card reveal in" style="--d: 0.16s">
          <div class="card-head">
            <h3>{{ isHistorical ? '当日告警' : '活跃告警' }}</h3>
            <div class="right">
              <span class="micro"
                >严重 {{ pageOverview.kpis.critical_alarms }} · 警告
                {{ pageOverview.kpis.warning_alarms }}</span
              >
              <button class="mini-btn primary" @click="router.push('/alarms')">全部告警</button>
            </div>
          </div>
          <div v-if="pageOverview.active_alarms.length" class="alert-list">
            <div
              v-for="alarm in pageOverview.active_alarms"
              :key="alarm.id"
              class="alert-row"
              @click="openAlarm(alarm.id)"
            >
              <div :class="['sev', alarm.level]">
                <Icon :name="alarm.level === 'info' ? 'info' : 'alert'" :size="16" />
              </div>
              <div style="min-width: 0">
                <b>{{ alarm.code }} · {{ alarm.title }}</b>
                <p>
                  {{ alarm.motor_code || alarm.device_code }} ·
                  <span class="feishu-tag">
                    <Icon name="send" :size="12" />
                    {{ NOTIFICATION_TEXT[alarm.notification_status] }}
                    {{ alarm.notification_to || alarm.owner }}
                  </span>
                </p>
              </div>
              <time>{{ timeAgo(alarm.triggered_at) }}</time>
            </div>
          </div>
          <div v-else class="empty-state" style="padding: 22px 20px">
            {{ isHistorical ? '该日期没有新增告警。' : '当前无活跃告警，全部电机运行正常。' }}
          </div>
        </div>

        <div class="card reveal in" style="--d: 0.2s">
          <div class="card-head">
            <h3>通知与处理闭环</h3>
            <div class="right">
              <StateBadge
                :tone="app.feishuConfigured ? 'info' : 'mut'"
                :label="app.feishuConfigured ? '飞书直达责任人' : '飞书未配置'"
              />
            </div>
          </div>
          <div class="loop-stats">
            <div class="loop-stat">
              <div class="v num" style="color: #8fb6ff">
                {{ pageOverview.loop.notifications_today }}
              </div>
              <div class="l">{{ isHistorical ? '当日飞书通知' : '今日飞书通知' }}</div>
            </div>
            <div class="loop-stat">
              <div class="v num" style="color: #5fe3bb">{{ pageOverview.loop.closed_today }}</div>
              <div class="l">{{ isHistorical ? '当日已闭环' : '今日已闭环' }}</div>
            </div>
            <div class="loop-stat">
              <div class="v num">
                {{
                  pageOverview.loop.avg_response_min === null
                    ? '—'
                    : Math.round(pageOverview.loop.avg_response_min)
                }}
                <small
                  v-if="pageOverview.loop.avg_response_min !== null"
                  style="font-size: 12px; color: var(--muted)"
                >
                  min</small
                >
              </div>
              <div class="l">平均响应</div>
            </div>
          </div>
          <div v-if="pageOverview.loop.items.length" class="loop-list">
            <div
              v-for="item in pageOverview.loop.items"
              :key="`${item.ts}-${item.text}`"
              class="loop-item"
            >
              <Icon name="checkc" :size="15" />
              <span>{{ item.text }} · {{ item.who }}</span>
              <time>{{ timeAgo(item.ts) }}</time>
            </div>
          </div>
          <div v-else class="empty-state" style="padding: 18px 20px">
            {{ isHistorical ? '该日期暂无闭环记录。' : '今日暂无闭环记录。' }}
          </div>
        </div>
      </div>

      <div class="sec-head reveal in" style="--d: 0.22s">
        <h2>电机矩阵</h2>
        <span class="micro">{{ onlineCount }} 台在线 · {{ pilotCount }} 台试点</span>
        <div class="right" id="motorFilters">
          <button
            v-for="filter in statusFilters"
            :key="filter.key"
            :class="['chip', motorFilter === filter.key ? 'active' : '']"
            @click="motorFilter = filter.key"
          >
            {{ filter.label }}
          </button>
        </div>
      </div>
      <div v-if="visibleMotors.length" class="motor-grid" id="motorGrid">
        <div
          v-for="(motor, index) in visibleMotors"
          :key="motor.code"
          :class="['card', 'motor', 'reveal', 'in', motor.status === 'crit' ? 'crit' : '']"
          :style="{ '--d': `${index * 0.05}s` }"
          role="button"
          tabindex="0"
          :aria-label="`查看 ${motor.name} 详情`"
          @click="openMotor(motor.code)"
          @keydown.enter.prevent="openMotor(motor.code)"
          @keydown.space.prevent="openMotor(motor.code)"
        >
          <div class="motor-head">
            <span :class="['severity-dot', motor.status]" />
            <b>{{ motor.name }}</b>
            <span class="tag">{{ motor.code }}</span>
            <span v-if="motor.pilot" class="badge pilot" style="font-size: 10px; padding: 2px 8px"
              >试点</span
            >
            <StateBadge :tone="statusClass(motor.status)" :label="STATUS_TEXT[motor.status]" />
          </div>
          <div class="motor-metrics">
            <div :class="['mm', 'temp', motor.status === 'crit' ? 'crit' : '']">
              <div class="l"><Icon name="thermo" :size="13" /> 外壳温度</div>
              <div class="v num">{{ fmt(motor.temperature_c) }}<small>°C</small></div>
              <div class="motor-spark">
                <Sparkline
                  :data="motor.spark_temp"
                  :color="motor.status === 'crit' ? '#FF4D6D' : '#FFB224'"
                  :width="100"
                  :height="26"
                />
              </div>
            </div>
            <div class="mm amp">
              <div class="l"><Icon name="zap" :size="13" /> 平均电流</div>
              <div class="v num">{{ fmt(motor.current_avg_a, 0) }}<small>A</small></div>
              <div class="motor-spark">
                <Sparkline :data="motor.spark_current" color="#2DD4EE" :width="100" :height="26" />
              </div>
            </div>
          </div>
          <div class="motor-foot">
            <span
              :class="[
                'dev-chip',
                (motor.temp_deviation_pct || 0) >= 8
                  ? 'up'
                  : (motor.temp_deviation_pct || 0) <= -3
                    ? 'down'
                    : 'flat',
              ]"
            >
              基线 {{ signed(motor.temp_deviation_pct) }}%
            </span>
            <span>{{ motor.rated_kw }} kW</span>
            <span class="sep"
              ><Icon name="radio" :size="12" /> {{ motor.node_code }} · 心跳
              {{ motor.last_seen_at ? hhmm(motor.last_seen_at) : '—' }}</span
            >
          </div>
        </div>
      </div>
      <div v-else class="card empty-state"><b>没有匹配的电机</b>调整筛选条件或搜索关键词试试。</div>

      <div class="ov-row ov-row-wide">
        <div class="card reveal in" style="--d: 0.1s">
          <div class="card-head">
            <h3>温度 × 电流关联速览</h3>
            <div class="right">
              <button class="mini-btn primary" @click="goAnalysis()">进入对比分析</button>
            </div>
            <div class="sub">
              偏离自身基线的百分比 · 点击象限图可定位电机 ·
              {{ isHistorical ? `${selectedDate} 历史快照` : '实时数据' }}
            </div>
          </div>
          <div class="chart-wrap">
            <QuadrantChart
              v-if="quadrant && quadrant.points.length"
              :points="quadrant.points"
              :selected="activeMotorCode"
              :height="310"
              @select="openMotor"
            />
            <div v-else class="chart-empty" style="height: 300px">该日期暂无关联分析数据</div>
          </div>
          <div class="insight">
            <Icon name="alert" :size="16" />
            <span>{{ quadrantInsight }}</span>
          </div>
        </div>

        <div class="card reveal in" style="--d: 0.14s">
          <div class="card-head">
            <h3>重点关注</h3>
            <div class="right"><span class="micro">按偏离基线排序</span></div>
          </div>
          <div class="risk-list">
            <div
              v-for="(point, index) in riskPoints"
              :key="point.code"
              class="risk-row"
              @click="openMotor(point.code)"
            >
              <span class="risk-rank">{{ index + 1 }}</span>
              <div class="risk-main">
                <b>{{ point.code }} {{ point.name }}</b>
                <p>
                  温度
                  <span
                    :style="{ color: point.temp_deviation_pct >= 8 ? '#FF8296' : 'var(--muted)' }"
                    >{{ signed(point.temp_deviation_pct) }}%</span
                  >
                  · 电流
                  <span
                    :style="{
                      color:
                        Math.abs(point.current_deviation_pct) >= 10 ? '#FFC65C' : 'var(--muted)',
                    }"
                    >{{ signed(point.current_deviation_pct) }}%</span
                  >
                </p>
              </div>
              <StateBadge :tone="statusClass(point.status)" :label="STATUS_TEXT[point.status]" />
            </div>
            <div v-if="!riskPoints.length" class="empty-state" style="padding: 24px 20px">
              暂无偏离数据。
            </div>
          </div>
          <div class="risk-actions">
            <button
              class="btn btn-ghost btn-sm"
              style="width: 100%; justify-content: center"
              @click="goAnalysis()"
            >
              <Icon name="compare" :size="14" /> 查看完整对比分析
            </button>
          </div>
          <div class="insight" style="border-top: 1px solid var(--line-soft)">
            <Icon name="info" :size="16" />
            <span
              >规则来自现场运维经验：温度高/电流正常优先查散热与轴承；电流异常优先查负载与电气。</span
            >
          </div>
        </div>
      </div>
    </template>

    <MotorDetailDrawer
      :open="motorDrawerOpen"
      :code="activeMotorCode"
      :date="isHistorical ? selectedDate : null"
      @close="motorDrawerOpen = false"
    />
    <AlarmDetailDrawer
      :open="alarmDrawerOpen"
      :alarm-id="activeAlarmId"
      @close="alarmDrawerOpen = false"
      @updated="onAlarmUpdated"
    />
  </section>
</template>

<style scoped>
.kpi-delta.up {
  color: #ff8296;
}
.kpi-delta.down {
  color: #5fe3bb;
}
.kpi-delta.flat {
  color: var(--muted);
}
.overview-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.overview-toolbar .right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ov-mode {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.ov-mode .pill {
  padding: 6px 12px;
}
.trend-card {
  margin-bottom: 16px;
}
.chart-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 14px 20px 0;
}
.chart-summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: var(--panel-2);
  font-size: 11px;
  color: var(--faint);
}
.chart-summary-item b {
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
}
.chart-summary-item small {
  font-size: 10px;
  color: var(--faint);
  font-weight: 500;
}
.link-strip-card {
  margin-bottom: 16px;
}
.link-strip {
  display: grid;
  grid-template-columns: minmax(0, 2.2fr) minmax(280px, 1fr);
  gap: 16px;
  padding: 16px 20px 20px;
  align-items: stretch;
}
.link-strip-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.link-strip .link-flow {
  padding: 0;
  align-items: center;
  flex-wrap: nowrap;
}
.link-strip .link-flow .hop {
  min-width: 0;
  padding: 9px 4px;
}
.ov-row {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}
.ov-row-wide {
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  margin-top: 20px;
}
.risk-list {
  padding: 4px 0 6px;
}
.risk-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--line-soft);
  cursor: pointer;
  transition: background 0.15s;
}
.risk-row:first-child {
  border-top: none;
}
.risk-row:hover {
  background: rgba(148, 163, 204, 0.05);
}
.risk-rank {
  width: 22px;
  height: 22px;
  flex: none;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: var(--panel-3);
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
}
.risk-main {
  flex: 1;
  min-width: 0;
}
.risk-main b {
  display: block;
  font-size: 12.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.risk-main p {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--faint);
}
.risk-actions {
  padding: 0 20px 14px;
}
@media (max-width: 1380px) {
  .chart-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 1200px) {
  .link-strip,
  .ov-row,
  .ov-row-wide {
    grid-template-columns: 1fr;
  }
  .link-strip-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 860px) {
  .chart-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .link-strip .link-flow {
    flex-wrap: wrap;
  }
  .overview-toolbar .right {
    margin-left: 0;
    width: 100%;
  }
}
</style>
