# AI 方向

## 当前定位

AI 是 TARS-Go 的结构化建议层，不是聊天机器人、事实源或自动决策者。

V0.2 第二阶段第一刀已经实现最小闭环：

~~~text
自然语言需求
→ AI 严格结构化草案
→ 人工修改 / 删除 / 新增
→ 后端确定性校验
→ 人工确认
→ 一个正式事项 + 若干一级分工
~~~

生成草案本身绝不写入 tasks。只有用户点击“确认并创建”后，系统才真正创建事项。

## 当前已经实现

入口位于“新建事项”附近，仅对满足后端授权条件的 admin 显示。

规划页不是聊天界面，只包含：

- 一段自然语言需求输入
- 可选的已确定事项标题
- 可选粘贴的本次活动文字
- 可按标题、路径或来源名称搜索，并明确选作本次资料的知识文档
- 系统自动检索的少量团队历史经验及生成后的来源说明
- 生成方案
- 可编辑事项信息
- 可编辑一级分工列表
- 少量“需要你确认”的问题
- 重新生成
- 确认并创建
- 始终保留的手动创建入口

事项草案可修改标题、完成标准和截止时间。

分工草案可修改标题、完成标准、删除 / 新增、是否开放负责人认领、是否开放自主协作。

确认问题只用于人工检查，不写入数据库。

## 结构化输出

AI 通过后端 Pydantic schema 返回严格结构化数据，不先生成 Markdown 再猜 JSON。

当前输出只允许：

- item.title
- item.deliverable
- item.deadline（不确定时为 null）
- tasks[].title
- tasks[].deliverable
- tasks[].owner_claimable
- tasks[].collaboration_open
- questions[]

限制：

- 标题最多 200 字符
- AI 完成标准最多 1000 字符
- 最多 15 个一级分工
- 最多 6 个确认问题
- 单个问题最多 200 字符
- AI schema 没有 owner_id
- AI 不允许指定真实姓名或成员
- 模型输出通过 schema 校验后才返回前端

## 任务颗粒度

AI 拆分时重点考虑时间、地点、人员连续性、交接点和完成标准。

原则：

- 同一责任链、适合同一个人连续完成的动作尽量合并
- 同时进行且通常无法一人兼任的工作拆开
- 不为了“看起来完整”过度拆分
- 每项尽量回答“谁把什么做到什么程度”
- 不确定信息不编造
- 会影响执行的不确定内容放入 questions
- 人员尚未明确时优先开放负责人认领
- 完成标准具体但不写成长 SOP

## 权限与安全

AI planner 必须同时满足：

1. 已登录且账号 active
2. 系统角色为 admin
3. member ID 在服务器 AI_PLANNER_ALLOWED_MEMBER_IDS 白名单
4. AI_PLANNER_ENABLED=true
5. 服务器已配置 AI_API_KEY 和 AI_MODEL

后端校验是安全边界。前端隐藏按钮只是体验优化。

API key 只存在 API 容器环境变量中，不进入 Git、前端 bundle、API response 或普通应用日志。

## Provider

当前使用 OpenAI 官方 Python SDK，并支持两个 provider adapter：

- `AI_PROVIDER=openai`：OpenAI
- `AI_PROVIDER=deepseek`：DeepSeek OpenAI-compatible API

二者保持同一个 `AIPlannerDraft`、同一套权限、频控和上层业务接口。

DeepSeek 使用 `AI_BASE_URL=https://api.deepseek.com`，模型仍由 `AI_MODEL` 配置，例如 `deepseek-flash`。

真实兼容性验证显示：普通 Responses API 可用，但 `responses.parse(..., text_format=AIPlannerDraft)` 返回的 `output_parsed` 为空。因此 DeepSeek adapter 不再调用 `responses.parse`，而是从第一次请求开始直接使用一次 `responses.create`：

- `text.format.type=json_schema`
- `strict=true`
- `schema=AIPlannerDraft.model_json_schema()`
- 读取 `response.output_text`
- `json.loads(...)`
- `AIPlannerDraft.model_validate(...)`

空输出、非法 JSON 或 Pydantic 校验失败统一视为无效模型响应。不会先尝试 parse 再 fallback 到 create，因此一次生成仍然只发生一次模型 API 请求。OpenAI provider 不受影响，继续使用 `responses.parse(..., text_format=AIPlannerDraft)`。

## 成本控制

当前 AI 功能的硬边界：

- 一次“生成方案”只调用模型一次
- “重新生成”是用户明确触发的另一笔单次请求
- 不做 agent loop
- 不做自动反思 / 二次检查 / 自动改写
- SDK max_retries=0，避免隐藏自动重试造成额外调用
- 不发送历史聊天或全部数据库任务
- 不做 embedding、向量数据库或模型检索
- 只发送最多 6 个相关历史片段，历史上下文最多 3000 字符
- 本次事项资料与历史经验分开，知识上下文总量不超过 8000 字符
- 记录发送的知识上下文字符数和 provider token usage，不保存完整 prompt 或草案
- 输入最多 5000 字符
- 输出最多 15 个分工、6 个问题
- max_output_tokens=2200 for OpenAI and 4096 for DeepSeek; DeepSeek reasoning effort remains `none`
- 每个白名单用户按 UTC 日最多 20 次规划尝试
- ai_planner_daily_usage 只保存请求次数、input/output/total token 汇总和知识上下文字符数
- 不保存用户完整输入和 AI 完整输出到 usage 表或普通日志

