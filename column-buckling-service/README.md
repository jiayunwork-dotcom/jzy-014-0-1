# 轴压杆屈曲核算服务（Column Buckling Service）

纯服务端的轴压杆稳定计算组件：给定杆长、截面惯性矩、弹性模量、端部约束系数、
截面积、材料屈服强度与初始缺陷，计算**欧拉临界力**、**长细比**，以及计入
Perry 型初始缺陷后的**承载力与控制模式**。支持批量核算、请求/结果持久化与
历史条件查询。

不包含钢结构 BIM、加工工单、前端页面或账户体系。

---

## 1. 计算约定（钉死）

| 量 | 公式 / 规则 |
| --- | --- |
| 有效长度 | `Le = K · L`，两端铰接 `K = 1` |
| 欧拉临界力 | `Fe = π² · E · I / Le²`，铰接时即 `π²EI/L²` |
| 回转半径 | `r = sqrt(I / A)` |
| 长细比 | `λ = Le / r` |
| 屈服力 | `Ny = fy · A` |
| 正则化长细比 | `λ̄ = sqrt(Ny / Fe)`（`λ̄<1` 短柱，`>1` 长柱） |
| Perry 缺陷项 | `η = α · max(0, λ̄ − 0.2)` |
| Perry 折减系数 | `φ = ½(1 + η + λ̄²)`，`χ = 1 / (φ + sqrt(φ² − λ̄²))` |
| 折减后承载力 | `Nr = χ · Ny` |

控制模式（三选一）：

- `yield` —— 材料屈服控制：`λ̄ ≤ 0.2` 或承载力触及 `Ny`，`Nr = Ny`；
- `euler` —— 欧拉屈曲控制：缺陷为零且未触及屈服（长柱），`Nr = Fe`；
- `perry` —— 初始缺陷折减控制：`Nr = χ·Ny`，严格低于 `Fe` 与 `Ny`。

已保证的行为：

- 只把杆长加倍 → `Fe` 变为 **1/4**；K 从 1 改到 2 → `Fe` 变为 **1/4**；
- 惯性矩加倍 / 弹性模量加倍 → `Fe` 加倍；
- 铰接 `K=1` 时临界力严格等于 `π²EI/L²`；
- 缺陷系数为 0 且未触及屈服时，承载力**回到欧拉临界力**；
- 短柱承载力**不超过屈服力**，绝不把欧拉力当成短柱承载力；
- 屈服强度加倍时，短柱承载力加倍，长柱欧拉值不变；
- 缺陷越大、长细比越大，折减后承载力越低（单调）。

> 所有力学量必须使用**同一套自洽单位制**。例如统一用 `N、mm、MPa(=N/mm²)`，
> 或统一用 `N、m、Pa`。未通过 `unit_system` 声明且 `fy/E > 0.1`（超出任何
> 真实材料量级，几乎必然是 MPa/Pa 混用）时直接拒绝。

---

## 2. 一键启动（Docker Compose）

```bash
docker compose up --build
# 服务：http://localhost:8000   依赖：PostgreSQL 16
```

健康探针：

- `GET /health` —— 轻量探活；
- `GET /ready` —— 连通数据库的就绪检查（供监控采集，DB 不可用返回 503）。

交互式文档：`http://localhost:8000/docs`。

本地裸跑（需自行提供 PostgreSQL 或覆盖 `DATABASE_URL` 为 SQLite）：

```bash
pip install -r requirements.txt
export DATABASE_URL="sqlite+aiosqlite:///./buckling.db"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 3. 接口

统一前缀 `/api/v1`。

| 方法 & 路径 | 说明 |
| --- | --- |
| `POST /euler` | 欧拉临界力接口 |
| `POST /buckling` | 折减承载力与控制模式接口（含回转半径、长细比） |
| `POST /batch` | 批量核算：`{"items": [ {...}, {...} ]}` |
| `GET /history` | 历史查询：`kind / success / control_mode / batch_id / limit / offset` |
| `GET /history/{id}` | 单条历史详情 |
| `GET /convention` | 回显 Perry 折减约定、公式、控制模式规则与容差配置 |
| `GET /example` | 预置算例（两端铰接工字型量级截面） |

单根压杆请求字段：

```json
{
  "length": 6000.0,
  "moment_of_inertia": 2.0e8,
  "elastic_modulus": 2.05e5,
  "effective_length_factor": 1.0,
  "area": 7000.0,
  "yield_strength": 345.0,
  "imperfection": 0.0,
  "unit_system": "MPA_MM"
}
```

- `effective_length_factor`（K）缺省 `1.0`（铰接）；`imperfection` 缺省 `0`；
- `unit_system` 可选：`SI` / `MPA_MM` / `CONSISTENT`，表示各量同属一套自洽单位制。

错误响应（不崩溃、可读、带字段定位）：

```json
{ "error": { "code": "NON_POSITIVE_VALUE", "message": "…约束系数K必须为正…",
             "field": "effective_length_factor" } }
```

批量中某组非法时其余照常返回，并指出**第几组、哪个参数**：

```json
{ "summary": {"total": 3, "succeeded": 2, "failed": 1},
  "items": [ {"index": 2, "success": false,
              "error": {"code": "NON_POSITIVE_VALUE", "message": "第2组：…",
                        "field": "length"}} ] }
```

所有成功与被拒绝的请求都持久化（被拒绝的记录 `success=false` 并保存错误体）。

---

## 4. 预置算例

两端铰接常见工字型量级截面（单位 N、mm、MPa）：
`L=6000 mm, I=2.0e8 mm⁴, A=7000 mm², E=2.05e5 MPa, fy=345 MPa, K=1`。

- 参考欧拉临界力 `Fe = π²EI/L² ≈ 1.124e7 N`，与 `/euler`、`/buckling`
  实算一致（K=1）；
- 该截面 `λ̄ ≈ 0.464 < 1`，短柱，承载力由屈服封顶为 `fy·A = 2.415e6 N`，
  不会被远超屈服的欧拉力带高。

直接查看：`GET /api/v1/example`。

---

## 5. 代码结构

```
app/
  domain/
    euler.py       # 欧拉临界力、有效长度（纯函数）
    geometry.py    # 回转半径、长细比、正则化长细比（纯函数）
    perry.py       # Perry 折减系数、承载力、控制模式（纯函数）
  schemas.py       # 请求数据模型
  validation.py    # 形状/有限性/正值/缺陷/量纲混用校验 → 可读错误
  service.py       # 计算编排（不碰 HTTP/DB）
  examples.py      # 预置算例
  database.py      # 异步引擎与会话（PostgreSQL / SQLite）
  models.py        # 核算记录 ORM
  repository.py    # 持久化与历史查询
  api/
    meta.py        # /convention、/example
    calc.py        # /euler、/buckling、/batch
    history.py     # /history、/history/{id}
  main.py          # 应用装配、生命周期、统一异常、健康探针
tests/             # 自动化测试（FastAPI + httpx + 内存/文件 SQLite）
```

## 6. 运行测试

```bash
pip install -r requirements.txt
pytest -q
```

覆盖：铰接 K=1 临界力等于 π²EI/L²、杆长/K 加倍临界力变 1/4、I/E 加倍加倍、
缺陷为零回到欧拉、短柱不超过屈服力、非法参数被拒、批量部分失败其余成功、
历史持久化正确、并发多请求互不串扰，以及元信息与监控探针。
