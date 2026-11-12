# API 接口文档

> 版本：v1.0 · 2026-11-12
> Base URL：`http://<host>:8000/api/v1`
> 在线文档：`/api/docs`（Swagger UI）· `/api/redoc` · `/api/openapi.json`

## 1. 通用约定

### 1.1 认证

| 模式 | 配置 | 行为 |
| :--- | :--- | :--- |
| 试点直连 | `MP_AUTH_MODE=off` | 所有请求使用默认用户“设备科 · 观察员”，适合内网隔离试点 |
| SSO 代理 | `MP_AUTH_MODE=proxy` | 必须由 SSO/oauth2-proxy 注入 `X-Auth-User`；缺失返回 401 |
| 角色头 | 可选 | `X-Auth-Role`，缺省“观察员”，用于页面展示 |

生产建议由 Nginx 前置 SSO，禁止直接暴露 backend 端口。

### 1.2 请求与响应

- `Content-Type: application/json; charset=utf-8`
- 时间：ISO 8601 UTC，例如 `"2026-11-12T06:30:00Z"`；前端本地化为北京时间。
- 数值单位：温度 `°C`，电流 `A`，偏离 `%`，温升 `°C/天`。
- 错误格式：

```json
{ "detail": "电机 M-99 不存在" }
```

| HTTP | 含义 |
| :--- | :--- |
| 200 | 成功 |
| 201 | 创建成功（当前接口未使用） |
| 401 | 未通过统一身份认证（proxy 模式） |
| 404 | 资源不存在 |
| 409 | 状态冲突（如重复闭环、删除未闭环告警） |
| 422 | 参数校验失败 |
| 500 | 服务内部错误，查看 backend 日志 |

### 1.3 分页

告警列表：`page` 从 1 开始，`page_size` 默认 50、最大 200；返回 `total/page/page_size`。

### 1.4 标识

- 电机、网关、传感器：业务编码字符串，如 `M-01`、`GW-01`、`T-01`。
- 告警：数字 `id` + 展示编码 `code`（如 `AL-0007`）；写操作使用数字 `id`。
- 读数使用 `(motor_id, ts)` 唯一；同一 15 分钟桶重复采集只更新。

## 2. 健康与系统

### 2.1 健康检查

`GET /health`

无需认证。

```json
{
  "status": "ok",
  "service": "motor-monitor-api",
  "version": "0.1.0",
  "time": "2026-11-12T06:30:00Z"
}
```

### 2.2 当前用户

`GET /system/me`

```json
{ "name": "设备科 · 观察员", "role": "设备科 · 观察员", "auth_mode": "off" }
```

### 2.3 系统信息

`GET /system/info`

返回应用信息、用户、计数、采集状态、保留策略、LoRa 参数、飞书配置、试点进度、验收指标、网关列表。

```json
{
  "app": { "name": "MotorPulse 大电机风险监测平台", "version": "0.1.0", "env": "dev", "timezone": "Asia/Shanghai" },
  "user": { "name": "设备科 · 观察员", "role": "设备科 · 观察员", "auth_mode": "off" },
  "counts": { "motors": 6, "gateways": 1, "sensors": 12 },
  "sampling": {
    "interval_minutes": 15,
    "last_poll_at": "2026-11-12T06:30:00Z",
    "next_poll_at": "2026-11-12T06:45:00Z",
    "collector_mode": "simulator",
    "collector_running": true
  },
  "collector": {
    "thread_alive": true,
    "running": false,
    "last_error": null,
    "last_cycle": { "gateways": 1, "attempts": 12, "successes": 12, "failures": 0, "duration_ms": 226 }
  },
  "retention_days": 180,
  "baseline_days": 30,
  "lora": { "frequency_mhz": 470, "baud_rate": 1200, "sf": 7, "bw_khz": 125, "cr": "4/5" },
  "feishu": { "configured": false, "masked_webhook": "", "group_name": "设备运维告警群" },
  "pilot": {
    "start_date": "2026-10-26",
    "days": 30,
    "current_day": 18,
    "progress_pct": 60.0,
    "remaining_days": 12,
    "scope": "M-01 循环水泵 / M-02 循环水泵 / M-03 主排风机"
  },
  "acceptance": {
    "items": [
      { "key": "notify_latency", "label": "异常发现到飞书通知 ≤ 1 分钟", "status": "pass", "detail": "平均 2.0 秒 / 最大 2.0 秒（6 条已通知告警）" }
    ],
    "generated_at": "2026-11-12T06:30:00Z",
    "pass_count": 2,
    "total_auto": 5
  },
  "gateways": []
}
```

