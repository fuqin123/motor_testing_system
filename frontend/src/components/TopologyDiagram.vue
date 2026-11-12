<script setup lang="ts">
import { computed } from 'vue'

import { ICON_PATHS } from '@/utils/icons'

interface TopoNode {
  key: string
  x: number
  y: number
  w: number
  h: number
  icon: string
  color: string
  title: string
  sub: string
}

interface TopoEdge {
  id: string
  d: string
  color: string
  dash?: boolean
  label?: string
  labelX?: number
  labelY?: number
  animate?: boolean
}

const props = defineProps<{
  tempCount: number
  currentCount: number
  nodeCount: number
  gatewayCount: number
  gatewayCode: string
  gatewayOnline: number
  baudRate: number
  packetSummary: string
}>()

const emit = defineEmits<{ select: [key: string] }>()

const nodes = computed<TopoNode[]>(() => [
  {
    key: 'sensors',
    x: 40,
    y: 56,
    w: 172,
    h: 62,
    icon: 'thermo',
    color: '#FFB224',
    title: `温度传感器 ×${props.tempCount}`,
    sub: 'PT100 · 外壳 / 轴承端盖',
  },
  {
    key: 'collector',
    x: 40,
    y: 156,
    w: 172,
    h: 62,
    icon: 'cpu',
    color: '#FFB224',
    title: 'RS485 采集模块',
    sub: 'Modbus RTU 汇聚',
  },
  {
    key: 'vfd',
    x: 40,
    y: 256,
    w: 172,
    h: 62,
    icon: 'zap',
    color: '#2DD4EE',
    title: `变频器 485 ×${props.currentCount}`,
    sub: '协议开放 · 读取电流',
  },
  {
    key: 'nodes',
    x: 368,
    y: 116,
    w: 180,
    h: 84,
    icon: 'radio',
    color: '#9D7CFF',
    title: `LoRa 采集节点 ×${props.nodeCount}`,
    sub: '顺序采集 · 15 分钟',
  },
  {
    key: 'gateway',
    x: 368,
    y: 282,
    w: 180,
    h: 70,
    icon: 'router',
    color: '#9D7CFF',
    title:
      props.gatewayCount === 1
        ? `LoRa 网关 ${props.gatewayCode}`
        : `LoRa 网关 ×${props.gatewayCount}`,
    sub: `470MHz · ${props.baudRate} bps · 网口上联`,
  },
  {
    key: 'server',
    x: 692,
    y: 76,
    w: 176,
    h: 64,
    icon: 'server',
    color: '#4F8CFF',
    title: '后台服务',
    sub: 'FastAPI · 本地部署',
  },
  {
    key: 'database',
    x: 692,
    y: 196,
    w: 176,
    h: 64,
    icon: 'db',
    color: '#4F8CFF',
    title: '本地数据库',
    sub: 'PostgreSQL · 数据不出厂',
  },
  {
    key: 'analysis',
    x: 692,
    y: 316,
    w: 176,
    h: 64,
    icon: 'activity',
    color: '#4F8CFF',
    title: '对比分析引擎',
    sub: '自身 / 同类 / 关联 / 趋势',
  },
  {
    key: 'dashboard',
    x: 968,
    y: 56,
    w: 168,
    h: 62,
    icon: 'grid',
    color: '#2ED3A3',
    title: '监测看板',
    sub: '集中监测 · 本页面',
  },
  {
    key: 'feishu',
    x: 968,
    y: 176,
    w: 168,
    h: 62,
    icon: 'send',
    color: '#FFB224',
    title: '飞书通知',
    sub: '异常直达责任人',
  },
  {
    key: 'maintenance',
    x: 968,
    y: 296,
    w: 168,
    h: 62,
    icon: 'wrench',
    color: '#2ED3A3',
    title: '人工检查 / 维修',
    sub: '处理结果回写数据库',
  },
])

const edges = computed<TopoEdge[]>(() => [
  { id: 't-r', d: 'M 126 118 L 126 156', color: '#FFB224' },
  {
    id: 'r-n',
    d: 'M 212 187 C 290 187, 290 157, 368 157',
    color: '#2DD4EE',
    animate: true,
  },
  {
    id: 'v-n',
    d: 'M 212 287 C 290 287, 290 159, 368 159',
    color: '#2DD4EE',
  },
  {
    id: 'n-g',
    d: 'M 458 200 L 458 282',
    color: '#9D7CFF',
    label: 'LoRa 无线',
    labelX: 468,
    labelY: 245,
    animate: true,
  },
  {
    id: 'g-s',
    d: 'M 548 317 C 620 317, 620 108, 692 108',
    color: '#9D7CFF',
    label: '网口 / 厂区网络',
    labelX: 620,
    labelY: 208,
    animate: true,
  },
  { id: 's-d', d: 'M 780 140 L 780 196', color: '#4F8CFF' },
  { id: 'd-a', d: 'M 780 260 L 780 316', color: '#4F8CFF' },
  {
    id: 'a-b',
    d: 'M 868 348 C 918 348, 918 87, 968 87',
    color: '#2ED3A3',
    label: '正常',
    labelX: 918,
    labelY: 212,
  },
  {
    id: 'a-f',
    d: 'M 868 348 C 918 348, 918 207, 968 207',
    color: '#FFB224',
    label: '异常',
    labelX: 918,
    labelY: 270,
    animate: true,
  },
  { id: 'f-h', d: 'M 1052 238 L 1052 296', color: '#FFB224' },
  {
    id: 'h-d',
    d: 'M 968 327 C 908 387, 928 288, 872 232',
    color: '#2ED3A3',
    dash: true,
    label: '处理结果回写',
    labelX: 918,
    labelY: 372,
  },
])

