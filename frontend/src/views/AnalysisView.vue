<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api } from '@/api/client'
import type { QuadrantPoint, SelfAnalysis, TrendAnalysis, TrendSeries } from '@/api/types'
import AlarmDetailDrawer from '@/components/AlarmDetailDrawer.vue'
import BaseModal from '@/components/BaseModal.vue'
import GaugeArc from '@/components/GaugeArc.vue'
import Icon from '@/components/Icon.vue'
import LineChart from '@/components/LineChart.vue'
import MotorDetailDrawer from '@/components/MotorDetailDrawer.vue'
import QuadrantChart from '@/components/QuadrantChart.vue'
import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'
import { downloadText } from '@/utils/download'
import { dateTime, fmt, pointLabel, signed } from '@/utils/format'

const app = useAppStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

type Mode = 'self' | 'peer' | 'quad' | 'trend'
const mode = ref<Mode>('self')
const motorCode = ref('')
const peerGroup = ref('')
const trendRange = ref('7d')
const loading = ref(false)
const selfData = ref<SelfAnalysis | null>(null)
const peerData = ref<import('@/api/types').PeerAnalysis | null>(null)
const quadData = ref<import('@/api/types').QuadrantAnalysis | null>(null)
const trendData = ref<TrendAnalysis | null>(null)
const trendSeries = ref<TrendSeries | null>(null)
const selectedQuad = ref<string | null>(null)
const motorDrawerOpen = ref(false)
const activeMotorCode = ref<string | null>(null)
const alarmDrawerOpen = ref(false)
const activeAlarmId = ref<number | null>(null)
const reportOpen = ref(false)
const reportText = ref('')
const analysisDate = computed(() => (typeof route.query.date === 'string' ? route.query.date : ''))
let initialLoadDone = false

const palette = [
  '#2DD4EE',
  '#4F8CFF',
  '#FF4D6D',
  '#9D7CFF',
  '#FFB224',
  '#2ED3A3',
  '#F06AD8',
  '#B8E62E',
]

const modes: { key: Mode; label: string }[] = [
  { key: 'self', label: '自身历史对比' },
  { key: 'peer', label: '同类电机对比' },
  { key: 'quad', label: '温度 × 电流关联' },
  { key: 'trend', label: '趋势分析' },
]

const selfSeries = computed(() => selfData.value?.series || [])
const selfLabels = computed(() => selfSeries.value.map((point) => pointLabel(point.ts, '30d')))
const selfTemp = computed(() => selfSeries.value.map((point) => point.temperature_c))
const selfCurrent = computed(() => selfSeries.value.map((point) => point.current_avg_a))
const selfBand = computed(() => {
  if (!selfData.value?.band.length) return null
  return {
    lo: selfData.value.band.map((point) => point.lo),
    hi: selfData.value.band.map((point) => point.hi),
  }
})
const selfDeviationSeries = computed(() => {
  const baseline = selfData.value?.baseline?.temp_median
  if (!baseline) return []
  return selfSeries.value.map((point) =>
    point.temperature_c === null ? null : ((point.temperature_c - baseline) / baseline) * 100,
  )
})
const selfTempLimit = computed(() => selfData.value?.motor.temp_limit_c ?? 85)
const verdictTone = computed(() => {
  const key = selfData.value?.verdict.key
  if (key === 'temp') return 'crit' as const
  if (key === 'both') return 'crit' as const
  if (key === 'current') return 'warn' as const
  return 'ok' as const
})

const peerMetrics = computed(() => {
  const motors = peerData.value?.motors || []
  if (!motors.length) return []
  const definitions = [
    { name: '外壳温度', unit: '°C', dec: 1, key: 'temperature_c' as const },
    { name: '运行电流', unit: 'A', dec: 0, key: 'current_avg_a' as const },
    { name: '振动总值', unit: 'mm/s', dec: 2, key: 'vibration_total_mm_s' as const },
    { name: '负载率', unit: '%', dec: 1, key: 'load_pct' as const },
    { name: '温度偏离基线', unit: '%', dec: 1, key: 'temp_deviation_pct' as const },
  ]
  return definitions.map((definition) => {
    const values = motors.map((motor) => motor[definition.key] ?? 0)
    const max = Math.max(1, ...values.map((value) => Math.abs(value)))
    return { ...definition, max }
  })
})

