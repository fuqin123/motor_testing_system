<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import type { QuadrantPoint } from '@/api/types'
import { fmt } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    points: QuadrantPoint[]
    selected?: string | null
    mini?: boolean
    height?: number
  }>(),
  { selected: null, mini: false, height: 430 },
)

const emit = defineEmits<{ select: [code: string] }>()
const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

const COLORS: Record<string, string> = {
  ok: '#2ED3A3',
  warn: '#FFB224',
  crit: '#FF4D6D',
  unknown: '#8E9BB8',
}

function domain(values: number[], fallbackMin: number, fallbackMax: number): [number, number] {
  if (!values.length) return [fallbackMin, fallbackMax]
  const low = Math.min(fallbackMin, ...values)
  const high = Math.max(fallbackMax, ...values)
  return [Math.floor(low - 5), Math.ceil(high + 5)]
}

function buildOption(): echarts.EChartsOption {
  const xs = props.points.map((point) => point.current_deviation_pct)
  const ys = props.points.map((point) => point.temp_deviation_pct)
  const [xMin, xMax] = domain(xs, -10, 22)
  const [yMin, yMax] = domain(ys, -10, 30)
  const labelSize = props.mini ? 10 : 11.5
  const symbolSize = props.mini ? 9 : 13

  const data = props.points.map((point) => ({
    value: [point.current_deviation_pct, point.temp_deviation_pct],
    code: point.code,
    name: point.name,
    status: point.status,
    symbolSize: props.selected === point.code ? symbolSize + 5 : symbolSize,
    itemStyle: {
      color: COLORS[point.status] || COLORS.unknown,
      borderColor: props.selected === point.code ? '#E9EFFC' : '#0D1424',
      borderWidth: props.selected === point.code ? 2.2 : 2,
      shadowBlur: point.status === 'ok' ? 0 : 12,
      shadowColor: COLORS[point.status] || COLORS.unknown,
    },
  }))

  return {
    backgroundColor: 'transparent',
    animationDuration: 450,
    grid: props.mini
      ? { left: 42, right: 16, top: 20, bottom: 28 }
      : { left: 54, right: 22, top: 28, bottom: 42 },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(13,20,36,.96)',
      borderColor: 'rgba(148,163,204,.14)',
      textStyle: { color: '#E9EFFC', fontSize: 12 },
      formatter: (params: any) => {
        const item = params.data
        if (!item?.value) return ''
        return `<div style="font-size:11px;color:#5B6A8C;margin-bottom:4px">${item.code} · ${item.name}</div>
          <div style="display:flex;gap:8px"><span style="color:#FFB224">温度偏离</span><b style="margin-left:auto">${fmt(item.value[1])}%</b></div>
          <div style="display:flex;gap:8px"><span style="color:#2DD4EE">电流偏离</span><b style="margin-left:auto">${fmt(item.value[0])}%</b></div>`
      },
    },
    xAxis: {
      type: 'value',
      min: xMin,
      max: xMax,
      axisLabel: {
        color: '#5B6A8C',
        fontSize: 10,
        formatter: (value: number) => `${value > 0 ? '+' : ''}${fmt(value, 0)}%`,
      },
      splitLine: { show: false },
      axisLine: { lineStyle: { color: 'rgba(148,163,204,.16)' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: yMin,
      max: yMax,
      axisLabel: {
        color: '#5B6A8C',
        fontSize: 10,
        formatter: (value: number) => `${value > 0 ? '+' : ''}${fmt(value, 0)}%`,
      },
      splitLine: { lineStyle: { color: 'rgba(148,163,204,.07)' } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    graphic: [
      {
        type: 'text',
        left: props.mini ? '14%' : '10%',
        top: '12%',
        style: {
          text: props.mini ? '散热 · 轴承' : '温度高 · 电流正常',
          fill: '#FF8296',
          font: `600 ${labelSize}px Inter, sans-serif`,
        },
      },
      {
        type: 'text',
        right: props.mini ? '10%' : '8%',
        top: '12%',
        style: {
          text: props.mini ? '双高 · 过载' : '双高 · 过载',
          fill: '#F06AD8',
          font: `600 ${labelSize}px Inter, sans-serif`,
        },
      },
      {
        type: 'text',
        right: props.mini ? '10%' : '8%',
        bottom: '16%',
        style: {
          text: props.mini ? '负载 · 电气' : '温度正常 · 电流异常',
          fill: '#FFC65C',
          font: `600 ${labelSize}px Inter, sans-serif`,
        },
      },
      {
        type: 'text',
        left: props.mini ? '14%' : '10%',
        bottom: '16%',
        style: {
          text: props.mini ? '运行健康' : '双正常 · 运行健康',
          fill: '#5FE3BB',
          font: `600 ${labelSize}px Inter, sans-serif`,
        },
      },
    ],
    series: [
      {
        type: 'scatter',
        data,
        z: 5,
        label: {
          show: true,
          formatter: (params: any) => params.data?.code || '',
          position: 'right',
          color: '#8E9BB8',
          fontSize: props.mini ? 9.5 : 11,
          fontWeight: 700,
        },
        emphasis: { scale: 1.25 },
        markArea: {
          silent: true,
          label: { show: false },
          data: [
            [
              { coord: [xMin, 0], itemStyle: { color: 'rgba(255,77,109,.055)' } },
              { coord: [0, yMax] },
            ],
            [
              { coord: [0, 0], itemStyle: { color: 'rgba(240,106,216,.05)' } },
              { coord: [xMax, yMax] },
            ],
            [
              { coord: [0, yMin], itemStyle: { color: 'rgba(255,178,36,.05)' } },
              { coord: [xMax, 0] },
            ],
            [
              { coord: [xMin, yMin], itemStyle: { color: 'rgba(46,211,163,.05)' } },
              { coord: [0, 0] },
            ],
          ],
        },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: 'rgba(233,239,252,.28)', width: 1.1 },
          data: [{ xAxis: 0 }, { yAxis: 0 }],
        },
      },
    ],
  }
}

function render() {
  if (!chart) return
  chart.setOption(buildOption(), true)
}

onMounted(() => {
  if (!el.value) return
  chart = echarts.init(el.value, undefined, {
    width: el.value.clientWidth || 600,
    height: el.value.clientHeight || props.height,
  })
  chart.on('click', (params) => {
    const code = (params.data as { code?: string } | undefined)?.code
    if (code) emit('select', code)
  })
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(el.value)
  render()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  chart = null
})

watch(
  () => [props.points, props.selected],
  () => render(),
  { deep: true },
)
</script>

<template>
  <div ref="el" class="line-chart" :style="{ height: `${props.height}px` }" />
  <div v-if="!props.mini" class="quadrant-axis-hint">
    <span>纵轴 · 温度偏离 ↑</span>
    <span>横轴 · 电流偏离 / 波动 →</span>
  </div>
</template>

<style scoped>
.quadrant-axis-hint {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 0 24px 6px;
  font-size: 11px;
  color: var(--faint);
}
</style>
