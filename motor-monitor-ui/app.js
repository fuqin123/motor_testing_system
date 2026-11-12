'use strict';
/* ============================================================
   MotorPulse · 大电机风险监测平台 — 静态 UI 参考实现
   无外部依赖 · 种子数据 · 手绘 SVG 图表 · 本地实时模拟
   ============================================================ */

/* ---------------- 工具 ---------------- */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const fmt = (n, d = 1) => Number(n).toFixed(d);
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let UID = 0;
function hashStr(s) { let h = 1779033703; for (let i = 0; i < s.length; i++) { h = Math.imul(h ^ s.charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; } return h >>> 0; }
function rng(seed) { let a = seed; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function timeAgo(ts) {
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return '刚刚'; if (m < 60) return m + ' 分钟前';
  const h = Math.floor(m / 60); if (h < 24) return h + ' 小时前';
  return Math.floor(h / 24) + ' 天前';
}
function hhmm(ts) { const d = new Date(ts); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); }
function mmdd(ts) { const d = new Date(ts); return (d.getMonth() + 1) + '/' + d.getDate(); }

/* ---------------- 图标 ---------------- */
const I = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  compare: '<path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
  radio: '<circle cx="12" cy="12" r="2"/><path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.2 19.1 19.1"/>',
  sliders: '<path d="M4 21v-7"/><path d="M4 10V3"/><path d="M12 21v-9"/><path d="M12 8V3"/><path d="M20 21v-5"/><path d="M20 12V3"/><path d="M2 14h4"/><path d="M10 8h4"/><path d="M18 16h4"/>',
  menu: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 13h6"/><path d="M9 17h6"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  checkc: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 5-5.5"/>',
  circle: '<circle cx="12" cy="12" r="9"/>',
  motor: '<circle cx="12" cy="12" r="6.5"/><circle cx="12" cy="12" r="2"/><path d="M12 5.5V3"/><path d="M12 21v-2.5"/><path d="M5.5 12H3"/><path d="M21 12h-2.5"/>',
  thermo: '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
  zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
  wifi: '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><path d="M12 20h.01"/>',
  router: '<rect x="2" y="14" width="20" height="6" rx="2"/><path d="M6 17h.01"/><path d="M10 17h.01"/><path d="M17 17h.01"/><path d="M12 14V9"/><path d="M8.5 6.5a5 5 0 0 1 7 0"/><path d="M5.5 3.5a9.5 9.5 0 0 1 13 0"/>',
  server: '<rect x="2" y="3" width="20" height="7" rx="2"/><rect x="2" y="14" width="20" height="7" rx="2"/><path d="M6 6.5h.01"/><path d="M6 17.5h.01"/>',
  db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v3"/><path d="M15 2v3"/><path d="M9 19v3"/><path d="M15 19v3"/><path d="M2 9h3"/><path d="M2 15h3"/><path d="M19 9h3"/><path d="M19 15h3"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  chevR: '<path d="m9 18 6-6-6-6"/>',
  activity: '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  gauge: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  battery: '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><path d="M6 11v2"/><path d="M10 11v2"/>',
  signal: '<path d="M2 20h.01"/><path d="M7 20v-4"/><path d="M12 20v-8"/><path d="M17 20V8"/><path d="M22 20V4"/>',
  up: '<path d="M7 17 17 7"/><path d="M8 7h9v9"/>',
  down: '<path d="m7 7 10 10"/><path d="M17 8v9H8"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
};
const icon = (n, sz = 18) => `<svg width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${I[n] || ''}</svg>`;
function injectIcons(root = document) {
  root.querySelectorAll('[data-ic]').forEach(el => { el.innerHTML = icon(el.dataset.ic, el.dataset.sz ? +el.dataset.sz : 18); el.removeAttribute('data-ic'); });
}

/* ---------------- 种子数据 ---------------- */
const MOTORS = [
  { id: 'M-01', name: '1#循环水泵电机', loc: '一车间 · 循环水泵房', kw: 132, ratedA: 240, group: '泵组A', pilot: true, node: 'N-01', vfd: 'ABB ACS580', sensor: 'PT100 · 外壳 / 轴承端盖', temp: 61.2, load: .72, baseTemp: 58.4, baseLoad: .71, ampDev: 1.4, tempLimit: 85, ampLimit: 252, status: 'ok', install: '2019-03', maint: '2026-10-28 润滑保养' },
  { id: 'M-02', name: '2#循环水泵电机', loc: '一车间 · 循环水泵房', kw: 132, ratedA: 240, group: '泵组A', pilot: true, node: 'N-01', vfd: 'ABB ACS580', sensor: 'PT100 · 外壳 / 轴承端盖', temp: 63.1, load: .70, baseTemp: 61.5, baseLoad: .69, ampDev: 1.6, tempLimit: 85, ampLimit: 252, status: 'ok', install: '2019-03', maint: '2026-11-11 清理风道滤网' },
  { id: 'M-03', name: '主排风机', loc: '二车间 · 排风机房', kw: 160, ratedA: 290, group: '风机组', pilot: true, node: 'N-02', vfd: '西门子 G120', sensor: 'PT100 · 外壳 / 轴承端盖', temp: 87.4, load: .64, baseTemp: 72.6, baseLoad: .65, ampDev: -1.5, tempLimit: 85, ampLimit: 305, status: 'crit', install: '2020-06', maint: '2026-09-15 轴承补脂' },
  { id: 'M-04', name: '空压机主电机', loc: '空压站', kw: 110, ratedA: 200, group: '空压站', pilot: false, node: 'N-02', vfd: '汇川 MD500', sensor: 'PT100 · 外壳', temp: 71.5, load: .81, baseTemp: 69.8, baseLoad: .80, ampDev: 1.3, tempLimit: 85, ampLimit: 210, status: 'ok', install: '2021-01', maint: '2026-11-09 负载阀门检修' },
  { id: 'M-05', name: '冷却塔风机', loc: '动力站 · 冷却塔', kw: 75, ratedA: 140, group: '风机组', pilot: false, node: 'N-03', vfd: '汇川 MD500', sensor: 'PT100 · 外壳', temp: 55.3, load: .58, baseTemp: 53.6, baseLoad: .57, ampDev: 12.4, tempLimit: 80, ampLimit: 147, status: 'warn', install: '2021-11', maint: '2026-10-30 皮带张紧' },
  { id: 'M-06', name: '锅炉给水泵', loc: '锅炉房', kw: 132, ratedA: 240, group: '泵组A', pilot: false, node: 'N-03', vfd: 'ABB ACS580', sensor: 'PT100 · 外壳 / 轴承端盖', temp: 58.9, load: .66, baseTemp: 57.2, baseLoad: .65, ampDev: 1.5, tempLimit: 85, ampLimit: 252, status: 'ok', install: '2018-08', maint: '2026-10-12 联轴器检查' }
];
const DEFAULT_LIMITS = MOTORS.map(m => ({ id: m.id, t: m.tempLimit, a: m.ampLimit }));
const motorById = id => MOTORS.find(m => m.id === id);
const tempDev = m => (m.temp - m.baseTemp) / m.baseTemp * 100;
const ampOf = m => m.load * m.ratedA;
const STATUS_TXT = { ok: '正常', warn: '警告', crit: '严重' };
const LEVEL_TXT = { crit: '严重', warn: '警告', info: '提示' };
const ST_TXT = { open: '未处理', doing: '处理中', closed: '已闭环' };
const MOTOR_COLORS = { 'M-01': '#2DD4EE', 'M-02': '#4F8CFF', 'M-03': '#FF4D6D', 'M-04': '#9D7CFF', 'M-05': '#FFB224', 'M-06': '#2ED3A3' };

const NOW = Date.now();
let ALARMS = [
  { id: 'AL-2041', level: 'crit', title: '外壳温度越限', motor: 'M-03', desc: '温度 87.4°C 超上限 85.0°C,已持续 42 分钟;电流正常,疑似散热 / 轴承 / 润滑问题。', value: '87.4 °C', threshold: '85.0 °C', ts: NOW - 42 * 60e3, feishu: 'read', feishuTo: '王工', status: 'open', owner: '王工', advice: '优先检查风道散热、轴承润滑与端盖温升,安排红外测温复核。' },
  { id: 'AL-2040', level: 'warn', title: '电流波动超基线', motor: 'M-05', desc: '运行电流波动 ±12.4%,超自身正常基线 ±5%;温度正常,疑似负载或电气侧波动。', value: '±12.4 %', threshold: '±5.0 %', ts: NOW - 68 * 60e3, feishu: 'sent', feishuTo: '李工', status: 'doing', owner: '李工', advice: '检查冷却塔液位与皮带张紧,观察变频器输出是否平衡。' },
  { id: 'AL-2039', level: 'info', title: 'LoRa 信号偏弱', motor: 'N-03', desc: '节点 N-03 RSSI -108 dBm,低于 -100 dBm 关注线,丢包率上升。', value: '-108 dBm', threshold: '-100 dBm', ts: NOW - 3.2 * 3600e3, feishu: 'sent', feishuTo: '李工', status: 'closed', owner: '李工', solution: '调整天线朝向后复测 -96 dBm,丢包恢复正常。', advice: '调整天线朝向或位置,必要时加装中继。' },
  { id: 'AL-2038', level: 'warn', title: '温度高于自身基线', motor: 'M-02', desc: '外壳温度较过去 30 天正常基线偏高 8.2%,连续 2 天上升。', value: '+8.2 %', threshold: '+5.0 %', ts: NOW - 20 * 3600e3, feishu: 'read', feishuTo: '王工', status: 'closed', owner: '王工', solution: '清理风道滤网,复测温度回落至基线区间。', advice: '对比同类电机,检查散热与环境温度。' },
  { id: 'AL-2037', level: 'info', title: '网关固件升级完成', motor: 'GW-01', desc: 'GW-01 固件升级至 v1.4.2,链路自检通过,转发正常。', value: 'v1.4.2', threshold: '—', ts: NOW - 27 * 3600e3, feishu: 'sent', feishuTo: '设备运维告警群', status: 'closed', owner: '系统', solution: '升级完成,无需处理。', advice: '' },
  { id: 'AL-2036', level: 'crit', title: '电流瞬时越限', motor: 'M-04', desc: '运行电流 212 A 瞬时超上限 210 A,持续 3 分钟后回落。', value: '212 A', threshold: '210 A', ts: NOW - 3 * 86400e3, feishu: 'read', feishuTo: '王工', status: 'closed', owner: '王工', solution: '负载侧阀门卡涩,已检修处理,复测正常。', advice: '检查负载侧机械阻力与阀门开度。' }
];
const DEVICES = [
  { id: 'GW-01', type: 'LoRa 网关', bind: '全部节点', sig: '—', bat: '市电供电', fw: 'v1.4.2', hb: '刚刚', status: 'ok', note: '厂区网口上联 · 今日转发 17,280 包' },
  { id: 'N-01', type: 'LoRa 采集节点', bind: 'M-01 / M-02', sig: '-87 dBm · SNR 9.5', bat: '88%', fw: 'v2.1.0', hb: '刚刚', status: 'ok', note: 'RS485 两路 · 30s 上报' },
  { id: 'N-02', type: 'LoRa 采集节点', bind: 'M-03 / M-04', sig: '-92 dBm · SNR 8.1', bat: '76%', fw: 'v2.1.0', hb: '刚刚', status: 'ok', note: 'RS485 两路 · 30s 上报' },
  { id: 'N-03', type: 'LoRa 采集节点', bind: 'M-05 / M-06', sig: '-96 dBm · SNR 6.4', bat: '41%', fw: 'v2.1.0', hb: '刚刚', status: 'warn', note: '电量偏低,建议两周内更换电池' },
  { id: 'T-01', type: '温度传感器', bind: 'M-01', sig: 'RS485 正常', bat: '回路供电', fw: '—', hb: '刚刚', status: 'ok', note: 'PT100 · 外壳 + 轴承端盖' },
  { id: 'T-02', type: '温度传感器', bind: 'M-02', sig: 'RS485 正常', bat: '回路供电', fw: '—', hb: '刚刚', status: 'ok', note: 'PT100 · 外壳 + 轴承端盖' },
  { id: 'T-03', type: '温度传感器', bind: 'M-03', sig: 'RS485 正常', bat: '回路供电', fw: '—', hb: '刚刚', status: 'ok', note: 'PT100 · 读数越限,传感器本体正常' },
  { id: 'T-04', type: '温度传感器', bind: 'M-04', sig: 'RS485 正常', bat: '回路供电', fw: '—', hb: '刚刚', status: 'ok', note: 'PT100 · 外壳' },
  { id: 'T-05', type: '温度传感器', bind: 'M-05', sig: 'RS485 正常', bat: '回路供电', fw: '—', hb: '刚刚', status: 'ok', note: 'PT100 · 外壳' },
  { id: 'T-06', type: '温度传感器', bind: 'M-06', sig: 'RS485 正常', bat: '回路供电', fw: '—', hb: '刚刚', status: 'ok', note: 'PT100 · 外壳 + 轴承端盖' }
];
const LINK_EVENTS = [
  { ts: NOW - 42 * 60e3, c: 'var(--red)', txt: 'M-03 温度越限,2 秒内推送飞书 @王工' },
  { ts: NOW - 68 * 60e3, c: 'var(--amber)', txt: 'M-05 电流波动告警,推送 @李工' },
  { ts: NOW - 2.4 * 3600e3, c: 'var(--green)', txt: 'N-03 天线调整完成,信号恢复 -96 dBm' },
  { ts: NOW - 3.2 * 3600e3, c: 'var(--amber)', txt: 'N-03 RSSI 跌至 -108 dBm,触发提示' },
  { ts: NOW - 4.1 * 3600e3, c: 'var(--amber)', txt: 'N-03 电量 41%,低于 45% 提醒线' },
  { ts: NOW - 14 * 3600e3, c: 'var(--info)', txt: 'GW-01 4G 备份链路自检通过' },
  { ts: NOW - 27 * 3600e3, c: 'var(--green)', txt: 'GW-01 固件升级 v1.4.2 完成' }
];
const LOOP_DONE = [
  { txt: 'M-02 风道滤网清理,温度回落基线', who: '王工', ts: NOW - 19 * 3600e3 },
  { txt: 'N-03 天线朝向调整,信号恢复', who: '李工', ts: NOW - 2.4 * 3600e3 },
  { txt: 'M-04 负载阀门检修,电流恢复', who: '王工', ts: NOW - 3 * 86400e3 }
];

