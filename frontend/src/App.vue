<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import Sidebar from '@/components/Sidebar.vue'
import ToastHost from '@/components/ToastHost.vue'
import Topbar from '@/components/Topbar.vue'
import { useAppStore } from '@/stores/app'
import { useUiStore } from '@/stores/ui'

const app = useAppStore()
const ui = useUiStore()
const route = useRoute()

onMounted(async () => {
  await Promise.all([app.fetchMeta(true), app.fetchOverview()])
  app.startPolling()
})

onBeforeUnmount(() => app.stopPolling())
</script>

<template>
  <div class="aurora" />
  <div class="grain" />

  <div class="app">
    <Sidebar />
    <div class="main">
      <Topbar />
      <main class="content">
        <RouterView v-slot="{ Component }">
          <component :is="Component" :key="route.path" />
        </RouterView>
      </main>
    </div>
  </div>

  <div v-if="ui.sidebarOpen" class="scrim show" style="z-index: 94" @click="ui.closeSidebar()" />
  <ToastHost />
</template>
