<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    data: number[]
    color?: string
    width?: number
    height?: number
  }>(),
  { color: '#2DD4EE', width: 100, height: 30 },
)

let uid = 0
const gradientId = `spark-${++uid}-${Math.random().toString(36).slice(2, 7)}`

function smoothPath(points: [number, number][]): string {
  if (points.length < 3) {
    return points
      .map((point, index) => `${index === 0 ? 'M' : 'L'}${point[0]} ${point[1]}`)
      .join(' ')
  }
  let path = `M ${points[0][0]} ${points[0][1]}`
  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[Math.max(0, index - 1)]
    const p1 = points[index]
    const p2 = points[index + 1]
    const p3 = points[Math.min(points.length - 1, index + 2)]
    const c1x = p1[0] + (p2[0] - p0[0]) / 6
    const c1y = p1[1] + (p2[1] - p0[1]) / 6
    const c2x = p2[0] - (p3[0] - p1[0]) / 6
    const c2y = p2[1] - (p3[1] - p1[1]) / 6
    path += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2[0]} ${p2[1]}`
  }
  return path
}

const geometry = computed(() => {
  const values = props.data.filter((value) => Number.isFinite(value))
  if (!values.length) return null
  const width = props.width
  const height = props.height
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const pad = (hi - lo) * 0.15 || 1
  const x = (index: number) =>
    values.length === 1 ? width / 2 : 2 + ((width - 4) * index) / (values.length - 1)
  const y = (value: number) => 3 + (height - 8) * (1 - (value - lo + pad) / (hi - lo + pad * 2))
  const points = values.map((value, index) => [x(index), y(value)] as [number, number])
  const line = smoothPath(points)
  const last = points[points.length - 1]
  const area = `${line} L ${points[points.length - 1][0]} ${height} L ${points[0][0]} ${height} Z`
  return { line, area, last, width, height }
})
</script>

<template>
  <svg
    v-if="geometry"
    class="spark"
    :viewBox="`0 0 ${geometry.width} ${geometry.height}`"
    preserveAspectRatio="none"
  >
    <defs>
      <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" :stop-color="props.color" stop-opacity=".3" />
        <stop offset="1" :stop-color="props.color" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path :d="geometry.area" :fill="`url(#${gradientId})`" />
    <path
      :d="geometry.line"
      fill="none"
      :stroke="props.color"
      stroke-width="1.8"
      stroke-linecap="round"
      vector-effect="non-scaling-stroke"
    />
    <circle :cx="geometry.last[0]" :cy="geometry.last[1]" r="2.6" :fill="props.color" />
  </svg>
  <svg
    v-else
    class="spark"
    :viewBox="`0 0 ${props.width} ${props.height}`"
    preserveAspectRatio="none"
  >
    <line
      x1="2"
      :y1="props.height / 2"
      :x2="props.width - 2"
      :y2="props.height / 2"
      stroke="rgba(148,163,204,.25)"
      stroke-width="1.5"
      stroke-dasharray="3 4"
    />
  </svg>
</template>
