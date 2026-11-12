<script setup lang="ts">
import { ICON_PATHS } from '@/utils/icons'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 18 })

const icons = ICON_PATHS
</script>

<template>
  <svg
    :width="props.size"
    :height="props.size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <g v-html="icons[props.name] || ''" />
  </svg>
</template>
