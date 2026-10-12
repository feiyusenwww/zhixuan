# PR：索引管理（费 · 后端 · 第 6 轮）

> 分支：`feature/fei-backend-v2`（承接第 5 轮 `services/review.py` 等未提交改动）
> 任务：`tasks.md` **8.3 索引管理（增量重建，不中断问答）**（产品书 6.6.4–6.6.5）
> 验证：`backend/test_index.py` **14/14 通过**；回归 9 个测试脚本全绿
> 迁移：**0005 新增 `index_task` 表**（1 张，第 7 章之外，同 0003 的 `admin_audit_log`）

---

## 一、任务边界与本轮取舍（先说清楚）

8.3 的任务标注是【②④】：**④ 负责真正的向量计算**（tasks.md 5.2 集成 Embedding + pgvector/HNSW），
**② 负责索引管理的编排层**。8.3 的验收条件是「**重建期间问答仍可响应**」——这是②能独立交付的部分，
且是本轮主要工作量：

| 本轮交付（②） | 留给 ④（5.2） |
|---|---|
| 重建范围判定（全量 / 增量 / 指定文档） | bge-small-zh-v1.5 模型接入 |
| 任务态与进度落库、后台执行不占请求线程 | pgvector + HNSW 索引构建 |
| 并发保护、操作留痕、异常如实落库 | 向量检索召回 |

**仍不做占位**：未接入 embedder 时任务以 `partial` 结束、`pending_embedding` 如实等于待向量化切片数、
`message` 明写「向量化未接入（待 ④ 号 5.2）」，绝不让 ⑤ 的索引页以为索引进度已完成。

## 二、为什么新增 `index_task` 表

产品书 6.6.4–6.6.5 只规定 `POST /index/rebuild` 返回 `{task_id, status}`、
`GET /index/tasks/{task_id}` 返回 `{status, progress}`，**任务的持久化载体未定义**。
若用进程内字典，重启即丢、无法查历史、也无法让查询侧与执行侧解耦。故新增 1 张表承载任务态
（与 8.1 新增 `admin_audit_log` 同一理由），已在需队长清单第 32 项登记。

## 三、实现内容

### 接口（产品书 6.6.4–6.6.5）

| 方法 | 路径 | 请求 / 响应 |
|---|---|---|
| POST | `/api/admin/index/rebuild` | `{ scope: all\|doc_ids, doc_ids?, incremental: bool }` → `{ task_id, status }` |
| GET | `/api/admin/index/tasks/{task_id}` | → `{ status, progress }` + 追加字段 |

`progress` = `{ total, processed, embedded, pending_embedding, failed, percent }`。
追加字段：`task_id / scope / doc_ids / incremental / message / embedder_ready / operator / created_at / started_at / finished_at`。

### 「不中断问答」是如何保证的（8.3 验收条件）

1. **请求线程只建单**：范围判定 + 建单 + 留痕，随后立刻返回 `{task_id, status}`，向量化在 daemon 后台线程执行；
2. **小步提交**：后台线程每 `BATCH_SIZE=200` 条提交一次进度，避免长时间持写锁；
3. **先算向量后落库**：embedder 调用期间不持有写事务，问答请求的读写不被阻塞；
4. **重建一律串行**：模块级锁 + 「已有任务进行中 → 1001」，避免多次重建互相拖慢（SQLite 写锁下无收益）。

用例 08 用「可控阻塞的 embedder」把任务稳定停在 `running`，期间连打 3 次 `/api/qa` 与
`/api/admin/stats` 均正常，随后放行并断言 `done`、`embedded=4`。

### 增量语义（如实定义）

`incremental=True` → 只处理**未向量化**（`embedding` 为空）的切片；`False` → 全量重算。

> 实现细节（易踩坑，已固化）：`knowledge_chunk.embedding` 是 JSON 列，SQLAlchemy 默认把 Python `None`
> 写成 JSON `null`（**不是 SQL NULL**），`embedding IS NULL` 一条也匹配不到 8.2 导入的切片。
> 故增量判定在 Python 层做（两种存储形态解码后都是 `None`）。
> 待 ④ 把该列切成 pgvector 原生 `vector` 后可改回 SQL 侧过滤，函数签名不变。