### 2.4 采集状态

`GET /system/collector/status`

```json
{
  "thread_alive": true,
  "running": false,
  "last_started_at": "2026-11-12T06:30:00Z",
  "last_finished_at": "2026-11-12T06:30:01Z",
  "last_error": null,
  "next_run_at": "2026-11-12T06:45:00Z",
  "last_cycle": { "gateways": 1, "attempts": 12, "successes": 12, "failures": 0, "new_alarms": 0, "duration_ms": 226 },
  "mode": "simulator",
  "sampling": { "interval_minutes": 15, "next_poll_at": "2026-11-12T06:45:00Z" }
}
```

### 2.5 立即召测

`POST /system/collector/poll`

```json
{ "accepted": true, "message": "已加入召测队列，下一轮采集立即执行" }
```

## 3. 监测总览与趋势

### 3.1 总览

`GET /dashboard/overview`

返回 KPI、电机卡片、活跃告警、链路统计、闭环统计、采样信息、试点信息。

```json
{
  "generated_at": "2026-11-12T06:30:00Z",
  "user": { "name": "设备科 · 观察员", "role": "设备科 · 观察员" },
  "sampling": {
    "interval_minutes": 15,
    "last_poll_at": "2026-11-12T06:30:00Z",
    "next_poll_at": "2026-11-12T06:45:00Z",
    "collector_mode": "simulator",
    "collector_running": true
  },
  "pilot": { "current_day": 18, "days": 30, "progress_pct": 60.0, "remaining_days": 12, "scope": "..." },
  "kpis": {
    "online_motors": 6,
    "total_motors": 6,
    "active_alarms": 3,
    "critical_alarms": 1,
    "warning_alarms": 2,
    "avg_temperature_c": 66.8,
    "avg_load_pct": 72.5,
    "link_availability_pct": 100.0,
    "packets_today": 720,
    "packet_loss_pct": 0.0,
    "avg_latency_ms": 433.0
  },
  "motors": [
    {
      "code": "M-03",
      "name": "主排风机",
      "location": "二车间 · 排风机房",
      "group": "风机组",
      "rated_kw": 160,
      "rated_current_a": 290,
      "temp_limit_c": 85,
      "current_limit_a": 305,
      "pilot": true,
      "node_code": "N-02",
      "status": "crit",
      "online": true,
      "temperature_c": 87.7,
      "current_avg_a": 196.1,
      "load_pct": 67.6,
      "temp_deviation_pct": 19.0,
      "last_seen_at": "2026-11-12T06:30:00Z",
      "quality": "ok",
      "spark_temp": [85.8, 86.1, 86.4],
      "spark_current": [180.2, 181.0, 182.3]
    }
  ],
  "active_alarms": [
    {
      "id": 1,
      "code": "AL-0001",
      "level": "crit",
      "level_text": "严重",
      "title": "外壳温度越限",
      "description": "温度 87.7°C 超过上限 85.0°C...",
      "advice": "优先检查风道散热、轴承润滑与端盖温升...",
      "motor_code": "M-03",
      "motor_name": "主排风机",
      "device_code": "M-03",
      "value": 87.7,
      "threshold": 85.0,
      "unit": "°C",
      "status": "open",
      "owner": "王工 · 设备科",
      "notification_status": "sent",
      "notification_to": "设备运维告警群 · 王工 · 设备科",
      "triggered_at": "2026-11-12T05:48:00Z",
      "timeline": []
    }
  ],
  "link": {
    "gateways_online": 1,
    "gateways_total": 1,
    "nodes_online": 3,
    "nodes_total": 3,
    "avg_rssi_dbm": null,
    "packets_today": 720,
    "packet_loss_pct": 0.0,
    "avg_latency_ms": 433.0
  },
  "loop": {
    "notifications_today": 5,
    "closed_today": 3,
    "avg_response_min": 60.0,
    "items": [
      { "text": "M-06 温度持续上升 · 补脂并清理散热片...", "who": "李工 · 电气", "ts": "2026-11-12T03:11:00Z" }
    ]
  }
}
```

