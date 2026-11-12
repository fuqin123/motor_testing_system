<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type { NotificationSettings, SettingsResponse, ThresholdMotor } from '@/api/types'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'
import { acceptanceClass, dateTime, timeAgo } from '@/utils/format'

const app = useAppStore()
const ui = useUiStore()

const settings = ref<SettingsResponse | null>(null)
const thresholdMotors = ref<ThresholdMotor[]>([])
const notification = ref<NotificationSettings | null>(null)
const originals = ref<Record<string, string>>({})
const dirty = ref(false)
const saving = ref(false)
const testing = ref(false)
const newOwner = ref('')

const lora = computed(() => settings.value?.lora || app.meta?.lora || null)
const pilot = computed(() => settings.value?.pilot || app.pilot || null)
const nextPoll = computed(() => {
  const value = settings.value?.sampling.next_poll_at
  return value ? `${dateTime(value)}（${timeAgo(value)}）` : '—'
})
const collectorMode = computed(() => {
  const mode = settings.value?.sampling.collector_mode || app.meta?.sampling.collector_mode
  return mode === 'simulator' ? '模拟器（演示）' : '真实 Modbus 网关'
})

function snapshot(motor: ThresholdMotor): string {
  return JSON.stringify({
    temp_limit_c: motor.temp_limit_c,
    current_limit_a: motor.current_limit_a,
    temp_deviation_pct: motor.temp_deviation_pct,
    current_deviation_pct: motor.current_deviation_pct,
    rise_rate_limit_c_per_day: motor.rise_rate_limit_c_per_day,
    notify_enabled: motor.notify_enabled,
  })
}

async function load() {
  try {
    const data = await api.settings()
    settings.value = data
    thresholdMotors.value = structuredClone(data.motors)
    notification.value = structuredClone(data.notifications)
    originals.value = Object.fromEntries(data.motors.map((motor) => [motor.code, snapshot(motor)]))
    dirty.value = false
  } catch (error) {
    ui.notify('err', '设置加载失败', error instanceof Error ? error.message : '')
  }
}

function markDirty() {
  dirty.value = true
}

function currentMax(motor: ThresholdMotor): number {
  return Math.max(
    100,
    Math.ceil(Math.max(motor.rated_current_a * 1.35, motor.current_limit_a * 1.2) / 10) * 10,
  )
}

function rangeStyle(
  value: number,
  min: number,
  max: number,
  color: string,
): Record<string, string> {
  const percent = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
  return { background: `linear-gradient(90deg, ${color} ${percent}%, #1B2742 ${percent}%)` }
}

function toggleNotify(motor: ThresholdMotor) {
  motor.notify_enabled = !motor.notify_enabled
  markDirty()
}

function addOwner() {
  if (!notification.value) return
  const value = newOwner.value.trim()
  if (!value) return
  if (notification.value.owners.includes(value)) {
    ui.notify('info', '责任人已存在', value)
    return
  }
  notification.value.owners.push(value)
  newOwner.value = ''
  markDirty()
}

function removeOwner(index: number) {
  notification.value?.owners.splice(index, 1)
  markDirty()
}

function toggleNotificationField(
  field: 'critical_enabled' | 'warning_enabled' | 'info_enabled' | 'quiet_hours_enabled',
) {
  if (!notification.value) return
  notification.value[field] = !notification.value[field]
  markDirty()
}

async function saveAll() {
  if (!notification.value || saving.value) return
  saving.value = true
  try {
    for (const motor of thresholdMotors.value) {
      if (snapshot(motor) === originals.value[motor.code]) continue
      await api.updateThresholds(motor.code, {
        temp_limit_c: motor.temp_limit_c,
        current_limit_a: motor.current_limit_a,
        temp_deviation_pct: motor.temp_deviation_pct,
        current_deviation_pct: motor.current_deviation_pct,
        rise_rate_limit_c_per_day: motor.rise_rate_limit_c_per_day,
        notify_enabled: motor.notify_enabled,
      })
    }
    await api.updateNotifications({
      critical_enabled: notification.value.critical_enabled,
      warning_enabled: notification.value.warning_enabled,
      info_enabled: notification.value.info_enabled,
      quiet_hours_enabled: notification.value.quiet_hours_enabled,
      quiet_start: notification.value.quiet_start,
      quiet_end: notification.value.quiet_end,
      group_name: notification.value.group_name,
      owners: notification.value.owners,
    })
    ui.notify('ok', '配置已保存并生效', '阈值与通知策略已同步到后台服务')
    await load()
    await app.fetchMeta(true)
  } catch (error) {
    ui.notify('err', '保存失败', error instanceof Error ? error.message : '')
  } finally {
    saving.value = false
  }
}

