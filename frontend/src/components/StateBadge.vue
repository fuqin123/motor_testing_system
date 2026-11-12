<script setup lang="ts">
withDefaults(
  defineProps<{
    tone: 'ok' | 'warn' | 'crit' | 'info' | 'mut' | 'pilot'
    label: string
    dot?: boolean
  }>(),
  { dot: true },
)
</script>

<template>
  <span :class="['badge', tone]">
    <span v-if="dot" class="dot" />
    {{ label }}
  </span>
</template>