### 3.2 趋势

`GET /dashboard/trend?range=24h|7d|30d&motor_id=M-03`

`motor_id` 省略时返回全部启用电机均值。

```json
{
  "motor_code": "M-03",
  "range": "24h",
  "bucket_minutes": 15,
  "points": [
    {
      "ts": "2026-11-12T06:00:00Z",
      "temperature_c": 87.2,
      "current_avg_a": 196.3,
      "current_a": 196.1,
      "current_b": 196.7,
      "current_c": 196.0
    }
  ]
}
```

## 4. 电机

### 4.1 电机列表

`GET /motors`

```json
{
  "items": [
    {
      "code": "M-01",
      "name": "1#循环水泵电机",
      "status": "ok",
      "online": true,
      "temperature_c": 61.4,
      "current_avg_a": 178.1,
      "load_pct": 74.2,
      "temp_deviation_pct": 5.3,
      "spark_temp": [60.8, 61.1],
      "spark_current": [177.2, 178.1]
    }
  ],
  "total": 6
}
```

### 4.2 电机详情

`GET /motors/{code}`

```json
{
  "motor": { "code": "M-03", "name": "主排风机", "status": "crit", "temperature_c": 87.7 },
  "sensors": [
    {
      "code": "T-03",
      "kind": "temperature",
      "kind_text": "温度传感器",
      "motor_code": "M-03",
      "gateway_code": "GW-01",
      "slave_id": 5,
      "register_address": 0,
      "register_count": 1,
      "scale": 0.1,
      "unit": "℃",
      "power_type": "市电供电",
      "online": true,
      "last_read_at": "2026-11-12T06:30:00Z",
      "last_error": null
    }
  ],
  "baseline": { "temp_median": 73.5, "temp_p10": 69.9, "temp_p90": 78.9, "current_median": 188.5, "current_p10": 179.7, "current_p90": 197.2, "sample_count": 2880 },
  "recent_alarms": []
}
```

### 4.3 历史序列

`GET /motors/{code}/series?range=24h|7d|30d`

返回 `{motor_code, range, bucket_minutes, points[]}`，`points` 结构同 3.2。

### 4.4 修改阈值

`PATCH /motors/{code}/thresholds`

请求（字段均可选，至少一个）：

```json
{
  "temp_limit_c": 85,
  "current_limit_a": 252,
  "temp_deviation_pct": 8,
  "current_deviation_pct": 10,
  "rise_rate_limit_c_per_day": 1.0,
  "notify_enabled": true,
  "pilot": true
}
```

响应：

```json
{
  "code": "M-01",
  "temp_limit_c": 85.0,
  "current_limit_a": 252.0,
  "temp_deviation_pct": 8.0,
  "current_deviation_pct": 10.0,
  "rise_rate_limit_c_per_day": 1.0,
  "notify_enabled": true,
  "pilot": true
}
```

写入 `audit_logs`。

## 5. 对比分析

### 5.1 自身历史

`GET /analysis/self?motor_id=M-03&range=30d`

返回：

```json
{
  "motor": { "code": "M-03", "name": "主排风机" },
  "range": "30d",
  "series": [ { "ts": "2026-10-13T00:00:00Z", "temperature_c": 72.1, "current_avg_a": 186.2 } ],
  "band": [ { "ts": "2026-10-13T00:00:00Z", "lo": 69.9, "hi": 76.0 } ],
  "baseline": { "temp_median": 73.53, "temp_p10": 69.87, "temp_p90": 78.91, "current_median": 188.49, "current_p10": 179.68, "current_p90": 197.19, "sample_count": 2880 },
  "latest": { "temperature_c": 87.4, "current_avg_a": 196.29, "load_pct": 67.7, "ts": "2026-11-12T06:00:00Z" },
  "deviation": { "temp_pct": 18.86, "current_pct": 4.14 },
  "rise_rate_c_per_day": 1.923,
  "rules": [
    { "key": "temp_deviation", "label": "高于自身基线 8.0%", "hit": true, "detail": "当前偏离 +18.9%" },
    { "key": "temp_high", "label": "超过温度上限 85°C", "hit": true, "detail": "87.4°C / 上限 85.0°C" },
    { "key": "temp_rise", "label": "温升速率超过 1.0°C/天", "hit": true, "detail": "近 7 天 +1.93°C/天 · 8 天样本" },
    { "key": "current_deviation", "label": "电流偏离基线 10.0%", "hit": false, "detail": "当前偏离 +4.1%" }
  ],
  "verdict": {
    "key": "temp",
    "text": "温度高 / 电流正常 · 散热、轴承或润滑方向",
    "advice": "电流正常但温度升高：优先检查风道散热、轴承润滑与端盖温升，建议红外测温复核。"
  }
}
```

