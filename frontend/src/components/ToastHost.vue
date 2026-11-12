<script setup lang="ts">
import { useUiStore } from '@/stores/ui'
import Icon from './Icon.vue'

const ui = useUiStore()

const iconName: Record<string, string> = {
  ok: 'checkc',
  warn: 'alert',
  err: 'alert',
  info: 'info',
}
</script>

<template>
  <div class="toasts">
    <div
      v-for="toast in ui.toasts"
      :key="toast.id"
      :class="['toast', toast.kind]"
      @click="ui.dismiss(toast.id)"
    >
      <Icon :name="iconName[toast.kind] || 'info'" />
      <div style="flex: 1; min-width: 0">
        <b>{{ toast.title }}</b>
        <p v-if="toast.sub">{{ toast.sub }}</p>
      </div>
    </div>
  </div>
</template>