/* ---------------- 序列生成 ---------------- */
const RANGE_CFG = { '24h': { n: 96, step: 15 * 60e3, days: 1 }, '7d': { n: 168, step: 3600e3, days: 7 }, '30d': { n: 120, step: 6 * 3600e3, days: 30 } };
function genSeries(m, range) {
  const cfg = RANGE_CFG[range], r = rng(hashStr(m.id + range)), now = Date.now(), out = { t: [], temp: [], amp: [] };
  for (let i = 0; i < cfg.n; i++) {
    const t = now - (cfg.n - 1 - i) * cfg.step, d = new Date(t), hour = d.getHours() + d.getMinutes() / 60;
    const daily = Math.sin((hour - 9) / 24 * Math.PI * 2), prog = i / (cfg.n - 1);
    let temp = m.baseTemp + 3.1 * daily + (r() - .5) * 2.1;
    let load = m.baseLoad + .03 * Math.sin((hour - 8) / 24 * Math.PI * 2) + (r() - .5) * .028;
    if (m.id === 'M-03') { const st = range === '24h' ? .5 : range === '7d' ? .68 : .78; if (prog > st) { const k = (prog - st) / (1 - st); temp += k * k * (m.temp - m.baseTemp - 2); } }
    if (m.id === 'M-05') load += Math.sin(i * 1.65) * .052 * (prog > .55 ? 1 : .35) + (r() - .5) * .03;
    out.t.push(t); out.temp.push(temp); out.amp.push(load * m.ratedA);
  }
  out.temp[cfg.n - 1] = m.temp; out.amp[cfg.n - 1] = ampOf(m);
  out.temp[cfg.n - 2] = m.temp - (m.id === 'M-03' ? .6 : .2); out.amp[cfg.n - 2] = ampOf(m) * (1 - .004);
  return out;
}
function avgSeries(range) {
  const all = MOTORS.map(m => genSeries(m, range)), n = RANGE_CFG[range].n, out = { t: all[0].t, temp: [], amp: [] };
  for (let i = 0; i < n; i++) { out.temp.push(all.reduce((s, a) => s + a.temp[i], 0) / all.length); out.amp.push(all.reduce((s, a) => s + a.amp[i], 0) / all.length); }
  return out;
}
function xLabels(t, range) {
  return t.map(ts => range === '24h' ? hhmm(ts) : mmdd(ts) + (range === '7d' ? ' ' + hhmm(ts) : ''));
}

/* ---------------- 图表基元 ---------------- */
function smoothPath(pts) {
  if (pts.length < 3) return 'M' + pts.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = p1[0] + (p2[0] - p0[0]) / 6, c1y = p1[1] + (p2[1] - p0[1]) / 6, c2x = p2[0] - (p3[0] - p1[0]) / 6, c2y = p2[1] - (p3[1] - p1[1]) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return d;
}
const TIP = $('#chartTip');
function showTip(html, x, y) {
  TIP.innerHTML = html; TIP.classList.add('show');
  const r = TIP.getBoundingClientRect();
  TIP.style.left = clamp(x + 16, 8, innerWidth - r.width - 10) + 'px';
  TIP.style.top = clamp(y - r.height - 14, 8, innerHeight - r.height - 10) + 'px';
}
function hideTip() { TIP.classList.remove('show'); }

function lineChart(el, opt) {
  const W = Math.max(el.clientWidth, 320), H = opt.height || el.clientHeight || 300;
  const has2 = !!opt.y2;
  const P = { l: 48, r: has2 ? 50 : 18, t: 16, b: 28 }, iw = W - P.l - P.r, ih = H - P.t - P.b;
  const n = opt.labels.length, X = i => P.l + iw * (n < 2 ? 0 : i / (n - 1));
  const s1 = opt.series.filter(s => !s.axis2), s2 = opt.series.filter(s => s.axis2);
  let d1 = []; s1.forEach(s => d1.push(...s.data));
  if (opt.band) d1.push(...opt.band.lo, ...opt.band.hi);
  (opt.thresholds || []).filter(t => !t.axis2).forEach(t => d1.push(t.v));
  let d2 = []; s2.forEach(s => d2.push(...s.data));
  (opt.thresholds || []).filter(t => t.axis2).forEach(t => d2.push(t.v));
  const ext = a => { let lo = Math.min(...a), hi = Math.max(...a); const p = (hi - lo) * .14 || 1; return [lo - p, hi + p]; };
  const [a1, b1] = ext(d1.length ? d1 : [0, 1]);
  const Y1 = v => P.t + ih * (1 - (v - a1) / (b1 - a1));
  let Y2 = null, a2 = 0, b2 = 1;
  if (has2 && d2.length) { [a2, b2] = ext(d2); Y2 = v => P.t + ih * (1 - (v - a2) / (b2 - a2)); }
  const u = 'u' + (++UID);
  let defs = '', body = '';
  opt.series.forEach((s, si) => {
    if (s.fill === false) return;
    defs += `<linearGradient id="${u}${si}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s.color}" stop-opacity=".26"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient>`;
  });
  for (let g = 0; g <= 4; g++) {
    const v = a1 + (b1 - a1) * g / 4, y = Y1(v);
    body += `<line x1="${P.l}" y1="${y}" x2="${W - P.r}" y2="${y}" stroke="rgba(148,163,204,${g === 0 ? .22 : .08})" stroke-width="1"/>`;
    body += `<text x="${P.l - 9}" y="${y + 4}" text-anchor="end" font-size="10.5" fill="#5B6A8C" class="num">${fmt(v, v >= 100 ? 0 : 1)}</text>`;
    if (Y2) { const v2 = a2 + (b2 - a2) * g / 4; body += `<text x="${W - P.r + 9}" y="${y + 4}" font-size="10.5" fill="#5B6A8C" class="num">${fmt(v2, 0)}</text>`; }
  }
  const lx = Math.min(6, n);
  for (let k = 0; k < lx; k++) {
    const i = Math.round(k * (n - 1) / (lx - 1));
    body += `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" font-size="10.5" fill="#5B6A8C">${esc(opt.labels[i])}</text>`;
  }
  if (opt.band) {
    const hi = opt.band.hi.map((v, i) => [X(i), Y1(v)]), lo = opt.band.lo.map((v, i) => [X(i), Y1(v)]).reverse();
    body += `<path d="${smoothPath(hi)} L ${lo.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L')} Z" fill="${opt.band.color || 'rgba(255,178,36,.09)'}" stroke="none"/>`;
    body += `<path d="${smoothPath(hi)}" fill="none" stroke="rgba(255,178,36,.4)" stroke-width="1" stroke-dasharray="3 4"/>`;
    body += `<path d="${smoothPath(lo.reverse())}" fill="none" stroke="rgba(255,178,36,.4)" stroke-width="1" stroke-dasharray="3 4"/>`;
  }
  (opt.markers || []).forEach(mk => {
    const x = X(mk.i);
    body += `<line x1="${x}" y1="${P.t}" x2="${x}" y2="${P.t + ih}" stroke="${mk.color}" stroke-width="1" stroke-dasharray="3 4" opacity=".55"/>`;
    body += `<circle cx="${x}" cy="${P.t + 5}" r="3.5" fill="${mk.color}"/>`;
  });
  opt.series.forEach((s, si) => {
    const Y = s.axis2 && Y2 ? Y2 : Y1;
    const pts = s.data.map((v, i) => [X(i), Y(v)]);
    const line = smoothPath(pts);
    if (s.fill !== false) body += `<path d="${line} L ${X(n - 1)} ${P.t + ih} L ${X(0)} ${P.t + ih} Z" fill="url(#${u}${si})" stroke="none"/>`;
    body += `<path d="${line}" fill="none" stroke="${s.color}" stroke-width="${s.width || 2.2}" ${s.dash ? 'stroke-dasharray="6 5"' : ''} stroke-linecap="round"/>`;
    const lp = pts[n - 1];
    body += `<circle cx="${lp[0]}" cy="${lp[1]}" r="3.6" fill="${s.color}" stroke="#0D1424" stroke-width="2"/>`;
  });
  (opt.thresholds || []).forEach(t => {
    const Y = t.axis2 && Y2 ? Y2 : Y1, y = Y(t.v);
    if (y < P.t - 4 || y > P.t + ih + 4) return;
    body += `<line x1="${P.l}" y1="${y}" x2="${W - P.r}" y2="${y}" stroke="${t.color}" stroke-width="1.4" stroke-dasharray="7 5" opacity=".8"/>`;
    body += `<text x="${W - P.r - 4}" y="${y - 6}" text-anchor="end" font-size="10.5" font-weight="600" fill="${t.color}">${esc(t.label)}</text>`;
  });
  body += `<g class="xh" style="display:none"><line class="xh-l" y1="${P.t}" y2="${P.t + ih}" stroke="rgba(233,239,252,.35)" stroke-width="1"/>${opt.series.map((s, si) => `<circle class="xh-c" data-si="${si}" r="4.2" fill="${s.color}" stroke="#0D1424" stroke-width="2"/>`).join('')}</g>`;
  body += `<rect class="ov" x="${P.l}" y="${P.t}" width="${iw}" height="${ih}" fill="transparent"/>`;
  el.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="display:block;max-width:100%"><defs>${defs}</defs>${body}</svg>`;
  const svg = el.firstChild, xh = svg.querySelector('.xh'), xl = svg.querySelector('.xh-l'), cs = [...svg.querySelectorAll('.xh-c')];
  const tipHtml = i => {
    let h = `<h6>${esc(opt.labels[i])}</h6>`;
    opt.series.forEach(s => { const Y = s.axis2 && Y2 ? Y2 : Y1; h += `<div class="row"><i style="background:${s.color}"></i>${esc(s.name)}<b class="num">${fmt(s.data[i], s.dec ?? 1)} ${esc(s.unit || '')}</b></div>`; });
    (opt.markers || []).filter(mk => Math.abs(mk.i - i) <= (opt.markerNear ?? 1)).forEach(mk => h += `<div class="mk">${esc(mk.label)}</div>`);
    return h;
  };
  svg.querySelector('.ov').addEventListener('mousemove', e => {
    el._hovering = true;
    const r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * (W / r.width);
    const i = clamp(Math.round((mx - P.l) / iw * (n - 1)), 0, n - 1), x = X(i);
    xh.style.display = ''; xl.setAttribute('x1', x); xl.setAttribute('x2', x);
    cs.forEach(c => { const s = opt.series[+c.dataset.si], Y = s.axis2 && Y2 ? Y2 : Y1; c.setAttribute('cx', x); c.setAttribute('cy', Y(s.data[i])); });
    showTip(tipHtml(i), e.clientX, e.clientY);
  });
  svg.querySelector('.ov').addEventListener('mouseleave', () => { el._hovering = false; xh.style.display = 'none'; hideTip(); });
}

function sparkSVG(data, color, w = 100, h = 30, uidSuffix = '') {
  const lo = Math.min(...data), hi = Math.max(...data), p = (hi - lo) * .15 || 1;
  const X = i => 2 + (w - 4) * i / (data.length - 1), Y = v => 3 + (h - 8) * (1 - (v - lo + p) / (hi - lo + 2 * p));
  const pts = data.map((v, i) => [X(i), Y(v)]), u = 'sp' + (++UID) + uidSuffix;
  const last = pts[pts.length - 1];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><defs><linearGradient id="${u}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".3"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><path d="${smoothPath(pts)} L ${X(data.length - 1)} ${h} L ${X(0)} ${h} Z" fill="url(#${u})"/><path d="${smoothPath(pts)}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" vector-effect="non-scaling-stroke"/><circle cx="${last[0]}" cy="${last[1]}" r="2.6" fill="${color}"/></svg>`;
}

function gaugeSVG(dev) {
  const capped = clamp(dev, 0, 30), frac = capped / 30;
  const cx = 90, cy = 92, r = 74, a0 = Math.PI, a1 = Math.PI * (1 - frac);
  const pol = a => [cx + r * Math.cos(a), cy - r * Math.sin(a)];
  const [sx, sy] = pol(a0), [ex, ey] = pol(a1);
  const color = dev >= 15 ? '#FF4D6D' : dev >= 8 ? '#FFB224' : '#2ED3A3';
  const arc = (s, e, c, wdt) => { const [x1, y1] = pol(s), [x2, y2] = pol(e); return `<path d="M ${x1} ${y1} A ${r} ${r} 0 ${e - s > Math.PI ? 1 : 0} 1 ${x2} ${y2}" fill="none" stroke="${c}" stroke-width="${wdt}" stroke-linecap="round"/>`; };
  let ticks = '';
  [0, 5, 15, 30].forEach(v => { const a = Math.PI * (1 - v / 30), [tx, ty] = [cx + (r + 13) * Math.cos(a), cy - (r + 13) * Math.sin(a)]; ticks += `<text x="${tx}" y="${ty + 3}" text-anchor="middle" font-size="9.5" fill="#5B6A8C">${v}</text>`; });
  return `<svg width="180" height="104" viewBox="0 0 180 104">${arc(Math.PI, 0, '#1B2742', 11)}${frac > 0.005 ? arc(a0, a1, color, 11) : ''}${ticks}</svg>`;
}

