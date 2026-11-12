<script setup lang="ts">
import { computed } from 'vue'

import { clamp } from '@/utils/format'

const props = withDefaults(defineProps<{ value: number | null; max?: number }>(), { max: 30 })

const geo = computed(() => {
  const value = clamp(props.value ?? 0, 0, props.max)
  const fraction = value / props.max
  const cx = 90
  const cy = 92
  const radius = 74
  const start = Math.PI
  const end = Math.PI * (1 - fraction)
  const point = (angle: number): [number, number] => [
    cx + radius * Math.cos(angle),
    cy - radius * Math.sin(angle),
  ]
  const arc = (a: number, b: number, color: string, width: number) => {
    const [x1, y1] = point(a)
    const [x2, y2] = point(b)
    const large = b - a > Math.PI ? 1 : 0
    return `<path d="M ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round"/>`
  }
  const color = value >= 15 ? '#FF4D6D' : value >= 8 ? '#FFB224' : '#2ED3A3'
  const ticks = [0, 5, 15, 30]
    .map((tick) => {
      const angle = Math.PI * (1 - tick / props.max)
      const x = cx + (radius + 13) * Math.cos(angle)
      const y = cy - (radius + 13) * Math.sin(angle)
      return `<text x="${x}" y="${y + 3}" text-anchor="middle" font-size="9.5" fill="#5B6A8C">${tick}</text>`
    })
    .join('')
  return {
    background: arc(Math.PI, 0, '#1B2742', 11),
    foreground: fraction > 0.005 ? arc(start, end, color, 11) : '',
    ticks,
    color,
  }
})
</script>

<template>
  <svg width="180" height="104" viewBox="0 0 180 104">
    <g v-html="geo.background" />
    <g v-if="geo.foreground" v-html="geo.foreground" />
    <g v-html="geo.ticks" />
  </svg>
</template>