const peerMaxScore = computed(() =>
  Math.max(1, ...(peerData.value?.ranking || []).map((item) => item.score)),
)

const selectedQuadPoint = computed<QuadrantPoint | null>(() => {
  const points = quadData.value?.points || []
  return points.find((point) => point.code === selectedQuad.value) || points[0] || null
})

const trendLabels = computed(() =>
  (trendSeries.value?.points || []).map((point) => pointLabel(point.ts, trendRange.value)),
)
const trendTemp = computed(() =>
  (trendSeries.value?.points || []).map((point) => point.temperature_c),
)
const trendCurrent = computed(() =>
  (trendSeries.value?.points || []).map((point) => point.current_avg_a),
)
const trendMarkers = computed(() => {
  const series = trendSeries.value?.points || []
  const events = trendData.value?.events || []
  return events
    .map((event) => {
      let index = -1
      series.forEach((point, position) => {
        if (new Date(point.ts).getTime() <= new Date(event.ts).getTime()) index = position
      })
      if (index < 0) return null
      return {
        index,
        label: `${event.id} ${event.title}`,
        color: event.level === 'crit' ? '#FF4D6D' : event.level === 'warn' ? '#FFB224' : '#4F8CFF',
      }
    })
    .filter((item): item is { index: number; label: string; color: string } => item !== null)
})

function colorFor(code: string): string {
  const digits = code.replace(/\D/g, '')
  const index = digits ? Number(digits) - 1 : 0
  return palette[index % palette.length]
}

function barWidth(value: number | null, max: number): number {
  if (value === null) return 0
  return Math.min(100, (Math.abs(value) / max) * 100)
}

function judgePoint(point: QuadrantPoint | null): { text: string; color: string } {
  if (!point) return { text: '暂无数据', color: 'var(--muted)' }
  if (point.status === 'crit') return { text: '严重偏差异常，需立即核查', color: '#FF8296' }
  if (point.status === 'warn') return { text: '偏离自身基线，建议关注', color: '#FFC65C' }
  return { text: '双正常 · 运行健康', color: '#5FE3BB' }
}

function openAlarm(alarmId: number) {
  activeAlarmId.value = alarmId
  alarmDrawerOpen.value = true
}