/* ---------------- 四象限 ---------------- */
function quadrantChart(el, { mini = false, selected = null, onSelect = null } = {}) {
  const W = Math.max(el.clientWidth, 320), H = el.clientHeight || (mini ? 252 : 430);
  const P = { l: 52, r: 20, t: 26, b: 40 }, iw = W - P.l - P.r, ih = H - P.t - P.b;
  const xDom = [-8, 18], yDom = [-8, 26];
  const X = v => P.l + iw * (v - xDom[0]) / (xDom[1] - xDom[0]);
  const Y = v => P.t + ih * (1 - (v - yDom[0]) / (yDom[1] - yDom[0]));
  const x0 = X(0), y0 = Y(0);
  let s = '';
  s += `<rect x="${P.l}" y="${P.t}" width="${x0 - P.l}" height="${y0 - P.t}" fill="rgba(255,77,109,.055)" rx="6"/>`;
  s += `<rect x="${x0}" y="${P.t}" width="${W - P.r - x0}" height="${y0 - P.t}" fill="rgba(240,106,216,.05)" rx="6"/>`;
  s += `<rect x="${x0}" y="${y0}" width="${W - P.r - x0}" height="${P.t + ih - y0}" fill="rgba(255,178,36,.05)" rx="6"/>`;
  s += `<rect x="${P.l}" y="${y0}" width="${x0 - P.l}" height="${P.t + ih - y0}" fill="rgba(46,211,163,.05)" rx="6"/>`;
  for (let g = 0; g <= 4; g++) {
    const xv = xDom[0] + (xDom[1] - xDom[0]) * g / 4, yv = yDom[0] + (yDom[1] - yDom[0]) * g / 4;
    s += `<text x="${X(xv)}" y="${H - 18}" text-anchor="middle" font-size="10.5" fill="#5B6A8C" class="num">${xv > 0 ? '+' : ''}${fmt(xv, 0)}%</text>`;
    s += `<text x="${P.l - 9}" y="${Y(yv) + 4}" text-anchor="end" font-size="10.5" fill="#5B6A8C" class="num">${yv > 0 ? '+' : ''}${fmt(yv, 0)}%</text>`;
  }
  s += `<line x1="${x0}" y1="${P.t}" x2="${x0}" y2="${P.t + ih}" stroke="rgba(233,239,252,.3)" stroke-width="1.2"/>`;
  s += `<line x1="${P.l}" y1="${y0}" x2="${W - P.r}" y2="${y0}" stroke="rgba(233,239,252,.3)" stroke-width="1.2"/>`;
  s += `<text x="${W - P.r}" y="${H - 4}" text-anchor="end" font-size="11" fill="#8E9BB8">电流偏离 / 波动 →</text>`;
  s += `<text x="${P.l - 38}" y="${P.t - 10}" font-size="11" fill="#8E9BB8">温度偏离 ↑</text>`;
  const ql = mini ? [
    { t: '散热 · 轴承', x: P.l + 10, y: P.t + 18, c: '#FF8296', a: 'start' },
    { t: '双高 · 过载', x: W - P.r - 10, y: P.t + 18, c: '#F06AD8', a: 'end' },
    { t: '负载 · 电气', x: W - P.r - 10, y: P.t + ih - 10, c: '#FFC65C', a: 'end' },
    { t: '运行健康', x: P.l + 10, y: P.t + ih - 10, c: '#5FE3BB', a: 'start' }
  ] : [
    { t: '温度高 · 电流正常', s: '散热 / 轴承 / 润滑', x: P.l + 12, y: P.t + 20, c: '#FF8296', a: 'start' },
    { t: '双高', s: '过载 / 综合劣化', x: W - P.r - 12, y: P.t + 20, c: '#F06AD8', a: 'end' },
    { t: '温度正常 · 电流异常', s: '负载 / 电气问题', x: W - P.r - 12, y: P.t + ih - 26, c: '#FFC65C', a: 'end' },
    { t: '双正常', s: '运行健康', x: P.l + 12, y: P.t + ih - 26, c: '#5FE3BB', a: 'start' }
  ];
  ql.forEach(q => {
    s += `<text x="${q.x}" y="${q.y}" text-anchor="${q.a}" font-size="${mini ? 10.5 : 11.5}" font-weight="600" fill="${q.c}">${q.t}</text>`;
    if (!mini) s += `<text x="${q.x}" y="${q.y + 15}" text-anchor="${q.a}" font-size="10" fill="#8E9BB8">${q.s}</text>`;
  });
  MOTORS.forEach(m => {
    const x = X(clamp(m.ampDev, xDom[0] + 1, xDom[1] - 1)), y = Y(clamp(tempDev(m), yDom[0] + 1, yDom[1] - 1));
    const c = m.status === 'crit' ? '#FF4D6D' : m.status === 'warn' ? '#FFB224' : '#2ED3A3';
    const sel = selected === m.id;
    s += `<g class="qpt" data-id="${m.id}" style="cursor:pointer">`;
    if (m.status !== 'ok') s += `<circle cx="${x}" cy="${y}" r="${mini ? 11 : 15}" fill="${c}" opacity=".18"><animate attributeName="r" values="${mini ? 8 : 11};${mini ? 14 : 20};${mini ? 8 : 11}" dur="2.2s" repeatCount="indefinite"/></circle>`;
    if (sel) s += `<circle cx="${x}" cy="${y}" r="${mini ? 10 : 13}" fill="none" stroke="#E9EFFC" stroke-width="1.6" stroke-dasharray="3 3"/>`;
    s += `<circle cx="${x}" cy="${y}" r="${mini ? 5.5 : 7.5}" fill="${c}" stroke="#0D1424" stroke-width="2.5"/>`;
    if (!mini || m.status !== 'ok' || sel) { const LDY = { 'M-01': -9, 'M-06': -2, 'M-04': 6, 'M-02': 13 }; s += `<text x="${x + (mini ? 9 : 12)}" y="${y + 4 + (LDY[m.id] || 0)}" font-size="${mini ? 10 : 11.5}" font-weight="700" fill="${sel ? '#E9EFFC' : '#8E9BB8'}">${m.id}</text>`; }
    s += `</g>`;
  });
  el.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="display:block;max-width:100%">${s}</svg>`;
  el.querySelectorAll('.qpt').forEach(g => {
    const m = motorById(g.dataset.id);
    g.addEventListener('mousemove', e => {
      const jd = m.ampDev > 8 && tempDev(m) < 8 ? '负载 / 电气方向' : tempDev(m) > 8 && m.ampDev < 8 ? '散热 / 轴承 / 润滑方向' : tempDev(m) > 8 && m.ampDev > 8 ? '过载 / 综合劣化' : '运行健康';
      showTip(`<h6>${m.id} · ${esc(m.name)}</h6><div class="row"><i style="background:#FFB224"></i>温度偏离<b class="num">${tempDev(m) >= 0 ? '+' : ''}${fmt(tempDev(m))}%</b></div><div class="row"><i style="background:#2DD4EE"></i>电流偏离/波动<b class="num">${m.ampDev >= 0 ? '+' : ''}${fmt(m.ampDev)}%</b></div><div class="mk">${jd}</div>`, e.clientX, e.clientY);
    });
    g.addEventListener('mouseleave', hideTip);
    g.addEventListener('click', () => { hideTip(); onSelect && onSelect(m); });
  });
}

/* ---------------- 拓扑 ---------------- */
function renderTopology() {
  const el = $('#topoSvg');
  const nodes = [
    { k: 'T', x: 40, y: 56, w: 172, h: 62, ic: 'thermo', c: '#FFB224', t: '温度传感器 ×6', s: 'PT100 · 外壳 / 轴承端盖', dev: 'T-01' },
    { k: 'R', x: 40, y: 156, w: 172, h: 62, ic: 'cpu', c: '#FFB224', t: 'RS485 采集模块', s: 'Modbus RTU 汇聚', dev: 'N-01' },
    { k: 'V', x: 40, y: 256, w: 172, h: 62, ic: 'zap', c: '#2DD4EE', t: '变频器 485 ×6', s: '协议开放 · 读取电流', dev: 'N-02' },
    { k: 'N', x: 368, y: 116, w: 180, h: 84, ic: 'radio', c: '#9D7CFF', t: 'LoRa 采集节点 ×3', s: 'N-01 / N-02 / N-03', dev: 'N-01' },
    { k: 'G', x: 368, y: 282, w: 180, h: 70, ic: 'router', c: '#9D7CFF', t: 'LoRa 网关 GW-01', s: '470MHz · SF7 · 网口上联', dev: 'GW-01' },
    { k: 'S', x: 692, y: 76, w: 176, h: 64, ic: 'server', c: '#4F8CFF', t: '后台服务', s: '现有工控机 · 本地部署', dev: 'GW-01' },
    { k: 'D', x: 692, y: 196, w: 176, h: 64, ic: 'db', c: '#4F8CFF', t: '本地数据库', s: '数据不出厂 · 保留 180 天', dev: 'GW-01' },
    { k: 'A', x: 692, y: 316, w: 176, h: 64, ic: 'activity', c: '#4F8CFF', t: '对比分析引擎', s: '自身 / 同类 / 关联 / 趋势', dev: 'GW-01' },
    { k: 'B', x: 968, y: 56, w: 168, h: 62, ic: 'grid', c: '#2ED3A3', t: '监测看板', s: '集中监测 · 本页面', dev: null },
    { k: 'F', x: 968, y: 176, w: 168, h: 62, ic: 'send', c: '#FFB224', t: '飞书通知', s: '异常 2 秒直达责任人', dev: null },
    { k: 'H', x: 968, y: 296, w: 168, h: 62, ic: 'wrench', c: '#2ED3A3', t: '人工检查 / 维修', s: '处理结果回写数据库', dev: null }
  ];
  const N = k => nodes.find(n => n.k === k);
  const edge = (a, b, c, dash = false, label = '') => {
    const x1 = a.x + a.w, y1 = a.y + a.h / 2, x2 = b.x, y2 = b.y + b.h / 2, mx = (x1 + x2) / 2;
    const d = `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
    let out = `<path d="${d}" fill="none" stroke="${c}" stroke-width="1.8" opacity=".65" ${dash ? 'stroke-dasharray="4 6"' : 'class="flow-line"'} marker-end="url(#arrw)"/>`;
    if (label) out += `<text x="${mx}" y="${(y1 + y2) / 2 - 8}" text-anchor="middle" font-size="10.5" fill="${c}">${label}</text>`;
    return { d, out };
  };
  const vedge = (a, b, c, label = '') => {
    const x1 = a.x + a.w / 2, y1 = a.y + a.h, x2 = b.x + b.w / 2, y2 = b.y;
    const d = `M ${x1} ${y1} L ${x2} ${y2}`;
    let out = `<path d="${d}" fill="none" stroke="${c}" stroke-width="1.8" opacity=".65" class="flow-line" marker-end="url(#arrw)"/>`;
    if (label) out += `<text x="${x1 + 10}" y="${(y1 + y2) / 2 + 4}" font-size="10.5" fill="${c}">${label}</text>`;
    return { d, out };
  };
  const bands = [
    { x: 16, w: 224, t: '现场采集层', c: '#FFB224' },
    { x: 344, w: 228, t: '无线传输层', c: '#9D7CFF' },
    { x: 668, w: 224, t: '后台平台层', c: '#4F8CFF' },
    { x: 944, w: 216, t: '应用处理层', c: '#2ED3A3' }
  ];
  let s = `<defs><marker id="arrw" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 z" fill="#8E9BB8"/></marker></defs>`;
  bands.forEach(b => {
    s += `<rect x="${b.x}" y="14" width="${b.w}" height="392" rx="14" fill="${b.c}" opacity=".045"/><rect x="${b.x}" y="14" width="${b.w}" height="392" rx="14" fill="none" stroke="${b.c}" stroke-opacity=".16"/>`;
    s += `<text x="${b.x + b.w / 2}" y="36" text-anchor="middle" font-size="11.5" font-weight="700" letter-spacing="2" fill="${b.c}">${b.t}</text>`;
  });
  const e1 = vedge(N('T'), N('R'), '#FFB224');
  const e2 = edge(N('R'), N('N'), '#2DD4EE');
  const e3 = edge(N('V'), N('N'), '#2DD4EE');
  const e4 = vedge(N('N'), N('G'), '#9D7CFF', 'LoRa 无线');
  const e5 = edge(N('G'), N('S'), '#9D7CFF', '网口 / 厂区网络');
  const e6 = vedge(N('S'), N('D'), '#4F8CFF');
  const e7 = vedge(N('D'), N('A'), '#4F8CFF');
  const e8 = edge(N('A'), N('B'), '#2ED3A3', '正常');
  const e9 = edge(N('A'), N('F'), '#FFB224', '异常');
  const e10 = vedge(N('F'), N('H'), '#FFB224');
  const x1 = N('H').x, y1 = N('H').y + N('H').h / 2, x2 = N('D').x + N('D').w, y2 = N('D').y + N('D').h / 2;
  const e11 = { d: `M ${x1} ${y1 + 20} C ${x1 - 60} ${y1 + 60}, ${x2 + 60} ${y2 + 60}, ${x2 + 4} ${y2 + 10}`, out: '' };
  e11.out = `<path d="${e11.d}" fill="none" stroke="#2ED3A3" stroke-width="1.6" stroke-dasharray="4 6" opacity=".6" marker-end="url(#arrw)"/><text x="${(x1 + x2) / 2}" y="${y1 + 48}" text-anchor="middle" font-size="10.5" fill="#2ED3A3">处理结果回写</text>`;
  [e1, e2, e3, e4, e5, e6, e7, e8, e9, e10, e11].forEach(e => s += e.out);
  [e2, e4, e5, e9].forEach((e, i) => {
    s += `<circle r="3.2" fill="${i === 3 ? '#FFB224' : '#2DD4EE'}"><animateMotion dur="${2.4 + i * .5}s" repeatCount="indefinite" path="${e.d}"/></circle>`;
  });
  for (let i = 0; i < 3; i++) {
    s += `<circle cx="458" cy="241" r="8" fill="none" stroke="#9D7CFF" stroke-width="1.4" opacity="0"><animate attributeName="r" values="8;34" dur="2.4s" begin="${i * .8}s" repeatCount="indefinite"/><animate attributeName="opacity" values=".7;0" dur="2.4s" begin="${i * .8}s" repeatCount="indefinite"/></circle>`;
  }
  nodes.forEach(nd => {
    s += `<g class="topo-node" data-dev="${nd.dev || ''}" data-k="${nd.k}">
      <rect x="${nd.x}" y="${nd.y}" width="${nd.w}" height="${nd.h}" rx="13" fill="#111B30" stroke="rgba(148,163,204,.25)" stroke-width="1" style="transition:stroke .2s"/>
      <rect x="${nd.x}" y="${nd.y}" width="3.5" height="${nd.h}" rx="2" fill="${nd.c}"/>
      <g transform="translate(${nd.x + 14},${nd.y + nd.h / 2 - 10})" color="${nd.c}"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${I[nd.ic]}</svg></g>
      <text x="${nd.x + 42}" y="${nd.y + (nd.h > 70 ? 32 : 26)}" font-size="12.5" font-weight="700" fill="#E9EFFC">${nd.t}</text>
      <text x="${nd.x + 42}" y="${nd.y + (nd.h > 70 ? 50 : 43)}" font-size="10" fill="#8E9BB8">${nd.s}</text>
      <circle cx="${nd.x + nd.w - 13}" cy="${nd.y + 13}" r="4" fill="#2ED3A3"><animate attributeName="opacity" values="1;.4;1" dur="2s" repeatCount="indefinite"/></circle>
    </g>`;
  });
  s += `<text x="458" y="392" text-anchor="middle" font-size="10.5" fill="#8E9BB8" class="num" id="topoPackets">今日转发 17,280 包 · 丢包 0.4% · 平均延迟 38ms</text>`;
  el.innerHTML = `<svg width="1160" height="420" viewBox="0 0 1160 420" style="min-width:1060px;width:100%;display:block">${s}</svg>`;
  el.querySelectorAll('.topo-node').forEach(g => {
    g.addEventListener('click', () => {
      const k = g.dataset.k;
      if (k === 'B') { go('overview'); return; }
      if (k === 'F') { openFeishuPreview(); return; }
      if (k === 'H') { go('alarms'); return; }
      if (k === 'A') { go('analysis'); return; }
      const dev = DEVICES.find(d => d.id === g.dataset.dev) || DEVICES[0];
      openDeviceDrawer(dev);
    });
  });
}

