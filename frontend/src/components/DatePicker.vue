<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import Icon from './Icon.vue'

const props = withDefaults(defineProps<{ modelValue: string; max?: string }>(), { max: '' })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function ymd(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const today = ymd(new Date())
const maxDate = computed(() => props.max || today)
const selected = computed(() => parseDate(props.modelValue) || new Date())
const viewYear = ref(selected.value.getFullYear())
const viewMonth = ref(selected.value.getMonth())

function parseDate(value: string): Date | null {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day)
}

function monthLabel(): string {
  return `${viewYear.value} 年 ${viewMonth.value + 1} 月`
}

function moveMonth(delta: number) {
  const date = new Date(viewYear.value, viewMonth.value + delta, 1)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

const cells = computed(() => {
  const first = new Date(viewYear.value, viewMonth.value, 1)
  const offset = (first.getDay() + 6) % 7
  const total = new Date(viewYear.value, viewMonth.value + 1, 0).getDate()
  const result: Array<{ day: number; date: string; disabled: boolean; outside: boolean }> = []
  for (let index = 0; index < offset; index += 1) {
    result.push({ day: 0, date: '', disabled: true, outside: true })
  }
  for (let day = 1; day <= total; day += 1) {
    const date = `${viewYear.value}-${pad(viewMonth.value + 1)}-${pad(day)}`
    result.push({ day, date, disabled: date > maxDate.value, outside: false })
  }
  return result
})

function choose(date: string) {
  emit('update:modelValue', date)
  open.value = false
}

function chooseToday() {
  choose(today)
  viewYear.value = new Date().getFullYear()
  viewMonth.value = new Date().getMonth()
}

function chooseYesterday() {
  const date = new Date()
  date.setDate(date.getDate() - 1)
  const value = ymd(date)
  choose(value)
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

function toggle() {
  open.value = !open.value
  const date = selected.value
  viewYear.value = date.getFullYear()
  viewMonth.value = date.getMonth()
}

function onDocumentClick(event: MouseEvent) {
  if (!open.value || !root.value) return
  if (!root.value.contains(event.target as Node)) open.value = false
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false
}

watch(
  () => props.modelValue,
  () => {
    const date = selected.value
    viewYear.value = date.getFullYear()
    viewMonth.value = date.getMonth()
  },
)

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="root" class="date-picker">
    <button type="button" class="date-trigger" :aria-expanded="open" @click.stop="toggle">
      <Icon name="calendar" :size="16" />
      <span class="num">{{ props.modelValue }}</span>
      <Icon name="chevR" :size="13" class="date-chev" />
    </button>

    <Transition name="date-fade">
      <div v-if="open" class="date-panel" @click.stop>
        <div class="date-panel-head">
          <button type="button" class="date-nav" aria-label="上个月" @click="moveMonth(-1)">
            <Icon name="chevR" :size="15" style="transform: rotate(180deg)" />
          </button>
          <b>{{ monthLabel() }}</b>
          <button type="button" class="date-nav" aria-label="下个月" @click="moveMonth(1)">
            <Icon name="chevR" :size="15" />
          </button>
        </div>

        <div class="date-week">
          <span v-for="weekday in ['一', '二', '三', '四', '五', '六', '日']" :key="weekday">
            {{ weekday }}
          </span>
        </div>

        <div class="date-grid">
          <button
            v-for="(cell, index) in cells"
            :key="`${cell.date}-${index}`"
            type="button"
            :disabled="cell.disabled || cell.outside"
            :class="[
              'date-cell',
              cell.date === props.modelValue ? 'selected' : '',
              cell.date === today ? 'today' : '',
            ]"
            @click="cell.date && choose(cell.date)"
          >
            {{ cell.day || '' }}
          </button>
        </div>

        <div class="date-panel-foot">
          <button type="button" class="date-quick" @click="chooseYesterday">昨天</button>
          <button type="button" class="date-quick primary" @click="chooseToday">今天</button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.date-picker {
  position: relative;
}
.date-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: var(--panel-2);
  color: var(--text);
  font-size: 12.5px;
  font-weight: 600;
  transition: border 0.18s, color 0.18s;
}
.date-trigger:hover,
.date-trigger[aria-expanded='true'] {
  border-color: rgba(45, 212, 238, 0.5);
  color: #7fe7f7;
}
.date-chev {
  color: var(--faint);
  transform: rotate(90deg);
}
.date-panel {
  position: absolute;
  z-index: 80;
  top: calc(100% + 8px);
  right: 0;
  width: 286px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #0f1830;
  box-shadow: 0 18px 44px rgba(2, 6, 18, 0.7);
}
.date-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 2px 10px;
  font-size: 13px;
}
.date-nav {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--muted);
  border: 1px solid var(--line-soft);
  background: var(--panel-3);
}
.date-nav:hover {
  color: var(--text);
  border-color: var(--line);
}
.date-week {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  padding: 4px 0 6px;
  color: var(--faint);
  font-size: 10.5px;
  text-align: center;
}
.date-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 3px;
}
.date-cell {
  height: 32px;
  border-radius: 8px;
  color: var(--muted);
  font-size: 12px;
  border: 1px solid transparent;
}
.date-cell:hover:not(:disabled) {
  background: rgba(45, 212, 238, 0.1);
  color: var(--text);
}
.date-cell.today {
  color: #7fe7f7;
  border-color: rgba(45, 212, 238, 0.35);
}
.date-cell.selected {
  background: linear-gradient(135deg, rgba(45, 212, 238, 0.25), rgba(79, 140, 255, 0.22));
  border-color: rgba(45, 212, 238, 0.6);
  color: #fff;
  font-weight: 700;
}
.date-cell:disabled {
  opacity: 0.22;
  cursor: not-allowed;
}
.date-panel-foot {
  display: flex;
  gap: 8px;
  padding-top: 10px;
  margin-top: 8px;
  border-top: 1px solid var(--line-soft);
}
.date-quick {
  flex: 1;
  padding: 7px 0;
  border-radius: 8px;
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 12px;
}
.date-quick:hover {
  color: var(--text);
}
.date-quick.primary {
  color: #7fe7f7;
  border-color: rgba(45, 212, 238, 0.4);
  background: rgba(45, 212, 238, 0.08);
}
.date-fade-enter-active,
.date-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}
.date-fade-enter-from,
.date-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (max-width: 520px) {
  .date-panel {
    right: auto;
    left: 0;
    width: min(286px, calc(100vw - 32px));
  }
}
</style>
