<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type { FeishuAppSettings, NotificationSettings } from '@/api/types'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useUiStore } from '@/stores/ui'
import { dateTime, timeAgo } from '@/utils/format'

const ui = useUiStore()

const appSettings = ref<FeishuAppSettings | null>(null)
const notification = ref<NotificationSettings | null>(null)
const appForm = ref({ enabled: false, app_id: '', app_secret: '', chat_id: '' })
const loading = ref(false)
const saving = ref(false)
const savingPolicy = ref(false)
const testing = ref(false)
const newOwner = ref('')

const connection = computed(() => appSettings.value?.long_connection || null)
const appReady = computed(
  () =>
    Boolean(appForm.value.app_id) &&
    Boolean(appForm.value.chat_id) &&
    (Boolean(appForm.value.app_secret) || Boolean(appSettings.value?.secret_set)),
)

async function load() {
  loading.value = true
  try {
    const [appData, settingsData] = await Promise.all([api.feishuSettings(), api.settings()])
    appSettings.value = appData
    notification.value = structuredClone(settingsData.notifications)
    appForm.value = {
      enabled: appData.enabled,
      app_id: appData.app_id,
      app_secret: '',
      chat_id: appData.chat_id,
    }
  } catch (error) {
    ui.notify('err', '通知配置加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

async function saveApp() {
  if (appForm.value.enabled && !appReady.value) {
    ui.notify('warn', '飞书应用凭据不完整', '启用前请填写 App ID、App Secret 和 Chat ID')
    return
  }
  saving.value = true
  try {
    const updated = await api.updateFeishuSettings({
      enabled: appForm.value.enabled,
      app_id: appForm.value.app_id.trim(),
      app_secret: appForm.value.app_secret.trim() || undefined,
      chat_id: appForm.value.chat_id.trim(),
    })
    appSettings.value = updated
    appForm.value.app_secret = ''
    if (updated.long_connection.restart_required) {
      ui.notify('warn', '应用配置已保存', 'App ID 已变更，请重启 backend 以重建长连接')
    } else {
      ui.notify('ok', '飞书应用配置已保存', '长连接会自动尝试启动')
    }
  } catch (error) {
    ui.notify('err', '保存失败', error instanceof Error ? error.message : '')
  } finally {
    saving.value = false
  }
}

async function testApp() {
  testing.value = true
  try {
    const result = await api.testFeishuApp()
    if (result.status === 'sent') {
      ui.notify('ok', '飞书测试消息已发送', '请到绑定的群聊中查看')
    } else {
      ui.notify('warn', '飞书测试消息未发送', result.detail)
    }
  } catch (error) {
    ui.notify('err', '飞书测试失败', error instanceof Error ? error.message : '')
  } finally {
    testing.value = false
  }
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
}

function removeOwner(index: number) {
  notification.value?.owners.splice(index, 1)
}

function toggle(field: 'critical_enabled' | 'warning_enabled' | 'info_enabled' | 'quiet_hours_enabled') {
  if (!notification.value) return
  notification.value[field] = !notification.value[field]
}

async function savePolicy() {
  if (!notification.value) return
  savingPolicy.value = true
  try {
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
    ui.notify('ok', '通知策略已保存', '责任人、级别开关与夜间静默已生效')
  } catch (error) {
    ui.notify('err', '通知策略保存失败', error instanceof Error ? error.message : '')
  } finally {
    savingPolicy.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <section class="view notification-page" id="view-notifications">
    <div class="config-intro card">
      <div>
        <h2>飞书通知机器人</h2>
        <p>
          绑定企业自建应用后，平台会把异常电机快照上传到飞书，并发送带“已解决 / 未解决”按钮的富文本卡片；
          长连接订阅卡片回传，责任人点击按钮即可完成告警闭环。
        </p>
      </div>
      <div class="config-intro-actions">
        <button class="mini-btn" @click="load"><Icon name="refresh" :size="14" /> 刷新</button>
      </div>
    </div>

    <div v-if="loading" class="card loading-block"><span class="spinner" />加载通知配置…</div>
    <template v-else-if="appSettings && notification">
      <div class="notification-grid">
        <div class="card">
          <div class="card-head">
            <h3>飞书应用凭据</h3>
            <div class="right">
              <StateBadge :tone="appForm.enabled ? 'ok' : 'mut'" :label="appForm.enabled ? '已启用' : '未启用'" />
            </div>
            <div class="sub">在飞书开放平台创建企业自建应用，开启机器人能力，并添加 im:message、im:resource 权限</div>
          </div>
          <div class="set-row">
            <span class="k">App ID</span>
            <div class="grow"><input v-model="appForm.app_id" class="input" placeholder="cli_xxxxxxxxxxxxxxxx" /></div>
          </div>
          <div class="set-row">
            <span class="k">App Secret</span>
            <div class="grow">
              <input
                v-model="appForm.app_secret"
                class="input"
                type="password"
                autocomplete="new-password"
                :placeholder="appSettings.secret_set ? '已保存，留空保持不变' : '请输入 App Secret'"
              />
            </div>
          </div>
          <div class="set-row">
            <span class="k">Chat ID</span>
            <div class="grow">
              <input v-model="appForm.chat_id" class="input" placeholder="oc_xxxxxxxxxxxxxxxx" />
              <span class="hint">飞书群设置中获取，机器人需先加入该群</span>
            </div>
          </div>
          <div class="set-row">
            <span class="k">启用应用通知</span>
            <div class="grow">
              <button class="switch" :class="{ on: appForm.enabled }" @click="appForm.enabled = !appForm.enabled" />
              <span class="hint">启用后告警优先通过飞书应用发送，Webhook 作为兼容回退</span>
            </div>
          </div>
          <div class="notification-actions">
            <button class="btn btn-ghost" :disabled="testing" @click="testApp">
              <Icon name="send" :size="15" /> {{ testing ? '发送中…' : '发送测试消息' }}
            </button>
            <button class="btn btn-primary" :disabled="saving" @click="saveApp">
              <Icon name="check" :size="15" /> {{ saving ? '保存中…' : '保存应用配置' }}
            </button>
          </div>
          <p class="settings-note">
            凭据只保存在本地数据库，接口不会回传 App Secret。修改 App ID 后长连接需要重启 backend 才能重建。
          </p>
        </div>

        <div class="card">
          <div class="card-head">
            <h3>长连接与卡片回调</h3>
            <div class="right">
              <StateBadge
                :tone="connection?.running ? 'ok' : connection?.restart_required ? 'warn' : 'mut'"
                :label="connection?.running ? '长连接运行中' : connection?.restart_required ? '需重启' : '未连接'"
              />
            </div>
            <div class="sub">飞书官方 SDK 长连接订阅 card.action.trigger，无需公网回调地址</div>
          </div>
          <div class="connection-rows">
            <div class="connection-row"><span>连接状态</span><b>{{ connection?.running ? '运行中' : '未连接' }}</b></div>
            <div class="connection-row"><span>订阅事件</span><b>card.action.trigger</b></div>
            <div class="connection-row"><span>最近回调</span><b>{{ connection?.last_event_at ? dateTime(connection.last_event_at) : '—' }}</b></div>
            <div class="connection-row"><span>最近事件</span><b>{{ connection?.last_event_at ? timeAgo(connection.last_event_at) : '—' }}</b></div>
          </div>
          <div v-if="connection?.last_error" class="notice-box connection-error">{{ connection.last_error }}</div>
          <div v-if="connection?.restart_required" class="notice-box" style="margin: 12px 20px 0; border-color: rgba(255,178,36,.35); color: #ffc65c">
            飞书应用凭据已变更，请重启 backend：<code>docker compose restart backend</code>
          </div>
          <div class="connection-guide">
            <b>飞书侧配置步骤</b>
            <ol>
              <li>开放平台创建企业自建应用，添加机器人能力。</li>
              <li>添加权限：发送消息、上传图片、读取群信息。</li>
              <li>事件订阅选择“长连接”，添加“卡片回传交互”事件。</li>
              <li>把机器人加入目标群，复制群 Chat ID 填入左侧。</li>
              <li>发布应用版本，等待管理员审核通过。</li>
            </ol>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head">
          <h3>通知策略</h3>
          <div class="right"><StateBadge tone="info" label="收到告警后按策略推送" /></div>
          <div class="sub">责任人、级别开关和夜间静默；严重告警不受夜间静默限制</div>
        </div>
        <div class="policy-grid">
          <div class="set-row">
            <span class="k">通知群名称</span>
            <div class="grow"><input v-model="notification.group_name" class="input" /></div>
          </div>
          <div class="set-row">
            <span class="k">异常响应责任人</span>
            <div class="grow" style="flex-direction: column; align-items: stretch">
              <div class="owner-chips">
                <span v-for="(owner, index) in notification.owners" :key="`${owner}-${index}`" class="person-chip">
                  <span class="avatar" style="background: linear-gradient(135deg, #4f8cff, #9d7cff); color: #fff">{{ owner.slice(0, 1) }}</span>
                  {{ owner }}
                  <button :aria-label="`移除 ${owner}`" @click="removeOwner(index)"><Icon name="x" :size="12" /></button>
                </span>
              </div>
              <div class="owner-add">
                <input v-model="newOwner" class="input" placeholder="如：张工 · 电气" @keydown.enter.prevent="addOwner" />
                <button class="btn btn-ghost btn-sm" @click="addOwner"><Icon name="plus" :size="13" /> 添加</button>
              </div>
            </div>
          </div>
          <div class="set-row">
            <span class="k">严重告警</span>
            <div class="grow"><span class="hint">立即推送并 @ 责任人</span><button class="switch" :class="{ on: notification.critical_enabled }" @click="toggle('critical_enabled')" /></div>
          </div>
          <div class="set-row">
            <span class="k">警告 / 提示</span>
            <div class="grow"><span class="hint">按级别开关推送</span><button class="switch" :class="{ on: notification.warning_enabled }" @click="toggle('warning_enabled')" /><button class="switch" :class="{ on: notification.info_enabled }" @click="toggle('info_enabled')" /></div>
          </div>
          <div class="set-row">
            <span class="k">夜间静默</span>
            <div class="grow">
              <button class="switch" :class="{ on: notification.quiet_hours_enabled }" @click="toggle('quiet_hours_enabled')" />
              <input v-model="notification.quiet_start" class="input" type="time" style="width: 105px" :disabled="!notification.quiet_hours_enabled" />
              <span style="color: var(--faint)">至</span>
              <input v-model="notification.quiet_end" class="input" type="time" style="width: 105px" :disabled="!notification.quiet_hours_enabled" />
              <span class="hint">严重告警不受静默限制</span>
            </div>
          </div>
          <div class="policy-actions">
            <button class="btn btn-primary" :disabled="savingPolicy" @click="savePolicy">
              <Icon name="check" :size="15" /> {{ savingPolicy ? '保存中…' : '保存通知策略' }}
            </button>
          </div>
        </div>
      </div>
    </template>
    <div v-else class="card empty-state"><b>通知配置不可用</b>请检查后端服务。</div>
  </section>
</template>

<style scoped>
.notification-page {
  min-height: calc(100vh - var(--topbar-h) - 52px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.config-intro {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px 22px;
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
.notification-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.notification-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 18px 20px;
  flex-wrap: wrap;
}
.connection-rows {
  padding: 6px 20px 0;
}
.connection-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--line-soft);
  font-size: 12.5px;
  color: var(--muted);
}
.connection-row:first-child {
  border-top: none;
}
.connection-row b {
  color: var(--text);
  text-align: right;
}
.connection-error {
  margin: 12px 20px 0;
  border-color: rgba(255, 77, 109, 0.3);
  color: #ff8296;
}
.connection-guide {
  margin: 16px 20px 20px;
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 11px;
  background: var(--panel-2);
}
.connection-guide b {
  display: block;
  font-size: 12.5px;
  margin-bottom: 8px;
}
.connection-guide ol {
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 11.5px;
  line-height: 1.8;
}
.policy-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
.policy-grid .set-row {
  border-top: 1px solid var(--line-soft);
}
.policy-grid .set-row:nth-child(-n + 2) {
  border-top: none;
}
.policy-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px 20px;
}
@media (max-width: 1100px) {
  .notification-grid,
  .policy-grid {
    grid-template-columns: 1fr;
  }
  .policy-grid .set-row:nth-child(2) {
    border-top: 1px solid var(--line-soft);
  }
  .config-intro {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .config-intro-actions {
    margin-left: 0;
  }
}
</style>