/* ---------------- Toast / 抽屉 / 弹窗 ---------------- */
function toast(kind, title, sub = '', undo = null) {
  const box = $('#toasts'), t = document.createElement('div');
  t.className = 'toast ' + kind;
  const ic = kind === 'ok' ? 'checkc' : kind === 'warn' ? 'alert' : kind === 'err' ? 'alert' : 'info';
  t.innerHTML = `${icon(ic)}<div style="flex:1;min-width:0"><b>${esc(title)}</b>${sub ? `<p>${esc(sub)}</p>` : ''}</div>${undo ? '<button class="undo">撤销</button>' : ''}`;
  box.appendChild(t);
  const kill = () => { t.classList.add('out'); setTimeout(() => t.remove(), 300); };
  const timer = setTimeout(kill, undo ? 6000 : 3600);
  if (undo) t.querySelector('.undo').addEventListener('click', () => { clearTimeout(timer); undo(); kill(); });
  while (box.children.length > 4) box.firstChild.remove();
}
let drawerReturnFocus = null;
function openDrawer(headHtml, bodyHtml) {
  drawerReturnFocus = document.activeElement;
  $('#drawerHead').innerHTML = headHtml;
  $('#drawerBody').innerHTML = bodyHtml;
  $('#drawerBody').scrollTop = 0;
  $('#scrim').classList.add('show');
  $('#drawer').classList.add('show');
  injectIcons($('#drawer'));
  const c = $('#drawerHead .drawer-close'); if (c) c.focus();
}
function closeDrawer() {
  $('#drawer').classList.remove('show');
  if (!$('#modal').classList.contains('show')) $('#scrim').classList.remove('show');
  if (drawerReturnFocus && drawerReturnFocus.focus) drawerReturnFocus.focus();
}
function hideScrimIfIdle() {
  if (!$('#drawer').classList.contains('show') && !$('#modal').classList.contains('show') && !$('#sidebar').classList.contains('open')) $('#scrim').classList.remove('show');
}
function drawerHead(title, sub, badge = '') {
  return `<div style="min-width:0"><h3>${title}</h3><div class="sub">${sub}</div></div>${badge}<button class="icon-btn drawer-close" aria-label="关闭">${icon('x')}</button>`;
}
function openModal(headHtml, bodyHtml) {
  $('#modalHead').innerHTML = headHtml;
  $('#modalBody').innerHTML = bodyHtml;
  $('#scrim').classList.add('show');
  $('#modal').classList.add('show');
  injectIcons($('#modal'));
}
function closeModal() {
  $('#modal').classList.remove('show');
  if (!$('#drawer').classList.contains('show')) $('#scrim').classList.remove('show');
}
$('#scrim').addEventListener('click', () => { if ($('#modal').classList.contains('show')) closeModal(); else closeDrawer(); $('#sidebar').classList.remove('open'); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { if ($('#modal').classList.contains('show')) closeModal(); else if ($('#drawer').classList.contains('show')) closeDrawer(); $('#sidebar').classList.remove('open'); hideScrimIfIdle(); }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); const s = $('#globalSearch'); if (s.offsetParent) s.focus(); else { go('overview'); setTimeout(() => $('#globalSearch').focus(), 80); } }
});
document.addEventListener('click', e => {
  if (e.target.closest('.drawer-close')) closeDrawer();
  if (e.target.closest('.modal-close')) closeModal();
});

/* ---------------- 视图状态 ---------------- */
const state = {
  view: 'overview', trendMotor: 'all', trendRange: '24h',
  anaMode: 'self', anaMotor: 'M-03', anaRange: '7d', trendMetric: 'both', peerGroup: '泵组A',
  motorFilter: 'all', motorQuery: '',
  sev: 'all', st: 'all', alarmQuery: '', sort: { key: 'time', dir: -1 }, selected: new Set(),
  quadSel: 'M-03', packets: 17280, rendered: {}
};
const VIEWS = {
  overview: { title: '监测总览', crumb: '监测中心 / 监测总览' },
  analysis: { title: '对比分析', crumb: '监测中心 / 对比分析 · 自己和自己比 · 同类比 · 关联比 · 趋势比' },
  alarms: { title: '告警中心', crumb: '监测中心 / 告警中心 · 飞书通知与处理闭环' },
  topology: { title: '设备与链路', crumb: '系统管理 / 设备与链路 · LoRa 全链路' },
  settings: { title: '阈值与通知', crumb: '系统管理 / 阈值与通知 · 飞书机器人' }
};
function go(view) {
  if (!VIEWS[view]) view = 'overview';
  state.view = view;
  $$('.view').forEach(v => v.hidden = v.id !== 'view-' + view);
  $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === view));
  $('#pageTitle').textContent = VIEWS[view].title;
  $('#pageCrumb').textContent = VIEWS[view].crumb;
  if (location.hash !== '#/' + view) history.replaceState(null, '', '#/' + view);
  $('#sidebar').classList.remove('open');
  hideScrimIfIdle();
  renderView(view);
  observeReveals();
  window.scrollTo(0, 0);
}
function renderView(view) {
  if (view === 'overview') renderOverview();
  else if (view === 'analysis') renderAnalysis();
  else if (view === 'alarms') renderAlarms();
  else if (view === 'topology') { renderTopology(); renderDevices(); renderLinkEvents(); }
  else if (view === 'settings') renderSettings();
  state.rendered[view] = true;
  observeReveals();
}