async function loadSelf() {
  if (!motorCode.value) return
  loading.value = true
  try {
    selfData.value = await api.selfAnalysis(motorCode.value, '30d', analysisDate.value || undefined)
  } catch (error) {
    ui.notify('err', '自身对比加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

async function loadPeer(group?: string) {
  loading.value = true
  try {
    const data = await api.peers(group || undefined, analysisDate.value || undefined)
    peerData.value = data
    if (!peerGroup.value) peerGroup.value = data.group
  } catch (error) {
    ui.notify('err', '同类对比加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

async function loadQuadrant() {
  loading.value = true
  try {
    quadData.value = await api.quadrant(analysisDate.value || undefined)
    if (!selectedQuad.value && quadData.value.points.length) {
      selectedQuad.value =
        quadData.value.points.find((point) => point.status !== 'ok')?.code ||
        quadData.value.points[0].code
    }
  } catch (error) {
    ui.notify('err', '关联分析加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

async function loadTrend() {
  if (!motorCode.value) return
  loading.value = true
  try {
    const [analysis, series] = await Promise.all([
      api.analysisTrend(motorCode.value, trendRange.value, analysisDate.value || undefined),
      api.dashboardTrend(trendRange.value, motorCode.value, analysisDate.value || undefined),
    ])
    trendData.value = analysis
    trendSeries.value = series
  } catch (error) {
    ui.notify('err', '趋势分析加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

function loadCurrentMode() {
  if (mode.value === 'self') void loadSelf()
  else if (mode.value === 'peer') void loadPeer(peerGroup.value)
  else if (mode.value === 'quad') void loadQuadrant()
  else void loadTrend()
}

function setMode(next: Mode) {
  mode.value = next
}

function setMotor(code: string) {
  motorCode.value = code
  if (mode.value === 'self' || mode.value === 'trend') loadCurrentMode()
}

function setRange(range: string) {
  trendRange.value = range
}

function selectPeerGroup(group: string) {
  peerGroup.value = group
  void loadPeer(group)
}

function openMotor(code: string) {
  activeMotorCode.value = code
  motorDrawerOpen.value = true
}

function buildReport() {
  if (!selfData.value) return
  const data = selfData.value
  const latest = data.latest
  const baseline = data.baseline
  const lines = [
    '# 电机对比分析报告',
    `生成时间：${dateTime(new Date().toISOString())}    平台：MotorPulse（试点）`,
    '',
    '## 对象',
    `${data.motor.code} · ${data.motor.name}（${data.motor.rated_kw} kW，${data.motor.group}，${data.motor.location}）`,
    '',
    '## 一、自己和自己比',
    `- 当前外壳温度：${fmt(latest.temperature_c)} °C；30 天正常基线：${fmt(baseline?.temp_median)} °C`,
    `- 温度偏离基线：${signed(data.deviation.temp_pct)} %`,
    `- 当前电流：${fmt(latest.current_avg_a)} A；基线电流：${fmt(baseline?.current_median)} A`,
    `- 当前负载率：${fmt(latest.load_pct)} %`,
    `- 近 7 天温升速率：${data.rise_rate_c_per_day === null ? '样本不足' : `${signed(data.rise_rate_c_per_day, 2)} °C/天`}`,
    '',
    '## 二、规则命中',
    ...data.rules.map(
      (rule) => `- ${rule.hit ? '【命中】' : '【正常】'} ${rule.label}：${rule.detail}`,
    ),
    '',
    '## 三、温度 × 电流关联',
    `判定：${data.verdict.text}`,
    '',
    '## 四、结论与建议',
    data.verdict.advice || '保持例行监测。',
    '',
    '—— 本报告由对比分析引擎自动生成；平台只监测、只报警，不控制电机。',
  ]
  reportText.value = lines.join('\n')
  reportOpen.value = true
}

async function copyReport() {
  try {
    await navigator.clipboard.writeText(reportText.value)
    ui.notify('ok', '已复制到剪贴板', '可直接粘贴到飞书文档')
  } catch {
    ui.notify('warn', '复制失败', '浏览器未授权剪贴板，请使用下载')
  }
}

function downloadReport() {
  const code = selfData.value?.motor.code || 'motor'
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
  downloadText(reportText.value, `分析报告_${code}_${stamp}.md`, 'text/markdown')
  ui.notify('ok', '报告已下载', `分析报告_${code}_${stamp}.md`)
}

async function onAlarmUpdated() {
  await app.refresh()
  if (mode.value === 'trend') void loadTrend()
}

watch(mode, () => loadCurrentMode())
watch(trendRange, () => {
  if (mode.value === 'trend') void loadTrend()
})
watch(
  () => route.query.date,
  () => loadCurrentMode(),
)
watch(
  () => route.query.motor,
  (value) => {
    if (typeof value === 'string' && value && value !== motorCode.value) {
      motorCode.value = value
      initialLoadDone = true
      loadCurrentMode()
    }
  },
)
watch(
  () => app.motors,
  (motors) => {
    if (!motors.length) return
    const queryMotor = typeof route.query.motor === 'string' ? route.query.motor : ''
    if (!motorCode.value) {
      motorCode.value = motors.some((motor) => motor.code === queryMotor)
        ? queryMotor
        : motors[0].code
    }
    if (!initialLoadDone) {
      initialLoadDone = true
      loadCurrentMode()
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="view" id="view-analysis">
    <div class="analysis-mode-bar">
      <div class="seg" id="anaModes">
        <button
          v-for="item in modes"
          :key="item.key"
          :class="{ active: mode === item.key }"
          @click="setMode(item.key)"
        >
          {{ item.label }}
        </button>
      </div>
      <div class="right">
        <span v-if="analysisDate" class="badge info">历史回看 · {{ analysisDate }}</span>
        <button
          v-if="analysisDate"
          class="mini-btn"
          @click="
            router.replace({ path: '/analysis', query: motorCode ? { motor: motorCode } : {} })
          "
        >
          回到实时
        </button>
        <span style="font-size: 12px; color: var(--faint)">分析对象</span>
        <select
          class="input analysis-motor-select"
          :value="motorCode"
          @change="setMotor(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="motor in app.motors" :key="motor.code" :value="motor.code">
            {{ motor.code }} · {{ motor.name }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="loading" class="card loading-block"><span class="spinner" />正在计算分析结果…</div>

    <!-- 自身历史对比 -->
    <div v-if="mode === 'self' && !loading" class="panel" id="panel-self">
      <div v-if="selfData" class="ana-grid">
        <div class="card">
          <div class="card-head">
            <h3>
              {{
                analysisDate
                  ? '所选日期表现 vs 过去 30 天正常基线'
                  : '当前表现 vs 过去 30 天正常基线'
              }}
            </h3>
            <div class="right"><span class="badge mut">基线 = 历史正常时段 P10–P90</span></div>
            <div class="sub">
              自己和自己比：同一台电机现在和过去正常状态比，看温度、电流是否偏高
            </div>
          </div>
          <div class="chart-wrap">
            <LineChart
              v-if="selfSeries.length"
              :labels="selfLabels"
              :series="[
                {
                  name: '当前温度',
                  color: '#FFB224',
                  data: selfTemp,
                  unit: '°C',
                  area: true,
                  width: 2.4,
                },
                {
                  name: '当前电流',
                  color: '#2DD4EE',
                  data: selfCurrent,
                  unit: 'A',
                  yAxisIndex: 1,
                  width: 1.8,
                },
              ]"
              :band="selfBand"
              :thresholds="[
                { value: selfTempLimit, label: `上限 ${selfTempLimit}°C`, color: '#FF4D6D' },
              ]"
              :height="330"
              fill
              y2
            />
            <div v-else class="chart-empty" style="height: 310px">暂无历史数据</div>
          </div>
          <div class="legend" style="padding: 0 22px 16px">
            <span><i style="background: #ffb224" />当前温度</span>
            <span
              ><i
                style="
                  background: rgba(255, 178, 36, 0.25);
                  border: 1px dashed rgba(255, 178, 36, 0.6);
                "
              />正常基线区间</span
            >
            <span><i style="background: #2dd4ee" />当前电流</span>
          </div>
          <div style="padding: 0 20px 18px; border-top: 1px solid var(--line-soft)">
            <div class="micro" style="margin: 14px 0 6px">温度偏离度走势 · 相对自身基线 %</div>
            <LineChart
              v-if="selfDeviationSeries.length"
              :labels="selfLabels"
              :series="[
                {
                  name: '温度偏离度',
                  color: (selfData.deviation.temp_pct || 0) > 8 ? '#FF4D6D' : '#FFB224',
                  data: selfDeviationSeries,
                  unit: '%',
                  area: true,
                },
              ]"
              :thresholds="[
                { value: 5, label: '关注线 +5%', color: '#FFB224' },
                { value: 0, label: '基线 0%', color: 'rgba(148,163,204,.5)' },
              ]"
              :height="150"
            />
            <div v-else class="chart-empty" style="height: 140px">暂无基线样本</div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>偏离判定</h3></div>
          <div class="gauge-wrap">
            <GaugeArc :value="selfData.deviation.temp_pct" />
            <div
              class="gauge-val num"
              :style="{
                color:
                  verdictTone === 'crit'
                    ? '#FF8296'
                    : verdictTone === 'warn'
                      ? '#FFC65C'
                      : '#5FE3BB',
              }"
            >
              {{ signed(selfData.deviation.temp_pct) }}%
            </div>
            <div class="gauge-lbl">温度较 30 天正常基线</div>
          </div>
          <div class="analysis-stat-grid">
            <div class="analysis-stat">
              <div class="l">{{ analysisDate ? '所选日期温度' : '当前外壳温度' }}</div>
              <div class="v num">{{ fmt(selfData.latest.temperature_c) }} °C</div>
            </div>
            <div class="analysis-stat">
              <div class="l">正常基线温度</div>
              <div class="v num">{{ fmt(selfData.baseline?.temp_median) }} °C</div>
            </div>
            <div class="analysis-stat">
              <div class="l">{{ analysisDate ? '所选日期电流' : '当前运行电流' }}</div>
              <div class="v num">{{ fmt(selfData.latest.current_avg_a, 0) }} A</div>
            </div>
            <div class="analysis-stat">
              <div class="l">基线电流</div>
              <div class="v num">{{ fmt(selfData.baseline?.current_median, 0) }} A</div>
            </div>
            <div class="analysis-stat">
              <div class="l">温升速率</div>
              <div class="v num">
                {{
                  selfData.rise_rate_c_per_day === null
                    ? '样本不足'
                    : `${signed(selfData.rise_rate_c_per_day, 2)} °C/天`
                }}
              </div>
            </div>
            <div class="analysis-stat">
              <div class="l">判定</div>
              <div class="v" style="font-size: 12px; color: #ffc65c">
                {{ selfData.verdict.text }}
              </div>
            </div>
          </div>
          <div class="rule-list">
            <div
              v-for="rule in selfData.rules"
              :key="rule.key"
              :class="['rule', rule.hit ? 'hit' : '']"
            >
              <Icon :name="rule.hit ? 'alert' : 'checkc'" :size="16" />
              <div>
                <b>{{ rule.label }}</b>
                <p>{{ rule.detail }}</p>
              </div>
            </div>
          </div>
          <div class="advice">
            <b><Icon name="wrench" :size="15" /> 处理建议</b>
            <p>{{ selfData.verdict.advice }}</p>
          </div>
          <div style="padding: 0 20px 20px">
            <button
              class="btn btn-primary"
              style="width: 100%; justify-content: center"
              @click="buildReport"
            >
              <Icon name="file" :size="15" /> 生成分析报告
            </button>
          </div>
        </div>
      </div>
      <div v-else class="card empty-state"><b>暂无分析数据</b>请确认该电机已有采集读数。</div>
    </div>

    <!-- 同类对比 -->
    <div v-if="mode === 'peer' && !loading" class="panel" id="panel-peer">
      <div v-if="peerData" class="ana-grid">
        <div class="card">
          <div class="card-head">
            <h3>同功率 · 同工况电机组对比</h3>
            <div class="right">
              <div class="seg">
                <button
                  v-for="group in peerData.groups"
                  :key="group"
                  :class="{ active: peerGroup === group }"
                  @click="selectPeerGroup(group)"
                >
                  {{ group }}
                </button>
              </div>
            </div>
            <div class="sub">同类电机比：同功率、同工况电机之间比，看哪台明显异常</div>
          </div>
          <div v-if="peerData.motors.length" class="peer-bars">
            <div v-for="metric in peerMetrics" :key="metric.name" class="peer-metric">
              <div class="peer-metric-head">
                <b>{{ metric.name }}</b><span>{{ metric.unit }}</span>
              </div>
              <div
                v-for="motor in peerData.motors"
                :key="`${metric.name}-${motor.code}`"
                class="peer-bar-row"
              >
                <span class="who" :style="{ color: colorFor(motor.code) }" :title="motor.name">{{
                  motor.code
                }}</span>
                <div class="track">
                  <i
                    :style="{
                      width: `${barWidth(motor[metric.key], metric.max)}%`,
                      background: `linear-gradient(90deg, ${colorFor(motor.code)}55, ${colorFor(motor.code)})`,
                    }"
                  />
                </div>
                <span class="val num"
                  >{{ fmt(motor[metric.key], metric.dec) }} {{ metric.unit }}</span
                >
              </div>
            </div>
          </div>
          <div v-else class="chart-empty" style="height: 280px">该分组暂无读数</div>
          <div class="peer-footer">
            <div>
              <span>对比组</span><b>{{ peerData.group }}</b>
            </div>
            <div>
              <span>组内电机</span><b>{{ peerData.motors.length }} 台</b>
            </div>
            <div>
              <span>最高偏离</span
              ><b>{{ peerData.ranking[0]?.code || '—' }} · {{ fmt(peerData.ranking[0]?.score) }}</b>
            </div>
            <p>偏离度基于自身 30 天正常基线；数值为当前或所选日期末值。</p>
          </div>
        </div>
        <div class="card peer-right">
          <div class="card-head">
            <h3>综合偏离排名</h3>
            <div class="sub">温度 / 电流偏离基线的加权得分，越高越异常</div>
          </div>
          <div class="rank-list">
            <div
              v-for="item in peerData.ranking"
              :key="item.code"
              :class="['rank-item', item.rank === 1 && item.score > 8 ? 'top' : '']"
            >
              <span class="no">{{ item.rank }}</span>
              <div style="width: 110px; flex: none">
                <b style="font-size: 12.5px">{{ item.code }}</b>
                <div style="font-size: 10.5px; color: var(--faint)">{{ item.name }}</div>
              </div>
              <div class="bar">
                <i
                  :style="{
                    width: `${Math.min(100, (item.score / peerMaxScore) * 100)}%`,
                    background:
                      item.rank === 1 && item.score > 8
                        ? 'linear-gradient(90deg,#FF4D6D,#FF7A45)'
                        : 'linear-gradient(90deg,#2DD4EE,#4F8CFF)',
                  }"
                />
              </div>
              <span
                class="val num"
                :style="{ color: item.rank === 1 && item.score > 8 ? '#FF8296' : '' }"
                >{{ fmt(item.score) }}</span
              >
            </div>
          </div>
          <div class="peer-score-note">
            <b>评分口径</b>
            <span
              >综合得分 = 0.6 × 温度偏离 + 0.4 ×
              电流偏离，仅统计正向偏离；振动总值按 mm/s 并列参与同类对比。</span
            >
          </div>
          <div class="insight">
            <Icon name="info" :size="16" /><span>{{ peerData.insight }}</span>
          </div>
        </div>
      </div>
      <div v-else class="card empty-state"><b>暂无同类对比数据</b>请确认电机分组与采集读数。</div>
    </div>

    <!-- 四象限 -->
    <div v-if="mode === 'quad' && !loading" class="panel" id="panel-quad">
      <div v-if="quadData" class="ana-grid">
        <div class="card">
          <div class="card-head">
            <h3>温度 × 电流四象限关联图</h3>
            <div class="right">
              <span class="badge mut">全部 {{ quadData.points.length }} 台 · 偏离基线 %</span>
            </div>
            <div class="sub">温度 + 电流一起看：两个维度交叉定位故障方向，点击数据点查看电机</div>
          </div>
          <div class="chart-wrap">
            <QuadrantChart
              v-if="quadData.points.length"
              :points="quadData.points"
              :selected="selectedQuadPoint?.code || null"
              :height="430"
              fill
              @select="selectedQuad = $event"
            />
            <div v-else class="chart-empty" style="height: 410px">暂无基线样本</div>
          </div>
        </div>
        <div class="card">
          <div class="card-head">
            <h3>象限解读</h3>
            <div class="sub">规则来自现场运维经验，领导看得懂</div>
          </div>
          <div class="quadrant-legend">
            <div class="quadrant-item">
              <i style="background: #ff4d6d" />
              <div>
                <b>左上 · 温度高 / 电流正常</b>
                <p>可能是散热、轴承或润滑问题。优先检查风道与温升。</p>
              </div>
            </div>
            <div class="quadrant-item">
              <i style="background: #ffb224" />
              <div>
                <b>右下 · 温度正常 / 电流异常</b>
                <p>可能是负载或电气问题。检查变频器输出与负载侧阻力。</p>
              </div>
            </div>
            <div class="quadrant-item">
              <i style="background: #f06ad8" />
              <div>
                <b>右上 · 双高</b>
                <p>过载或综合劣化，需立即核查负载与机械状态。</p>
              </div>
            </div>
            <div class="quadrant-item">
              <i style="background: #2ed3a3" />
              <div>
                <b>左下 · 双正常</b>
                <p>运行健康，保持例行监测即可。</p>
              </div>
            </div>
          </div>
          <div v-if="selectedQuadPoint" class="quadrant-detail">
            <h4 style="margin-bottom: 10px">选中电机</h4>
            <div class="info-grid">
              <div class="info-cell">
                <div class="l">电机</div>
                <div class="v">{{ selectedQuadPoint.code }} · {{ selectedQuadPoint.name }}</div>
              </div>
              <div class="info-cell">
                <div class="l">判定</div>
                <div
                  class="v"
                  :style="{ color: judgePoint(selectedQuadPoint).color, fontSize: '12px' }"
                >
                  {{ judgePoint(selectedQuadPoint).text }}
                </div>
              </div>
              <div class="info-cell">
                <div class="l">温度偏离</div>
                <div class="v num" style="color: #ffc65c">
                  {{ signed(selectedQuadPoint.temp_deviation_pct) }} %
                </div>
              </div>
              <div class="info-cell">
                <div class="l">电流偏离</div>
                <div class="v num" style="color: #7fe7f7">
                  {{ signed(selectedQuadPoint.current_deviation_pct) }} %
                </div>
              </div>
            </div>
            <button
              class="btn btn-ghost btn-sm"
              style="margin-top: 12px; width: 100%; justify-content: center"
              @click="openMotor(selectedQuadPoint.code)"
            >
              <Icon name="eye" :size="14" /> 打开电机详情
            </button>
          </div>
        </div>
      </div>
      <div v-else class="card empty-state">
        <b>暂无关联数据</b>请确认至少一台电机具有 30 天基线样本。
      </div>
    </div>

    <!-- 趋势 -->
    <div v-if="mode === 'trend' && !loading" class="panel" id="panel-trend">
      <div v-if="trendData" class="card">
        <div class="card-head">
          <h3>走势与事件标注</h3>
          <div class="right">
            <div class="seg">
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
          <div class="sub">趋势比较：看一天、一周、一月的走势，判断是偶发还是持续恶化</div>
        </div>
        <div class="chart-wrap">
          <LineChart
            v-if="trendSeries?.points.length"
            :labels="trendLabels"
            :series="[
              { name: '外壳温度', color: '#FFB224', data: trendTemp, unit: '°C', area: true },
              { name: '运行电流', color: '#2DD4EE', data: trendCurrent, unit: 'A', yAxisIndex: 1 },
            ]"
            :markers="trendMarkers"
            :thresholds="[
              {
                value: trendData.motor.temp_limit_c,
                label: `上限 ${trendData.motor.temp_limit_c}°C`,
                color: '#FF4D6D',
              },
            ]"
            :height="340"
            fill
            y2
          />
          <div v-else class="chart-empty" style="height: 320px">暂无趋势数据</div>
        </div>
        <div class="trend-stats">
          <div class="loop-stat">
            <div class="v num" style="color: #ff8296; font-size: 18px">
              {{ fmt(trendData.stats.max_temp_c) }} °C
            </div>
            <div class="l">最高温度</div>
          </div>
          <div class="loop-stat">
            <div class="v num" style="color: #7fe7f7; font-size: 18px">
              {{ fmt(trendData.stats.min_temp_c) }} °C
            </div>
            <div class="l">最低温度</div>
          </div>
          <div class="loop-stat">
            <div class="v num" style="color: #ffc65c; font-size: 18px">
              {{ fmt(trendData.stats.avg_temp_c) }} °C
            </div>
            <div class="l">平均温度</div>
          </div>
          <div class="loop-stat">
            <div
              class="v num"
              :style="{
                color: (trendData.stats.slope_c_per_day || 0) > 1 ? '#FF8296' : '#5FE3BB',
                fontSize: '18px',
              }"
            >
              {{ signed(trendData.stats.slope_c_per_day, 2) }} °C/天
            </div>
            <div class="l">温升速率（{{ trendData.stats.sample_days }} 天）</div>
          </div>
        </div>
        <div class="insight" style="border-top: 1px solid var(--line-soft)">
          <Icon :name="trendData.verdict.bad ? 'alert' : 'checkc'" :size="16" />
          <span style="flex: 1">{{ trendData.verdict.text }}</span>
          <span :class="['verdict', trendData.verdict.bad ? 'bad' : 'good']">{{
            trendData.verdict.tag
          }}</span>
        </div>
        <div v-if="trendData.events.length" class="drawer-sec" style="padding: 10px 20px 0">
          <h4>区间事件</h4>
          <div
            v-for="event in trendData.events"
            :key="event.id"
            class="loop-item"
            style="cursor: pointer"
            @click="openAlarm(Number(event.id.replace('AL-', '')))"
          >
            <Icon :name="event.status === 'closed' ? 'checkc' : 'alert'" :size="15" />
            <span>{{ event.id }} {{ event.title }}</span>
            <time>{{ dateTime(event.ts) }}</time>
          </div>
        </div>
      </div>
      <div v-else class="card empty-state"><b>暂无趋势数据</b>请确认该电机已有采集读数。</div>
    </div>

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
    <BaseModal
      :open="reportOpen"
      title="分析报告"
      subtitle="可直接下载 Markdown 或复制到飞书文档"
      @close="reportOpen = false"
    >
      <pre class="report-pre">{{ reportText }}</pre>
      <div class="report-actions">
        <button class="btn btn-ghost" @click="copyReport">
          <Icon name="file" :size="15" /> 复制全文
        </button>
        <button class="btn btn-primary" @click="downloadReport">
          <Icon name="download" :size="15" /> 下载 .md
        </button>
      </div>
    </BaseModal>
  </section>
</template>

<style scoped>
#view-analysis {
  min-height: calc(100vh - var(--topbar-h) - 52px);
  display: flex;
  flex-direction: column;
}
#view-analysis .panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
#view-analysis .ana-grid {
  flex: 1;
  width: 100%;
  align-items: stretch;
}
#view-analysis .ana-grid > .card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
#view-analysis .ana-grid .chart-wrap {
  flex: 1;
  min-height: 280px;
  display: flex;
  flex-direction: column;
}
#view-analysis .ana-grid .chart-wrap > .line-chart {
  flex: 1;
  min-height: 280px;
}
#view-analysis #panel-trend > .card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: calc(100vh - 230px);
}
#view-analysis #panel-trend .chart-wrap {
  flex: 1;
  min-height: 320px;
}
#view-analysis #panel-trend .chart-wrap > .line-chart {
  flex: 1;
  min-height: 320px;
}
#view-analysis .ana-grid > .card {
  overflow: hidden;
}
#view-analysis .peer-footer {
  margin-top: auto;
  padding: 14px 20px 18px;
  border-top: 1px solid var(--line-soft);
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
#view-analysis .peer-footer div {
  min-width: 90px;
}
#view-analysis .peer-footer span {
  display: block;
  font-size: 10.5px;
  color: var(--faint);
}
#view-analysis .peer-footer b {
  display: block;
  margin-top: 2px;
  font-size: 13px;
  color: var(--text);
}
#view-analysis .peer-footer p {
  flex-basis: 100%;
  margin-top: 2px;
  font-size: 11px;
  color: var(--faint);
}
#view-analysis .peer-right {
  display: flex;
  flex-direction: column;
}
#view-analysis .peer-right .rank-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
}
#view-analysis .peer-right .peer-score-note {
  padding: 12px 20px;
  border-top: 1px solid var(--line-soft);
  font-size: 11.5px;
  color: var(--faint);
  line-height: 1.6;
}
#view-analysis .peer-right .peer-score-note b {
  display: block;
  color: var(--text);
  font-size: 12px;
  margin-bottom: 3px;
}
#view-analysis .peer-right .insight {
  border-top: 1px solid var(--line-soft);
}
#view-analysis #panel-peer .peer-bars {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
}
#view-analysis #panel-peer .peer-metric {
  margin-bottom: 0;
}
#view-analysis #panel-self > .ana-grid > .card:first-child .chart-wrap {
  min-height: 320px;
}
@media (max-width: 1200px) {
  #view-analysis {
    min-height: 0;
  }
  #view-analysis .ana-grid,
  #view-analysis #panel-trend > .card {
    min-height: 0;
    height: auto;
  }
  #view-analysis .ana-grid .chart-wrap,
  #view-analysis #panel-trend .chart-wrap {
    min-height: 300px;
  }
}
</style>
