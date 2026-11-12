<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'

import Icon from './Icon.vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    subtitle?: string
  }>(),
  { subtitle: '' },
)
const emit = defineEmits<{ close: [] }>()

function handleKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) emit('close')
}

watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
  },
)

onMounted(() => window.addEventListener('keydown', handleKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="scrim-fade">
      <div v-if="props.open" class="scrim show" @click="emit('close')" />
    </Transition>
    <Transition name="drawer-slide">
      <aside v-if="props.open" class="drawer show" role="dialog" aria-modal="true">
        <div class="drawer-head">
          <div style="min-width: 0">
            <h3>{{ props.title }}</h3>
            <div class="sub">{{ props.subtitle }}</div>
          </div>
          <slot name="badge" />
          <button class="icon-btn drawer-close" aria-label="关闭" @click="emit('close')">
            <Icon name="x" />
          </button>
        </div>
        <div class="drawer-body">
          <slot />
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>

<style scoped>
.scrim-fade-enter-active,
.scrim-fade-leave-active {
  transition: opacity 0.25s ease;
}
.scrim-fade-enter-from,
.scrim-fade-leave-to {
  opacity: 0;
}
.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 0.38s cubic-bezier(0.22, 0.75, 0.25, 1);
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(105%);
}
</style>
