<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fmt } from '@/utils/format'

export interface ChartSeries {
  name: string
  color: string
  data: (number | null)[]
  yAxisIndex?: 0 | 1 | 2
  unit?: string
  area?: boolean
  width?: number
  dashed?: boolean
}

export interface ChartThreshold {
  value: number
  label: string
  color: string
  yAxisIndex?: 0 | 1 | 2
}

export interface ChartMarker {
  index: number
  label: string
  color: string
}

export interface ChartBand {
  lo: (number | null)[]
  hi: (number | null)[]
}

const props = withDefaults(
  defineProps<{
    labels: string[]
    series: ChartSeries[]
    thresholds?: ChartThreshold[]
    band?: ChartBand | null
    markers?: ChartMarker[]
    height?: number
    fill?: boolean
    y2?: boolean
    y3?: boolean
    y1Name?: string
    y2Name?: string
    y3Name?: string
  }>(),
  {
    thresholds: () => [],
    band: null,
    markers: () => [],
    height: 300,
    fill: false,
    y2: false,
    y3: false,
    y1Name: '',
    y2Name: '',
    y3Name: '',
  },
)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

function colorWithAlpha(hex: string, alpha: number): string {
  const normalized = hex.replace('#', '')
  if (normalized.length !== 6) return hex
  const red = Number.parseInt(normalized.slice(0, 2), 16)
  const green = Number.parseInt(normalized.slice(2, 4), 16)
  const blue = Number.parseInt(normalized.slice(4, 6), 16)
  return `rgba(${red},${green},${blue},${alpha})`
}

function axisNumber(value: number): string {
  return Math.abs(value) >= 100 ? fmt(value, 0) : fmt(value, 1)
}

function buildMarkLine() {
  const anchorIndex = Math.max(
    0,
    props.series.findIndex((item) => (item.yAxisIndex || 0) === 0),
  )
  const anchor = props.series[anchorIndex]
  if (!anchor) return { seriesIndex: -1, data: [] as Record<string, unknown>[] }
  const data: Record<string, unknown>[] = []
  props.thresholds.forEach((threshold) => {
    if ((threshold.yAxisIndex || 0) !== (anchor.yAxisIndex || 0)) return
    data.push({
      yAxis: threshold.value,
      label: {
        formatter: threshold.label,
        color: threshold.color,
        fontSize: 10,
        fontWeight: 600,
        position: 'insideEndTop',
      },
      lineStyle: { color: threshold.color, type: 'dashed', width: 1.3, opacity: 0.8 },
    })
  })
  props.markers.forEach((marker) => {
    const label = props.labels[marker.index]
    if (!label) return
    data.push({
      xAxis: label,
      label: {
        formatter: marker.label,
        color: marker.color,
        fontSize: 9.5,
        position: 'insideEndTop',
      },
      lineStyle: { color: marker.color, type: 'dashed', width: 1, opacity: 0.55 },
    })
  })
  return { seriesIndex: anchorIndex, data }
}

