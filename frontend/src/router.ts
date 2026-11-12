import { createRouter, createWebHistory } from 'vue-router'

const OverviewView = () => import('@/views/OverviewView.vue')
const AnalysisView = () => import('@/views/AnalysisView.vue')
const AlarmsView = () => import('@/views/AlarmsView.vue')
const TopologyView = () => import('@/views/TopologyView.vue')
const DeviceConfigView = () => import('@/views/DeviceConfigView.vue')
const SettingsView = () => import('@/views/SettingsView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/overview' },
    {
      path: '/overview',
      name: 'overview',
      component: OverviewView,
      meta: { title: '监测总览', crumb: '监测中心 / 监测总览' },
    },
    {
      path: '/analysis',
      name: 'analysis',
      component: AnalysisView,
      meta: { title: '对比分析', crumb: '监测中心 / 对比分析 · 自身比 · 同类比 · 关联比 · 趋势比' },
    },
    {
      path: '/alarms',
      name: 'alarms',
      component: AlarmsView,
      meta: { title: '告警中心', crumb: '监测中心 / 告警中心 · 飞书通知与处理闭环' },
    },
    {
      path: '/topology',
      name: 'topology',
      component: TopologyView,
      meta: { title: '设备与链路', crumb: '系统管理 / 设备与链路 · LoRa 全链路' },
    },
    {
      path: '/device-config',
      name: 'device-config',
      component: DeviceConfigView,
      meta: { title: '设备配置', crumb: '系统管理 / 设备配置 · 电机 / 网关 / 采集点' },
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView,
      meta: { title: '阈值与通知', crumb: '系统管理 / 阈值与通知 · 采集参数与飞书机器人' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/overview' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '监测总览')} · MotorPulse`
})

export default router