### 5.2 同类对比

`GET /analysis/peers?group=泵组A`

```json
{
  "group": "泵组A",
  "groups": ["泵组A", "空压站", "风机组"],
  "motors": [
    {
      "code": "M-01",
      "name": "1#循环水泵电机",
      "status": "ok",
      "temperature_c": 61.4,
      "current_avg_a": 178.1,
      "load_pct": 74.2,
      "temp_deviation_pct": 5.3,
      "current_deviation_pct": 4.5,
      "score": 5.01
    }
  ],
  "ranking": [ { "code": "M-01", "score": 5.01, "rank": 1 } ],
  "insight": "组内电机指标接近，无明显离群电机，M-01 略高但在正常波动范围内。"
}
```

### 5.3 四象限

`GET /analysis/quadrant`

```json
{
  "points": [
    { "code": "M-03", "name": "主排风机", "temp_deviation_pct": 18.86, "current_deviation_pct": 4.14, "status": "crit" },
    { "code": "M-05", "name": "冷却塔风机", "temp_deviation_pct": 4.78, "current_deviation_pct": 17.92, "status": "warn" }
  ],
  "thresholds": { "temp_pct": 8.0, "current_pct": 10.0 }
}
```

### 5.4 趋势

`GET /analysis/trend?motor_id=M-03&range=7d`

```json
{
  "motor": { "code": "M-03", "name": "主排风机", "temp_limit_c": 85 },
  "range": "7d",
  "series": [ { "ts": "2026-11-05T06:00:00Z", "temperature_c": 72.0, "current_avg_a": 186.0 } ],
  "stats": {
    "max_temp_c": 87.4,
    "min_temp_c": 70.95,
    "avg_temp_c": 80.03,
    "slope_c_per_day": 1.926,
    "sample_days": 8
  },
  "verdict": { "bad": true, "tag": "持续恶化", "text": "M-03 近 7 天温度单边上行（+1.93°C/天）..." },
  "events": [
    { "id": "AL-0001", "level": "crit", "title": "外壳温度越限", "ts": "2026-11-12T05:48:00Z", "status": "open" }
  ]
}
```

## 6. 告警

### 6.1 告警列表

`GET /alarms?level=all|crit|warn|info&status=all|open|ack|closed|active&q=&from=&to=&page=1&page_size=50`

```json
{
  "items": [
    {
      "id": 7,
      "code": "AL-0007",
      "level": "warn",
      "level_text": "警告",
      "title": "温度持续上升",
      "description": "近 7 天温度呈单边上行...",
      "advice": "持续温升多与机械或散热侧劣化相关...",
      "motor_code": "M-03",
      "motor_name": "主排风机",
      "device_code": "M-03",
      "metric": "rise_rate_c_per_day",
      "value": 1.93,
      "threshold": 1.0,
      "unit": "°C/天",
      "status": "open",
      "owner": "王工 · 设备科",
      "notification_status": "skipped",
      "notification_to": "设备运维告警群 · 王工 · 设备科",
      "triggered_at": "2026-11-12T06:00:00Z",
      "last_seen_at": "2026-11-12T06:00:00Z",
      "closed_at": null,
      "closed_by": null,
      "solution": null,
      "suppressed_until": null,
      "timeline": []
    }
  ],
  "total": 7,
  "page": 1,
  "page_size": 50,
  "stats": { "open": 3, "today": 6, "closed": 4, "avg_response_min": 60.0 }
}
```

