import { defineStore } from 'pinia'

export type ToastKind = 'ok' | 'warn' | 'err' | 'info'

interface Toast {
  id: number
  kind: ToastKind
  title: string
  sub: string
}

let counter = 0
const timers = new Map<number, number>()

export const useUiStore = defineStore('ui', {
  state: () => ({
    toasts: [] as Toast[],
    sidebarOpen: false,
  }),
  actions: {
    toggleSidebar() {
      this.sidebarOpen = !this.sidebarOpen
    },
    closeSidebar() {
      this.sidebarOpen = false
    },
    notify(kind: ToastKind, title: string, sub = '') {
      const id = ++counter
      this.toasts.push({ id, kind, title, sub })
      while (this.toasts.length > 4) {
        const removed = this.toasts.shift()
        if (removed) {
          const timer = timers.get(removed.id)
          if (timer) window.clearTimeout(timer)
          timers.delete(removed.id)
        }
      }
      const timer = window.setTimeout(() => this.dismiss(id), 3800)
      timers.set(id, timer)
    },
    dismiss(id: number) {
      const timer = timers.get(id)
      if (timer) window.clearTimeout(timer)
      timers.delete(id)
      this.toasts = this.toasts.filter((toast) => toast.id !== id)
    },
  },
})
