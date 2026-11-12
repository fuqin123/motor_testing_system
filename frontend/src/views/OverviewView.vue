<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api/client'
import type { MotorStatus, QuadrantAnalysis, SeriesPoint } from '@/api/types'
import AlarmDetailDrawer from '@/components/AlarmDetailDrawer.vue'
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

const overview = computed(() => app.overview)
const motors = computed(() => app.motors)
const visibleMotors = computed(() =>
  app.filteredMotors.filter(
    (motor) => motorFilter.value === 'all' || motor.status === motorFilter.value,
  ),
)
const selectedMotor = computed(
  () => motors.value.find((motor) => motor.code === trendMotor.value) || null,
)
const onlineCount = computed(() => motors.value.filter((motor) => motor.online).length)
const pilotCount = computed(() => motors.value.filter((motor) => motor.pilot).length)

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
  const kpi = overview.value?.kpis
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
      label: '活跃告警',
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
      delta: `每 ${app.intervalMinutes} 分钟采集一次`,
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

const linkStats = computed(() => {
  const link = overview.value?.link
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
    { value: link.packets_today.toLocaleString(), label: '今日数据包', color: '#7FE7F7' },
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

const statusFilters = [
  { key: 'all' as const, label: '全部' },
  { key: 'crit' as const, label: '严重' },
  { key: 'warn' as const, label: '警告' },
  { key: 'ok' as const, label: '正常' },
]

async function loadTrend() {
  trendLoading.value = true
  try {
    const data = await api.dashboardTrend(trendRange.value, trendMotor.value)
    trendPoints.value = data.points
  } catch (error) {
    ui.notify('err', '趋势数据加载失败', error instanceof Error ? error.message : '')
  } finally {
    trendLoading.value = false
  }
}

async function loadQuadrant() {
  try {
    quadrant.value = await api.quadrant()
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
  await app.refresh()
  await loadQuadrant()
}

function goAnalysis() {
  void router.push('/analysis')
}

watch(
  () => app.overview?.generated_at,
  (value, oldValue) => {
    if (value && oldValue && value !== oldValue) {
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
    <div v-if="!overview && app.loading" class="loading-block">
      <span class="spinner" />正在加载监测数据…
    </div>
    <div v-else-if="!overview" class="empty-state card">
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

      <div class="ov-grid">
        <div class="card reveal in" style="--d: 0.08s">
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
              <span class="dot live" />
              <span>每 {{ app.intervalMinutes }} 分钟上报一次 · LoRa 无线回传</span>
            </div>
          </div>
          <div
            style="padding: 12px 20px 0; display: flex; gap: 7px; flex-wrap: wrap"
            id="trendChips"
          >
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
            <div v-if="trendLoading" class="loading-block" style="min-height: 308px">
              <span class="spinner" />加载趋势…
            </div>
            <LineChart
              v-else-if="trendPoints.length"
              :labels="trendLabels"
              :series="[
                { name: '外壳温度', color: '#FFB224', data: trendTemp, unit: '°C', area: true },
                {
                  name: '运行电流',
                  color: '#2DD4EE',
                  data: trendCurrent,
                  unit: 'A',
                  yAxisIndex: 1,
                },
              ]"
              :thresholds="[
                { value: tempThreshold, label: `温度上限 ${tempThreshold}°C`, color: '#FF4D6D' },
              ]"
              :height="308"
              y2
            />
            <div v-else class="chart-empty" style="height: 292px">暂无趋势数据</div>
          </div>
          <div class="legend" style="padding: 0 22px 16px">
            <span><i style="background: #ffb224" />外壳温度 °C（左轴）</span>
            <span><i style="background: #2dd4ee" />运行电流 A（右轴）</span>
            <span style="margin-left: auto; color: var(--faint)">
              {{
                selectedMotor ? `${selectedMotor.code} · ${selectedMotor.name}` : '全部电机均值'
              }}
              ·
              {{ trendRange === '24h' ? '15 分钟' : trendRange === '7d' ? '1 小时' : '6 小时' }}粒度
            </span>
          </div>
        </div>

        <div class="rail">
          <div class="card reveal in" style="--d: 0.14s">
            <div class="card-head">
              <h3>LoRa 链路状态</h3>
              <div class="right">
                <StateBadge
                  :tone="overview.link.gateways_online > 0 ? 'ok' : 'warn'"
                  :label="overview.link.gateways_online > 0 ? '网关在线' : '网关离线'"
                />
              </div>
            </div>
            <div class="link-stats">
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
                <b>LoRa 网关 ×{{ overview.link.gateways_total }}</b
                >470MHz
              </div>
              <span class="arr"><Icon name="chevR" :size="14" /></span>
              <div class="hop"><b>后台服务</b>厂区网口</div>
            </div>
          </div>

          <div class="card reveal in" style="--d: 0.2s">
            <div class="card-head">
              <h3>活跃告警</h3>
              <div class="right">
                <button class="mini-btn primary" @click="router.push('/alarms')">全部告警</button>
              </div>
            </div>
            <div v-if="overview.active_alarms.length" class="alert-list">
              <div
                v-for="alarm in overview.active_alarms"
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
              当前无活跃告警，全部电机运行正常。
            </div>
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
              <div class="l"><Icon name="zap" :size="13" /> 运行电流</div>
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
              >基线 {{ signed(motor.temp_deviation_pct) }}%</span
            >
            <span>{{ motor.rated_kw }} kW</span>
            <span class="sep">
              <Icon name="radio" :size="12" /> {{ motor.node_code }} · 心跳
              {{ motor.last_seen_at ? hhmm(motor.last_seen_at) : '—' }}
            </span>
          </div>
        </div>
      </div>
      <div v-else class="card empty-state">
        <b>没有匹配的电机</b>
        调整筛选条件或搜索关键词试试。
      </div>

      <div class="ov-bottom">
        <div class="card reveal in" style="--d: 0.1s">
          <div class="card-head">
            <h3>温度 × 电流关联速览</h3>
            <div class="right">
              <button class="mini-btn primary" @click="goAnalysis">进入对比分析</button>
            </div>
            <div class="sub">偏离自身基线的百分比 · 点击象限图可定位电机</div>
          </div>
          <div class="chart-wrap">
            <QuadrantChart
              v-if="quadrant && quadrant.points.length"
              :points="quadrant.points"
              :selected="activeMotorCode"
              mini
              :height="252"
              @select="openMotor"
            />
            <div v-else class="chart-empty" style="height: 252px">暂无关联分析数据</div>
          </div>
          <div class="insight">
            <Icon name="alert" :size="16" />
            <span>{{ quadrantInsight }}</span>
          </div>
        </div>

        <div class="card reveal in" style="--d: 0.16s">
          <div class="card-head">
            <h3>通知与处理闭环</h3>
            <div class="right">
              <StateBadge
                :tone="overview.link.gateways_online > 0 ? 'info' : 'mut'"
                :label="app.feishuConfigured ? '飞书直达责任人' : '飞书未配置'"
              />
            </div>
          </div>
          <div class="loop-stats">
            <div class="loop-stat">
              <div class="v num" style="color: #8fb6ff">
                {{ overview.loop.notifications_today }}
              </div>
              <div class="l">今日飞书通知</div>
            </div>
            <div class="loop-stat">
              <div class="v num" style="color: #5fe3bb">{{ overview.loop.closed_today }}</div>
              <div class="l">今日已闭环</div>
            </div>
            <div class="loop-stat">
              <div class="v num">
                {{
                  overview.loop.avg_response_min === null
                    ? '—'
                    : Math.round(overview.loop.avg_response_min)
                }}
                <small
                  v-if="overview.loop.avg_response_min !== null"
                  style="font-size: 12px; color: var(--muted)"
                >
                  min</small
                >
              </div>
              <div class="l">平均响应</div>
            </div>
          </div>
          <div v-if="overview.loop.items.length" class="loop-list">
            <div
              v-for="item in overview.loop.items"
              :key="`${item.ts}-${item.text}`"
              class="loop-item"
            >
              <Icon name="checkc" :size="15" />
              <span>{{ item.text }} · {{ item.who }}</span>
              <time>{{ timeAgo(item.ts) }}</time>
            </div>
          </div>
          <div v-else class="empty-state" style="padding: 18px 20px">今日暂无闭环记录。</div>
        </div>
      </div>
    </template>

    <MotorDetailDrawer
      :open="motorDrawerOpen"
      :code="activeMotorCode"
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
</style>