function buildOption(): echarts.EChartsOption {
  const yAxis: echarts.YAXisComponentOption[] = [
    {
      type: 'value',
      name: props.y1Name,
      nameTextStyle: { color: '#5B6A8C', fontSize: 10.5, padding: [0, 0, 4, 0] },
      scale: true,
      axisLabel: { color: '#5B6A8C', fontSize: 10.5, formatter: axisNumber },
      splitLine: { lineStyle: { color: 'rgba(148,163,204,.10)' } },
      axisLine: { show: false },
      axisTick: { show: false },
    },
  ]
  if (props.y2) {
    yAxis.push({
      type: 'value',
      name: props.y2Name,
      position: 'right',
      nameTextStyle: { color: '#5B6A8C', fontSize: 10.5, padding: [0, 0, 4, 0] },
      scale: true,
      axisLabel: { color: '#5B6A8C', fontSize: 10.5, formatter: axisNumber },
      splitLine: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
    })
  }
  if (props.y3) {
    yAxis.push({
      type: 'value',
      name: props.y3Name,
      position: 'right',
      offset: 48,
      nameTextStyle: { color: '#5B6A8C', fontSize: 10.5, padding: [0, 0, 4, 0] },
      scale: true,
      axisLabel: { color: '#5B6A8C', fontSize: 10.5, formatter: axisNumber },
      splitLine: { show: false },
      axisLine: { show: false },
      axisTick: { show: false },
    })
  }

  const markLine = buildMarkLine()
  const series: echarts.SeriesOption[] = []

  if (props.band) {
    const bandLo = props.band.lo
    const bandHi = props.band.hi.map((value, index) => {
      const low = bandLo[index]
      if (value === null || low === null || value === undefined || low === undefined) return null
      return Number((value - low).toFixed(3))
    })
    series.push({
      name: '__band_low',
      type: 'line',
      data: bandLo,
      stack: 'band',
      symbol: 'none',
      silent: true,
      lineStyle: { color: 'rgba(255,178,36,.28)', width: 1, type: 'dashed' },
      areaStyle: { opacity: 0 },
      z: 1,
      tooltip: { show: false },
    })
    series.push({
      name: '__band_high',
      type: 'line',
      data: bandHi,
      stack: 'band',
      symbol: 'none',
      silent: true,
      lineStyle: { color: 'rgba(255,178,36,.28)', width: 1, type: 'dashed' },
      areaStyle: { color: 'rgba(255,178,36,.12)' },
      z: 1,
      tooltip: { show: false },
    })
  }

  props.series.forEach((item, index) => {
    const yAxisIndex = item.yAxisIndex || 0
    series.push({
      name: item.name,
      type: 'line',
      data: item.data,
      yAxisIndex,
      smooth: true,
      showSymbol: false,
      connectNulls: true,
      lineStyle: {
        color: item.color,
        width: item.width || 2.2,
        type: item.dashed ? 'dashed' : 'solid',
      },
      itemStyle: { color: item.color },
      areaStyle: item.area
        ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: colorWithAlpha(item.color, 0.26) },
              { offset: 1, color: colorWithAlpha(item.color, 0) },
            ]),
          }
        : undefined,
      emphasis: { focus: 'series' },
      z: 3,
      markLine:
        index === markLine.seriesIndex && markLine.data.length
          ? {
              silent: true,
              symbol: 'none',
              animation: false,
              data: markLine.data,
            }
          : undefined,
    } as echarts.SeriesOption)
  })

  return {
    backgroundColor: 'transparent',
    animationDuration: 280,
    textStyle: {
      fontFamily: "Inter, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
    },
    grid: { left: 48, right: props.y3 ? 90 : props.y2 ? 54 : 20, top: 24, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(13,20,36,.96)',
      borderColor: 'rgba(148,163,204,.14)',
      borderWidth: 1,
      padding: [10, 13],
      textStyle: { color: '#E9EFFC', fontSize: 12 },
      axisPointer: {
        type: 'line',
        lineStyle: { color: 'rgba(233,239,252,.28)', type: 'dashed' },
      },
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params : [params]
        const rows = items
          .filter((item: { seriesName?: string }) => !item.seriesName?.startsWith('__'))
          .map((item: { marker?: string; seriesName?: string; value?: number | null }) => {
            const source = props.series.find((entry) => entry.name === item.seriesName)
            const unit = source?.unit || ''
            const value = typeof item.value === 'number' ? fmt(item.value, 1) : '—'
            return `<div style="display:flex;align-items:center;gap:7px;margin-top:3px">${item.marker || ''}${item.seriesName}<b style="margin-left:auto;padding-left:16px;font-variant-numeric:tabular-nums">${value} ${unit}</b></div>`
          })
          .join('')
        return `<div style="font-size:11px;color:#5B6A8C;margin-bottom:5px">${items[0]?.axisValueLabel || ''}</div>${rows}`
      },
    },
    xAxis: {
      type: 'category',
      data: props.labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'rgba(148,163,204,.16)' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#5B6A8C',
        fontSize: 10.5,
        hideOverlap: true,
        margin: 10,
      },
    },
    yAxis,
    series,
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
    useDirtyRect: true,
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
  () => [props.labels, props.series, props.thresholds, props.band, props.markers, props.y2, props.y3],
  () => render(),
  { deep: true },
)
</script>

<template>
  <div
    ref="el"
    class="line-chart"
    :style="
      props.fill
        ? { height: '100%', minHeight: `${props.height}px` }
        : { height: `${props.height}px` }
    "
  />
</template>