因此一次正常生成的模型调用次数是：**1 次**。

## Knowledge Source V0.1

知识源支持一个由服务器配置的 GitHub 仓库，以及管理员上传的 Markdown、TXT、DOCX 和 PDF。GitHub 仅只读同步配置目录，不会写回源仓库；上传原文件保存在仓库外的私有目录。单文件最多 10 MiB。文本直接读取，DOCX/PDF 使用轻量解析器；不执行 OCR，扫描 PDF 没有可提取文字时标记为不可解析。

每个 `KnowledgeDocument` 保存来源类型、名称和路径、标题、提取文本、内容 hash、GitHub blob/commit SHA、同步时间、上传者、解析状态和 active 标记。GitHub 用“仓库 + path”作为稳定身份：同 hash 跳过正文处理，变更时更新原记录，源文件消失时标记 removed。删除知识条目不会触及 tasks、members 或其他业务数据。

检索使用标题、路径和正文的关键词匹配与简单相关度排序，不访问外部模型。Planner 根据事项标题、负责人描述和粘贴的本次活动文字自动检索最多 6 份历史资料，历史片段不超过 3000 字符。页面只展示关联资料的标题和轻量来源，不展示完整正文。管理员可以通过标题、路径或来源名称搜索，再明确把结果添加为本次事项资料；默认不展示完整知识库列表。当前事项材料最多 5000 字符，知识上下文总计硬限制为 8000 字符。一次规划仍然只有一次模型调用。

### 事实与经验分层

Planner 的输入清楚划分为：

1. **负责人描述**：本次生成的自然语言需求。
2. **本次事项资料**：负责人本次粘贴的文字，以及明确选作本次资料的知识文档。
3. **团队历史经验**：本地检索出的 SOP、复盘、周报或类似活动经验。

负责人描述和本次事项资料中的明确事实共同构成当前事实。只有负责人本次粘贴的文字或明确搜索选择为本次资料的文档才会进入“本次事项资料”区。系统自动关联的文档始终只进入“团队历史经验”区，即使它们与标题或描述相关，也不能将其中旧活动的时间、地点、人数或负责人套用到当前活动。历史资料与本次事实冲突时采用本次事实；负责人描述与本次资料彼此矛盾时请负责人确认。当前仍缺少的关键信息才进入 questions。资料内容都是不可信参考文本，不是 system 指令；要求忽略规则、泄露数据或执行命令的段落不改变模型行为。当前活动资料不会自动写入长期知识库。

### 知识源安全边界

- `/api/knowledge/*` 和 `/knowledge` 仅 admin 可访问。
- GitHub 仓库、branch、允许目录、token 都通过服务器环境变量配置；token 不返回前端、不入普通字段、不写日志。
- 上传文件扩展名白名单、10 MiB 大小限制、路径名净化和仓库外私有存储；绝不执行文件。
- 忽略隐藏文件、`.git`、依赖目录、secrets、环境文件、数据库和构建产物。
- 解析错误只返回简短说明，不向普通前端暴露堆栈或服务器绝对路径。
- 知识索引不可用时，Planner 仍使用负责人描述和本次粘贴文字完成单次生成。

## 确认发布

确认发布不让 AI 直接操作数据库。

前端把人工编辑后的草案提交到 /api/tasks/batch。

后端复用现有 Task 创建校验，在同一个数据库事务中：

1. 创建根事项
2. flush 得到根事项 ID
3. 创建所有一级分工
4. 全部成功后 commit

任何一个分工创建失败都会 rollback，避免留下半套事项。

为避免 AI 或草案偷偷选择真实人员：

- 根事项由确认发布的 admin / manager 负责
- owner_claimable=true 的分工不指定负责人
- owner_claimable=false 的分工由确认发布者暂代负责人
- 发布后仍可使用正常任务编辑功能重新分配

## AI 与确定性规则的边界

AI 不负责成员权限、active 状态、真实负责人选择、认领冲突、数据库约束、已发布任务状态、自动排班或时间冲突。

这些继续由数据库、权限校验和确定性后端代码负责。

## 暂缓能力

当前明确不做：

- AI 自动选择负责人
- 自动排班
- 工作量评分
- 时间 / 地点冲突
- 独占 / 可兼任
- 前后依赖
- 成员能力画像
- 任务推荐
- embedding / 向量数据库
- AI 聊天机器人
- Planner 页面临时直传活动文件（管理员可先将文件明确上传到知识库，再选择作本次资料）
- 微信记录导入
- 多 Agent
- AI 自动修改已发布任务

等真实使用产生明确需求后再继续演化。
