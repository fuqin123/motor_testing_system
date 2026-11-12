<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type {
  DevicesResponse,
  GatewayConfigPayload,
  GatewayInfo,
  MotorCard,
  MotorConfigPayload,
  SensorConfigPayload,
  SensorInfo,
  ThresholdMotor,
} from '@/api/types'
import BaseModal from '@/components/BaseModal.vue'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useUiStore } from '@/stores/ui'
import { timeAgo } from '@/utils/format'

const ui = useUiStore()

type Tab = 'motors' | 'gateways' | 'sensors'
type DeleteTarget =
  | { kind: 'gateway'; code: string; name: string }
  | { kind: 'sensor'; id: number; code: string; name: string }

const tab = ref<Tab>('motors')
const loading = ref(false)
const devices = ref<DevicesResponse | null>(null)
const motors = ref<MotorCard[]>([])
const thresholdMap = ref<Record<string, ThresholdMotor>>({})

const motorModal = ref(false)
const gatewayModal = ref(false)
const sensorModal = ref(false)
const deleteModal = ref(false)
const saving = ref(false)
const editingMotor = ref(false)
const editingGateway = ref(false)
const editingSensor = ref(false)
const deleteTarget = ref<DeleteTarget | null>(null)

const motorForm = ref<MotorConfigPayload>({
  code: '',
  name: '',
  location: '',
  group_name: '未分组',
  rated_kw: 0,
  rated_current_a: 0,
  pilot: false,
  enabled: true,
  node_code: 'N-01',
  vfd_model: '',
  install_date: '',
  last_maintenance: '',
  temp_limit_c: 85,
  current_limit_a: 0,
  temp_deviation_pct: 8,
  current_deviation_pct: 10,
  phase_imbalance_pct: 10,
  rise_rate_limit_c_per_day: 1,
  notify_enabled: true,
})

const gatewayForm = ref<GatewayConfigPayload>({
  code: '',
  name: '',
  host: '',
  port: 10123,
  framer: 'rtu',
  enabled: true,
  model: 'LoRa 网关',
  firmware: '—',
  note: '',
})

const sensorForm = ref<SensorConfigPayload>({
  motor_code: '',
  gateway_code: '',
  kind: 'temperature',
  name: '',
  slave_id: 1,
  register_address: 0,
  register_count: 1,
  scale: 0.1,
  unit: '℃',
  enabled: true,
  power_type: '市电供电',
  firmware: '—',
})

const gateways = computed(() => devices.value?.gateways || [])
const sensors = computed(() => devices.value?.sensors || [])
const sensorCount = computed(() => sensors.value.length)
const gatewayCount = computed(() => gateways.value.length)
const formTitle = computed(() => {
  if (motorModal.value) return editingMotor.value ? '编辑电机' : '新增电机'
  if (gatewayModal.value) return editingGateway.value ? '编辑网关' : '新增网关'
  return editingSensor.value ? '编辑采集点' : '新增采集点'
})