/* ---------------- 总览渲染 ---------------- */
const sparks = {};
function motorSparkData(m) {
  if (!sparks[m.id]) {
    const s = genSeries(m, '24h');
    sparks[m.id] = { temp: s.temp.slice(-26), amp: s.amp.slice(-26) };
  }
  return sparks[m.id];
}
function renderKPIs() {
  const avgT = MOTORS.reduce((s, m) => s + m.temp, 0) / MOTORS.length;
  const avgL = MOTORS.reduce((s, m) => s + m.load, 0) / MOTORS.length * 100;
  const active = ALARMS.filter(a => a.status !== 'closed');
  const crit = active.filter(a => a.level === 'crit').length;
  const tSpark = avgSeries('24h').temp.slice(-26), aSpark = avgSeries('24h').amp.slice(-26);
  const kpis = [
    { ic: 'motor', c: '#2DD4EE', label: '在线电机', val: '6', unit: '/ 6 台', delta: '<span class="kpi-delta flat">试点 3 台 · 全部在线</span>', spark: sparkSVG(tSpark.map((v, i) => 5.8 + Math.sin(i / 4) * .2), '#2DD4EE') },
    { ic: 'bell', c: '#FF4D6D', label: '活跃告警', val: String(active.length), unit: '条', delta: `<span class="kpi-delta up">${icon('up', 12)} 严重 ${crit} · 警告 ${active.length - crit}</span>`, spark: sparkSVG([1, 1, 2, 1, 2, 3, 2, 2, 3, 2, 2, 2], '#FF4D6D') },
    { ic: 'thermo', c: '#FFB224', label: '平均外壳温度', val: fmt(avgT), unit: '°C', delta: `<span class="kpi-delta up">${icon('up', 12)} 较昨日 +1.6°C</span>`, spark: sparkSVG(tSpark, '#FFB224'), id: 'kpiTemp' },
    { ic: 'zap', c: '#4F8CFF', label: '平均负载率', val: fmt(avgL), unit: '%', delta: `<span class="kpi-delta flat">电流均值 ${fmt(MOTORS.reduce((s, m) => s + ampOf(m), 0) / MOTORS.length, 0)} A</span>`, spark: sparkSVG(aSpark, '#4F8CFF'), id: 'kpiLoad' },
    { ic: 'radio', c: '#9D7CFF', label: '链路完好率', val: '99.6', unit: '%', delta: '<span class="kpi-delta down">丢包 0.4% · 延迟 38ms</span>', spark: sparkSVG([99.2, 99.5, 99.1, 99.6, 99.8, 99.4, 99.6, 99.7, 99.5, 99.6, 99.6, 99.6], '#9D7CFF') }
  ];
  $('#kpiRow').innerHTML = kpis.map((k, i) => `
    <div class="card kpi ${rv()}" style="--accent:${k.c};--d:${i * .06}s">
      <div class="kpi-top"><div class="kpi-ic">${icon(k.ic)}</div><span class="kpi-label">${k.label}</span></div>
      <div class="kpi-val num" ${k.id ? `id="${k.id}"` : ''} data-count="${parseFloat(k.val)}" data-dec="${k.val.includes('.') ? 1 : 0}">0<small>${k.unit}</small></div>
      <div class="kpi-foot">${k.delta}<div class="kpi-spark">${k.spark}</div></div>
    </div>`).join('');
  $$('#kpiRow .kpi-val').forEach(el => {
    const target = +el.dataset.count, dec = +el.dataset.dec, unit = el.querySelector('small').outerHTML, t0 = performance.now();
    const step = t => { const k = clamp((t - t0) / 750, 0, 1), e = 1 - Math.pow(1 - k, 3); el.innerHTML = fmt(target * e, dec) + unit; if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}
function renderTrend() {
  const m = state.trendMotor === 'all' ? null : motorById(state.trendMotor);
  const s = m ? genSeries(m, state.trendRange) : avgSeries(state.trendRange);
  const labels = xLabels(s.t, state.trendRange);
  const tempLimit = m ? m.tempLimit : 85;
  const markers = [];
  if (m && state.trendRange !== '30d') ALARMS.filter(a => a.motor === m.id).forEach(a => {
    const i = s.t.findIndex(t => t >= a.ts);
    if (i >= 0) markers.push({ i, color: a.level === 'crit' ? '#FF4D6D' : '#FFB224', label: `${a.id} ${a.title}` });
  });
  lineChart($('#trendChart'), {
    height: 308, labels, y2: true,
    series: [
      { name: '外壳温度', color: '#FFB224', data: s.temp, unit: '°C' },
      { name: '运行电流', color: '#2DD4EE', data: s.amp, unit: 'A', axis2: true, dec: 0 }
    ],
    thresholds: [{ v: tempLimit, color: '#FF4D6D', label: `温度上限 ${tempLimit}°C` }],
    markers
  });
  $('#trendLegend').innerHTML = `
    <span><i style="background:#FFB224"></i>外壳温度 °C(左轴)</span>
    <span><i style="background:#2DD4EE"></i>运行电流 A(右轴)</span>
    <span><i style="background:transparent;border:1.5px dashed #FF4D6D;height:0;border-radius:0;width:14px;vertical-align:3px"></i>温度上限</span>
    <span style="margin-left:auto;color:var(--faint)">${m ? m.id + ' · ' + esc(m.name) : '全部电机均值'} · ${state.trendRange === '24h' ? '15 分钟' : state.trendRange === '7d' ? '1 小时' : '6 小时'}粒度</span>`;
}
function renderTrendChips() {
  $('#trendChips').innerHTML = ['all', ...MOTORS.map(m => m.id)].map(id =>
    `<button class="chip ${state.trendMotor === id ? 'active' : ''}" data-tm="${id}">${id === 'all' ? '全部均值' : id}</button>`).join('');
  $$('#trendChips .chip').forEach(c => c.addEventListener('click', () => { state.trendMotor = c.dataset.tm; renderTrendChips(); renderTrend(); }));
}
function renderLinkStats() {
  $('#linkStats').innerHTML = [
    { v: '1 / 1', l: '网关在线', c: '#5FE3BB' }, { v: '3 / 3', l: '节点在线', c: '#5FE3BB' },
    { v: '-92 dBm', l: '平均信号强度', c: '#C9B3FF' }, { v: '<span id="pktToday">17,280</span>', l: '今日数据包', c: '#7FE7F7' }
  ].map(k => `<div class="link-stat"><div class="v num" style="color:${k.c}">${k.v}</div><div class="l">${k.l}</div></div>`).join('');
}
function renderActiveAlarms() {
  const act = ALARMS.filter(a => a.status !== 'closed').slice(0, 3);
  $('#activeAlarms').innerHTML = act.length ? act.map(a => {
    const m = motorById(a.motor);
    return `<div class="mini-alarm" data-alarm="${a.id}">
      <div class="sev ${a.level}">${icon(a.level === 'info' ? 'info' : 'alert', 16)}</div>
      <div style="min-width:0"><b>${a.id} · ${esc(a.title)}</b><p>${m ? m.id + ' ' + esc(m.name) : a.motor} · <span class="feishu-tag">${icon('send', 12)} 飞书已${a.feishu === 'read' ? '读' : '送达'} ${esc(a.feishuTo)}</span></p></div>
      <time>${timeAgo(a.ts)}</time></div>`;
  }).join('') : '<div style="padding:18px 20px;color:var(--muted);font-size:12.5px">当前无活跃告警,全部电机运行正常。</div>';
  $$('#activeAlarms .mini-alarm').forEach(el => el.addEventListener('click', () => openAlarmDrawer(ALARMS.find(a => a.id === el.dataset.alarm))));
}
function renderMotorGrid() {
  const q = state.motorQuery.trim().toLowerCase();
  const list = MOTORS.filter(m => (state.motorFilter === 'all' || m.status === state.motorFilter) &&
    (!q || (m.id + m.name + m.loc + m.group).toLowerCase().includes(q)));
  $('#motorGrid').innerHTML = list.length ? list.map((m, i) => {
    const sp = motorSparkData(m), dev = tempDev(m);
    const devCls = dev >= 8 ? 'up' : dev <= -3 ? 'down' : 'flat';
    return `<div class="card motor ${rv()} ${m.status === 'crit' ? 'crit' : ''}" data-motor="${m.id}" style="--d:${i * .05}s" tabindex="0" role="button" aria-label="查看 ${m.name} 详情">
      <div class="motor-head">
        <span class="dot ${m.status === 'ok' ? 'ok' : m.status === 'warn' ? '' : 'live'}" style="${m.status === 'warn' ? 'background:var(--amber);box-shadow:0 0 8px rgba(255,178,36,.9)' : m.status === 'crit' ? 'background:var(--red);box-shadow:0 0 8px rgba(255,77,109,.9)' : ''}"></span>
        <b>${esc(m.name)}</b><span class="tag">${m.id}</span>
        ${m.pilot ? '<span class="badge pilot" style="font-size:10px;padding:2px 8px">试点</span>' : ''}
        <span class="badge ${m.status}"><span class="dot"></span>${STATUS_TXT[m.status]}</span>
      </div>
      <div class="motor-metrics">
        <div class="mm temp ${m.status === 'crit' ? 'crit' : ''}"><div class="l">${icon('thermo', 13)} 外壳温度</div><div class="v num" data-f="temp">${fmt(m.temp)}<small>°C</small></div>${sparkSVG(sp.temp, m.status === 'crit' ? '#FF4D6D' : '#FFB224', 100, 26)}</div>
        <div class="mm amp"><div class="l">${icon('zap', 13)} 运行电流</div><div class="v num" data-f="amp">${fmt(ampOf(m), 0)}<small>A</small></div>${sparkSVG(sp.amp, '#2DD4EE', 100, 26)}</div>
      </div>
      <div class="motor-foot">
        <span class="dev-chip ${devCls}">基线 ${dev >= 0 ? '+' : ''}${fmt(dev)}%</span>
        <span>${m.kw} kW</span>
        <span class="sep">${icon('radio', 12)} ${m.node} · 心跳 <span data-f="hb">刚刚</span></span>
      </div>
    </div>`;
  }).join('') : '<div class="card card-pad" style="grid-column:1/-1;color:var(--muted)">没有匹配「' + esc(state.motorQuery) + '」的电机,试试其他关键词。</div>';
  $$('#motorGrid .motor').forEach(el => {
    const open = () => openMotorDrawer(motorById(el.dataset.motor));
    el.addEventListener('click', open);
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
  });
}
function renderLoopList() {
  $('#loopList').innerHTML = LOOP_DONE.map(l => `<div class="loop-item">${icon('checkc', 15)}<span>${esc(l.txt)} · ${esc(l.who)}</span><time>${timeAgo(l.ts)}</time></div>`).join('');
}
function renderOverview() {
  renderKPIs(); renderTrendChips(); renderTrend(); renderLinkStats(); renderActiveAlarms(); renderMotorGrid(); renderLoopList();
  quadrantChart($('#miniQuadrant'), { mini: true, selected: state.quadSel, onSelect: m => { state.quadSel = m.id; openMotorDrawer(m); } });
}

/* ---------------- 电机抽屉 ---------------- */
function openMotorDrawer(m) {
  const dev = tempDev(m), sp = motorSparkData(m);
  const badge = `<span class="badge ${m.status}" style="margin-left:6px"><span class="dot"></span>${STATUS_TXT[m.status]}</span>`;
  const events = ALARMS.filter(a => a.motor === m.id).slice(0, 3);
  openDrawer(
    drawerHead(`${esc(m.name)} ${badge}`, `${m.id} · ${esc(m.loc)} · ${m.kw} kW · ${m.group}`),
    `<div class="drawer-sec">
      <div class="info-grid" style="grid-template-columns:1fr 1fr">
        <div class="info-cell"><div class="l">外壳温度 / 上限</div><div class="v num" style="color:${m.status === 'crit' ? '#FF8296' : '#FFC65C'}">${fmt(m.temp)} °C <span style="color:var(--faint);font-weight:400">/ ${m.tempLimit} °C</span></div></div>
        <div class="info-cell"><div class="l">运行电流 / 额定</div><div class="v num" style="color:#7FE7F7">${fmt(ampOf(m), 0)} A <span style="color:var(--faint);font-weight:400">/ ${m.ratedA} A</span></div></div>
        <div class="info-cell"><div class="l">负载率</div><div class="v num">${fmt(m.load * 100)} %</div></div>
        <div class="info-cell"><div class="l">偏离自身基线</div><div class="v num" style="color:${dev >= 8 ? '#FF8296' : '#5FE3BB'}">${dev >= 0 ? '+' : ''}${fmt(dev)} %</div></div>
      </div>
    </div>
    <div class="drawer-sec"><h4>24 小时趋势</h4><div id="drawerChart" style="height:210px"></div></div>
    <div class="drawer-sec"><h4>设备档案</h4>
      <div class="info-grid">
        <div class="info-cell"><div class="l">变频器</div><div class="v">${esc(m.vfd)}</div></div>
        <div class="info-cell"><div class="l">温度传感器</div><div class="v" style="font-size:12px">${esc(m.sensor)}</div></div>
        <div class="info-cell"><div class="l">LoRa 节点</div><div class="v">${m.node} · 30s 上报</div></div>
        <div class="info-cell"><div class="l">投运 / 最近维护</div><div class="v" style="font-size:12px">${m.install} · ${esc(m.maint)}</div></div>
      </div>
    </div>
    <div class="drawer-sec"><h4>最近告警</h4>
      ${events.length ? events.map(a => `<div class="loop-item" style="border-top:1px solid var(--line-soft)">${icon(a.status === 'closed' ? 'checkc' : 'alert', 15)}<span style="${a.status === 'closed' ? '' : 'color:#FFC65C'}">${a.id} ${esc(a.title)} · ${ST_TXT[a.status]}</span><time>${timeAgo(a.ts)}</time></div>`).join('') : '<p style="font-size:12.5px;color:var(--muted)">近 30 天无告警记录。</p>'}
    </div>
    <div style="display:flex;gap:9px;flex-wrap:wrap">
      <button class="btn btn-primary" id="dGoAna">${icon('compare', 15)} 查看对比分析</button>
      <button class="btn btn-ghost" id="dExport">${icon('download', 15)} 导出 24h 数据</button>
      <button class="btn btn-ghost" id="dMaint">${icon('wrench', 15)} 标记检修</button>
    </div>`
  );
  const s = genSeries(m, '24h');
  lineChart($('#drawerChart'), {
    height: 210, labels: xLabels(s.t, '24h'), y2: true,
    series: [{ name: '温度', color: '#FFB224', data: s.temp, unit: '°C' }, { name: '电流', color: '#2DD4EE', data: s.amp, unit: 'A', axis2: true, dec: 0 }],
    thresholds: [{ v: m.tempLimit, color: '#FF4D6D', label: `上限 ${m.tempLimit}°C` }]
  });
  $('#dGoAna').addEventListener('click', () => { state.anaMotor = m.id; closeDrawer(); go('analysis'); });
  $('#dExport').addEventListener('click', () => {
    const rows = [['time', 'temperature_C', 'current_A'], ...s.t.map((t, i) => [new Date(t).toISOString(), fmt(s.temp[i]), fmt(s.amp[i], 1)])];
    downloadCSV(rows, `${m.id}_24h_监测数据.csv`);
    toast('ok', '已导出 24 小时数据', `${m.id} · ${s.t.length} 条记录`);
  });
  $('#dMaint').addEventListener('click', () => { m.maint = '2026-11-12 标记检修(待执行)'; toast('ok', '已标记检修', `${m.id} 已加入检修队列,飞书同步通知责任人`); });
}

/* ---------------- 对比分析 ---------------- */
function renderAnalysis() {
  const sel = $('#anaMotor');
  sel.innerHTML = MOTORS.map(m => `<option value="${m.id}" ${state.anaMotor === m.id ? 'selected' : ''}>${m.id} · ${m.name}</option>`).join('');
  sel.onchange = () => { state.anaMotor = sel.value; renderAnalysis(); };
  $$('#anaModes button').forEach(b => b.classList.toggle('active', b.dataset.mode === state.anaMode));
  ['self', 'peer', 'quad', 'trend'].forEach(p => $('#panel-' + p).hidden = p !== state.anaMode);
  if (state.anaMode === 'self') renderSelf();
  else if (state.anaMode === 'peer') renderPeer();
  else if (state.anaMode === 'quad') renderQuad();
  else renderAnaTrend();
}
function judge(m) {
  const td = tempDev(m), ad = m.ampDev;
  if (td > 8 && ad > 8) return { k: 'both', txt: '双高 · 过载或综合劣化', c: '#F06AD8' };
  if (td > 8) return { k: 'temp', txt: '温度高 / 电流正常 · 散热、轴承或润滑方向', c: '#FF4D6D' };
  if (ad > 8) return { k: 'amp', txt: '温度正常 / 电流异常 · 负载或电气方向', c: '#FFB224' };
  return { k: 'ok', txt: '双正常 · 运行健康', c: '#2ED3A3' };
}
function renderSelf() {
  const m = motorById(state.anaMotor), s = genSeries(m, '30d'), labels = xLabels(s.t, '30d');
  const r = rng(hashStr(m.id + 'band'));
  const lo = [], hi = [];
  for (let i = 0; i < s.t.length; i++) {
    const d = new Date(s.t[i]), hour = d.getHours() + d.getMinutes() / 60, daily = Math.sin((hour - 9) / 24 * Math.PI * 2);
    lo.push(m.baseTemp - 2.6 + 2.4 * daily + (r() - .5)); hi.push(m.baseTemp + 3.4 + 2.4 * daily + (r() - .5));
  }
  lineChart($('#selfChart'), {
    height: 330, labels, y2: true,
    band: { lo, hi },
    series: [{ name: '当前温度', color: '#FFB224', data: s.temp, unit: '°C', width: 2.4 }, { name: '当前电流', color: '#2DD4EE', data: s.amp, unit: 'A', axis2: true, dec: 0, fill: false, width: 1.8 }],
    thresholds: [{ v: m.tempLimit, color: '#FF4D6D', label: `上限 ${m.tempLimit}°C` }]
  });
  const dev = tempDev(m);
  const devSeries = s.temp.map(v => (v - m.baseTemp) / m.baseTemp * 100);
  lineChart($('#selfDevChart'), {
    height: 150, labels,
    series: [{ name: '温度偏离度', color: dev > 8 ? '#FF4D6D' : '#FFB224', data: devSeries, unit: '%', dec: 1 }],
    thresholds: [{ v: 5, color: '#FFB224', label: '关注线 +5%' }, { v: 0, color: 'rgba(148,163,204,.5)', label: '基线 0%' }]
  });
  const j = judge(m);
  $('#devGauge').innerHTML = `${gaugeSVG(dev)}<div class="gauge-val num" style="color:${j.c}">${dev >= 0 ? '+' : ''}${fmt(dev)}%</div><div class="gauge-lbl">温度较 30 天正常基线</div>`;
  $('#selfStats').innerHTML = [
    ['当前外壳温度', fmt(m.temp) + ' °C'], ['正常基线温度', fmt(m.baseTemp) + ' °C'],
    ['当前运行电流', fmt(ampOf(m), 0) + ' A'], ['基线电流', fmt(m.baseLoad * m.ratedA, 0) + ' A'],
    ['判定', `<span style="color:${j.c}">${j.txt}</span>`]
  ].map(r2 => `<div class="stat-row"><span class="k">${r2[0]}</span><span class="v num">${r2[1]}</span></div>`).join('');
  const rules = [
    { hit: dev > 5, t: '规则 1 · 高于自身基线 5%', d: dev > 5 ? `当前偏离 +${fmt(dev)}%,已触发` : `当前偏离 ${fmt(dev)}%,未触发` },
    { hit: m.temp > m.tempLimit, t: '规则 2 · 超过温度上限', d: m.temp > m.tempLimit ? `${fmt(m.temp)}°C > ${m.tempLimit}°C,已触发飞书告警` : `${fmt(m.temp)}°C ≤ ${m.tempLimit}°C,未触发` },
    { hit: m.id === 'M-03', t: '规则 3 · 连续 3 天上升', d: m.id === 'M-03' ? '温升速率 +1.8°C/天,持续恶化' : '走势平稳,无持续上升' }
  ];
  $('#selfRules').innerHTML = rules.map(r2 => `<div class="rule ${r2.hit ? 'hit' : ''}">${icon(r2.hit ? 'alert' : 'checkc', 16)}<div><b>${r2.t}</b><p>${r2.d}</p></div></div>`).join('');
  $('#selfAdvice').innerHTML = `<b>${icon('wrench', 15)} 处理建议</b><p>${j.k === 'temp' ? '电流正常但温度持续升高:优先检查风道散热、轴承润滑与端盖温升,建议红外测温复核并安排检修窗口。' : j.k === 'amp' ? '温度正常但电流异常:检查负载侧阻力、阀门开度与变频器输出平衡,排查电气连接。' : j.k === 'both' ? '温度电流双高:立即核查负载与机械状态,必要时降载运行并安排停机检查。' : '各项指标在正常基线内,保持例行监测,无需干预。'}</p>`;
  $('#reportBtn').onclick = () => openReport(m);
}
function renderPeer() {
  const group = MOTORS.filter(m => m.group === state.peerGroup);
  $$('#peerGroup button').forEach(b => b.classList.toggle('active', b.dataset.g === state.peerGroup));
  const metrics = [
    { name: '外壳温度', unit: '°C', get: m => m.temp, dec: 1 },
    { name: '运行电流', unit: 'A', get: m => ampOf(m), dec: 0 },
    { name: '负载率', unit: '%', get: m => m.load * 100, dec: 1 },
    { name: '温度偏离基线', unit: '%', get: m => tempDev(m), dec: 1 }
  ];
  $('#peerChart').innerHTML = metrics.map(mt => {
    const vals = group.map(mt.get), max = Math.max(...vals.map(Math.abs), 1);
    return `<div style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:7px"><b style="color:var(--text);font-size:12.5px">${mt.name}</b><span>${mt.unit}</span></div>
      ${group.map((m, i) => {
        const v = vals[i], bad = (mt.name === '温度偏离基线' && v > 8) || (mt.name === '外壳温度' && m.status === 'crit');
        return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
          <span style="width:52px;flex:none;font-size:11.5px;font-weight:600;color:${MOTOR_COLORS[m.id]}">${m.id}</span>
          <div style="flex:1;height:14px;border-radius:5px;background:#1B2742;overflow:hidden"><i style="display:block;height:100%;width:${Math.abs(v) / max * 100}%;border-radius:5px;background:linear-gradient(90deg,${MOTOR_COLORS[m.id]}55,${MOTOR_COLORS[m.id]});${bad ? 'box-shadow:0 0 12px ' + MOTOR_COLORS[m.id] : ''};transition:width .7s var(--ease)"></i></div>
          <span class="num" style="width:64px;flex:none;text-align:right;font-size:12.5px;font-weight:${bad ? 750 : 550};color:${bad ? '#FF8296' : 'var(--text)'}">${fmt(v, mt.dec)}</span>
        </div>`;
      }).join('')}</div>`;
  }).join('');
  $('#peerLegend').innerHTML = group.map(m => `<span><i style="background:${MOTOR_COLORS[m.id]}"></i>${m.id} ${esc(m.name)}</span>`).join('');
  const ranked = [...group].map(m => ({ m, score: Math.max(0, tempDev(m)) * .6 + Math.max(0, m.ampDev) * .4 })).sort((a, b) => b.score - a.score);
  const maxS = Math.max(...ranked.map(r2 => r2.score), 1);
  $('#peerRank').innerHTML = ranked.map((r2, i) => `<div class="rank-item ${i === 0 && r2.score > 8 ? 'top' : ''}">
    <span class="no">${i + 1}</span>
    <div style="width:110px;flex:none"><b style="font-size:12.5px">${r2.m.id}</b><div style="font-size:10.5px;color:var(--faint)">${esc(r2.m.name)}</div></div>
    <div class="bar"><i style="width:${r2.score / maxS * 100}%;background:${i === 0 && r2.score > 8 ? 'linear-gradient(90deg,#FF4D6D,#FF7A45)' : 'linear-gradient(90deg,#2DD4EE,#4F8CFF)'}"></i></div>
    <span class="val num" style="color:${i === 0 && r2.score > 8 ? '#FF8296' : 'var(--text)'}">${fmt(r2.score)}</span>
  </div>`).join('');
  const worst = ranked[0];
  $('#peerInsight').innerHTML = `${icon('info', 16)}<span>${worst.score > 8 ? `<b>${worst.m.id} ${esc(worst.m.name)}</b> 在同类组中偏离最明显(得分 ${fmt(worst.score)}),显著高于同功率同工况电机,建议优先排查。` : `组内电机指标接近,无明显离群电机,${worst.m.id} 略高但在正常波动范围内。`}</span>`;
}
function renderQuad() {
  quadrantChart($('#quadChart'), { selected: state.quadSel, onSelect: m => { state.quadSel = m.id; renderQuad(); } });
  const m = motorById(state.quadSel), j = judge(m);
  $('#quadDetail').innerHTML = `
    <div class="info-grid">
      <div class="info-cell"><div class="l">电机</div><div class="v">${m.id} · ${esc(m.name)}</div></div>
      <div class="info-cell"><div class="l">判定</div><div class="v" style="color:${j.c};font-size:12px">${j.txt}</div></div>
      <div class="info-cell"><div class="l">温度偏离</div><div class="v num" style="color:#FFC65C">${tempDev(m) >= 0 ? '+' : ''}${fmt(tempDev(m))} %</div></div>
      <div class="info-cell"><div class="l">电流偏离 / 波动</div><div class="v num" style="color:#7FE7F7">${m.ampDev >= 0 ? '+' : ''}${fmt(m.ampDev)} %</div></div>
    </div>
    <button class="btn btn-ghost btn-sm" id="quadOpen" style="margin-top:12px;width:100%;justify-content:center">${icon('eye', 14)} 打开电机详情</button>`;
  $('#quadOpen').addEventListener('click', () => openMotorDrawer(m));
}
function renderAnaTrend() {
  const m = motorById(state.anaMotor), s = genSeries(m, state.anaRange), labels = xLabels(s.t, state.anaRange);
  $$('#anaRange button').forEach(b => b.classList.toggle('active', b.dataset.range === state.anaRange));
  $$('#trendMetric button').forEach(b => b.classList.toggle('active', b.dataset.m === state.trendMetric));
  const series = [];
  if (state.trendMetric !== 'amp') series.push({ name: '外壳温度', color: '#FFB224', data: s.temp, unit: '°C' });
  if (state.trendMetric !== 'temp') series.push({ name: '运行电流', color: '#2DD4EE', data: s.amp, unit: 'A', axis2: state.trendMetric === 'both', dec: 0, fill: state.trendMetric !== 'both' });
  const markers = ALARMS.filter(a => a.motor === m.id).map(a => { const i = s.t.findIndex(t => t >= a.ts); return i >= 0 ? { i, color: a.level === 'crit' ? '#FF4D6D' : a.level === 'warn' ? '#FFB224' : '#4F8CFF', label: `${a.id} ${a.title}` } : null; }).filter(Boolean);
  lineChart($('#anaTrendChart'), { height: 340, labels, y2: state.trendMetric === 'both', series, markers, thresholds: state.trendMetric !== 'amp' ? [{ v: m.tempLimit, color: '#FF4D6D', label: `上限 ${m.tempLimit}°C` }] : [] });
  const t = s.temp, mx = Math.max(...t), mn = Math.min(...t), avg = t.reduce((a, b) => a + b) / t.length;
  const slope = (t[t.length - 1] - t[0]) / RANGE_CFG[state.anaRange].days;
  $('#trendStats').innerHTML = [
    ['最高温度', fmt(mx) + ' °C', '#FF8296'], ['最低温度', fmt(mn) + ' °C', '#7FE7F7'],
    ['平均温度', fmt(avg) + ' °C', '#FFC65C'], ['温升速率', (slope >= 0 ? '+' : '') + fmt(slope) + ' °C/天', slope > 1 ? '#FF8296' : '#5FE3BB']
  ].map(x => `<div class="loop-stat"><div class="v num" style="color:${x[2]};font-size:18px">${x[1]}</div><div class="l">${x[0]}</div></div>`).join('');
  const worsening = slope > 1 && m.id === 'M-03';
  const verdictTxt = worsening
    ? `<b>M-03 判定:持续恶化。</b>近 ${RANGE_CFG[state.anaRange].days} 天温度单边上行(+${fmt(slope)}°C/天),非偶发波动,与电流平稳形成背离 —— 指向机械 / 散热侧劣化,建议本周内安排检查。`
    : `<b>${m.id} 判定:${slope > 0.5 ? '缓慢上升,需关注' : '走势平稳,偶发波动'}。</b>当前温升速率 ${fmt(slope)}°C/天,${slope > 0.5 ? '建议持续观察一周。' : '属于正常工况波动,无需干预。'}`;
  const verdictTag = worsening ? '持续恶化' : slope > 0.5 ? '需关注' : '偶发 · 正常';
  $('#trendVerdict').innerHTML = `${icon(worsening ? 'alert' : 'checkc', 16)}<span style="flex:1">${verdictTxt}</span><span class="verdict ${worsening ? 'bad' : 'good'}">${verdictTag}</span>`;
}

/* ---------------- 报告 ---------------- */
function openReport(m) {
  const dev = tempDev(m), j = judge(m), s = genSeries(m, '7d');
  const slope = (s.temp[s.temp.length - 1] - s.temp[0]) / 7;
  const txt = `# 电机对比分析报告
生成时间:2026-11-12 ${hhmm(Date.now())}    平台:MotorPulse(试点)

## 对象
${m.id} · ${m.name}(${m.kw} kW,${m.group},${m.loc})

## 一、自己和自己比
- 当前外壳温度:${fmt(m.temp)} °C;30 天正常基线:${fmt(m.baseTemp)} °C
- 温度偏离基线:${dev >= 0 ? '+' : ''}${fmt(dev)} %
- 当前电流:${fmt(ampOf(m), 0)} A;基线电流:${fmt(m.baseLoad * m.ratedA, 0)} A
- 近 7 天温升速率:${slope >= 0 ? '+' : ''}${fmt(slope)} °C/天

## 二、同类电机比
同组(${m.group})电机:${MOTORS.filter(x => x.group === m.group).map(x => x.id).join('、')}
${j.k !== 'ok' ? '本电机在组内偏离最明显,列为优先排查对象。' : '组内指标接近,本电机无显著离群。'}

## 三、温度 × 电流关联
判定:${j.txt}
${j.k === 'temp' ? '电流正常但温度持续升高 → 散热、轴承或润滑问题方向。' : j.k === 'amp' ? '温度正常但电流异常 → 负载或电气问题方向。' : j.k === 'both' ? '双高 → 过载或综合劣化,需立即核查。' : '双正常 → 保持例行监测。'}

## 四、结论与建议
${j.k === 'ok' ? '运行健康,无需干预,保持 30s 采集与例行巡检。' : '建议本周内安排现场检查;处理结果请在告警中心闭环回写,平台持续跟踪复测数据。'}

—— 本报告由对比分析引擎自动生成(演示数据),只监测只报警,不控制电机。`;
  openModal(
    `<div style="min-width:0"><h3>分析报告 · ${m.id}</h3><div class="sub" style="font-size:12px;color:var(--faint)">可直接下载 Markdown,粘贴到飞书文档</div></div><button class="icon-btn modal-close" aria-label="关闭">${icon('x')}</button>`,
    `<pre class="report-pre">${esc(txt)}</pre>
     <div style="display:flex;gap:10px;margin-top:16px;justify-content:flex-end">
       <button class="btn btn-ghost" id="copyReport">${icon('file', 15)} 复制全文</button>
       <button class="btn btn-primary" id="dlReport">${icon('download', 15)} 下载 .md</button>
     </div>`
  );
  $('#dlReport').addEventListener('click', () => { downloadText(txt, `分析报告_${m.id}_20261112.md`, 'text/markdown'); toast('ok', '报告已下载', `分析报告_${m.id}_20261112.md`); });
  $('#copyReport').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(txt); toast('ok', '已复制到剪贴板', '可直接粘贴到飞书文档'); }
    catch { toast('warn', '复制失败', '浏览器未授权剪贴板,请使用下载'); }
  });
}

/* ---------------- 告警中心 ---------------- */
function filteredAlarms() {
  const q = state.alarmQuery.trim().toLowerCase();
  const lv = { crit: 3, warn: 2, info: 1 };
  let list = ALARMS.filter(a =>
    (state.sev === 'all' || a.level === state.sev) &&
    (state.st === 'all' || a.status === state.st) &&
    (!q || (a.id + a.title + a.motor + a.desc + (a.owner || '')).toLowerCase().includes(q)));
  list.sort((a, b) => state.sort.key === 'level' ? (lv[b.level] - lv[a.level]) * state.sort.dir : (a.ts - b.ts) * state.sort.dir);
  return list;
}
function feishuTag(a) {
  if (a.feishu === 'none') return `<span class="feishu-tag off">${icon('send', 13)} 未通知</span>`;
  return `<span class="feishu-tag">${icon('send', 13)} ${a.feishu === 'read' ? '已读' : '已送达'} · ${esc(a.feishuTo)}</span>`;
}
function renderAlarms() {
  const open = ALARMS.filter(a => a.status === 'open').length;
  const today = ALARMS.filter(a => Date.now() - a.ts < 86400e3).length;
  const closed = ALARMS.filter(a => a.status === 'closed').length;
  $('#alarmStats').innerHTML = [
    { v: open, l: '未处理', c: '#FF8296', ic: 'alert' }, { v: today, l: '24h 新增', c: '#FFC65C', ic: 'bell' },
    { v: closed, l: '已闭环', c: '#5FE3BB', ic: 'checkc' }, { v: '12 min', l: '平均响应时长', c: '#8FB6FF', ic: 'clock' }
  ].map(k => `<div class="card alarm-stat"><div class="kpi-ic" style="--accent:${k.c};width:38px;height:38px">${icon(k.ic, 19)}</div><div><div class="v num" style="color:${k.c}">${k.v}</div><div class="l">${k.l}</div></div></div>`).join('');
  const list = filteredAlarms();
  $('#alarmTbody').innerHTML = list.length ? list.map(a => {
    const m = motorById(a.motor);
    return `<tr class="clickable" data-id="${a.id}">
      <td><input type="checkbox" class="checkbox row-check" data-id="${a.id}" ${state.selected.has(a.id) ? 'checked' : ''} aria-label="选择 ${a.id}"></td>
      <td><span class="badge ${a.level}"><span class="dot"></span>${LEVEL_TXT[a.level]}</span></td>
      <td><b style="font-size:12.5px">${esc(a.title)}</b><div class="sub">${a.id} · ${esc(a.desc.slice(0, 26))}…</div></td>
      <td>${m ? `<b style="font-size:12.5px">${m.id}</b><div class="sub">${esc(m.name)}</div>` : `<b style="font-size:12.5px">${a.motor}</b><div class="sub">链路设备</div>`}</td>
      <td class="num" style="font-size:12.5px"><b style="color:${a.level === 'crit' ? '#FF8296' : a.level === 'warn' ? '#FFC65C' : 'var(--text)'}">${esc(a.value)}</b><div class="sub">阈值 ${esc(a.threshold)}</div></td>
      <td class="num" style="font-size:12px">${mmdd(a.ts)} ${hhmm(a.ts)}<div class="sub">${timeAgo(a.ts)}</div></td>
      <td>${feishuTag(a)}</td>
      <td><span class="badge ${a.status === 'closed' ? 'ok' : a.status === 'doing' ? 'info' : 'crit'}"><span class="dot"></span>${ST_TXT[a.status]}</span></td>
      <td><div class="row-actions">
        ${a.status !== 'closed' ? `<button class="mini-btn primary" data-act="close" data-id="${a.id}">处理</button>` : `<button class="mini-btn danger" data-act="del" data-id="${a.id}">删除</button>`}
        <button class="mini-btn" data-act="view" data-id="${a.id}">详情</button>
      </div></td></tr>`;
  }).join('') : `<tr><td colspan="9" style="text-align:center;padding:34px;color:var(--muted)">没有匹配的告警记录 —— 调整筛选或搜索关键词试试。</td></tr>`;
  $('#alarmTbody').querySelectorAll('tr.clickable').forEach(tr => tr.addEventListener('click', e => {
    if (e.target.closest('button') || e.target.closest('input')) return;
    openAlarmDrawer(ALARMS.find(a => a.id === tr.dataset.id));
  }));
  $('#alarmTbody').querySelectorAll('[data-act]').forEach(b => b.addEventListener('click', () => {
    const a = ALARMS.find(x => x.id === b.dataset.id);
    if (b.dataset.act === 'view') openAlarmDrawer(a);
    else if (b.dataset.act === 'close') openAlarmDrawer(a, true);
    else if (b.dataset.act === 'del') deleteAlarm(a);
  }));
  $('#alarmTbody').querySelectorAll('.row-check').forEach(c => c.addEventListener('change', () => {
    c.checked ? state.selected.add(c.dataset.id) : state.selected.delete(c.dataset.id);
    updateBulkBar();
  }));
  updateBulkBar();
  updateAlarmBadges();
}
function updateAlarmBadges() {
  const n = ALARMS.filter(a => a.status !== 'closed').length;
  $('#bellBadge').textContent = n; $('#navAlarmBadge').textContent = n;
  $('#bellBadge').style.display = n ? '' : 'none'; $('#navAlarmBadge').style.display = n ? '' : 'none';
}
function updateBulkBar() {
  const n = state.selected.size;
  $('#bulkBar').hidden = n === 0;
  $('#bulkCount').textContent = n;
  $('#checkAll').checked = n > 0 && n === filteredAlarms().length;
}
function closeAlarm(a, solution, silent = false) {
  const snapshot = { ...a };
  a.status = 'closed'; a.solution = solution || '已现场检查处理,复测正常。'; a.closedTs = Date.now();
  if (!silent) {
    renderAlarms(); renderActiveAlarms();
    toast('ok', `${a.id} 已闭环`, '处理结果已回写数据库,飞书同步更新', () => { Object.assign(a, snapshot); delete a.closedTs; renderAlarms(); renderActiveAlarms(); });
  }
}
function deleteAlarm(a) {
  const snapshot = [...ALARMS];
  ALARMS = ALARMS.filter(x => x !== a); state.selected.delete(a.id);
  renderAlarms();
  toast('warn', `${a.id} 已删除`, '仅删除已闭环的历史记录', () => { ALARMS = snapshot; renderAlarms(); });
}
function openAlarmDrawer(a, focusForm = false) {
  const m = motorById(a.motor);
  const tl = [
    { t: '触发告警', d: `${a.value} 超阈值 ${a.threshold}`, ts: a.ts, cls: 'hot' },
    { t: '飞书推送', d: `机器人 2 秒内送达「设备运维告警群」并 @${a.feishuTo}`, ts: a.ts + 2000, cls: '' },
    a.feishu === 'read' ? { t: '责任人已读', d: `${a.feishuTo} 已查看告警卡片`, ts: a.ts + 24000, cls: '' } : null,
    a.status !== 'open' ? { t: '签收处理', d: `${a.owner} 已签收,开始现场排查`, ts: a.ts + 8 * 60e3, cls: '' } : null,
    a.status === 'closed' ? { t: '处理闭环', d: a.solution || '已处理', ts: a.closedTs || a.ts + 40 * 60e3, cls: 'done' } : { t: '等待人工处理', d: '平台只监测只报警,由责任人现场检查后回写结果', ts: null, cls: '' }
  ].filter(Boolean);
  openDrawer(
    drawerHead(`${a.id} · ${esc(a.title)}`, `${m ? m.id + ' ' + esc(m.name) : a.motor} · ${mmdd(a.ts)} ${hhmm(a.ts)} · ${timeAgo(a.ts)}`, `<span class="badge ${a.level}" style="margin-left:6px"><span class="dot"></span>${LEVEL_TXT[a.level]}</span>`),
    `<div class="drawer-sec"><h4>告警详情</h4>
      <p style="font-size:13px;color:var(--muted);margin-bottom:12px">${esc(a.desc)}</p>
      <div class="info-grid">
        <div class="info-cell"><div class="l">触发值</div><div class="v num" style="color:#FF8296">${esc(a.value)}</div></div>
        <div class="info-cell"><div class="l">阈值</div><div class="v num">${esc(a.threshold)}</div></div>
        <div class="info-cell"><div class="l">责任人</div><div class="v">${esc(a.owner)}</div></div>
        <div class="info-cell"><div class="l">当前状态</div><div class="v">${ST_TXT[a.status]}</div></div>
      </div>
    </div>
    <div class="drawer-sec"><h4>飞书通知卡片</h4>
      <div class="feishu-card">
        <div class="fc-head ${a.level === 'crit' ? 'crit' : 'warn'}">${icon('alert', 15)} 【${LEVEL_TXT[a.level]}】${m ? m.id + ' ' + esc(m.name) : a.motor} · ${esc(a.title)}</div>
        <div class="fc-body">
          <div class="fc-row"><span>触发值</span><b class="num">${esc(a.value)}</b></div>
          <div class="fc-row"><span>阈值</span><b class="num">${esc(a.threshold)}</b></div>
          <div class="fc-row"><span>时间</span><b class="num">2026-11-12 ${hhmm(a.ts)}</b></div>
          <div class="fc-row"><span>建议</span><b style="max-width:60%;text-align:right;font-weight:500">${esc(a.advice || '请现场检查确认')}</b></div>
        </div>
        <div class="fc-foot"><span class="fc-btn">查看详情</span><span class="fc-btn">签收</span></div>
      </div>
    </div>
    <div class="drawer-sec"><h4>处理时间线</h4>
      <div class="timeline">${tl.map(x => `<div class="tl-item ${x.cls}"><b>${x.t}</b><p>${esc(x.d)}</p><time>${x.ts ? hhmm(x.ts) : '进行中'}</time></div>`).join('')}</div>
    </div>
    ${a.status !== 'closed' ? `<div class="drawer-sec"><h4>处理记录(闭环回写)</h4>
      <textarea class="input" id="solveTxt" placeholder="记录现场检查与处理结果,例如:清理风道滤网,复测温度回落至 76.8°C…"></textarea>
      <div style="display:flex;gap:9px;margin-top:11px">
        <button class="btn btn-primary" id="solveBtn" style="flex:1;justify-content:center">${icon('check', 15)} 确认闭环</button>
        ${m ? `<button class="btn btn-ghost" id="solveGo">${icon('compare', 15)} 查看分析</button>` : ''}
      </div></div>` : `<div class="advice" style="margin:0"><b>${icon('checkc', 15)} 已闭环</b><p>${esc(a.solution || '已处理')}</p></div>`}`
  );
  if (focusForm) setTimeout(() => { const t = $('#solveTxt'); if (t) t.focus(); }, 350);
  const sb = $('#solveBtn');
  if (sb) sb.addEventListener('click', () => { closeAlarm(a, $('#solveTxt').value.trim()); closeDrawer(); });
  const sg = $('#solveGo');
  if (sg) sg.addEventListener('click', () => { state.anaMotor = m.id; closeDrawer(); go('analysis'); });
}

/* ---------------- 设备 ---------------- */
function renderDevices() {
  $('#devCount').textContent = DEVICES.length + ' 台设备';
  $('#deviceTbody').innerHTML = DEVICES.map(d => `<tr class="clickable" data-id="${d.id}">
    <td><b style="font-size:12.5px">${d.id}</b></td><td style="font-size:12.5px;color:var(--muted)">${d.type}</td>
    <td style="font-size:12.5px">${d.bind}</td>
    <td style="font-size:12px" class="num">${d.sig}<div class="sub">${d.bat}</div></td>
    <td style="font-size:12px" class="num">${d.fw}</td>
    <td style="font-size:12px;color:var(--muted)">${d.hb}</td>
    <td><span class="badge ${d.status}"><span class="dot"></span>${d.status === 'ok' ? '在线' : '需关注'}</span></td></tr>`).join('');
  $$('#deviceTbody tr').forEach(tr => tr.addEventListener('click', () => openDeviceDrawer(DEVICES.find(d => d.id === tr.dataset.id))));
}
function openDeviceDrawer(d) {
  openDrawer(
    drawerHead(`${d.id} · ${d.type}`, d.note, `<span class="badge ${d.status}" style="margin-left:6px"><span class="dot"></span>${d.status === 'ok' ? '在线' : '需关注'}</span>`),
    `<div class="drawer-sec"><div class="info-grid">
      <div class="info-cell"><div class="l">绑定对象</div><div class="v">${d.bind}</div></div>
      <div class="info-cell"><div class="l">固件版本</div><div class="v num">${d.fw}</div></div>
      <div class="info-cell"><div class="l">信号 / 接口</div><div class="v num" style="font-size:12px">${d.sig}</div></div>
      <div class="info-cell"><div class="l">供电 / 电量</div><div class="v">${d.bat}</div></div>
      <div class="info-cell"><div class="l">最近心跳</div><div class="v">${d.hb}</div></div>
      <div class="info-cell"><div class="l">上报间隔</div><div class="v">30 秒</div></div>
    </div></div>
    ${d.status === 'warn' ? `<div class="advice" style="margin:0 0 18px"><b>${icon('alert', 15)} 维护提醒</b><p>${esc(d.note)}。更换电池不影响监测,节点支持热插拔。</p></div>` : ''}
    <div class="drawer-sec"><h4>说明</h4><p style="font-size:12.5px;color:var(--muted)">设备通过 RS485 / LoRa 接入平台,只上行数据,平台不下发控制指令。${d.type === 'LoRa 网关' ? '网关经现有厂区网口上联,无需新增布线;4G 作为备份链路。' : ''}</p></div>
    <button class="btn btn-ghost" id="devPing" style="width:100%;justify-content:center">${icon('refresh', 15)} 立即召测</button>`
  );
  $('#devPing').addEventListener('click', () => toast('ok', `${d.id} 召测成功`, '最近心跳:刚刚 · 数据已刷新'));
}
function renderLinkEvents() {
  $('#linkEvents').innerHTML = LINK_EVENTS.map(e => `<div class="link-event"><time class="num">${hhmm(e.ts)}</time><span class="dot" style="background:${e.c};flex:none"></span><span>${esc(e.txt)}</span></div>`).join('');
}
function openFeishuPreview() {
  openModal(
    `<div><h3>飞书测试消息</h3><div class="sub" style="font-size:12px;color:var(--faint)">以下为机器人将发送到「设备运维告警群」的卡片</div></div><button class="icon-btn modal-close" aria-label="关闭">${icon('x')}</button>`,
    `<div class="feishu-card">
      <div class="fc-head" style="background:rgba(46,211,163,.1);color:#5FE3BB">${icon('checkc', 15)} 【测试】MotorPulse 通知链路正常</div>
      <div class="fc-body">
        <div class="fc-row"><span>平台</span><b>大电机风险监测 · 试点</b></div>
        <div class="fc-row"><span>链路</span><b>LoRa 网关 → 后台 → 飞书机器人</b></div>
        <div class="fc-row"><span>时延</span><b class="num">1.8 秒</b></div>
        <div class="fc-row"><span>时间</span><b class="num">2026-11-12 ${hhmm(Date.now())}</b></div>
      </div>
      <div class="fc-foot"><span class="fc-btn">查看监测看板</span></div>
    </div>
    <p style="font-size:12px;color:var(--faint);margin-top:12px">静态演示:实际部署后点击「发送测试消息」将真实推送到飞书群。</p>`
  );
  toast('info', '测试消息已生成', '演示环境未真实推送');
}

/* ---------------- 设置 ---------------- */
function sliderRow(motor, field, label, min, max, unit, color) {
  const val = motor[field];
  return `<div class="set-row" style="padding-top:9px;padding-bottom:9px">
    <span class="k" style="width:110px;font-size:12px">${label}</span>
    <div class="grow"><input type="range" class="range" min="${min}" max="${max}" step="1" value="${val}" data-m="${motor.id}" data-f="${field}" style="background:linear-gradient(90deg,${color} ${(val - min) / (max - min) * 100}%,#1B2742 ${(val - min) / (max - min) * 100}%)">
    <span class="range-val num ${color === '#FFB224' ? 'amber' : ''}" data-rv="${motor.id}.${field}">${val} ${unit}</span></div>
  </div>`;
}
function renderSettings() {
  $('#thresholdRows').innerHTML = MOTORS.map(m => `
    <div style="border-top:1px solid var(--line-soft)">
      <div class="set-row" style="border-top:none;padding-bottom:4px">
        <span class="k" style="width:auto;flex:1;color:var(--text);font-weight:600">${m.id} · ${esc(m.name)} ${m.pilot ? '<span class="badge pilot" style="font-size:10px;padding:1px 7px;margin-left:6px">试点</span>' : ''}</span>
        <span class="hint">阈值越限即飞书提醒</span>
        <button class="switch on" data-sw aria-label="${m.id} 监测启用开关"></button>
      </div>
      ${sliderRow(m, 'tempLimit', '温度上限', 60, 100, '°C', '#FFB224')}
      ${sliderRow(m, 'ampLimit', '电流上限', Math.round(m.ratedA * .8), Math.round(m.ratedA * 1.2), 'A', '#2DD4EE')}
    </div>`).join('');
  $$('#thresholdRows .range').forEach(r => r.addEventListener('input', () => {
    const m = motorById(r.dataset.m); m[r.dataset.f] = +r.value;
    const min = +r.min, max = +r.max, p = (r.value - min) / (max - min) * 100;
    const color = r.dataset.f === 'tempLimit' ? '#FFB224' : '#2DD4EE';
    r.style.background = `linear-gradient(90deg,${color} ${p}%,#1B2742 ${p}%)`;
    $(`[data-rv="${m.id}.${r.dataset.f}"]`).textContent = `${r.value} ${r.dataset.f === 'tempLimit' ? '°C' : 'A'}`;
    markSettingsDirty();
  }));
  bindSwitches($('#thresholdRows'));
  renderOwners();
}
let owners = ['王工 · 设备科', '李工 · 电气', '惠哥 · 生产'];
function renderOwners() {
  $('#ownerChips').innerHTML = owners.map((o, i) => `<span class="person-chip"><span class="avatar" style="background:linear-gradient(135deg,#4F8CFF,#9D7CFF);color:#fff">${o[0]}</span>${esc(o)}<button data-oi="${i}" aria-label="移除 ${esc(o)}">${icon('x', 12)}</button></span>`).join('') +
    `<button class="chip" id="addOwner">${icon('plus', 13)} 添加</button>`;
  $$('#ownerChips [data-oi]').forEach(b => b.addEventListener('click', () => { owners.splice(+b.dataset.oi, 1); renderOwners(); markSettingsDirty(); }));
  $('#addOwner').addEventListener('click', () => {
    openModal(
      `<div><h3>添加异常响应责任人</h3><div class="sub" style="font-size:12px;color:var(--faint)">格式:姓名 · 部门,告警时飞书 @ 提醒</div></div><button class="icon-btn modal-close" aria-label="关闭">${icon('x')}</button>`,
      `<div class="set-row" style="border:0;padding:2px 0 16px"><span class="k">责任人</span><div class="grow"><input class="input" id="ownerInput" placeholder="如:张工 · 电气"></div></div>
       <div style="display:flex;justify-content:flex-end;gap:10px"><button class="btn btn-ghost modal-close">取消</button><button class="btn btn-primary" id="ownerConfirm">${icon('plus', 14)} 添加</button></div>`
    );
    const inp = $('#ownerInput'); inp.focus();
    const submit = () => { const v = inp.value.trim(); if (!v) { inp.focus(); return; } owners.push(v); renderOwners(); markSettingsDirty(); closeModal(); toast('ok', '责任人已添加', v); };
    $('#ownerConfirm').addEventListener('click', submit);
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
  });
}
function bindSwitches(root) {
  root.querySelectorAll('[data-sw]').forEach(sw => sw.addEventListener('click', () => { sw.classList.toggle('on'); markSettingsDirty(); }));
}
let settingsDirty = false;
function markSettingsDirty() {
  settingsDirty = true;
  $('#saveSettings').innerHTML = `${icon('check', 15)} 保存更改 ●`;
}
function downloadCSV(rows, name) {
  const csv = '﻿' + rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\r\n');
  downloadText(csv, name, 'text/csv');
}
function downloadText(txt, name, mime) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([txt], { type: mime + ';charset=utf-8' }));
  a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 800);
}

