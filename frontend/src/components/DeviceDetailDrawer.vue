<script setup lang="ts">
import { computed, ref } from 'vue'

import { api } from '@/api/client'
import type { GatewayInfo, SensorInfo } from '@/api/types'
import BaseDrawer from '@/components/BaseDrawer.vue'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useUiStore } from '@/stores/ui'
import { dateTime, timeAgo } from '@/utils/format'

const props = defineProps<{
  open: boolean
  kind: 'gateway' | 'sensor'
  device: GatewayInfo | SensorInfo | null
}>()
const emit = defineEmits<{ close: [] }>()
const ui = useUiStore()
const polling = ref(false)

const gateway = computed(() => (props.kind === 'gateway' ? (props.device as GatewayInfo) : null))
const sensor = computed(() => (props.kind === 'sensor' ? (props.device as SensorInfo) : null))
const online = computed(() => props.device?.online ?? false)

async function poll() {
  if (!gateway.value) return
  polling.value = true
  try {
    const result = await api.pollGateway(gateway.value.code)
    ui.notify('ok', `${gateway.value.code} 召测已触发`, result.message)
  } catch (error) {
    ui.notify('err', '召测失败', error instanceof Error ? error.message : '')
  } finally {
    polling.value = false
  }
}
</script>

<template>
  <BaseDrawer
    :open="props.open"
    :title="
      props.device
        ? `${props.device.code} · ${props.kind === 'gateway' ? 'LoRa 网关' : sensor?.kind_text}`
        : '设备详情'
    "
    :subtitle="
      gateway
        ? `${gateway.name} · ${gateway.host}:${gateway.port}`
        : sensor
          ? `${sensor.motor_code} ${sensor.motor_name}`
          : ''
    "
    @close="emit('close')"
  >
    <template v-if="props.device" #badge>
      <StateBadge
        :tone="online ? 'ok' : 'mut'"
        :label="online ? '在线' : '离线'"
        style="margin-left: 6px"
      />
    </template>

    <template v-if="gateway">
      <div class="drawer-sec">
        <div class="info-grid">
          <div class="info-cell">
            <div class="l">网关型号</div>
            <div class="v">{{ gateway.model }}</div>
          </div>
          <div class="info-cell">
            <div class="l">固件版本</div>
            <div class="v num">{{ gateway.firmware }}</div>
          </div>
          <div class="info-cell">
            <div class="l">通信方式</div>
            <div class="v">{{ gateway.framer === 'rtu' ? 'RTU over TCP' : 'Modbus TCP' }}</div>
          </div>
          <div class="info-cell">
            <div class="l">采集点</div>
            <div class="v num">{{ gateway.sensor_count }} 个</div>
          </div>
          <div class="info-cell">
            <div class="l">最近心跳</div>
            <div class="v" style="font-size: 12px">{{ timeAgo(gateway.last_seen_at) }}</div>
          </div>
          <div class="info-cell">
            <div class="l">连续失败</div>
            <div class="v num">{{ gateway.consecutive_failures }} 次</div>
          </div>
        </div>
      </div>
      <div class="drawer-sec">
        <h4>说明</h4>
        <p style="font-size: 12.5px; color: var(--muted)">
          {{ gateway.note || '网关经厂区网口上联，后台按 15 分钟周期顺序读取采集点。' }}
        </p>
        <p v-if="gateway.last_error" style="font-size: 12px; color: #ff8296; margin-top: 8px">
          最近错误：{{ gateway.last_error }}
        </p>
      </div>
      <button
        class="btn btn-ghost"
        :disabled="polling"
        style="width: 100%; justify-content: center"
        @click="poll"
      >
        <Icon name="refresh" :size="15" /> {{ polling ? '召测中…' : '立即召测' }}
      </button>
    </template>

    <template v-else-if="sensor">
      <div class="drawer-sec">
        <div class="info-grid">
          <div class="info-cell">
            <div class="l">绑定电机</div>
            <div class="v">{{ sensor.motor_code }} {{ sensor.motor_name }}</div>
          </div>
          <div class="info-cell">
            <div class="l">接入网关</div>
            <div class="v">{{ sensor.gateway_code }}</div>
          </div>
          <div class="info-cell">
            <div class="l">从站地址</div>
            <div class="v num">{{ sensor.slave_id }}</div>
          </div>
          <div class="info-cell">
            <div class="l">寄存器</div>
            <div class="v num">
              {{ sensor.register_address }} ~
              {{ sensor.register_address + sensor.register_count - 1 }}
            </div>
          </div>
          <div class="info-cell">
            <div class="l">倍率 / 单位</div>
            <div class="v num">{{ sensor.scale }} / {{ sensor.unit }}</div>
          </div>
          <div class="info-cell">
            <div class="l">供电方式</div>
            <div class="v">{{ sensor.power_type }}</div>
          </div>
          <div class="info-cell">
            <div class="l">最近读取</div>
            <div class="v" style="font-size: 12px">{{ dateTime(sensor.last_read_at) }}</div>
          </div>
          <div class="info-cell">
            <div class="l">连续失败</div>
            <div class="v num">{{ sensor.consecutive_failures }} 次</div>
          </div>
        </div>
      </div>
      <div
        v-if="sensor.last_error"
        class="notice-box"
        style="border-color: rgba(255, 77, 109, 0.3); color: #ff8296"
      >
        最近错误：{{ sensor.last_error }}
      </div>
      <div class="drawer-sec" style="margin-top: 16px">
        <h4>说明</h4>
        <p style="font-size: 12.5px; color: var(--muted)">
          传感器由现场电源供电，只上行数据。平台只监测、只报警，不下发任何控制指令。
        </p>
      </div>
    </template>
  </BaseDrawer>
</template>