async function load() {
  loading.value = true
  try {
    const [deviceData, motorData, settingsData] = await Promise.all([
      api.devices(),
      api.motors(true),
      api.settings(),
    ])
    devices.value = deviceData
    motors.value = motorData.items
    thresholdMap.value = Object.fromEntries(settingsData.motors.map((motor) => [motor.code, motor]))
    if (!sensorForm.value.motor_code) sensorForm.value.motor_code = motors.value[0]?.code || ''
    if (!sensorForm.value.gateway_code)
      sensorForm.value.gateway_code = gateways.value[0]?.code || ''
  } catch (error) {
    ui.notify('err', '设备配置加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

function openMotorForm(motor?: MotorCard) {
  editingMotor.value = Boolean(motor)
  const threshold = motor ? thresholdMap.value[motor.code] : undefined
  motorForm.value = motor
    ? {
        code: motor.code,
        name: motor.name,
        location: motor.location,
        group_name: motor.group,
        rated_kw: motor.rated_kw,
        rated_current_a: motor.rated_current_a,
        pilot: motor.pilot,
        enabled: motor.enabled,
        node_code: motor.node_code,
        vfd_model: motor.vfd_model,
        install_date: motor.install_date,
        last_maintenance: motor.last_maintenance,
        temp_limit_c: motor.temp_limit_c,
        current_limit_a: motor.current_limit_a,
        temp_deviation_pct: threshold?.temp_deviation_pct ?? 8,
        current_deviation_pct: threshold?.current_deviation_pct ?? 10,
        phase_imbalance_pct: threshold?.phase_imbalance_pct ?? 10,
        rise_rate_limit_c_per_day: threshold?.rise_rate_limit_c_per_day ?? 1,
        notify_enabled: threshold?.notify_enabled ?? true,
      }
    : {
        code: '',
        name: '',
        location: '',
        group_name: '未分组',
        rated_kw: 0,
        rated_current_a: 0,
        pilot: false,
        enabled: true,
        node_code: 'N-01',
        vfd_model: '',
        install_date: '',
        last_maintenance: '',
        temp_limit_c: 85,
        current_limit_a: 0,
        temp_deviation_pct: 8,
        current_deviation_pct: 10,
        phase_imbalance_pct: 10,
        rise_rate_limit_c_per_day: 1,
        notify_enabled: true,
      }
  motorModal.value = true
}

function applySensorKindDefaults() {
  const isCurrent = sensorForm.value.kind === 'current'
  sensorForm.value.register_count = isCurrent ? 3 : 1
  sensorForm.value.scale = isCurrent ? 0.01 : 0.1
  sensorForm.value.unit = isCurrent ? 'A' : '℃'
  if (!sensorForm.value.name.trim()) {
    sensorForm.value.name = isCurrent ? '三相电流' : '外壳温度'
  }
}

function openGatewayForm(gateway?: GatewayInfo) {
  editingGateway.value = Boolean(gateway)
  gatewayForm.value = gateway
    ? {
        code: gateway.code,
        name: gateway.name,
        host: gateway.host,
        port: gateway.port,
        framer: gateway.framer === 'tcp' ? 'tcp' : 'rtu',
        enabled: gateway.enabled,
        model: gateway.model,
        firmware: gateway.firmware,
        note: gateway.note,
      }
    : {
        code: '',
        name: '',
        host: '',
        port: 10123,
        framer: 'rtu',
        enabled: true,
        model: 'LoRa 网关',
        firmware: '—',
        note: '',
      }
  gatewayModal.value = true
}

function openSensorForm(sensor?: SensorInfo) {
  editingSensor.value = Boolean(sensor)
  sensorForm.value = sensor
    ? {
        id: sensor.id,
        code: sensor.code,
        motor_code: sensor.motor_code || '',
        gateway_code: sensor.gateway_code || '',
        kind: sensor.kind,
        name: sensor.name,
        slave_id: sensor.slave_id,
        register_address: sensor.register_address,
        register_count: sensor.register_count,
        scale: sensor.scale,
        unit: sensor.unit,
        enabled: sensor.enabled,
        power_type: sensor.power_type,
        firmware: sensor.firmware,
      }
    : {
        motor_code: motors.value[0]?.code || '',
        gateway_code: gateways.value[0]?.code || '',
        kind: 'temperature',
        name: '',
        slave_id: 1,
        register_address: 0,
        register_count: 1,
        scale: 0.1,
        unit: '℃',
        enabled: true,
        power_type: '市电供电',
        firmware: '—',
      }
  sensorModal.value = true
}

async function saveMotor() {
  if (!motorForm.value.code.trim() || !motorForm.value.name.trim()) {
    ui.notify('warn', '请填写电机编码和名称', '编码与名称不能为空')
    return
  }
  saving.value = true
  try {
    const result = await api.upsertMotor({
      ...motorForm.value,
      code: motorForm.value.code.trim().toUpperCase(),
      name: motorForm.value.name.trim(),
    })
    ui.notify('ok', result.created ? '电机已新增' : '电机已更新', result.code)
    motorModal.value = false
    await load()
  } catch (error) {
    ui.notify('err', '电机保存失败', error instanceof Error ? error.message : '')
  } finally {
    saving.value = false
  }
}

async function saveGateway() {
  if (
    !gatewayForm.value.code.trim() ||
    !gatewayForm.value.name.trim() ||
    !gatewayForm.value.host.trim()
  ) {
    ui.notify('warn', '请填写完整网关信息', '编码、名称、IP 地址不能为空')
    return
  }
  saving.value = true
  try {
    const result = await api.upsertGateway({
      ...gatewayForm.value,
      code: gatewayForm.value.code.trim().toUpperCase(),
      name: gatewayForm.value.name.trim(),
      host: gatewayForm.value.host.trim(),
    })
    ui.notify('ok', result.created ? '网关已新增' : '网关已更新', result.gateway.code)
    gatewayModal.value = false
    await load()
  } catch (error) {
    ui.notify('err', '网关保存失败', error instanceof Error ? error.message : '')
  } finally {
    saving.value = false
  }
}

async function saveSensor() {
  if (!sensorForm.value.motor_code || !sensorForm.value.gateway_code) {
    ui.notify('warn', '请选择电机和网关', '采集点必须绑定电机与网关')
    return
  }
  saving.value = true
  try {
    const result = await api.upsertSensor({
      ...sensorForm.value,
      code: sensorForm.value.code?.trim() || undefined,
      name: sensorForm.value.name.trim(),
    })
    ui.notify('ok', result.created ? '采集点已新增' : '采集点已更新', result.sensor.code)
    sensorModal.value = false
    await load()
  } catch (error) {
    ui.notify('err', '采集点保存失败', error instanceof Error ? error.message : '')
  } finally {
    saving.value = false
  }
}

function askDelete(target: DeleteTarget) {
  deleteTarget.value = target
  deleteModal.value = true
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  saving.value = true
  try {
    if (deleteTarget.value.kind === 'gateway') {
      await api.deleteGateway(deleteTarget.value.code)
      ui.notify('ok', '网关已删除', deleteTarget.value.code)
    } else {
      await api.deleteSensor(deleteTarget.value.id)
      ui.notify('ok', '采集点已删除', deleteTarget.value.code)
    }
    deleteModal.value = false
    deleteTarget.value = null
    await load()
  } catch (error) {
    ui.notify('err', '删除失败', error instanceof Error ? error.message : '')
  } finally {
    saving.value = false
  }
}

async function pollGateway(gateway: GatewayInfo) {
  try {
    const result = await api.pollGateway(gateway.code)
    ui.notify('ok', `${gateway.code} 召测已触发`, result.message)
  } catch (error) {
    ui.notify('err', '召测失败', error instanceof Error ? error.message : '')
  }
}

onMounted(() => void load())
</script>

<template>
  <section class="view" id="view-device-config">
    <div class="config-intro card">
      <div>
        <h2>设备配置</h2>
        <p>
          维护电机档案、LoRa 网关和采集点位。保存后下一轮 15
          分钟采集自动读取新配置，也可在网关行点击“立即召测”验证。
        </p>
      </div>
      <div class="config-intro-stats">
        <div>
          <b class="num">{{ motors.length }}</b
          ><span>电机</span>
        </div>
        <div>
          <b class="num">{{ gatewayCount }}</b
          ><span>网关</span>
        </div>
        <div>
          <b class="num">{{ sensorCount }}</b
          ><span>采集点</span>
        </div>
        <div>
          <b class="num">{{ devices?.summary.sensors_online ?? 0 }}</b
          ><span>在线采集点</span>
        </div>
      </div>
      <div class="config-intro-actions">
        <button class="mini-btn" @click="load"><Icon name="refresh" :size="14" /> 刷新</button>
      </div>
    </div>

    <div class="config-toolbar">
      <div class="seg config-tabs">
        <button :class="{ active: tab === 'motors' }" @click="tab = 'motors'">
          电机 <span class="count">{{ motors.length }}</span>
        </button>
        <button :class="{ active: tab === 'gateways' }" @click="tab = 'gateways'">
          网关 <span class="count">{{ gatewayCount }}</span>
        </button>
        <button :class="{ active: tab === 'sensors' }" @click="tab = 'sensors'">
          采集点 <span class="count">{{ sensorCount }}</span>
        </button>
      </div>
      <div class="config-toolbar-right">
        <button v-if="tab === 'motors'" class="btn btn-primary btn-sm" @click="openMotorForm()">
          <Icon name="plus" :size="14" /> 新增电机
        </button>
        <button v-if="tab === 'gateways'" class="btn btn-primary btn-sm" @click="openGatewayForm()">
          <Icon name="plus" :size="14" /> 新增网关
        </button>
        <button v-if="tab === 'sensors'" class="btn btn-primary btn-sm" @click="openSensorForm()">
          <Icon name="plus" :size="14" /> 新增采集点
        </button>
      </div>
    </div>

    <div v-if="loading" class="card loading-block"><span class="spinner" />加载设备配置…</div>

    <div v-else-if="tab === 'motors'" class="card">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>编码</th>
              <th>名称</th>
              <th>分组 / 位置</th>
              <th>功率 / 额定电流</th>
              <th>温度上限</th>
              <th>单相电流上限</th>
              <th>试点</th>
              <th>状态</th>
              <th style="text-align: right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="motor in motors" :key="motor.code">
              <td>
                <b>{{ motor.code }}</b>
              </td>
              <td>
                {{ motor.name }}
                <div class="sub">{{ motor.node_code }} · {{ motor.vfd_model || '未填变频器' }}</div>
              </td>
              <td>
                {{ motor.group }}
                <div class="sub">{{ motor.location || '未填位置' }}</div>
              </td>
              <td class="num">
                {{ motor.rated_kw }} kW
                <div class="sub">{{ motor.rated_current_a }} A</div>
              </td>
              <td class="num">{{ motor.temp_limit_c }} °C</td>
              <td class="num">{{ motor.current_limit_a }} A</td>
              <td>
                <span v-if="motor.pilot" class="badge pilot">试点</span
                ><span v-else class="faint">—</span>
              </td>
              <td>
                <StateBadge
                  :tone="motor.enabled ? 'ok' : 'mut'"
                  :label="motor.enabled ? '启用' : '停用'"
                />
              </td>
              <td>
                <div class="row-actions">
                  <button class="mini-btn" @click="openMotorForm(motor)">编辑</button>
                </div>
              </td>
            </tr>
            <tr v-if="!motors.length">
              <td colspan="9" class="empty-state">暂无电机，请先新增电机。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="tab === 'gateways'" class="card">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>编码</th>
              <th>名称</th>
              <th>地址</th>
              <th>透传方式</th>
              <th>采集点</th>
              <th>最近心跳</th>
              <th>状态</th>
              <th style="text-align: right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="gateway in gateways" :key="gateway.code">
              <td>
                <b>{{ gateway.code }}</b>
              </td>
              <td>
                {{ gateway.name }}
                <div class="sub">{{ gateway.model }}</div>
              </td>
              <td class="num">{{ gateway.host }}:{{ gateway.port }}</td>
              <td>{{ gateway.framer === 'rtu' ? 'RTU over TCP' : 'Modbus TCP' }}</td>
              <td class="num">{{ gateway.sensor_count }}</td>
              <td>{{ timeAgo(gateway.last_seen_at) }}</td>
              <td>
                <StateBadge
                  :tone="gateway.online ? 'ok' : 'mut'"
                  :label="gateway.online ? '在线' : '离线'"
                />
              </td>
              <td>
                <div class="row-actions">
                  <button class="mini-btn primary" @click="pollGateway(gateway)">召测</button>
                  <button class="mini-btn" @click="openGatewayForm(gateway)">编辑</button>
                  <button
                    class="mini-btn danger"
                    @click="askDelete({ kind: 'gateway', code: gateway.code, name: gateway.name })"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!gateways.length">
              <td colspan="8" class="empty-state">暂无网关，请先新增网关。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else class="card">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>编码</th>
              <th>类型</th>
              <th>电机</th>
              <th>网关</th>
              <th>从站 / 寄存器</th>
              <th>倍率 / 单位</th>
              <th>供电</th>
              <th>状态</th>
              <th style="text-align: right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="sensor in sensors" :key="sensor.id">
              <td>
                <b>{{ sensor.code }}</b>
              </td>
              <td>
                {{ sensor.kind_text }}
                <div class="sub">{{ sensor.name || '未命名' }}</div>
              </td>
              <td>
                {{ sensor.motor_code }}
                <div class="sub">{{ sensor.motor_name }}</div>
              </td>
              <td>{{ sensor.gateway_code }}</td>
              <td class="num">
                从站 {{ sensor.slave_id }} · {{ sensor.register_address }}~{{
                  sensor.register_address + sensor.register_count - 1
                }}
              </td>
              <td class="num">{{ sensor.scale }} / {{ sensor.unit }}</td>
              <td>{{ sensor.power_type }}</td>
              <td>
                <StateBadge
                  :tone="sensor.online ? 'ok' : 'mut'"
                  :label="sensor.online ? '在线' : '离线'"
                />
              </td>
              <td>
                <div class="row-actions">
                  <button class="mini-btn" @click="openSensorForm(sensor)">编辑</button>
                  <button
                    class="mini-btn danger"
                    @click="
                      askDelete({
                        kind: 'sensor',
                        id: sensor.id,
                        code: sensor.code,
                        name: sensor.name,
                      })
                    "
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="!sensors.length">
              <td colspan="9" class="empty-state">暂无采集点，请先新增采集点。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div
      class="insight"
      style="border: 1px solid var(--line-soft); border-radius: 12px; background: var(--panel)"
    >
      <Icon name="shield" :size="16" />
      <span
        >设备配置只影响采集映射，不会写寄存器或控制电机；修改网关/从站/寄存器/倍率后会重置该采集点的通信状态。</span
      >
    </div>

    <BaseModal
      :open="motorModal"
      :title="formTitle"
      subtitle="电机档案与告警阈值"
      @close="motorModal = false"
    >
      <div class="form-grid">
        <label class="form-field"
          ><span class="form-label">电机编码 *</span
          ><input
            v-model="motorForm.code"
            class="input"
            :disabled="editingMotor"
            placeholder="如 M-07"
        /></label>
        <label class="form-field"
          ><span class="form-label">电机名称 *</span
          ><input v-model="motorForm.name" class="input" placeholder="如 3#循环水泵电机"
        /></label>
        <label class="form-field"
          ><span class="form-label">位置</span
          ><input v-model="motorForm.location" class="input" placeholder="车间 / 区域"
        /></label>
        <label class="form-field"
          ><span class="form-label">分组</span
          ><input v-model="motorForm.group_name" class="input" placeholder="如 泵组A"
        /></label>
        <label class="form-field"
          ><span class="form-label">额定功率 kW</span
          ><input
            v-model.number="motorForm.rated_kw"
            type="number"
            class="input"
            min="0"
            step="0.1"
        /></label>
        <label class="form-field"
          ><span class="form-label">额定电流 A</span
          ><input
            v-model.number="motorForm.rated_current_a"
            type="number"
            class="input"
            min="0"
            step="0.1"
        /></label>
        <label class="form-field"
          ><span class="form-label">LoRa 节点</span
          ><input v-model="motorForm.node_code" class="input" placeholder="如 N-01"
        /></label>
        <label class="form-field"
          ><span class="form-label">变频器型号</span
          ><input v-model="motorForm.vfd_model" class="input" placeholder="如 ABB ACS580"
        /></label>
        <label class="form-field"
          ><span class="form-label">温度上限 °C</span
          ><input
            v-model.number="motorForm.temp_limit_c"
            type="number"
            class="input"
            min="20"
            max="200"
            step="0.1"
        /></label>
        <label class="form-field"
          ><span class="form-label">单相电流上限 A</span
          ><input
            v-model.number="motorForm.current_limit_a"
            type="number"
            class="input"
            min="0"
            step="0.1"
        /></label>
        <label class="form-field"
          ><span class="form-label">温度偏离 %</span
          ><input
            v-model.number="motorForm.temp_deviation_pct"
            type="number"
            class="input"
            min="0"
            max="100"
            step="0.5"
        /></label>
        <label class="form-field"
          ><span class="form-label">电流偏离 %</span
          ><input
            v-model.number="motorForm.current_deviation_pct"
            type="number"
            class="input"
            min="0"
            max="100"
            step="0.5"
        /></label>
        <label class="form-field"
          ><span class="form-label">三相不平衡 %</span
          ><input
            v-model.number="motorForm.phase_imbalance_pct"
            type="number"
            class="input"
            min="0"
            max="100"
            step="0.5"
        /></label>
        <label class="form-field"
          ><span class="form-label">温升速率线 °C/天</span
          ><input
            v-model.number="motorForm.rise_rate_limit_c_per_day"
            type="number"
            class="input"
            min="0"
            max="50"
            step="0.1"
        /></label>
        <label class="form-field"
          ><span class="form-label">投运时间</span
          ><input v-model="motorForm.install_date" class="input" placeholder="如 2024-01"
        /></label>
        <label class="form-field full"
          ><span class="form-label">最近维护</span
          ><input
            v-model="motorForm.last_maintenance"
            class="input"
            placeholder="如 2026-11-01 润滑保养"
        /></label>
        <label class="form-check"
          ><button
            type="button"
            class="switch"
            :class="{ on: motorForm.pilot }"
            @click="motorForm.pilot = !motorForm.pilot"
          />试点电机</label
        >
        <label class="form-check"
          ><button
            type="button"
            class="switch"
            :class="{ on: motorForm.enabled }"
            @click="motorForm.enabled = !motorForm.enabled"
          />启用监测</label
        >
        <label class="form-check"
          ><button
            type="button"
            class="switch"
            :class="{ on: motorForm.notify_enabled }"
            @click="motorForm.notify_enabled = !motorForm.notify_enabled"
          />启用通知</label
        >
      </div>
      <div class="form-actions">
        <button class="btn btn-ghost" @click="motorModal = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="saveMotor">
          {{ saving ? '保存中…' : '保存电机' }}
        </button>
      </div>
    </BaseModal>

    <BaseModal
      :open="gatewayModal"
      :title="formTitle"
      subtitle="网关地址与透传参数"
      @close="gatewayModal = false"
    >
      <div class="form-grid">
        <label class="form-field"
          ><span class="form-label">网关编码 *</span
          ><input
            v-model="gatewayForm.code"
            class="input"
            :disabled="editingGateway"
            placeholder="如 GW-02"
        /></label>
        <label class="form-field"
          ><span class="form-label">网关名称 *</span
          ><input v-model="gatewayForm.name" class="input" placeholder="如 二车间 LoRa 网关"
        /></label>
        <label class="form-field"
          ><span class="form-label">IP / 主机 *</span
          ><input v-model="gatewayForm.host" class="input" placeholder="如 10.112.66.231"
        /></label>
        <label class="form-field"
          ><span class="form-label">端口 *</span
          ><input v-model.number="gatewayForm.port" type="number" class="input" min="1" max="65535"
        /></label>
        <label class="form-field"
          ><span class="form-label">透传方式</span
          ><select v-model="gatewayForm.framer" class="input">
            <option value="rtu">RTU over TCP</option>
            <option value="tcp">Modbus TCP</option>
          </select></label
        >
        <label class="form-field"
          ><span class="form-label">型号</span><input v-model="gatewayForm.model" class="input"
        /></label>
        <label class="form-field"
          ><span class="form-label">固件版本</span
          ><input v-model="gatewayForm.firmware" class="input" placeholder="如 v1.4.2"
        /></label>
        <label class="form-field full"
          ><span class="form-label">备注</span
          ><input v-model="gatewayForm.note" class="input" placeholder="上联方式 / 现场位置"
        /></label>
        <label class="form-check"
          ><button
            type="button"
            class="switch"
            :class="{ on: gatewayForm.enabled }"
            @click="gatewayForm.enabled = !gatewayForm.enabled"
          />启用网关</label
        >
      </div>
      <div class="form-actions">
        <button class="btn btn-ghost" @click="gatewayModal = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="saveGateway">
          {{ saving ? '保存中…' : '保存网关' }}
        </button>
      </div>
    </BaseModal>

    <BaseModal
      :open="sensorModal"
      :title="formTitle"
      subtitle="采集点寄存器映射"
      @close="sensorModal = false"
    >
      <div class="form-grid">
        <label class="form-field"
          ><span class="form-label">采集点编码</span
          ><input v-model="sensorForm.code" class="input" placeholder="留空自动生成 T-07/C-07"
        /></label>
        <label class="form-field"
          ><span class="form-label">类型</span
          ><select v-model="sensorForm.kind" class="input" @change="applySensorKindDefaults">
            <option value="temperature">温度</option>
            <option value="current">三相电流</option>
          </select></label
        >
        <label class="form-field"
          ><span class="form-label">绑定电机 *</span
          ><select v-model="sensorForm.motor_code" class="input">
            <option v-for="motor in motors" :key="motor.code" :value="motor.code">
              {{ motor.code }} · {{ motor.name }}
            </option>
          </select></label
        >
        <label class="form-field"
          ><span class="form-label">接入网关 *</span
          ><select v-model="sensorForm.gateway_code" class="input">
            <option v-for="gateway in gateways" :key="gateway.code" :value="gateway.code">
              {{ gateway.code }} · {{ gateway.name }}
            </option>
          </select></label
        >
        <label class="form-field"
          ><span class="form-label">名称</span
          ><input v-model="sensorForm.name" class="input" placeholder="如 外壳温度 / 三相电流"
        /></label>
        <label class="form-field"
          ><span class="form-label">从站地址</span
          ><input
            v-model.number="sensorForm.slave_id"
            type="number"
            class="input"
            min="1"
            max="247"
        /></label>
        <label class="form-field"
          ><span class="form-label">起始寄存器</span
          ><input v-model.number="sensorForm.register_address" type="number" class="input" min="0"
        /></label>
        <label class="form-field"
          ><span class="form-label">寄存器数量</span
          ><input
            v-model.number="sensorForm.register_count"
            type="number"
            class="input"
            min="1"
            max="16"
        /></label>
        <label class="form-field"
          ><span class="form-label">倍率</span
          ><input
            v-model.number="sensorForm.scale"
            type="number"
            class="input"
            min="0.0001"
            step="0.0001"
        /></label>
        <label class="form-field"
          ><span class="form-label">单位</span
          ><input v-model="sensorForm.unit" class="input" placeholder="℃ / A"
        /></label>
        <label class="form-field"
          ><span class="form-label">供电方式</span
          ><input v-model="sensorForm.power_type" class="input"
        /></label>
        <label class="form-field"
          ><span class="form-label">固件版本</span
          ><input v-model="sensorForm.firmware" class="input"
        /></label>
        <label class="form-check"
          ><button
            type="button"
            class="switch"
            :class="{ on: sensorForm.enabled }"
            @click="sensorForm.enabled = !sensorForm.enabled"
          />启用采集点</label
        >
      </div>
      <div class="form-hint">
        温度通常：从站 1、寄存器 0、数量 1、倍率 0.1；电流通常：数量 3、倍率
        0.01。请以现场设备手册为准。
      </div>
      <div class="form-actions">
        <button class="btn btn-ghost" @click="sensorModal = false">取消</button>
        <button class="btn btn-primary" :disabled="saving" @click="saveSensor">
          {{ saving ? '保存中…' : '保存采集点' }}
        </button>
      </div>
    </BaseModal>

    <BaseModal
      :open="deleteModal"
      title="确认删除"
      subtitle="删除后下一采集周期不再读取该配置"
      @close="deleteModal = false"
    >
      <p style="font-size: 13px; color: var(--muted)">
        确认删除
        <b style="color: var(--text)">{{ deleteTarget?.code }} {{ deleteTarget?.name }}</b
        >？ 网关仍绑定采集点时会拒绝删除。
      </p>
      <div class="form-actions">
        <button class="btn btn-ghost" @click="deleteModal = false">取消</button>
        <button class="btn btn-danger" :disabled="saving" @click="confirmDelete">
          {{ saving ? '删除中…' : '确认删除' }}
        </button>
      </div>
    </BaseModal>
  </section>
</template>

<style scoped>
.config-intro {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 22px;
  margin-bottom: 16px;
}
.config-intro h2 {
  font-size: 17px;
  margin-bottom: 4px;
}
.config-intro p {
  font-size: 12.5px;
  color: var(--muted);
  max-width: 900px;
}
.config-intro-actions {
  margin-left: auto;
  flex: none;
}
.config-intro-stats {
  display: flex;
  gap: 18px;
  margin-left: auto;
  flex-wrap: wrap;
}
.config-intro-stats div {
  min-width: 62px;
  text-align: right;
}
.config-intro-stats b {
  display: block;
  font-size: 19px;
  color: var(--text);
}
.config-intro-stats span {
  font-size: 10.5px;
  color: var(--faint);
}
.config-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.config-toolbar-right {
  margin-left: auto;
}
.config-tabs .count {
  font-size: 10.5px;
  color: var(--faint);
  margin-left: 2px;
}
.config-tabs button.active .count {
  color: #7fe7f7;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.form-field.full {
  grid-column: 1 / -1;
}
.form-label {
  font-size: 11.5px;
  color: var(--faint);
}
.form-field .input {
  width: 100%;
}
.form-field .input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.form-check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--muted);
  padding-top: 18px;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
.form-hint {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 9px;
  font-size: 11.5px;
  color: var(--faint);
  line-height: 1.6;
}
@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .form-field.full {
    grid-column: auto;
  }
  .config-intro {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .config-intro-actions {
    margin-left: 0;
  }
  .config-intro-stats {
    margin-left: 0;
    width: 100%;
  }
  .config-intro-stats div {
    text-align: left;
  }
  .config-toolbar-right {
    margin-left: 0;
    width: 100%;
  }
}
</style>
