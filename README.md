# MotorPulse 大电机风险监测平台

## 项目简介

面向工厂大电机的温度 / 电流 LoRa 无线监测平台：每 15 分钟通过 LoRa 网关读取现场温度与变频器电流，提供集中看板、自身历史对比、同类电机对比、温度 × 电流关联、趋势分析、阈值告警和飞书通知闭环。

平台只监测、只报警，**不控制电机、不自动停机**，数据保存在厂内数据库，不出厂。

## 业务背景

大电机目前主要依靠人工巡检，异常发现不及时，容易造成非计划停机。试点先覆盖 1—3 台关键电机，用 LoRa 免去现场网线改造，以较低投入验证“监测 + 对比分析 + 飞书通知”的价值。

## 技术栈

| 层级 | 技术 | 版本 |
| :--- | :--- | :--- |
| 前端 | Vue 3 + TypeScript + Vite | Vue 3.5 / TS 5.7 / Vite 6 |
| 前端状态与路由 | Pinia / Vue Router | 2.3 / 4.5 |
| 图表 | Apache ECharts | 5.5 |
| 后端 | Python + FastAPI + Pydantic | 3.12 / 0.115 / 2.10 |
| 数据访问 | SQLAlchemy + Alembic | 2.0 / 1.14 |
| 数据库 | PostgreSQL（本地开发可 SQLite） | 16 |
| 采集 | pymodbus（RTU over TCP） | 3.8 |
| 通知 | 飞书 Webhook（httpx + 重试） | - |
| 部署 | Docker Compose + Nginx | - |
| 质量 | pytest / black / flake8 / isort / vue-tsc / ESLint / Prettier | - |

## 功能

- **监测总览**：在线电机、活跃告警、平均温度/负载、链路完好率、温度电流趋势、电机矩阵、四象限速览。
- **对比分析**：自身历史基线（30 天 P10–P90）、同类电机对比、温度 × 电流四象限、趋势与事件标注。
- **告警中心**：阈值/基线/温升/通信告警，飞书通知状态、处理时间线、闭环回写、批量闭环、CSV 导出。
- **设备与链路**：采集 → LoRa → 网关 → 后台 → 数据库 → 分析 → 看板/飞书全链路，设备清单与链路事件。
- **阈值与通知**：逐电机阈值、采集与 LoRa 参数展示、责任人、夜间静默、飞书测试、试点验收进度。

## 快速开始（Docker，推荐）

前置：Docker 24+、Docker Compose v2，建议 2 vCPU / 2 GB 内存 / 10 GB 磁盘。

```bash
cp .env.example .env
# 修改 .env：数据库密码、飞书 Webhook、采集模式等
docker compose up -d --build
```

访问：

- 前端：<http://服务器IP:8080>
- API 文档：<http://服务器IP:8000/api/docs>
- 健康检查：<http://服务器IP:8000/api/v1/health>

导入现场点表：

```bash
cp config/points.example.yaml config/points.yaml
# 按实际网关 IP、从站地址、寄存器、倍率修改 points.yaml
docker compose exec backend python -m app.cli import-points /app/config/points.yaml
```

演示数据（仅用于验收演示，不要在生产库执行）：

```bash
# .env 中设置 MP_COLLECTOR_MODE=simulator 后重启 backend
docker compose exec backend python -m app.cli seed-demo --reset
docker compose restart backend
```

详细步骤见 [部署手册](docs/05-部署手册.md)。

## 本地开发

### 后端

Ubuntu / Linux：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 根目录 .env 默认 MP_DATABASE_URL=sqlite:///./data/motor.db
python -m app.cli init-db
python -m app.cli seed-demo          # 演示数据；真实点表用 import-points ../config/points.yaml
uvicorn app.main:app --reload --port 8000
```

Windows（Git Bash / PowerShell）：

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
python -m app.cli init-db
python -m app.cli seed-demo
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 <http://127.0.0.1:5173>，Vite 会将 `/api` 代理到 `http://127.0.0.1:8000`。

### 测试与构建

Ubuntu / Linux：

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
flake8 app tests

cd ../frontend
npm run lint
npm run build
```

Windows：

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m flake8 app tests

cd ../frontend
npm run lint
npm run build
```

## 目录结构

```text
motor_testing_system/
├── backend/                 # FastAPI、采集器、告警与分析、Alembic
│   ├── app/
│   │   ├── api/routes/      # REST API
│   │   ├── core/            # 配置、时间、认证、日志
│   │   ├── db/              # 模型、会话、初始化、演示数据/点表导入
│   │   └── services/        # Modbus、采集调度、告警、基线、分析、飞书
│   ├── alembic/             # 数据库迁移
│   └── tests/               # pytest
├── frontend/                # Vue 3 + TypeScript 生产前端
├── config/                  # YAML 点表示例
├── deploy/                  # 预留部署扩展目录
├── docs/                    # 规范、方案、设计与验收文档
├── motor-monitor-ui/        # 原始静态 UI 设计参考（非生产代码）
├── docker-compose.yml
└── .env.example
```

`motor-monitor-ui/` 是最初的静态 UI 参考实现，生产界面已迁移到 `frontend/`；其中 30 秒等演示文案不代表最终参数，最终采集周期为 **15 分钟**。

## 关键约定

- 采集周期：**15 分钟**；现场传感器采用**市电供电**，不依赖电池。
- LoRa 参数：当前按 **470 MHz / 1200 bps** 记录展示，均可通过环境变量调整；若“1200”指其他含义请现场确认。
- 规模：单网关试点，后续支持多网关；采集点位 ≤ 100；在线观察 ≤ 10 人。
- 数据保留：默认 180 天，可通过 `MP_RETENTION_DAYS` 调整。
- 认证：试点默认 `MP_AUTH_MODE=off`；生产建议接入公司 SSO，通过 `MP_AUTH_MODE=proxy` + 网关注入 `X-Auth-User`。
- 飞书 Webhook 只从环境变量读取，不写入数据库。

## 文档

- [技术栈选型](docs/01-技术栈选型.md)
- [整体框架设计](docs/02-整体框架设计.md)
- [开发记录](docs/03-开发记录.md)
- [验收功能文档](docs/04-验收功能文档.md)
- [API 接口文档](docs/API接口文档.md)
- [部署手册](docs/05-部署手册.md)
- [项目规范](docs/项目规范.md)
- [业务方案](docs/大电机风险检测系统.md)

## 维护人

- Owner：设备科项目组（待指定）
- 现场点表 / 网关：设备科
- 后端与部署：项目开发组

## 关联文档

- API 文档（运行时）：`/api/docs`、`/api/redoc`、`/api/openapi.json`
- 设计参考：`motor-monitor-ui/`
