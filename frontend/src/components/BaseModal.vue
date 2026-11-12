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
    <Transition name="modal-pop">
      <div v-if="props.open" class="modal show" role="dialog" aria-modal="true">
        <div class="modal-box">
          <div class="modal-head">
            <div style="min-width: 0">
              <h3>{{ props.title }}</h3>
              <div class="sub">{{ props.subtitle }}</div>
            </div>
            <button
              class="icon-btn modal-close"
              style="margin-left: auto"
              aria-label="关闭"
              @click="emit('close')"
            >
              <Icon name="x" />
            </button>
          </div>
          <div class="modal-body">
            <slot />
          </div>
        </div>
      </div>
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
.modal-pop-enter-active,
.modal-pop-leave-active {
  transition: opacity 0.25s ease;
}
.modal-pop-enter-from,
.modal-pop-leave-to {
  opacity: 0;
}
</style>
