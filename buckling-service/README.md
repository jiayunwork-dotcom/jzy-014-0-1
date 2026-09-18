# 轴压杆屈曲核算服务 (Column Buckling Assessment Service)

纯服务端的压杆稳定计算组件：输入杆长、截面惯性矩、弹性模量、端部约束系数、
截面积、屈服强度与初始缺陷，输出欧拉临界力、长细比、计入缺陷后的
Perry 折减承载力与控制模式。

## 计算约定

- 有效长度 `L_eff = K · L`，欧拉临界力 `P_cr = π²·E·I / L_eff²`（两端铰接 K=1）
- 回转半径 `r = √(I/A)`，长细比 `λ = L_eff / r`
- 屈服力 `P_y = fy·A`，相对长细比 `λ̄ = √(P_y/P_cr)`
- Perry 折减：`(fy − σ)(σ_e − σ) = η·σ_e·σ`，取较小根，
  其中 `σ_e = P_cr/A`，`η = α·max(λ̄ − 0.2, 0)`
- 承载力 `P_rd = σ·A`，永不超过 `P_y`；`α = 0` 且未触及屈服时回到欧拉临界力
- 控制模式：`material_yield` / `euler_buckling` / `imperfection_interaction`

约定与容差可通过 `GET /api/v1/config` 回显确认。

## 快速开始

```bash
docker compose up --build
# 服务监听 http://localhost:8000 ，交互文档见 /docs
```

本地开发：

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest            # 运行全部自动化测试
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 运行状态（含数据库连通性与记录数），供监控采集 |
| GET | `/api/v1/config` | 回显 Perry 折减约定与容差配置 |
| GET | `/api/v1/examples/pinned-pinned` | 预置算例（两端铰接 K=1，工字型量级截面） |
| POST | `/api/v1/buckling/euler` | 欧拉临界力核算 |
| POST | `/api/v1/buckling/capacity` | 折减承载力与控制模式核算 |
| POST | `/api/v1/buckling/batch` | 批量核算（单组非法不影响其余各组） |
| GET | `/api/v1/history` | 历史记录查询（`endpoint`/`status`/`limit`/`offset`） |

### 请求示例

```bash
curl -X POST http://localhost:8000/api/v1/buckling/capacity \
  -H 'Content-Type: application/json' \
  -d '{
    "length": 4000.0,
    "moment_of_inertia": 8.35e7,
    "elastic_modulus": 200000.0,
    "end_condition_factor": 1.0,
    "area": 8450.0,
    "yield_strength": 355.0,
    "imperfection_factor": 0.21,
    "units": "N-mm"
  }'
```

## 输入校验

- 杆长、惯性矩、弹性模量、K、截面积、屈服强度必须为正的有限数值，
  缺陷系数非负；缺字段、非数值、NaN/无穷一律返回 422 并指明参数
- `E/fy` 超出工程合理区间 `[10, 1e5]` 时判定为屈服强度与弹性模量
  量纲混用，返回 400 说明，绝不输出看似正常实则错误的承载力
- 批量核算逐组独立校验，错误信息包含组序号与参数名

## 持久化与并发

每次核算（含批量与失败请求）都写入数据库（默认 SQLite WAL 模式，
挂载卷 `/data`；可用 `DATABASE_URL` 切换到 PostgreSQL 等）。
每请求独立会话，并发核算互不干扰。

## 代码结构

```
app/
├── core/           # 纯计算：euler.py / slenderness.py / perry.py
├── services/       # validation.py（量纲检查）/ calculator.py（编排）/ persistence.py
├── models/         # schemas.py（Pydantic）/ db_models.py（SQLAlchemy）
├── db/database.py  # 引擎与会话
├── api/routes.py   # HTTP 路由
└── main.py         # 应用入口与异常处理
tests/              # 核心规则、接口行为、并发测试
```