const bands = [
  { x: 16, w: 224, title: '现场采集层', color: '#FFB224' },
  { x: 344, w: 228, title: '无线传输层', color: '#9D7CFF' },
  { x: 668, w: 224, title: '后台平台层', color: '#4F8CFF' },
  { x: 944, w: 216, title: '应用处理层', color: '#2ED3A3' },
]

function nodeColor(key: string): string {
  if (key === 'gateway' && props.gatewayOnline === 0) return '#FFB224'
  return '#2ED3A3'
}
</script>

<template>
  <div class="topo-wrap">
    <svg
      width="1160"
      height="420"
      viewBox="0 0 1160 420"
      style="min-width: 1060px; width: 100%; display: block"
      role="img"
      aria-label="采集到通知的全链路拓扑"
    >
      <defs>
        <marker
          id="topo-arrow"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0 1 L 9 5 L 0 9 z" fill="#8E9BB8" />
        </marker>
      </defs>

      <g v-for="band in bands" :key="band.title">
        <rect
          :x="band.x"
          y="14"
          :width="band.w"
          height="392"
          rx="14"
          :fill="band.color"
          opacity=".045"
        />
        <rect
          :x="band.x"
          y="14"
          :width="band.w"
          height="392"
          rx="14"
          fill="none"
          :stroke="band.color"
          stroke-opacity=".16"
        />
        <text
          :x="band.x + band.w / 2"
          y="36"
          text-anchor="middle"
          font-size="11.5"
          font-weight="700"
          letter-spacing="2"
          :fill="band.color"
        >
          {{ band.title }}
        </text>
      </g>

      <g v-for="edge in edges" :key="edge.id">
        <path
          :d="edge.d"
          fill="none"
          :stroke="edge.color"
          stroke-width="1.8"
          opacity=".65"
          :stroke-dasharray="edge.dash ? '4 6' : undefined"
          marker-end="url(#topo-arrow)"
        />
        <text
          v-if="edge.label"
          :x="edge.labelX"
          :y="edge.labelY"
          text-anchor="middle"
          font-size="10.5"
          :fill="edge.color"
        >
          {{ edge.label }}
        </text>
      </g>

      <circle
        v-for="edge in edges.filter((item) => item.animate)"
        :key="`dot-${edge.id}`"
        r="3.2"
        :fill="edge.color"
      >
        <animateMotion dur="2.6s" repeatCount="indefinite" :path="edge.d" />
      </circle>

      <g
        v-for="node in nodes"
        :key="node.key"
        class="topo-node"
        :aria-label="node.title"
        @click="emit('select', node.key)"
      >
        <rect
          :x="node.x"
          :y="node.y"
          :width="node.w"
          :height="node.h"
          rx="13"
          fill="#111B30"
          stroke="rgba(148,163,204,.25)"
          stroke-width="1"
        />
        <rect :x="node.x" :y="node.y" width="3.5" :height="node.h" rx="2" :fill="node.color" />
        <svg
          :x="node.x + 14"
          :y="node.y + node.h / 2 - 10"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          :style="{ color: node.color }"
        >
          <g v-html="ICON_PATHS[node.icon] || ''" />
        </svg>
        <text
          :x="node.x + 42"
          :y="node.y + (node.h > 70 ? 32 : 26)"
          font-size="12.5"
          font-weight="700"
          fill="#E9EFFC"
        >
          {{ node.title }}
        </text>
        <text :x="node.x + 42" :y="node.y + (node.h > 70 ? 50 : 43)" font-size="10" fill="#8E9BB8">
          {{ node.sub }}
        </text>
        <circle :cx="node.x + node.w - 13" :cy="node.y + 13" r="4" :fill="nodeColor(node.key)">
          <animate attributeName="opacity" values="1;.4;1" dur="2s" repeatCount="indefinite" />
        </circle>
      </g>
      <text x="458" y="396" text-anchor="middle" font-size="10.5" fill="#8E9BB8" class="num">
        {{ props.packetSummary }}
      </text>
    </svg>
  </div>
</template>
