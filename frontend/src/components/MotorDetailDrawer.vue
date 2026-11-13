<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api/client'
import type { Baseline, MotorCard, SensorInfo, SeriesPoint } from '@/api/types'
import BaseDrawer from '@/components/BaseDrawer.vue'
import Icon from '@/components/Icon.vue'
import LineChart from '@/components/LineChart.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useUiStore } from '@/stores/ui'
import { downloadCsv } from '@/utils/download'
import {
  STATUS_TEXT,
  dateTime,
  fmt,
  pointLabel,
  signed,
  statusClass,
  timeAgo,
} from '@/utils/format'

const props = defineProps<{ open: boolean; code: string | null; date?: string | null }>()
const emit = defineEmits<{ close: []; analysis: [code: string] }>()
const router = useRouter()
const ui = useUiStore()

const loading = ref(false)
const detail = ref<{
  motor: MotorCard
  sensors: SensorInfo[]
  baseline: Baseline | null
  recent_alarms: import('@/api/types').Alarm[]
} | null>(null)
const series = ref<SeriesPoint[]>([])

async function load() {
  if (!props.code) return
  loading.value = true
  try {
    const date = props.date || undefined
    const [motorDetail, trend] = await Promise.all([
      api.motor(props.code, date),
      api.motorSeries(props.code, '24h', date),
    ])
    detail.value = motorDetail
    series.value = trend.points
  } catch (error) {
    ui.notify('err', '电机详情加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.code, props.date],
  () => {
    if (props.open && props.code) void load()
  },
)

const labels = computed(() => series.value.map((point) => pointLabel(point.ts, '24h')))
const tempData = computed(() => series.value.map((point) => point.temperature_c))
const currentData = computed(() => series.value.map((point) => point.current_avg_a))
const vibrationData = computed(() => series.value.map((point) => point.vibration_total_mm_s ?? null))

const motor = computed(() => detail.value?.motor || null)
const phaseImbalance = computed(() => {
  const values = [motor.value?.current_a, motor.value?.current_b, motor.value?.current_c].filter(
    (value): value is number => typeof value === 'number',
  )
  if (values.length !== 3) return null
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length
  if (mean <= 0) return null
  return ((Math.max(...values) - Math.min(...values)) / mean) * 100
})

function exportCsv() {
  if (!motor.value || !series.value.length) return
  const rows: unknown[][] = [
    ['time', 'temperature_C', 'current_avg_A', 'current_A', 'current_B', 'current_C'],
    ...series.value.map((point) => [
      point.ts,
      point.temperature_c ?? '',
      point.current_avg_a ?? '',
      point.current_a ?? '',
      point.current_b ?? '',
      point.current_c ?? '',
    ]),
  ]
  downloadCsv(rows, `${motor.value.code}_24h_监测数据.csv`)
  ui.notify('ok', '已导出 24 小时数据', `${motor.value.code} · ${series.value.length} 条记录`)
}

function goAnalysis() {
  if (!motor.value) return
  emit('close')
  emit('analysis', motor.value.code)
  const query: Record<string, string> = { motor: motor.value.code }
  if (props.date) query.date = props.date
  void router.push({ path: '/analysis', query })
}
</script>

<template>
  <BaseDrawer
    :open="props.open"
    :title="motor ? `${motor.name}` : '电机详情'"
    :subtitle="
      motor
        ? `${motor.code} · ${motor.location} · ${motor.rated_kw} kW · ${motor.group}${props.date ? ` · 历史 ${props.date}` : ''}`
        : ''
    "
    @close="emit('close')"
  >
    <template v-if="motor" #badge>
      <StateBadge :tone="statusClass(motor.status)" :label="STATUS_TEXT[motor.status]" />
    </template>

    <div v-if="loading" class="loading-block"><span class="spinner" />加载中…</div>
    <template v-else-if="detail && motor">
      <div class="drawer-sec">
        <div class="info-grid" style="grid-template-columns: 1fr 1fr">
          <div class="info-cell">
            <div class="l">外壳温度 / 上限</div>
            <div class="v num" :style="{ color: motor.status === 'crit' ? '#FF8296' : '#FFC65C' }">
              {{ fmt(motor.temperature_c) }} °C
              <span style="color: var(--faint); font-weight: 400"
                >/ {{ motor.temp_limit_c }} °C</span
              >
            </div>
          </div>
          <div class="info-cell">
            <div class="l">平均电流 / 单相上限</div>
            <div class="v num" style="color: #7fe7f7">
              {{ fmt(motor.current_avg_a) }} A
              <span style="color: var(--faint); font-weight: 400"
                >/ {{ motor.current_limit_a }} A</span
              >
            </div>
          </div>
          <div class="info-cell">
            <div class="l">三相电流 A / B / C</div>
            <div class="v num" style="font-size: 13px; color: #7fe7f7">
              {{ fmt(motor.current_a) }} / {{ fmt(motor.current_b) }} / {{ fmt(motor.current_c) }} A
            </div>
          </div>
          <div class="info-cell">
            <div class="l">三相不平衡</div>
            <div
              class="v num"
              :style="{ color: (phaseImbalance || 0) >= 10 ? '#FFC65C' : '#5FE3BB' }"
            >
              {{ fmt(phaseImbalance) }} %
            </div>
          </div>
          <div class="info-cell">
            <div class="l">负载率</div>
            <div class="v num">{{ fmt(motor.load_pct) }} %</div>
          </div>
          <div class="info-cell">
            <div class="l">偏离自身基线</div>
            <div
              class="v num"
              :style="{ color: (motor.temp_deviation_pct || 0) >= 8 ? '#FF8296' : '#5FE3BB' }"
            >
              {{ signed(motor.temp_deviation_pct) }} %
            </div>
          </div>
        </div>
      </div>

      <div class="drawer-sec">
        <h4>24 小时趋势</h4>
        <div v-if="series.length" class="chart-box">
          <LineChart
            :labels="labels"
            :series="[
              { name: '外壳温度', color: '#FFB224', data: tempData, unit: '°C', area: true },
              { name: '平均电流', color: '#2DD4EE', data: currentData, unit: 'A', yAxisIndex: 1 },
              { name: '振动总值', color: '#9D7CFF', data: vibrationData, unit: 'mm/s', yAxisIndex: 2 },
            ]"
            :thresholds="[
              {
                value: motor.temp_limit_c,
                label: `上限 ${motor.temp_limit_c}°C`,
                color: '#FF4D6D',
              },
            ]"
            :height="210"
            y2
            y3
          />
        </div>
        <div v-else class="chart-empty">暂无 24 小时数据</div>
      </div>

      <div class="drawer-sec">
        <h4>设备档案</h4>
        <div class="info-grid">
          <div class="info-cell">
            <div class="l">变频器</div>
            <div class="v">{{ motor.vfd_model || '—' }}</div>
          </div>
          <div class="info-cell">
            <div class="l">LoRa 节点</div>
            <div class="v">{{ motor.node_code }}</div>
          </div>
          <div class="info-cell">
            <div class="l">采集传感器</div>
            <div class="v" style="font-size: 12px">{{ motor.sensors || '未配置' }}</div>
          </div>
          <div class="info-cell">
            <div class="l">最近心跳</div>
            <div class="v" style="font-size: 12px">{{ timeAgo(motor.last_seen_at) }}</div>
          </div>
          <div class="info-cell">
            <div class="l">基线温度</div>
            <div class="v num">{{ fmt(detail.baseline?.temp_median) }} °C</div>
          </div>
          <div class="info-cell">
            <div class="l">基线电流</div>
            <div class="v num">{{ fmt(detail.baseline?.current_median) }} A</div>
          </div>
        </div>
      </div>

      <div class="drawer-sec">
        <h4>采集点</h4>
        <div v-if="detail.sensors.length" class="info-grid">
          <div v-for="sensor in detail.sensors" :key="sensor.id" class="info-cell">
            <div class="l">{{ sensor.kind_text }} · {{ sensor.code }}</div>
            <div class="v" style="font-size: 12px">
              从站 {{ sensor.slave_id }} · 寄存器 {{ sensor.register_address }}~{{
                sensor.register_address + sensor.register_count - 1
              }}
            </div>
            <div style="font-size: 11px; color: var(--faint); margin-top: 3px">
              {{ sensor.power_type }} · {{ sensor.online ? '在线' : '离线' }}
            </div>
          </div>
        </div>
        <div v-else class="notice-box">尚未配置温度/电流采集点</div>
      </div>

      <div class="drawer-sec">
        <h4>最近告警</h4>
        <div v-if="detail.recent_alarms.length">
          <div
            v-for="alarm in detail.recent_alarms.slice(0, 4)"
            :key="alarm.id"
            class="loop-item"
            style="border-top: 1px solid var(--line-soft)"
          >
            <Icon :name="alarm.status === 'closed' ? 'checkc' : 'alert'" />
            <span :style="{ color: alarm.status === 'closed' ? '' : '#FFC65C' }">
              {{ alarm.code }} {{ alarm.title }} ·
              {{ alarm.status === 'closed' ? '已闭环' : '未闭环' }}
            </span>
            <time>{{ timeAgo(alarm.triggered_at) }}</time>
          </div>
        </div>
        <p v-else style="font-size: 12.5px; color: var(--muted)">近 30 天无告警记录。</p>
      </div>

      <div class="drawer-actions">
        <button class="btn btn-primary" @click="goAnalysis">
          <Icon name="compare" :size="15" /> 查看对比分析
        </button>
        <button class="btn btn-ghost" @click="exportCsv">
          <Icon name="download" :size="15" /> 导出 24h 数据
        </button>
      </div>
      <p style="font-size: 11px; color: var(--faint); margin-top: 12px">
        平台只监测、只报警，不下发任何控制指令。数据时间：{{ dateTime(motor.last_seen_at) }}
      </p>
    </template>
    <div v-else class="empty-state">
      <b>未找到电机</b>
      请检查点表配置或刷新页面。
    </div>
  </BaseDrawer>
</template>