/* ---------------- 实时模拟 ---------------- */
function tick() {
  MOTORS.forEach(m => {
    const r = Math.random();
    m.temp = clamp(m.temp + (r - .5) * .5, m.id === 'M-03' ? 86.8 : 40, m.id === 'M-03' ? 88.6 : 95);
    m.load = clamp(m.load + (Math.random() - .5) * .012, .3, .95);
    const sp = motorSparkData(m);
    sp.temp.push(m.temp); sp.temp.shift(); sp.amp.push(ampOf(m)); sp.amp.shift();
    const card = $(`[data-motor="${m.id}"]`);
    if (card) {
      card.querySelector('[data-f="temp"]').innerHTML = `${fmt(m.temp)}<small>°C</small>`;
      card.querySelector('[data-f="amp"]').innerHTML = `${fmt(ampOf(m), 0)}<small>A</small>`;
      const svs = card.querySelectorAll('.mm svg.spark');
      if (svs[0]) svs[0].outerHTML = sparkSVG(sp.temp, m.status === 'crit' ? '#FF4D6D' : '#FFB224', 100, 26);
      if (svs[1]) svs[1].outerHTML = sparkSVG(sp.amp, '#2DD4EE', 100, 26);
    }
  });
  const kt = $('#kpiTemp'), kl = $('#kpiLoad');
  if (kt) kt.innerHTML = fmt(MOTORS.reduce((s, m) => s + m.temp, 0) / MOTORS.length) + '<small>°C</small>';
  if (kl) kl.innerHTML = fmt(MOTORS.reduce((s, m) => s + m.load, 0) / MOTORS.length * 100) + '<small>%</small>';
  state.packets += 2;
  const pk = $('#pktToday'); if (pk) pk.textContent = state.packets.toLocaleString();
  const tp = $('#topoPackets'); if (tp) tp.textContent = `今日转发 ${state.packets.toLocaleString()} 包 · 丢包 0.4% · 平均延迟 38ms`;
  if (state.view === 'overview' && state.trendRange === '24h' && !$('#trendChart')._hovering) renderTrend();
}
function startClock() {
  const f = () => { const d = new Date(); $('#clock').textContent = [d.getHours(), d.getMinutes(), d.getSeconds()].map(x => String(x).padStart(2, '0')).join(':'); };
  f(); setInterval(f, 1000);
}