async function resetSettings() {
  await load()
  ui.notify('info', '已恢复服务器当前配置', '未保存的修改已丢弃')
}

async function testFeishu() {
  if (testing.value) return
  testing.value = true
  try {
    const result = await api.testFeishu()
    if (result.status === 'sent') {
      ui.notify(
        'ok',
        '飞书测试消息已发送',
        `HTTP ${result.response_code ?? '—'} · 尝试 ${result.attempts} 次`,
      )
    } else {
      ui.notify('warn', '飞书测试未发送', result.detail)
    }
  } catch (error) {
    ui.notify('err', '飞书测试失败', error instanceof Error ? error.message : '')
  } finally {
    testing.value = false
  }
}

function acceptanceIcon(status: string): string {
  if (status === 'pass') return 'checkc'
  if (status === 'fail') return 'alert'
  if (status === 'manual') return 'user'
  return 'circle'
}

function acceptanceText(status: string): string {
  if (status === 'pass') return '已达标'
  if (status === 'fail') return '未达标'
  if (status === 'manual') return '人工确认'
  return '待验证'
}

onMounted(() => void load())
</script>

<template>
  <section class="view" id="view-settings">
    <div v-if="!settings || !notification" class="card loading-block">
      <span class="spinner" />加载设置…
    </div>
    <template v-else>
      <div class="settings-grid">
        <div>
          <div class="card set-section">
            <div class="card-head">
              <h3>阈值配置</h3>
              <div class="right"><span class="badge mut">超过上限即触发飞书提醒</span></div>
              <div class="sub">温度上限 / 电流上限 / 偏离基线 / 温升速率 · 修改后点击底部保存</div>
            </div>
            <div v-for="motor in thresholdMotors" :key="motor.code" class="settings-motor-block">
              <div class="settings-motor-head">
                <b>{{ motor.code }} · {{ motor.name }}</b>
                <span
                  v-if="motor.pilot"
                  class="badge pilot"
                  style="font-size: 10px; padding: 1px 7px"
                  >试点</span
                >
                <span class="hint">阈值越限即通知责任人</span>
                <button
                  class="switch"
                  :class="{ on: motor.notify_enabled }"
                  :aria-label="`${motor.code} 通知开关`"
                  @click="toggleNotify(motor)"
                />
              </div>
              <div class="settings-motor-body">
                <div class="settings-slider">
                  <span class="k">温度上限</span>
                  <input
                    v-model.number="motor.temp_limit_c"
                    type="range"
                    class="range"
                    min="40"
                    max="120"
                    step="1"
                    :style="rangeStyle(motor.temp_limit_c, 40, 120, '#FFB224')"
                    @input="markDirty"
                  />
                  <span class="range-val amber">{{ motor.temp_limit_c }} °C</span>
                </div>
                <div class="settings-slider">
                  <span class="k">电流上限</span>
                  <input
                    v-model.number="motor.current_limit_a"
                    type="range"
                    class="range"
                    min="0"
                    :max="currentMax(motor)"
                    step="1"
                    :style="rangeStyle(motor.current_limit_a, 0, currentMax(motor), '#2DD4EE')"
                    @input="markDirty"
                  />
                  <span class="range-val">{{ Math.round(motor.current_limit_a) }} A</span>
                </div>
                <div class="settings-two-col">
                  <div class="settings-slider">
                    <span class="k">温度偏离基线</span>
                    <input
                      v-model.number="motor.temp_deviation_pct"
                      type="number"
                      class="input"
                      min="0"
                      max="100"
                      step="0.5"
                      style="width: 90px"
                      @input="markDirty"
                    />
                    <span style="font-size: 12px; color: var(--faint)">%</span>
                  </div>
                  <div class="settings-slider">
                    <span class="k">温升速率线</span>
                    <input
                      v-model.number="motor.rise_rate_limit_c_per_day"
                      type="number"
                      class="input"
                      min="0"
                      max="20"
                      step="0.1"
                      style="width: 90px"
                      @input="markDirty"
                    />
                    <span style="font-size: 12px; color: var(--faint)">°C/天</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="card set-section">
            <div class="card-head"><h3>采集与链路参数</h3></div>
            <div class="set-row">
              <span class="k">采样上报间隔</span>
              <div class="grow">
                <span class="tag">{{ settings.sampling.interval_minutes }} 分钟</span
                ><span class="hint">现场传感器市电供电，15 分钟周期可兼顾时效与 LoRa 空口占用</span>
              </div>
            </div>
            <div class="set-row">
              <span class="k">LoRa 射频参数</span>
              <div class="grow" style="flex-wrap: wrap">
                <span class="tag">{{ lora?.frequency_mhz }} MHz</span>
                <span class="tag">{{ lora?.baud_rate }} bps</span>
                <span class="tag">SF{{ lora?.sf }}</span>
                <span class="tag">BW {{ lora?.bw_khz }} kHz</span>
                <span class="tag">CR {{ lora?.cr }}</span>
                <span class="hint">参数由网关侧配置，后台记录展示</span>
              </div>
            </div>
            <div class="set-row">
              <span class="k">网关上联方式</span>
              <div class="grow">
                <span class="tag">厂区网口</span
                ><span class="hint">网关经现有厂区网络上联，无需新增布线</span>
              </div>
            </div>
            <div class="set-row">
              <span class="k">采集模式 / 下次采集</span>
              <div class="grow">
                <span class="badge info">{{ collectorMode }}</span
                ><span class="hint">{{ nextPoll }}</span>
              </div>
            </div>
            <div class="set-row">
              <span class="k">数据存储</span>
              <div class="grow">
                <StateBadge tone="ok" label="本地数据库 · 数据不出厂" />
                <span class="hint"
                  >保留 {{ app.meta?.retention_days || 180 }} 天 · 只监测只报警</span
                >
              </div>
            </div>
            <p class="settings-note">
              LoRa 参数当前按现场实测配置为
              <b>{{ lora?.frequency_mhz }}MHz / {{ lora?.baud_rate }}bps</b>。
              若网关频点或串口速率调整，请同步修改部署环境变量并重启采集服务。
            </p>
          </div>
        </div>

        <div>
          <div class="card set-section">
            <div class="card-head">
              <h3>飞书通知</h3>
              <div class="right">
                <StateBadge
                  :tone="settings.feishu.configured ? 'ok' : 'mut'"
                  :label="settings.feishu.configured ? '机器人在线' : '未配置 Webhook'"
                />
              </div>
            </div>
            <div class="set-row">
              <span class="k">Webhook 地址</span>
              <div class="grow">
                <input
                  class="input"
                  :value="
                    settings.feishu.masked_webhook ||
                    '未配置（通过环境变量 MP_FEISHU_WEBHOOK_URL 设置）'
                  "
                  readonly
                />
              </div>
            </div>
            <div class="set-row">
              <span class="k">通知群</span>
              <div class="grow">
                <input v-model="notification.group_name" class="input" @input="markDirty" />
              </div>
            </div>
            <div class="set-row" style="align-items: flex-start">
              <span class="k">异常响应责任人</span>
              <div class="grow" style="flex-direction: column; align-items: stretch">
                <div class="owner-chips">
                  <span
                    v-for="(owner, index) in notification.owners"
                    :key="`${owner}-${index}`"
                    class="person-chip"
                  >
                    <span
                      class="avatar"
                      style="background: linear-gradient(135deg, #4f8cff, #9d7cff); color: #fff"
                      >{{ owner.slice(0, 1) }}</span
                    >
                    {{ owner }}
                    <button :aria-label="`移除 ${owner}`" @click="removeOwner(index)">
                      <Icon name="x" :size="12" />
                    </button>
                  </span>
                </div>
                <div class="owner-add">
                  <input
                    v-model="newOwner"
                    class="input"
                    placeholder="如：张工 · 电气"
                    @keydown.enter.prevent="addOwner"
                  />
                  <button class="btn btn-ghost btn-sm" @click="addOwner">
                    <Icon name="plus" :size="13" /> 添加
                  </button>
                </div>
              </div>
            </div>
            <div class="set-row">
              <span class="k">严重告警</span>
              <div class="grow">
                <span style="font-size: 12.5px; color: var(--muted)">立即推送 + @责任人</span>
                <button
                  class="switch"
                  :class="{ on: notification.critical_enabled }"
                  aria-label="严重告警通知开关"
                  @click="toggleNotificationField('critical_enabled')"
                />
              </div>
            </div>
            <div class="set-row">
              <span class="k">警告 / 提示</span>
              <div class="grow">
                <span style="font-size: 12.5px; color: var(--muted)">按级别开关推送</span>
                <button
                  class="switch"
                  :class="{ on: notification.warning_enabled }"
                  aria-label="警告通知开关"
                  @click="toggleNotificationField('warning_enabled')"
                />
                <button
                  class="switch"
                  :class="{ on: notification.info_enabled }"
                  aria-label="提示通知开关"
                  @click="toggleNotificationField('info_enabled')"
                />
              </div>
            </div>
            <div class="set-row">
              <span class="k">夜间静默</span>
              <div class="grow">
                <button
                  class="switch"
                  :class="{ on: notification.quiet_hours_enabled }"
                  aria-label="夜间静默开关"
                  @click="toggleNotificationField('quiet_hours_enabled')"
                />
                <input
                  v-model="notification.quiet_start"
                  class="input"
                  type="time"
                  style="width: 105px"
                  :disabled="!notification.quiet_hours_enabled"
                  @input="markDirty"
                />
                <span style="color: var(--faint)">至</span>
                <input
                  v-model="notification.quiet_end"
                  class="input"
                  type="time"
                  style="width: 105px"
                  :disabled="!notification.quiet_hours_enabled"
                  @input="markDirty"
                />
                <span class="hint">严重告警不受静默限制</span>
              </div>
            </div>
            <div style="padding: 14px 20px 18px">
              <button
                class="btn btn-ghost"
                :disabled="testing"
                style="width: 100%; justify-content: center"
                @click="testFeishu"
              >
                <Icon name="send" :size="15" /> {{ testing ? '发送中…' : '发送测试消息' }}
              </button>
            </div>
          </div>

          <div class="card set-section">
            <div class="card-head">
              <h3>试点与验收</h3>
              <div class="right">
                <span class="badge pilot">第 {{ pilot?.current_day }} / {{ pilot?.days }} 天</span>
              </div>
            </div>
            <div class="pilot-progress">
              <div class="progress"><i :style="{ width: `${pilot?.progress_pct || 0}%` }" /></div>
              <p>{{ pilot?.scope }}</p>
            </div>
            <div class="acceptance-list">
              <div
                v-for="item in settings.acceptance.items"
                :key="item.key"
                class="acceptance-item"
              >
                <Icon :name="acceptanceIcon(item.status)" :size="16" />
                <div>
                  <b>{{ item.label }}</b>
                  <p>{{ item.detail }}</p>
                </div>
                <span :class="['state', acceptanceClass(item.status)]">{{
                  acceptanceText(item.status)
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="save-bar">
        <Icon name="shield" :size="18" style="color: var(--green)" />
        <p>
          配置保存在本地服务器，立即生效；本平台<b style="color: var(--text)">只监测、只报警</b
          >，不下发任何控制指令。
        </p>
        <div class="save-actions">
          <button class="btn btn-ghost" @click="resetSettings">恢复当前配置</button>
          <button class="btn btn-primary" :disabled="saving" @click="saveAll">
            <Icon name="check" :size="15" />
            {{ saving ? '保存中…' : dirty ? '保存更改 ●' : '保存配置' }}
          </button>
        </div>
      </div>
    </template>
  </section>
</template>