### ④ 的接入点

```python
from app.services import indexing
indexing.register_embedder(lambda text: embedder.encode(text).tolist())  # 5.2 完成后注入
```
本模块负责 L2 归一化后落库（符合 `knowledge_chunk.embedding` 的写入约定），④ 只管算向量。

### 其他

| 项 | 说明 |
|---|---|
| 留痕 | 发起重建写 `admin_audit_log`：`index.rebuild`，detail 含 `scope/doc_ids/incremental/total/embedder_ready` |
| 参数校验 | `scope` 非法、`doc_ids` 为空、文档不存在 → 1001（错误码不新增） |
| 异常 | 后台异常一律落 `failed` + 摘要（`message`），不让线程异常静默丢失 |
| 状态取值 | `pending / running / partial / done / failed`；`partial` = 处理结束但仍有切片未向量化 |

## 四、涉及文件

| 文件 | 改动 |
|---|---|
| `app/services/indexing.py` | **新增**（编排、进度、后台执行、embedder 注册点） |
| `app/api/v1/admin/index.py` | **新增**（2 个接口） |
| `app/api/v1/admin/__init__.py` | 挂载 index 子路由；**管理端 6.6 接口至此全部落地** |
| `app/models/knowledge.py` | 新增 `IndexTask` 模型与 5 个状态常量 |
| `app/models/__init__.py` | 登记 `IndexTask`（否则迁移不建表） |
| `app/models/audit.py` | 新增动作常量 `index.rebuild` |
| `app/schemas/admin.py` | 新增 `IndexRebuildRequest`、`IndexScope` |
| `alembic/versions/20261012_0005_index_task.py` | **新增迁移**（建 `index_task` + 2 索引，可完整回滚） |
| `test_index.py` | **新增** 14 条用例 |
| `test_routes.py` | 契约冒烟集补 2 条（46 个接口） |
| `test_models.py` | 期望表集补 `index_task`（24 张表） |

## 五、验证方式

```bash
cd backend
.venv\Scripts\python.exe test_index.py     # 14/14 通过
.venv\Scripts\python.exe test_models.py    # migration check passed（24 张表，幂等 + 回滚均通过）
.venv\Scripts\python.exe test_routes.py    # route contract check passed (46 个接口)
.venv\Scripts\python.exe test_admin.py     # 29/29 通过
.venv\Scripts\python.exe test_review.py    # 20/20 通过
```

用例清单（14 条）：鉴权 1002/1003、参数校验 1001、增量圈定、未接入时不假装成功、
空范围、**重建期间问答与统计照常响应（8.3 验收）**、向量落库 + L2 归一化、
全量重算、`scope=doc_ids` 生效、并发拒绝、留痕、任务态字段齐全。

## 六、未做与依赖（如实标注）

| 项 | 状态 | 依赖 / 说明 |
|---|---|---|
| 真实向量化 | 未做 | ④ 号 5.2；已留 `register_embedder` 接入点，注入即全链路生效 |
| pgvector + HNSW 索引 | 未做 | ④ 号 5.2 需一条迁移把 `embedding` 改为 `vector(512)` 并建 HNSW；本模块无需改动 |
| 「文档改动后算陈旧」的增量判定 | 未做 | 当前增量 = 未向量化。若需按文档更新时间判陈旧，须给 `knowledge_chunk` 加 `indexed_at`/`doc_updated_at` 列（涉及 1.4 表结构，**待队长与 ④ 确认**，见清单第 33 项） |
| 重建中断续跑 | 未做 | 进程重启后 `running` 任务会滞留；当前按「异常落 failed」处理，如需续跑请提出 |

## 七、需相关方同步

- **⑤ 号 `/admin/index` 页**：2 个接口 + 5 个状态取值 + 追加字段见上；`partial` 与 `done` 均属结束态，建议按 `message` 提示用户。
- **④ 号**：5.2 完成后调用 `indexing.register_embedder`；另请注意向量落库已由本模块做 L2 归一化，勿重复归一化。
- **队长**：见需队长清单第 32、33 项（新表 `index_task`、增量口径待确认）。