### 6.2 告警详情

`GET /alarms/{alarm_id}`

返回列表项全部字段 + `timeline[]` + `notification`：

```json
{
  "id": 7,
  "code": "AL-0007",
  "timeline": [
    { "key": "triggered", "title": "触发告警", "detail": "温度持续上升 · ...", "ts": "2026-11-12T06:00:00Z", "state": "hot" },
    { "key": "notification", "title": "飞书通知", "detail": "设备运维告警群 · ... · skipped", "ts": "2026-11-12T06:00:00Z", "state": "" },
    { "key": "waiting", "title": "等待人工处理", "detail": "平台只监测、只报警...", "ts": null, "state": "" }
  ],
  "notification": {
    "id": 3,
    "channel": "feishu",
    "target": "设备运维告警群 · 王工 · 设备科",
    "status": "skipped",
    "attempts": 0,
    "response_code": null,
    "created_at": "2026-11-12T06:00:00Z"
  }
}
```

### 6.3 签收处理

`POST /alarms/{alarm_id}/ack`

- 将未处理告警置为“处理中”（`ack`）；
- 已闭环返回 409；
- 写入审计。

响应：更新后的告警对象（`status: "ack"`）。

### 6.4 告警闭环

`POST /alarms/{alarm_id}/close`

```json
{ "solution": "验收测试：现场检查风道并复测正常。" }
```

- 已闭环再次调用返回 409。
- 闭环后设置 `suppressed_until = now + 30 分钟`，抑制期内同 `dedup_key` 不重建。
- 写入 `audit_logs`。

响应：更新后的告警对象。

### 6.5 批量闭环

`POST /alarms/bulk-close`

```json
{
  "ids": [7, 8],
  "solution": "批量闭环：已现场确认处理。"
}
```

```json
{ "closed": 2, "items": [ { "id": 7, "status": "closed" } ] }
```

### 6.6 删除已闭环告警

`DELETE /alarms/{alarm_id}`

- 仅允许删除 `closed` 状态；否则 409。
- 写入审计。

```json
{ "deleted": true, "id": 7 }
```

### 6.7 CSV 导出

`GET /alarms/export.csv?level=&status=&q=&from=&to=`

- `text/csv; charset=utf-8`，带 UTF-8 BOM。
- 字段：告警编号、级别、内容、电机/设备、触发值、阈值、触发时间、飞书通知、状态、责任人、处理结果。
- 对 `= + - @` 等危险前缀加 `'`，防 CSV 注入。

## 7. 设备与链路

### 7.1 设备列表

`GET /devices`

```json
{
  "summary": { "gateways_online": 1, "gateways_total": 1, "sensors_total": 12, "sensors_online": 12 },
  "gateways": [
    {
      "id": 1,
      "code": "GW-01",
      "name": "一车间 LoRa 网关",
      "host": "10.112.66.231",
      "port": 10123,
      "framer": "rtu",
      "enabled": true,
      "online": true,
      "last_seen_at": "2026-11-12T06:30:00Z",
      "last_error": null,
      "consecutive_failures": 0,
      "sensor_count": 12
    }
  ],
  "sensors": [
    {
      "code": "T-03",
      "kind": "temperature",
      "kind_text": "温度传感器",
      "motor_code": "M-03",
      "gateway_code": "GW-01",
      "slave_id": 5,
      "register_address": 0,
      "register_count": 1,
      "scale": 0.1,
      "unit": "℃",
      "power_type": "市电供电",
      "online": true,
      "last_read_at": "2026-11-12T06:30:00Z",
      "last_error": null,
      "consecutive_failures": 0
    }
  ],
  "events": [
    { "ts": "2026-11-12T06:30:00Z", "level": "ok", "text": "GW-01 采集完成：成功 12/12，耗时 420ms" }
  ]
}
```

### 7.2 网关召测

`POST /devices/gateways/{code}/poll`

```json
{ "accepted": true, "message": "已加入召测队列，下一轮采集立即执行" }
```

## 8. 设置

### 8.1 获取设置

`GET /settings`

