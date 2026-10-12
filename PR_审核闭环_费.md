# PR：审核工作台与审核闭环（费 · 后端 · 第 5 轮）

> 分支：`feature/fei-backend-v2`（承接第 4 轮 `3056067`）
> 任务：`tasks.md` **8.4 审核工作台**、**8.5 审核操作与回流**（产品书 6.6.9–6.6.10）
> 验证：`backend/test_review.py` **20/20 通过**；回归 `test_routes` / `test_admin` / `test_models` / `test_auth` / `test_eligibility` / `test_plans` / `test_schools` / `test_user_plans` 全绿
> 迁移：**无新增表、无迁移**（`qa_log` / `review_task` 两表在 1.4 已建，本次仅新增状态常量）

---

## 一、为什么现在能做（此前判断已修正）

上一轮进度表把 8.4/8.5 判为「均依赖 ④ 号 RAG 产出 `qa_log`」而搁置。复核后修正：
**表已经在 1.4 建好**（`qa_log` / `review_task`），后端可以先把「触发判定 + 入队 + 审核操作 + 回流」全部落地，
只是**队列数据要等 ④ 写日志才会出现**——这与 4.3「接口已实现、数据待 ③ 号」同一模式，属可交付状态。

因此本轮把 8.4/8.5 做完，**不阻塞 ⑤ 号 `/admin/review` 页面**（此前契约缺这一节，是 ⑤ 号最阻塞项之一）。

## 二、实现内容

### 8.4 审核工作台（自动入队）

新增 [`app/services/review.py`](../backend/app/services/review.py)，触发条件纯确定性、无模型参与：

| 触发条件 | 判定 | 入队原因 |
|---|---|---|
| 低置信 | `qa_log.confidence == "low"` | `低置信` |
| 涉分数线 | 问题/答案命中「分数线/投档线/省控线/录取线/位次/一分一段/招生计划」 | `涉分数线` |
| 涉规则 | 命中「资格/户籍/学籍/专项/政策/报名条件/章程」 | `涉规则` |

- **`auto_enqueue(db, qa_log)`** —— 幂等建单（一条问答最多一个任务），置 `needs_review=true`、
  `qa_log.status=pending_review`。**不自行提交事务**，是 ④ 号问答链路的唯一接入点：
  ④ 写完 `qa_log` 后在同一事务里调用一次即可。
- **`enqueue_missing(db)`** —— 扫描补建，供管理端「刷新待审队列」与 ④ 批量补录兜底。

接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/review/tasks?status=&trigger_reason=&page=&page_size=` | 待审列表，分页，默认 `status=pending` |
| POST | `/api/admin/review/enqueue` | 刷新待审队列（扫描补建，幂等），返回 `{scanned, enqueued}` |
| GET | `/api/admin/review/tasks/{id}` | 详情：任务 + 问答原文 + `citations` 原文片段，供审核对照 |
| POST | `/api/admin/review/tasks/{id}` | 审核操作（见下） |

> `POST /review/enqueue` 为**追加接口**（产品书 6.6 无此条），已在需队长清单第 29 项登记。

### 8.5 审核操作与回流

`POST /api/admin/review/tasks/{id}`，请求 `{ action: approve|correct|reject, corrected_answer?, comment? }`，
成功返回 `data: null`（契约要求）。**三类动作全部留痕**（`admin_audit_log`：`review.approve` / `review.correct` / `review.reject`）。

| 动作 | 任务状态 | 问答状态 | 附加 |
|---|---|---|---|
| `approve` 通过 | `approved` | `approved` | — |
| `correct` 修正 | `corrected` | `approved` | 保存 `corrected_answer`；**回流沉淀**（见下） |
| `reject` 驳回 | `rejected` | `rejected` | 保存 `comment`，`reviewer` / `reviewed_at` 可追踪 |

- **回流（修正内容沉淀）**：把修正答案落成一条 `knowledge_doc`（`doc_type="审核修正"`）+ 一条 `knowledge_chunk`，
  来源取自**原问答的首条可用引用**；引用缺来源三要素时**不沉淀**（遵守「缺来源不展示、不臆测」），
  留痕 detail 里以 `sedimented: false` 如实标注。切片 `embedding` 留空，**向量化与索引重建属 8.3 / ④**。
- 边界：动作非法 / 任务不存在 / **已处理任务重复审核** / `correct` 缺 `corrected_answer` → 一律 `1001`，
  且不改动任何状态（用例 14 已固化）。

## 三、涉及文件

| 文件 | 改动 |
|---|---|
| `app/services/review.py` | **新增**（8.4 + 8.5 全部业务逻辑） |
| `app/api/v1/admin/review.py` | **新增**（4 个接口） |
| `app/api/v1/admin/__init__.py` | 挂载 review 子路由到 protected（统一管理员鉴权） |
| `app/models/knowledge.py` | 新增状态常量 `QA_STATUS_REJECTED`、`REVIEW_STATUS_APPROVED/CORRECTED/REJECTED`（注释已含这四个取值） |
| `app/models/audit.py` | 新增动作常量 `review.approve/correct/reject` |
| `app/schemas/admin.py` | 新增 `ReviewDecisionRequest`、`ReviewAction` |
| `test_review.py` | **新增**测试 20 条 |
| `test_routes.py` | 契约冒烟集补 4 条新路径（44 个接口） |

## 四、验证方式

```bash
cd backend
.venv\Scripts\python.exe test_review.py    # 20/20 通过
.venv\Scripts\python.exe test_routes.py    # route contract check passed (44 个接口)
.venv\Scripts\python.exe test_admin.py     # 29/29 通过
```

用例覆盖 8.4/8.5 验收条件：低置信/涉分数线/涉规则**触发即出现在待审列表**、无需审核者不入队、
幂等不重复建单、**三类操作状态流转正确**、**修正内容确实沉淀为知识文档与切片**、
**驳回记录可追踪**、已处理任务不可重复审核。

## 五、未做与依赖（如实标注）

| 项 | 状态 | 依赖 |
|---|---|---|
| **8.3 索引管理**（`POST /index/rebuild`、`GET /index/tasks/{id}`） | **未做** | 其向量化与切片策略由 ④ 号 5.1/5.2 产出；后端此刻只提供「任务态接口」会沦为占位（同 `GET /api/qa` 的教训），故不做。**接口形态已按产品书 6.6 备好，待 ④ 就绪即可落地** |
| 队列数据 | 空 | ④ 号写 `qa_log`（调用 `auto_enqueue`）后即出现；本测试用直插 `QaLog` 模拟 |
| 修正内容**重建索引** | 只沉淀不索引 | 8.3 / ④（沉淀切片 `embedding` 为 NULL） |
| 管理员角色细分 | `admin` 与 `reviewer` 权限仍相同 | 见需队长清单第 26 项；本轮未细分 |

## 六、需队长/相关方同步

- **⑤ 号**：`/admin/review` 页可直接对接上表 4 个接口；列表项含追加字段 `status` / `reviewer`。
- **④ 号**：请在写 `qa_log` 的事务里调用 `app.services.review.auto_enqueue(db, qa_log)`，
  低置信/涉分数线/涉规则问答即自动入队；未接也已由「刷新待审队列」兜底。
- **契约**：见 `需队长修订清单_费.md` 第 29 项（管理端审核章节）。