/* ---------------- 进场 & resize ---------------- */
let bootDone = false;
const rv = () => bootDone ? 'reveal in' : 'reveal';
function observeReveals() {
  const els = $$('.reveal:not(.in)');
  if (bootDone) { els.forEach(el => el.classList.add('in')); return; }
  requestAnimationFrame(() => requestAnimationFrame(() => els.forEach(el => el.classList.add('in'))));
}
let rsTimer;
window.addEventListener('resize', () => {
  clearTimeout(rsTimer);
  rsTimer = setTimeout(() => { hideTip(); renderView(state.view); }, 220);
});

/* ---------------- 事件绑定 ---------------- */
function bindEvents() {
  $$('.nav-item').forEach(n => n.addEventListener('click', () => go(n.dataset.view)));
  $$('[data-goto]').forEach(b => b.addEventListener('click', () => go(b.dataset.goto)));
  $('#bellBtn').addEventListener('click', () => go('alarms'));
  $('#hamburger').addEventListener('click', () => { const sb = $('#sidebar'); sb.classList.toggle('open'); if (sb.classList.contains('open')) $('#scrim').classList.add('show'); else hideScrimIfIdle(); });
  window.addEventListener('hashchange', () => go(location.hash.replace('#/', '') || 'overview'));
  $('#globalSearch').addEventListener('input', e => { state.motorQuery = e.target.value; if (state.view === 'overview') renderMotorGrid(); });
  $('#globalSearch').addEventListener('keydown', e => { if (e.key === 'Enter' && state.view !== 'overview') go('overview'); });
  $$('#trendRange button').forEach(b => b.addEventListener('click', () => {
    state.trendRange = b.dataset.range;
    $$('#trendRange button').forEach(x => x.classList.toggle('active', x === b));
    renderTrend();
  }));
  $$('#motorFilters .chip').forEach(c => c.addEventListener('click', () => {
    state.motorFilter = c.dataset.mf;
    $$('#motorFilters .chip').forEach(x => x.classList.toggle('active', x === c));
    renderMotorGrid(); observeReveals();
  }));
  $$('#anaModes button').forEach(b => b.addEventListener('click', () => { state.anaMode = b.dataset.mode; renderAnalysis(); }));
  $$('#peerGroup button').forEach(b => b.addEventListener('click', () => { state.peerGroup = b.dataset.g; renderPeer(); }));
  $$('#anaRange button').forEach(b => b.addEventListener('click', () => { state.anaRange = b.dataset.range; renderAnaTrend(); }));
  $$('#trendMetric button').forEach(b => b.addEventListener('click', () => { state.trendMetric = b.dataset.m; renderAnaTrend(); }));
  $$('#sevFilters .chip').forEach(c => c.addEventListener('click', () => { state.sev = c.dataset.sev; $$('#sevFilters .chip').forEach(x => x.classList.toggle('active', x === c)); state.selected.clear(); renderAlarms(); }));
  $$('#statusFilters .chip').forEach(c => c.addEventListener('click', () => { state.st = c.dataset.st; $$('#statusFilters .chip').forEach(x => x.classList.toggle('active', x === c)); state.selected.clear(); renderAlarms(); }));
  $('#alarmSearch').addEventListener('input', e => { state.alarmQuery = e.target.value; renderAlarms(); });
  $$('#alarmTable th.sortable').forEach(th => th.addEventListener('click', () => {
    const k = th.dataset.sort;
    state.sort = { key: k, dir: state.sort.key === k ? -state.sort.dir : -1 };
    renderAlarms();
  }));
  $('#checkAll').addEventListener('change', e => {
    state.selected = e.target.checked ? new Set(filteredAlarms().map(a => a.id)) : new Set();
    renderAlarms();
  });
  $('#bulkCancel').addEventListener('click', () => { state.selected.clear(); renderAlarms(); });
  $('#bulkClose').addEventListener('click', () => {
    const targets = ALARMS.filter(a => state.selected.has(a.id) && a.status !== 'closed');
    if (!targets.length) { toast('info', '所选记录均已闭环', '无需重复处理'); return; }
    const snapshots = targets.map(a => ({ ...a }));
    targets.forEach(a => closeAlarm(a, '批量闭环:已现场确认处理。', true));
    state.selected.clear(); renderAlarms(); renderActiveAlarms();
    toast('ok', `已批量闭环 ${targets.length} 条告警`, '处理结果已回写数据库', () => { snapshots.forEach(s => Object.assign(ALARMS.find(a => a.id === s.id), s)); renderAlarms(); renderActiveAlarms(); });
  });
  $('#exportAlarms').addEventListener('click', () => {
    const list = filteredAlarms();
    const rows = [['告警ID', '级别', '内容', '电机/设备', '触发值', '阈值', '时间', '飞书通知', '状态', '责任人', '处理结果'],
      ...list.map(a => [a.id, LEVEL_TXT[a.level], a.title, a.motor, a.value, a.threshold, `2026-11-12 ${hhmm(a.ts)}`, a.feishu === 'none' ? '未通知' : `已${a.feishu === 'read' ? '读' : '送达'} ${a.feishuTo}`, ST_TXT[a.status], a.owner, a.solution || ''])];
    downloadCSV(rows, `告警记录_20261112.csv`);
    toast('ok', `已导出 ${list.length} 条告警记录`, 'CSV 含 UTF-8 BOM,Excel 直接打开不乱码');
  });
  $('#testFeishu').addEventListener('click', openFeishuPreview);
  $('#saveSettings').addEventListener('click', () => {
    settingsDirty = false;
    $('#saveSettings').innerHTML = `${icon('check', 15)} 保存配置`;
    toast('ok', '配置已保存并生效', '阈值与通知策略已同步到后台服务(本地存储)');
    if (state.rendered.overview) renderTrend();
  });
  $('#resetSettings').addEventListener('click', () => {
    DEFAULT_LIMITS.forEach(d => { const m = motorById(d.id); m.tempLimit = d.t; m.ampLimit = d.a; });
    renderSettings(); toast('info', '已恢复默认阈值', '点击「保存配置」后生效');
  });
  bindSwitches($('#view-settings'));
}

/* ---------------- 启动 ---------------- */
function init() {
  injectIcons();
  bindEvents();
  startClock();
  const initial = location.hash.replace('#/', '');
  go(VIEWS[initial] ? initial : 'overview');
  observeReveals();
  bootDone = true;
  setInterval(tick, 3000);
  setTimeout(() => toast('info', '演示数据已加载', '6 台电机 · LoRa 链路在线 · 每 3 秒模拟刷新'), 900);
}
init();