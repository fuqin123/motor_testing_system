<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    total: number
    page: number
    pageSize: number
    pageSizes?: number[]
    unit?: string
  }>(),
  { pageSizes: () => [10, 20, 50], unit: '条' },
)

const emit = defineEmits<{
  (event: 'update:page', value: number): void
  (event: 'update:pageSize', value: number): void
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const jump = ref('')

watch(
  () => props.page,
  () => {
    jump.value = ''
  },
)

const pages = computed<(number | string)[]>(() => {
  const last = totalPages.value
  const current = Math.min(Math.max(1, props.page), last)
  if (last <= 7) return Array.from({ length: last }, (_, index) => index + 1)
  const picked = new Set<number>([1, last, current, current - 1, current + 1])
  if (current <= 3) [2, 3, 4, 5].forEach((n) => n <= last && picked.add(n))
  if (current >= last - 2)
    [last - 4, last - 3, last - 2, last - 1].forEach((n) => n >= 1 && picked.add(n))
  const ordered = [...picked].filter((n) => n >= 1 && n <= last).sort((a, b) => a - b)
  const result: (number | string)[] = []
  ordered.forEach((n, index) => {
    if (index > 0 && n - ordered[index - 1] > 1) result.push(`gap-${n}`)
    result.push(n)
  })
  return result
})

function go(target: number) {
  const next = Math.min(Math.max(1, Math.round(target)), totalPages.value)
  if (next !== props.page) emit('update:page', next)
}

function changeSize(event: Event) {
  const next = Number((event.target as HTMLSelectElement).value)
  if (Number.isFinite(next) && next > 0) emit('update:pageSize', next)
}

function submitJump() {
  const next = Number(jump.value)
  if (!Number.isFinite(next) || next < 1) {
    jump.value = ''
    return
  }
  go(next)
}
</script>

<template>
  <div class="pager-bar">
    <span class="pager-total">共 <b class="num">{{ total }}</b> {{ unit }}</span>
    <label class="pager-size">
      每页
      <select :value="pageSize" @change="changeSize">
        <option v-for="size in pageSizes" :key="size" :value="size">{{ size }}</option>
      </select>
    </label>
    <div class="pager-pages">
      <button class="pager-step" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <template v-for="item in pages" :key="String(item)">
        <span v-if="typeof item !== 'number'" class="pager-gap">…</span>
        <button
          v-else
          :class="['pager-num', item === Math.min(page, totalPages) ? 'active' : '']"
          @click="go(item)"
        >
          {{ item }}
        </button>
      </template>
      <button class="pager-step" :disabled="page >= totalPages" @click="go(page + 1)">
        下一页
      </button>
    </div>
    <label class="pager-jump">
      跳至
      <input
        v-model="jump"
        type="number"
        min="1"
        :max="totalPages"
        inputmode="numeric"
        @keyup.enter="submitJump"
        @blur="submitJump"
      />
      页
    </label>
  </div>
</template>

<style scoped>
.pager-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 12px 4px 0;
  font-size: 12px;
  color: var(--faint);
}
.pager-total b {
  color: var(--text);
  font-weight: 600;
}
.pager-size,
.pager-jump {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.pager-size select,
.pager-jump input {
  height: 27px;
  border: 1px solid var(--line);
  background: var(--panel-2);
  color: var(--text);
  border-radius: 7px;
  font-size: 12px;
  padding: 0 6px;
  outline: none;
}
.pager-size select {
  padding-right: 4px;
}
.pager-jump input {
  width: 52px;
  text-align: center;
}
.pager-size select:focus,
.pager-jump input:focus {
  border-color: rgba(45, 212, 238, 0.55);
}
.pager-pages {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: auto;
}
.pager-pages button {
  min-width: 27px;
  height: 27px;
  padding: 0 8px;
  border-radius: 7px;
  border: 1px solid var(--line);
  background: var(--panel-2);
  color: var(--muted);
  font-size: 12px;
  transition: all 0.16s var(--ease);
}
.pager-pages button:hover:not(:disabled) {
  color: var(--text);
  border-color: rgba(148, 163, 204, 0.4);
}
.pager-pages button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.pager-num.active {
  background: linear-gradient(135deg, rgba(45, 212, 238, 0.26), rgba(79, 140, 255, 0.2));
  border-color: rgba(45, 212, 238, 0.55) !important;
  color: #eafcff !important;
  font-weight: 650;
}
.pager-gap {
  color: var(--faint);
  padding: 0 2px;
}
@media (max-width: 900px) {
  .pager-pages {
    margin-left: 0;
  }
}
</style>