```json
{
  "motors": [
    {
      "code": "M-01",
      "name": "1#循环水泵电机",
      "pilot": true,
      "enabled": true,
      "rated_current_a": 240,
      "temp_limit_c": 85,
      "current_limit_a": 252,
      "temp_deviation_pct": 8,
      "current_deviation_pct": 10,
      "rise_rate_limit_c_per_day": 1.0,
      "notify_enabled": true
    }
  ],
  "notifications": {
    "critical_enabled": true,
    "warning_enabled": true,
    "info_enabled": true,
    "quiet_hours_enabled": true,
    "quiet_start": "22:00",
    "quiet_end": "06:00",
    "group_name": "设备运维告警群",
    "owners": ["王工 · 设备科", "李工 · 电气", "惠哥 · 生产"]
  },
  "sampling": { "interval_minutes": 15, "last_poll_at": "2026-11-12T06:30:00Z", "next_poll_at": "2026-11-12T06:45:00Z", "collector_mode": "simulator", "collector_running": true },
  "lora": { "frequency_mhz": 470, "baud_rate": 1200, "sf": 7, "bw_khz": 125, "cr": "4/5" },
  "feishu": { "configured": false, "masked_webhook": "", "group_name": "设备运维告警群" },
  "pilot": { "current_day": 18, "days": 30, "progress_pct": 60.0, "remaining_days": 12, "scope": "..." },
  "acceptance": { "items": [], "generated_at": "2026-11-12T06:30:00Z", "pass_count": 2, "total_auto": 5 }
}
```

### 8.2 保存通知设置

`PUT /settings/notifications`

字段均可选；时间格式 `HH:MM`：

```json
{
  "critical_enabled": true,
  "warning_enabled": true,
  "info_enabled": false,
  "quiet_hours_enabled": true,
  "quiet_start": "22:00",
  "quiet_end": "06:00",
  "group_name": "设备运维告警群",
  "owners": ["王工 · 设备科", "李工 · 电气"]
}
```

响应：合并后的通知配置。写入 `audit_logs`。

### 8.3 飞书测试

`POST /settings/feishu/test`

```json
{
  "status": "sent",
  "attempts": 1,
  "response_code": 200,
  "detail": "测试消息已发送"
}
```

未配置 Webhook 时：

```json
{
  "status": "skipped",
  "attempts": 0,
  "response_code": null,
  "detail": "测试消息未发送，请检查飞书配置"
}
```

## 9. 错误码示例

| 场景 | HTTP | 响应 |
| :--- | :--- | :--- |
| SSO 模式缺少用户头 | 401 | `{"detail":"未通过统一身份认证，请从 SSO 入口访问"}` |
| 电机不存在 | 404 | `{"detail":"电机 M-99 不存在"}` |
| 重复闭环 | 409 | `{"detail":"该告警已闭环，不能重复处理"}` |
| 删除未闭环告警 | 409 | `{"detail":"仅允许删除已闭环的历史告警"}` |
| 阈值有空字段 | 422 | `{"detail":"没有需要更新的字段"}` |
| 时间格式错误 | 422 | `{"detail":"时间格式不正确: ..."}` |
| 内部错误 | 500 | `{"detail":"服务内部错误，请查看日志"}` |

## 10. 调用示例

```bash
# 健康
curl http://127.0.0.1:8000/api/v1/health

# 总览
curl http://127.0.0.1:8000/api/v1/dashboard/overview

# SSO 代理模式示例
curl -H "X-Auth-User: wang.gong" \
     -H "X-Auth-Role: 设备科" \
     http://127.0.0.1:8000/api/v1/alarms

# 闭环
curl -X POST http://127.0.0.1:8000/api/v1/alarms/7/close \
     -H "Content-Type: application/json" \
     -d '{"solution":"现场检查并复测正常"}'

# 修改阈值
curl -X PATCH http://127.0.0.1:8000/api/v1/motors/M-01/thresholds \
     -H "Content-Type: application/json" \
     -d '{"temp_limit_c":85,"current_limit_a":252}'

# 立即召测
curl -X POST http://127.0.0.1:8000/api/v1/system/collector/poll
```

---

关联文档：[整体框架设计](02-整体框架设计.md) · [验收功能文档](04-验收功能文档.md) · [部署手册](05-部署手册.md)
