<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '@/api/client'
import type { Alarm } from '@/api/types'
import BaseDrawer from '@/components/BaseDrawer.vue'
import Icon from '@/components/Icon.vue'
import StateBadge from '@/components/StateBadge.vue'
import { useUiStore } from '@/stores/ui'
import {
  ALARM_STATUS_TEXT,
  LEVEL_TEXT,
  NOTIFICATION_TEXT,
  dateTime,
  fmt,
  timeAgo,
} from '@/utils/format'

const props = defineProps<{ open: boolean; alarmId: number | null }>()
const emit = defineEmits<{ close: []; updated: [] }>()
const ui = useUiStore()
const router = useRouter()

const loading = ref(false)
const detail = ref<Alarm | null>(null)
const solution = ref('')
const submitting = ref(false)

async function load() {
  if (!props.alarmId) return
  loading.value = true
  try {
    detail.value = await api.alarm(props.alarmId)
  } catch (error) {
    ui.notify('err', '告警详情加载失败', error instanceof Error ? error.message : '')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.open, props.alarmId],
  () => {
    if (props.open && props.alarmId) void load()
  },
)

const canAck = computed(() => detail.value?.status === 'open')
const canClose = computed(() => detail.value && detail.value.status !== 'closed')

async function acknowledge() {
  if (!detail.value) return
  try {
    detail.value = await api.ackAlarm(detail.value.id)
    ui.notify('ok', `${detail.value.code} 已签收`, '已通知责任人开始处理')
    emit('updated')
  } catch (error) {
    ui.notify('err', '签收失败', error instanceof Error ? error.message : '')
  }
}

async function closeAlarm() {
  if (!detail.value || submitting.value) return
  submitting.value = true
  try {
    detail.value = await api.closeAlarm(detail.value.id, solution.value.trim())
    solution.value = ''
    ui.notify('ok', `${detail.value.code} 已闭环`, '处理结果已写入审计记录')
    emit('updated')
  } catch (error) {
    ui.notify('err', '闭环失败', error instanceof Error ? error.message : '')
  } finally {
    submitting.value = false
  }
}

function goAnalysis() {
  if (!detail.value?.motor_code) return
  emit('close')
  void router.push({ path: '/analysis', query: { motor: detail.value.motor_code } })
}
</script>

<template>
  <BaseDrawer
    :open="props.open"
    :title="detail ? `${detail.code} · ${detail.title}` : '告警详情'"
    :subtitle="
      detail
        ? `${detail.motor_code || detail.device_code || ''} · ${dateTime(detail.triggered_at)} · ${timeAgo(detail.triggered_at)}`
        : ''
    "
    @close="emit('close')"
  >
    <template v-if="detail" #badge>
      <StateBadge :tone="detail.level" :label="LEVEL_TEXT[detail.level]" style="margin-left: 6px" />
    </template>

    <div v-if="loading" class="loading-block"><span class="spinner" />加载中…</div>
    <template v-else-if="detail">
      <div class="drawer-sec">
        <h4>告警详情</h4>
        <p style="font-size: 13px; color: var(--muted); margin-bottom: 12px">
          {{ detail.description }}
        </p>
        <div class="info-grid">
          <div class="info-cell">
            <div class="l">触发值</div>
            <div class="v num" style="color: #ff8296">
              {{ detail.value === null ? '—' : `${fmt(detail.value)} ${detail.unit}` }}
            </div>
          </div>
          <div class="info-cell">
            <div class="l">阈值</div>
            <div class="v num">
              {{ detail.threshold === null ? '—' : `${fmt(detail.threshold)} ${detail.unit}` }}
            </div>
          </div>
          <div class="info-cell">
            <div class="l">责任人</div>
            <div class="v">{{ detail.owner }}</div>
          </div>
          <div class="info-cell">
            <div class="l">当前状态</div>
            <div class="v">{{ ALARM_STATUS_TEXT[detail.status] }}</div>
          </div>
        </div>
      </div>

      <div class="drawer-sec">
        <h4>飞书通知</h4>
        <div class="feishu-card">
          <div :class="['fc-head', detail.level === 'crit' ? 'crit' : 'warn']">
            <Icon name="alert" :size="15" />
            【{{ LEVEL_TEXT[detail.level] }}】{{ detail.motor_code || detail.device_code }} ·
            {{ detail.title }}
          </div>
          <div class="fc-body">
            <div class="fc-row">
              <span>触发值</span
              ><b class="num">{{
                detail.value === null ? '—' : `${fmt(detail.value)} ${detail.unit}`
              }}</b>
            </div>
            <div class="fc-row">
              <span>阈值</span
              ><b class="num">{{
                detail.threshold === null ? '—' : `${fmt(detail.threshold)} ${detail.unit}`
              }}</b>
            </div>
            <div class="fc-row">
              <span>时间</span><b class="num">{{ dateTime(detail.triggered_at) }}</b>
            </div>
            <div class="fc-row">
              <span>建议</span
              ><b style="max-width: 62%; text-align: right; font-weight: 500">{{
                detail.advice || '请现场检查确认'
              }}</b>
            </div>
          </div>
          <div class="fc-foot">
            <span class="fc-btn">{{ NOTIFICATION_TEXT[detail.notification_status] }}</span>
            <span class="fc-btn">{{ detail.notification_to || '未配置通知' }}</span>
          </div>
        </div>
        <p v-if="detail.notification" style="font-size: 11px; color: var(--faint); margin-top: 8px">
          最近发送：{{ dateTime(detail.notification.created_at) }} · 尝试
          {{ detail.notification.attempts }} 次 · HTTP
          {{ detail.notification.response_code ?? '—' }}
        </p>
      </div>

      <div class="drawer-sec">
        <h4>处理时间线</h4>
        <div class="timeline">
          <div
            v-for="(item, index) in detail.timeline"
            :key="`${item.key}-${index}`"
            :class="['tl-item', item.state]"
          >
            <b>{{ item.title }}</b>
            <p>{{ item.detail }}</p>
            <time>{{ item.ts ? dateTime(item.ts) : '进行中' }}</time>
          </div>
        </div>
      </div>

      <div v-if="canClose" class="drawer-sec">
        <h4>处理记录（闭环回写）</h4>
        <div class="drawer-form">
          <textarea
            v-model="solution"
            class="input"
            placeholder="记录现场检查与处理结果，例如：清理风道滤网，复测温度回落至 76.8°C…"
          />
          <div style="display: flex; gap: 9px; flex-wrap: wrap">
            <button v-if="canAck" class="btn btn-ghost" @click="acknowledge">
              <Icon name="eye" :size="15" /> 签收处理
            </button>
            <button
              class="btn btn-primary"
              :disabled="submitting"
              style="flex: 1; justify-content: center"
              @click="closeAlarm"
            >
              <Icon name="check" :size="15" /> 确认闭环
            </button>
            <button v-if="detail.motor_code" class="btn btn-ghost" @click="goAnalysis">
              <Icon name="compare" :size="15" /> 查看分析
            </button>
          </div>
        </div>
      </div>
      <div v-else class="advice" style="margin: 0">
        <b><Icon name="checkc" :size="15" /> 已闭环</b>
        <p>{{ detail.solution || '已处理' }}</p>
      </div>
    </template>
  </BaseDrawer>
</template>
