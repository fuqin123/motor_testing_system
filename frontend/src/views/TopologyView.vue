<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api/client'
import type { DevicesResponse, GatewayInfo, SensorInfo } from '@/api/types'
import DeviceDetailDrawer from '@/components/DeviceDetailDrawer.vue'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import TopologyDiagram from '@/components/TopologyDiagram.vue'
import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'
import { dateTime, timeAgo } from '@/utils/format'

const app = useAppStore()
const ui = useUiStore()
const router = useRouter()

const data = ref<DevicesResponse | null>(null)
const loading = ref(false)
const drawerOpen = ref(false)
const drawerKind = ref<'gateway' | 'sensor'>('gateway')
const drawerDevice = ref<GatewayInfo | SensorInfo | null>(null)
let refreshTimer: number | null = null

const tempCount = computed(
  () =>
    data.value?.sensors.filter((sensor) => sensor.kind === 'temperature' && sensor.enabled)
      .length || 0,
)
const currentCount = computed(
  () =>
    data.value?.sensors.filter((sensor) => sensor.kind === 'current' && sensor.enabled).length || 0,
)
const nodeCount = computed(() => new Set(app.motors.map((motor) => motor.node_code)).size)
const gatewayCode = computed(() => data.value?.gateways[0]?.code || 'GW-01')
const packetSummary = computed(() => {
  const link = app.overview?.link
  if (!link) return '今日转发 — 包 · 丢包 —'
  return `今日转发 ${link.packets_today.toLocaleString()} 包 · 丢包 ${link.packet_loss_pct}% · 平均延迟 ${Math.round(link.avg_latency_ms)}ms`
})

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    data.value = await api.devices()
  } catch (error) {
    ui.notify('err', '设备链路加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

function openGateway(gateway: GatewayInfo) {
  drawerKind.value = 'gateway'
  drawerDevice.value = gateway
  drawerOpen.value = true
}

function openSensor(sensor: SensorInfo) {
  drawerKind.value = 'sensor'
  drawerDevice.value = sensor
  drawerOpen.value = true
}

function onTopologySelect(key: string) {
  if (key === 'gateway' && data.value?.gateways.length) {
    openGateway(data.value.gateways[0])
    return
  }
  if (key === 'dashboard') {
    void router.push('/overview')
    return
  }
  if (key === 'analysis') {
    void router.push('/analysis')
    return
  }
  if (key === 'feishu') {
    void router.push('/settings')
    return
  }
  if (key === 'maintenance') {
    void router.push('/alarms')
    return
  }
  ui.notify('info', '链路节点', '该节点由现场传感器、网关与后台服务组成，数据只上行不控制。')
}

function sensorSignal(sensor: SensorInfo): string {
  if (sensor.last_error) return sensor.last_error.slice(0, 18)
  if (sensor.signal_dbm !== null) return `${sensor.signal_dbm} dBm`
  return sensor.online ? 'RS485 正常' : '无响应'
}

onMounted(() => {
  void load()
  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void load(true)
  }, 60_000)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<template>
  <section class="view" id="view-topology">
    <div v-if="loading" class="card loading-block"><span class="spinner" />加载设备与链路…</div>
    <template v-else-if="data">
      <div class="card" style="margin-bottom: 16px">
        <div class="card-head">
          <h3>采集 → 传输 → 分析 → 通知 全链路</h3>
          <div class="right">
            <StateBadge
              :tone="data.summary.gateways_online > 0 ? 'ok' : 'warn'"
              :label="data.summary.gateways_online > 0 ? '全链路正常' : '链路异常'"
            />
            <span class="badge pilot">只监测 · 只报警 · 不控制</span>
            <button class="mini-btn primary" @click="router.push('/device-config')">
              <Icon name="plus" :size="13" /> 配置设备
            </button>
          </div>
          <div class="sub">数据流与方案架构一致 · 点击节点查看设备详情 · 数据不出厂</div>
        </div>
        <div class="topo-summary">
          <span class="badge mut"
            ><span class="dot" />{{ data.summary.gateways_online }} /
            {{ data.summary.gateways_total }} 网关在线</span
          >
          <span class="badge mut"
            ><span class="dot" />{{ data.summary.sensors_online }} /
            {{ data.summary.sensors_total }} 采集点在线</span
          >
          <span class="badge mut"><span class="dot" />{{ nodeCount }} 个 LoRa 节点</span>
          <span class="badge mut"
            ><span class="dot" />{{ app.meta?.sampling.interval_minutes || 15 }} 分钟采集周期</span
          >
        </div>
        <TopologyDiagram
          :temp-count="tempCount"
          :current-count="currentCount"
          :node-count="nodeCount"
          :gateway-count="data.summary.gateways_total"
          :gateway-code="gatewayCode"
          :gateway-online="data.summary.gateways_online"
          :baud-rate="app.meta?.lora.baud_rate || 1200"
          :packet-summary="packetSummary"
          @select="onTopologySelect"
        />
      </div>

      <div
        class="ov-bottom"
        style="grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); margin-top: 0"
      >
        <div class="card">
          <div class="card-head">
            <h3>设备清单</h3>
            <div class="right">
              <span class="micro">{{ data.sensors.length + data.gateways.length }} 台设备</span>
            </div>
          </div>
          <div class="table-wrap" style="padding: 6px 8px 12px">
            <table>
              <thead>
                <tr>
                  <th>设备</th>
                  <th>类型</th>
                  <th>绑定对象</th>
                  <th>信号 / 供电</th>
                  <th>固件</th>
                  <th>最近心跳</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="gateway in data.gateways"
                  :key="gateway.code"
                  class="device-row"
                  @click="openGateway(gateway)"
                >
                  <td>
                    <b style="font-size: 12.5px">{{ gateway.code }}</b>
                  </td>
                  <td class="device-type">LoRa 网关</td>
                  <td style="font-size: 12.5px">{{ gateway.sensor_count }} 个采集点</td>
                  <td class="num" style="font-size: 12px">
                    {{ gateway.framer === 'rtu' ? 'RTU over TCP' : 'Modbus TCP' }}
                    <div class="sub">市电供电 · 网口上联</div>
                  </td>
                  <td class="num" style="font-size: 12px">{{ gateway.firmware }}</td>
                  <td style="font-size: 12px; color: var(--muted)">
                    {{ timeAgo(gateway.last_seen_at) }}
                  </td>
                  <td>
                    <StateBadge
                      :tone="gateway.online ? 'ok' : 'mut'"
                      :label="gateway.online ? '在线' : '离线'"
                    />
                  </td>
                </tr>
                <tr
                  v-for="sensor in data.sensors"
                  :key="sensor.code"
                  class="device-row"
                  @click="openSensor(sensor)"
                >
                  <td>
                    <b style="font-size: 12.5px">{{ sensor.code }}</b>
                  </td>
                  <td class="device-type">{{ sensor.kind_text }}</td>
                  <td style="font-size: 12.5px">{{ sensor.motor_code }} {{ sensor.motor_name }}</td>
                  <td class="num" style="font-size: 12px">
                    {{ sensorSignal(sensor) }}
                    <div class="sub">{{ sensor.power_type }}</div>
                  </td>
                  <td class="num" style="font-size: 12px">{{ sensor.firmware }}</td>
                  <td style="font-size: 12px; color: var(--muted)">
                    {{ timeAgo(sensor.last_read_at) }}
                  </td>
                  <td>
                    <StateBadge
                      :tone="sensor.online ? 'ok' : 'mut'"
                      :label="sensor.online ? '在线' : '离线'"
                    />
                  </td>
                </tr>
                <tr v-if="!data.sensors.length && !data.gateways.length">
                  <td colspan="7" style="text-align: center; padding: 30px; color: var(--muted)">
                    尚未配置设备与采集点。
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>链路事件</h3></div>
          <div class="link-events">
            <div
              v-for="(event, index) in data.events"
              :key="`${event.ts}-${index}`"
              class="link-event"
            >
              <time class="num">{{ dateTime(event.ts).slice(11, 16) }}</time>
              <span
                class="dot"
                :style="{
                  background:
                    event.level === 'crit'
                      ? 'var(--red)'
                      : event.level === 'warn'
                        ? 'var(--amber)'
                        : event.level === 'ok'
                          ? 'var(--green)'
                          : 'var(--blue)',
                }"
              />
              <span>{{ event.text }}</span>
            </div>
            <div v-if="!data.events.length" class="empty-state">暂无链路事件。</div>
          </div>
          <div class="insight">
            <Icon name="info" :size="16" />
            <span
              >LoRa
              适合温度、电流有效值等低频小数据传输；高频振动分析需另行考虑有线或高速无线方案。</span
            >
          </div>
        </div>
      </div>
    </template>
    <div v-else class="card empty-state"><b>暂无设备数据</b>请检查网关配置。</div>

    <DeviceDetailDrawer
      :open="drawerOpen"
      :kind="drawerKind"
      :device="drawerDevice"
      @close="drawerOpen = false"
    />
  </section>
</template>
