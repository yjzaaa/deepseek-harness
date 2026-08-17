# DeepSeek Harness 架构设计 · 源码解读

> 基于 it-zhouyu《DeepSeek Harness 架构设计.pdf》（31 页 / 10 章）× 视频字幕 × 仓库实证 `deepseek-ai/deepseek-harness @ 47f9438`（2026-08）。
>
> 本文档按**依赖关系**组织：Cordis 基座 → 插件生态 → 协作模式 → 全景回顾。每个插件都有代码导航，文字和代码结合，HTML 图作为可视化辅助。

---

## 架构图集（交互式 HTML）

以下交互图由 archify 生成，带仓库代码证据、缩放、搜索与主题切换。点击后可用 Simple Browser 或外部浏览器查看。

| 图 | 内容 | 链接 |
|----|------|------|
| Cordis 内核 | 第 1 章：六概念运行时 | [cordis-kernel.html](../.diagrams/cordis-kernel.html) |
| 插件生态 | 第 2 章：一切皆插件，互相平行 | [plugin-ecosystem.html](../.diagrams/plugin-ecosystem.html) |
| 协作模式 | 第 3 章：接缝/日志/作用域/恢复 | [collaboration-patterns.html](../.diagrams/collaboration-patterns.html) |
| 全景回顾 | 第 4 章：四层结构与关键结论 | [panorama.html](../.diagrams/panorama.html) |
| 会话日志 | 2.2.4/3.2：模型可见即可重建 | [session-log.html](../.diagrams/session-log.html) |
| 能力接缝 | 3.1：三角色定义边界 | [capability-seam.html](../.diagrams/capability-seam.html) |
| 作用域遮蔽 | 3.3：两层查找 | [scope-shadowing.html](../.diagrams/scope-shadowing.html) |
| 崩溃恢复 | 3.4：两种场景 | [crash-recovery.html](../.diagrams/crash-recovery.html) |
| 主架构图 | 产品全景，可下钻 | [harness-architecture.html](../.diagrams/harness-architecture.html) |
| Turn/Step 时序 | agent-loop 执行周期 | [turn-step.html](../.diagrams/turn-step.html) |
| 工具三道关口 | pre / execute / post | [tool-pipeline.html](../.diagrams/tool-pipeline.html) |
| 插件生命周期 | fiber 挂载 / 卸载 | [plugin-lifecycle.html](../.diagrams/plugin-lifecycle.html) |
| 完整单文件图集 | 五视图导航页 | [harness-full.html](../.diagrams/harness-full.html) |

---

## 目录

- [第 1 章 · Cordis 基座（运行时内核）](#第-1-章--cordis-基座运行时内核)
- [第 2 章 · 插件生态（一切皆插件）](#第-2-章--插件生态一切皆插件)
- [第 3 章 · 插件怎么协作](#第-3-章--插件怎么协作)
- [第 4 章 · 全景回顾](#第-4-章--全景回顾)

---

## 第 1 章 · Cordis 基座（运行时内核）

> [⇢ Cordis 内核六概念图](../.diagrams/cordis-kernel.html)

Cordis 是底层插件运行时，只负责六类基础工作：**挂载 plugin、发布 service、跟踪 inject、管理生命周期（fiber）、分发事件、把配置加载成插件树（loader）**。它不理解模型消息、不定义工具参数、不做会话持久化——那些是 harness 的领域逻辑。一句话：**Cordis 负责运行时的组织能力，harness 负责插件管 agent 的领域能力**。

### 1.1 为什么需要插件化运行时

模型供应商变了、沙箱要换、某类会话要加审批——传统框架里这些都得改核心。dsh 的回答：**全部拆成插件，一个不留**。模型适配器、工具注册表、会话日志、执行循环本身都是插件，没有特权核心可打补丁。

组合机制两层：**bundle**（一组 Cordis 配置行 + 挂载代码）与 **profile**（若干 bundle 有序叠加 + 用户补丁）。`web` 与 `headless` 两个模板共享基础层 `dsh-base`。任何一行组合配置都可用 `--patch` 整行替换——用 `dsh --profile web --dump-config` 打印你机器上真实的插件树。

### 1.2 plugin —— 运行时挂载单元

package 是代码怎么打包分发，plugin 是代码运行时怎么被装进系统。三种形态：函数、带 `apply` 的对象、继承 Service 的类。配置列表只决定**装什么**，启动顺序不由配置先后决定。

> 三形态归一：resolve 出可执行回调
> [vendor/cordis/src/registry.ts:222](../vendor/cordis/src/registry.ts#L222)

```typescript
resolve(plugin: Plugin): Function | undefined {
  try {
    if (typeof plugin === 'function') return plugin
    if (isApplicable(plugin)) return plugin.apply  // { apply(ctx, config) } 对象
  } catch {}  // plugin.apply 的 getter 可能抛
}
```

### 1.3 context —— 协作的路口

插件挂载后拿到的第一个对象。四类事：访问 service、注册/分发 event、经 effect 登记待清理资源、挂载子 plugin。它**记录当前插件是谁、作用域是什么、贡献属于哪个生命周期**——这是它与普通全局对象的最大区别。

> Context 是 Proxy，构造时安装内建服务
> [vendor/cordis/src/context.ts:70](../vendor/cordis/src/context.ts#L70)

```typescript
constructor() {
  const self = new Proxy<this>(this, ReflectService.handler)
  this.fiber    = new Fiber(self, {}, Object.create(null), null, () => [])
  this.reflect  = new ReflectService(self)   // 服务注册表(谁提供/对谁可见)
  this.registry = new RegistryService(self)  // 插件登记
  this.events   = new EventsService(self)    // 事件分发
  return self   // 返回代理：属性读取走服务解析器
}
```

### 1.4 service —— 按稳定名称共享的能力

能力名称与实现彻底分开：`ctx.shell` 左边可以本地执行也可以远程沙箱，右边的 agent/host/UI 一律不改。Cordis 跟踪服务由谁提供、哪个作用域可见、何时出现消失——所以它不是简单的对象字典。

> 构造即注册，所属 fiber 卸载即消失
> [vendor/cordis/src/service.ts:42](../vendor/cordis/src/service.ts#L42)

```typescript
constructor(protected ctx: Context, name: string) {
  // ctx.reflect.provide(name, this, this[Service.check])
  // → 服务随 owning fiber 自动注销，不需要手写清理
}
```

### 1.5 inject —— 持续跟踪的依赖关系

不是“把对象传进来”就完事：服务未就绪时插件停在 **pending**，全部出现才 **active**；运行中必需服务消失了，Cordis **先卸载 consumer、清理它，服务恢复再重新激活**。这就是为什么插件不能依赖配置顺序。

> inject 写入 intercept 解析表，可空依赖走查询式
> [vendor/cordis/src/fiber.ts:238](../vendor/cordis/src/fiber.ts#L238)

```typescript
const injectEntries = Object.entries(this.inject)
if (injectEntries.length) {
  this.ctx[Context.intercept] = Object.create(parent[Context.intercept])
  for (const [name, config] of injectEntries) {
    if (isNullable(config)) continue          // 可选依赖：查不到拿空值
    this.ctx[Context.intercept][name] = config // 强依赖：不就位不激活
  }
}
```

### 1.6 fiber + effect —— 生命周期与可撤销的资源

> [⇢ 插件生命周期图](../.diagrams/plugin-lifecycle.html)

fiber 表示一个插件的运行状态（pending → active → unloading → disposed）。插件注册的每个服务、监听器、定时器都由 fiber 记录所有权；退出时沿 fiber 树**逆序调用全部 disposer**。最关键原则：**注册必须可反向撤销**——热更新、配置重载、依赖切换才不会留下重复监听器或僵尸进程。

> ctx.effect()：登记什么，就附带登记怎么撤销
> [vendor/cordis/src/fiber.ts:418](../vendor/cordis/src/fiber.ts#L418)

```typescript
effect(execute: () => Effect, label = 'anonymous'): any {
  this.assertActive()  // 已卸载的 fiber 拒绝新效果(INACTIVE_EFFECT)
  // ...
  const dispose = () => {
    if (disposing) return disposalTask       // 二次调用是 no-op
    for (const disposable of disposables.splice(0).reverse()) {
      // 逆序撤销：后登记的先清理
    }
  }
}
```

### 1.7 typed events / waterfall —— 插件参与决策的通道

五种分发：`emit` 通知 / `parallel` 并行 / `serial` 顺序带值 / `bail` 首个有效即退 / **waterfall** 包装调用链。waterfall 直接进入 agent 执行路径：审批插件检查确认、守卫插件检查参数权限、遥测插件记录耗时，最后才到真实执行。**策略记录的是实际执行路径，不是写在 prompt 里或 UI 表面限制**。

> 真实监听者：超时守卫（换 signal → 委托 → 恢复 → 改写超时结果）
> [packages/guard/timeout-policy/src/index.ts:55](../packages/guard/timeout-policy/src/index.ts#L55)

```typescript
export function apply(ctx: Context): void {
  ctx.on('tools/execute', async (exec, next): Promise<ToolExecutionResult> => {
    const timeoutMs = ctx.tools.get(exec.name, exec.agent)?.timeoutMs
    if (timeoutMs === undefined) return next()   // 无预算：原样委托
    using d = deadline(exec.signal, timeoutMs, TOOL_TIMEOUT)
    const upstream = exec.signal
    exec.signal = d.signal                        // 换上有期限的 signal
    try {
      const result = await next()                 // 委托下游直到真实执行
      if (timeoutOf(d.signal, TOOL_TIMEOUT) !== undefined) {
        return toolTimeoutResult(timeoutMs)       // 回程加工：改写为超时结果
      }
      return result
    } finally {
      exec.signal = upstream                      // 恢复调用方 signal
    }
  })
}
```

### 1.8 bundle / profile —— 决定装什么；loader 决定怎么跑

bundle 是一层可分发的 patch（有序配置修改）；profile 选择哪些 bundle 再叠加用户补丁与命令行 patch。web 与 headless 的差异**不写进 agent-loop 的条件分支**，只是选择了不同的插件树。

> web bundle patch：按 id 整行覆盖基础层配置
> [packages/bundle/web-app/cordis.patch.yml:16](../packages/bundle/web-app/cordis.patch.yml#L16)

```yaml
# A patch replaces the targeted row's whole `config`
- id: system-prompt
  config:
    persona: You are a coding agent powered by the {{model}} model ...
- id: hmr
  disabled: true
```

> **加新功能时的判断口诀**：新运行模块 → plugin；某项能力的新实现 → provider；把已有能力接到工具/API/UI → consumer；拦截真实执行路径 → typed event + waterfall；改变产品默认组合 → bundle / profile。

---

## 第 2 章 · 插件生态（一切皆插件）

> [⇢ 插件生态图](../.diagrams/plugin-ecosystem.html)

第 1 章讲了 Cordis 基座，这一章讲**装在基座上的插件**。关键原则：**所有插件互相平行，没有谁比谁更核心**。`agent-loop` 只是 `packages/core/agent-loop` 这个包，和 `system-prompt`、`tools`、`session`、CLI、Web、LLM、Shell 等插件平起平坐。

### 2.1 插件树：bundle → profile → patch

harness 启动时从一颗**空的插件树**开始叠加：

1. **最底层**：基础组合包 `dsh-base`（模型、会话、工具、权限、沙箱、持久化）
2. **第二层**：根据运行方式加载 `web` 或 `headless`
3. **最上层**：用户自己的配置补丁（`--patch`）

这套设计不只是让功能可以开关——**整个产品本身就是插件组合出来的**。想换模型就提供新的适配器；想把本地执行迁到远程沙箱，就替换对应的能力提供方；想让某类会话少用几个工具，就换一份 agent 预设配置。

> Profile 发现与 patch 层组合
> [packages/boot/app-boot/src/profile.ts:2](../packages/boot/app-boot/src/profile.ts#L2)

```typescript
// Profile 发现与 patch 层组合
// 最底层 dsh-base → 第二层 web/headless → 最上层用户 patch
```

### 2.2 核心插件（平行）

以下插件都属于 `packages/core/`，但它们**没有特权**，和其他插件一样经 Cordis 挂载。

#### 2.2.1 agent-loop —— Turn/Step 状态机

> [⇢ Turn/Step 时序图](../.diagrams/turn-step.html)

agent-loop 负责轮次和步骤的状态机。但它**本身薄得惊人**——策略全在外围事件上。它的主要职责是维护状态变化和事件边界，上下文压缩、权限检查、工具超时都尽量通过现有扩展点接入，不必不断给 loop 增加新分支。

> Agent 出生：收件箱、轮次号从日志推导、专属作用域
> [packages/core/agent-loop/src/agent.ts:84](../packages/core/agent-loop/src/agent.ts#L84)

```typescript
constructor(public readonly session: Session) {
  this.inbox = new Inbox(session, {
    inserted: (m) => this.dispatch.emit('agent/inbox/inserted', { message: m }),
    claimed:  (m, turn) => this.dispatch.emit('agent/inbox/claimed', { message: m, turn }),
  })
  // 轮次号不从内存读——从日志里最后一个 turn/start 推导（重启可续）
  const lastTurn = session.events.findLast(e => e.type === 'turn/start')?.data.turn ?? 0
  this.phase = { kind: 'idle', lastTurn }
  this.scope = createScope(loopCtx, this)            // 第 8 章：专属层
  this.ctx = this.scope.ctx.extend({ agent: this })
}
```

**Inbox 三种动作**：

| 动作 | 时机 | 行为 |
|------|------|------|
| **follow up** | 后续任务 | 把新工作放到下一轮，并唤醒 agent |
| **steer** | 当前工作过程中 | 补充指令，让 agent 在下一个步骤处理，同样会唤醒 agent |
| **inject** | 静默注入 | 给下一个步骤补充上下文，但不主动唤醒 agent；适合让工具或插件先留下信息，等下一项真实任务到来时再一起处理 |

**PRESTEP：每个步骤都重新组装**

每一轮开始，系统先写入 `turn/start` 事件，随后进入 **PRESTEP 阶段**：领取输入队列里的消息，**重新组装**系统提示词、运行时上下文和工具定义。

这里最关键的是：每个步骤都重新组装，**不是在 agent 创建时只做一次**。权限刚刚变化、工具刚刚卸载、预设配置刚刚换了人格、或者插件新加了一段工作区说明——下次请求都会拿到当前的真实状态。

PRESTEP 还可以**改写或者拒绝**这批输入。即使输入被拒绝、最终没有发出模型请求，这次尝试也会留下完整的一轮边界，不会从日志里凭空消失。

#### 2.2.2 system-prompt —— 提示词组装

> 有序片段/上下文/schema 注册表
> [packages/core/system-prompt/src/index.ts:2](../packages/core/system-prompt/src/index.ts#L2)

```typescript
// 有序片段/上下文/schema 注册表
// 组装结果的 expert waterfall
```

system-prompt 插件负责组装发给模型的系统提示词。它按 Agent 视角解析提示词分节和工具清单，支持 expert waterfall 让其他插件介入组装过程。

#### 2.2.3 tools —— 工具注册表

> [⇢ 工具三道关口图](../.diagrams/tool-pipeline.html)

> 工具注册表 + pre/execute/post 把关
> [packages/core/tools/src/index.ts:152](../packages/core/tools/src/index.ts#L152)

```typescript
// 第一站·准入：权限/审批，拒绝 = 不调 next()
'tools/pre-execute'(this: Scoped<ToolRuntime>, exec: ToolExecution,
                    next: () => Promise<PreToolDecision>): Promise<PreToolDecision>
// 第二站·执行：超时/重试/指标；registry 重接 caller signal，替换不能断开取消
'tools/execute'(this: Scoped<ToolRuntime>, exec: ToolDispatchExecution,
                next: () => Promise<ToolExecutionResult>): Promise<ToolExecutionResult>
// 第三站·出口：截断/限额/脱敏——限额施加在完整产出上，连包装一并计算
'tools/post-execute'(this: Scoped<ToolRuntime>, exec: ToolExecution,
                     result: ToolExecutionResult, next: …): …
```

tools 插件维护统一工具目录。插件加载后工具出现在目录里，插件卸载后工具消失。每次调用都经过固定管道：解析 → 准入（单向保护）→ 执行 → 出口（格式校验）。

**工具调用的固定管道**：

1. **解析**：系统根据当前 agent 的配置确定它能看见哪些工具，并解析调用参数。
2. **准入（pre-execute）**：权限插件可以允许、拒绝或者要求人工审批。随后还有一层**单向保护规则**——它只能进一步收紧权限，前面的策略不能绕过它。
3. **执行（execute）**：真正执行工具。
4. **出口（post-execute）**：插件可以在这里阻断结果、补充上下文或者调整模型最终看到的内容。

成功结果首先必须通过**输出格式校验**，成为结构明确的 JSON 数据。然后工具自己的渲染器会把同一份结果转换成模型需要的内容块，并生成网页需要的展示信息——**模型文字和网页卡片来自同一个标准结果**，不需要分别猜测工具输出的结构。

**并发与屏障**：

- **可以并发的工具**：进入一个限制并发数量的执行池；
- **必须独占的工具**：形成屏障，排队执行；
- **策略判断和最终写入日志的顺序**：仍然与模型给出的调用顺序一致。

如果任务被取消，已经启动的调用要先结束或停止，尚未启动的调用也会得到一条系统生成的结果——保证日志里不会留下只有调用没有结果的悬空记录。

#### 2.2.4 session —— 会话日志

> [⇢ 会话日志图](../.diagrams/session-log.html)

session 插件维护**只追加、不修改的事件日志**，其余一切都是它的投影。纪律：**模型可见即可重建**——到达模型请求的一切必须能从日志重建，运行时有断言持续检查，违背就报错。机制维护纪律，不靠文档。

> 事件表：类型集中声明，负载字段逐个写明
> [packages/core/session/src/types.ts:236](../packages/core/session/src/types.ts#L236)

```typescript
export interface SessionEventMap {
  'turn/start': { turn: number }            // 认领输入前开启；被拒也记录
  'turn/end':   { turn: number; reason: TurnEndReason }
  'step/start': { turn: number; step: number }  // 一次模型调用+其工具执行
  'step/end':   { turn: number; step: number }
  'user/message': UserMessage               // 人类输入/注入上下文/目标续跑
  'assistant/chunk': { turn: number; step: number; chunk: StreamChunk }  // 原始流分片，回放保真
  // 'assistant/message' / 'tool/call' / 'tool/result' …
}
```

> 模型历史从日志现算，内存不维护第二手状态
> [packages/core/session/src/index.ts:726](../packages/core/session/src/index.ts#L726)

```typescript
deriveMessages(): Message[] {
  // 增量投影：surface.replaceGeneration 变了就重算；新增事件逐条投影。
  // 返回的 Message 对象共享且 deep-frozen——消费方无法篡改日志。
  for (const seq of nodes.slice(this.derivedNodes)) {
    const msg = this.deriveEventMessage(this.log[seq]!)
    if (msg) this.derived.push(msg)
  }
}
```

**Surface：有效视图**

系统从日志里选出当前应该进入模型上下文的那部分事件，这个有效视图叫 **surface**。例如对话太长需要用摘要压缩，系统不会回头删除或修改旧消息，而是**追加一条替换记录**，用摘要取代有效视图里的一段旧内容。此后模型看到的是摘要，原始数据块和完整消息仍然保留在日志中——回放、审计和问题定位都不会丢失依据。

**崩溃恢复：两种场景**

假设模型要求执行一个工具，进程崩溃可能发生在两个时间点：

1. **工具启动前崩溃**：恢复后系统明确记下 `tool not started`（工具未启动）。模型知道这个操作没有发生，如有必要可以重新执行。
2. **工具启动后、结果写回前崩溃**：日志里已有 `tool/call`，说明工具开始了，却没有保存下来的执行结果。工具可能已经改完文件，甚至已经向外部系统发出请求。这时系统**不会假定它失败，也不会直接重跑**，而是补上一条 `tool outcome unknown`（结果未知）。恢复提示会要求模型先检查外部状态；只有只读操作、或者重复执行也不会产生额外影响的操作，才适合直接重试。

> 普通运行日志主要帮助人追查问题；这里的事件日志还会直接决定 agent 的下一步怎样行动才不会重复制造副作用。

### 2.3 入口插件（平行）

入口插件负责把外部输入送进统一收件箱。它们互相平行，都进同一个收件箱。

#### 2.3.1 CLI（apps/cli）

> CLI / headless 入口
> [apps/cli](../apps/cli)

CLI 插件提供命令行入口，支持 headless 模式（无界面自动化）。所有输入（界面/CLI/程序调用）进同一个收件箱排队。

#### 2.3.2 Web（apps/web）

> 浏览器应用
> [apps/web](../apps/web)

Web 插件提供浏览器应用入口，有界面交互。和 CLI 一样，所有输入进同一个收件箱。

#### 2.3.3 ACP（apps/acp）

> ACP 自动化入口
> [apps/acp](../apps/acp)

ACP（Agent Client Protocol）插件提供自动化入口，支持远程委托和程序调用。

### 2.4 能力插件（平行）

能力插件提供具体能力，通过**能力接缝**（见第 3 章）被上层工具使用。它们互相平行，Provider 可插拔。

#### 2.4.1 LLM（模型适配）

> 模型适配器 seam · 流式词汇表
> [packages/llm/llm/src/index.ts:64](../packages/llm/llm/src/index.ts#L64)

```typescript
// @mode waterfall —— 包裹每一次发往模型的流式请求
'llm/stream'(this: LlmRuntime, options: GenerateOptions,
             next: () => AsyncIterable<StreamChunk>): AsyncIterable<StreamChunk>
```

LLM 插件提供模型适配能力。Provider 可以是 DeepSeek、OpenAI、Claude 等，Consumer 是 agent-loop 等需要调用模型的插件。

**Provider 实现**：

- [packages/llm/llm-deepseek/src/index.ts](../packages/llm/llm-deepseek/src/index.ts) —— DeepSeek 适配器
- [packages/llm/llm-pi-ai/src/index.ts](../packages/llm/llm-pi-ai/src/index.ts) —— Pi AI 适配器

**Consumer 使用方**：

- [packages/core/agent-loop/src/agent.ts:84](../packages/core/agent-loop/src/agent.ts#L84) —— agent-loop 调用模型

#### 2.4.2 Shell（命令执行）

> shell 接缝的 Service Definition——注释里就写死了组合纪律
> [packages/shell/shell/src/index.ts:1](../packages/shell/shell/src/index.ts#L1)

```typescript
/** Service Definition for the `ctx.shell` capability seam …
 *  a host composes exactly one provider of `ctx.shell` (the win32 layer swaps
 *  the POSIX rows for the pwsh ones, and mounting both fails loud on a
 *  duplicate service registration) */
// 定义方拥有 settings 命名空间，因为它命名的是能力而非实现
export const SHELL_SETTINGS_NAMESPACE = settingsNamespace('shell')
```

Shell 插件提供命令执行能力。Provider 可以是 `bash-local`、`bash-sandbox`、`pwsh-local`、`pwsh-sandbox`，Consumer 是 Bash 工具、PTY 终端、LSP 等。

**Provider 实现**：

- [packages/shell/bash-local/src/index.ts](../packages/shell/bash-local/src/index.ts) —— 本地 bash 执行
- [packages/shell/bash-sandbox/src/index.ts](../packages/shell/bash-sandbox/src/index.ts) —— 沙箱 bash 执行
- [packages/shell/pwsh-local/src/index.ts](../packages/shell/pwsh-local/src/index.ts) —— 本地 pwsh 执行
- [packages/shell/pwsh-sandbox/src/index.ts](../packages/shell/pwsh-sandbox/src/index.ts) —— 沙箱 pwsh 执行

**Consumer 使用方**：

- [packages/shell/tool-bash/src/index.ts](../packages/shell/tool-bash/src/index.ts) —— Bash 工具
- [packages/shell/tool-pwsh/src/index.ts](../packages/shell/tool-pwsh/src/index.ts) —— Pwsh 工具

#### 2.4.3 FS（文件系统）

FS 插件提供文件系统能力。上层工具只依赖统一的文件服务，不直接调用本地 node 文件接口。

**Provider 实现**：

- [packages/fs/fs-local/src/index.ts](../packages/fs/fs-local/src/index.ts) —— 本地文件系统
- [packages/fs/fs-sandbox/src/index.ts](../packages/fs/fs-sandbox/src/index.ts) —— 沙箱文件系统

**Consumer 使用方**：

- [packages/fs/tool-fs/src/index.ts](../packages/fs/tool-fs/src/index.ts) —— 文件工具
- [packages/fs/tool-fs-search/src/index.ts](../packages/fs/tool-fs-search/src/index.ts) —— 文件搜索工具
- [packages/fs/tool-str-replace-editor/src/index.ts](../packages/fs/tool-str-replace-editor/src/index.ts) —— 字符串替换编辑器

#### 2.4.4 Subagent（子代理）

> 能力核对：启动前逐项验证，不支持当场报错，绝不悄悄降级
> [packages/subagent/subagent/src/types.ts:86](../packages/subagent/subagent/src/types.ts#L86)

```typescript
export interface SubagentCapabilities {           // Provider 自报能力
  readonly outputSchema: boolean
  readonly depthLimit: boolean                  // 委托深度上限，防无限套娃
  readonly toolFilter: boolean                  // 子代理工具集=父代理划定子集
  readonly persona: boolean
}
export interface SubagentStartRequest {
  readonly prompt: ContentBlock[]
  readonly parent: Agent                        // 谱系与深度由此推导
  readonly signal: AbortSignal                  // 启动前后统一的取消通道
  readonly outputSchema?: ObjectJsonSchema      // 不支持就拒绝，不降级
}
```

Subagent 插件提供任务委托能力。Provider 可以是进程内子代理、fork 副本、外部产品代理（ACP），Consumer 是 `tool-subagent` 工具。

**Provider 实现**：

- [packages/subagent/subagent-fork-in-process/src/index.ts](../packages/subagent/subagent-fork-in-process/src/index.ts) —— 进程内 fork 副本
- [packages/subagent/subagent-spawn-in-process/src/index.ts](../packages/subagent/subagent-spawn-in-process/src/index.ts) —— 进程内新建 agent
- [packages/subagent/subagent-acp/src/index.ts](../packages/subagent/subagent-acp/src/index.ts) —— ACP 外部产品代理

**Consumer 使用方**：

- [packages/subagent/tool-subagent/src/index.ts](../packages/subagent/tool-subagent/src/index.ts) —— 子代理工具
- [packages/subagent/tool-subagent-control/src/index.ts](../packages/subagent/tool-subagent-control/src/index.ts) —— 子代理控制工具

---

## 第 3 章 · 插件怎么协作

> [⇢ 协作模式图](../.diagrams/collaboration-patterns.html)

第 2 章讲了各种插件，这一章讲它们**怎么协作**。插件之间不直接 import 实例，而是通过以下模式协作。

### 3.1 能力接缝：三角色定义边界

> [⇢ 能力接缝图](../.diagrams/capability-seam.html)

每种能力 = 三角色齐备才算一条缝：**Service Definition**（接口，挂在 ctx 名下）+ **Service Provider**（可插拔实现）+ **Consumer**（通常是面向模型的工具）。只有一个角色的包不构成接缝。

> shell 接缝的 Service Definition——注释里就写死了组合纪律
> [packages/shell/shell/src/index.ts:1](../packages/shell/shell/src/index.ts#L1)

```typescript
/** Service Definition for the `ctx.shell` capability seam …
 *  a host composes exactly one provider of `ctx.shell` (the win32 layer swaps
 *  the POSIX rows for the pwsh ones, and mounting both fails loud on a
 *  duplicate service registration) */
// 定义方拥有 settings 命名空间，因为它命名的是能力而非实现
export const SHELL_SETTINGS_NAMESPACE = settingsNamespace('shell')
```

```text
Service Definition（ctx.shell 接口）
  ├─ Provider: bash-local        Consumer: Bash 工具
  ├─ Provider: bash-sandbox  →   Consumer: PTY 终端
  └─ Provider: pwsh-local        Consumer: LSP
换掉任一 Provider，右侧全部 Consumer 同时切换，零改动
```

> 图 6-1 定义居中、实现可插拔、使用者只认定义——换掉左侧 Provider，右侧全部 Consumer 同时切换，零改动

**Provider 实现**：

- [packages/shell/bash-local/src/index.ts](../packages/shell/bash-local/src/index.ts) —— 本地 bash 执行
- [packages/shell/bash-sandbox/src/index.ts](../packages/shell/bash-sandbox/src/index.ts) —— 沙箱 bash 执行
- [packages/shell/pwsh-local/src/index.ts](../packages/shell/pwsh-local/src/index.ts) —— 本地 pwsh 执行
- [packages/shell/pwsh-sandbox/src/index.ts](../packages/shell/pwsh-sandbox/src/index.ts) —— 沙箱 pwsh 执行

**Consumer 使用方**：

- [packages/shell/tool-bash/src/index.ts](../packages/shell/tool-bash/src/index.ts) —— Bash 工具
- [packages/shell/tool-pwsh/src/index.ts](../packages/shell/tool-pwsh/src/index.ts) —— Pwsh 工具

仓库实证（`packages/shell/`）：`shell`（定义）+ `bash-local` / `bash-sandbox` / `pwsh-local` / `pwsh-sandbox`（四个 Provider）+ `tool-bash` / `tool-pwsh`（Consumer）。fs 与 subprocess 共享执行世界——两者 Provider 一起指向远程沙箱，Bash/终端/LSP 整体搬进沙箱，无一需要单独适配。

> 试金石：Provider 列表跨越的世界差异越大（本地进程→远程沙箱；进程内→别家产品），接口含金量越高。文档站的接缝全景图由脚本从代码推导——**图就是代码的投影**，永不脱节。

### 3.2 会话日志：唯一事实来源

> [⇢ Turn/Step 时序图](../.diagrams/turn-step.html)

session 插件（第 2.2.4 节）维护的会话日志是所有插件的**唯一事实来源**。模型能看见的内容必须能够从会话日志里重新生成。

> 事件表：类型集中声明，负载字段逐个写明
> [packages/core/session/src/types.ts:236](../packages/core/session/src/types.ts#L236)

```typescript
export interface SessionEventMap {
  'turn/start': { turn: number }            // 认领输入前开启；被拒也记录
  'turn/end':   { turn: number; reason: TurnEndReason }
  'step/start': { turn: number; step: number }  // 一次模型调用+其工具执行
  'step/end':   { turn: number; step: number }
  'user/message': UserMessage               // 人类输入/注入上下文/目标续跑
  'assistant/chunk': { turn: number; step: number; chunk: StreamChunk }  // 原始流分片，回放保真
  // 'assistant/message' / 'tool/call' / 'tool/result' …
}
```

```text
会话日志（只追加）
  turn/start · user/message · assistant/message · tool/call · tool/result · turn/end
        ↓ 投影
  模型历史 deriveMessages() · 界面回放 · 会话分叉 fork · 持久化 JSONL/SQLite · 遥测统计
```

> 图 4-1 一份事实，无数视图——事件溯源在 Agent 运行时的完整落地

### 3.3 作用域与同名遮蔽

> [⇢ 作用域遮蔽图](../.diagrams/scope-shadowing.html)

同进程多个 Agent 共享全局注册表，又各自需要定制。机制只有两层 + 一条规则：**专属层（agent.ctx）优先查找，同名遮蔽全局层；遮蔽是视角性的，其他 Agent 看到的仍是原装**。

> 作用域原语：键是不透明对象身份（直接用 Agent 对象），只做身份比较
> [packages/core/scope/src/index.ts:137](../packages/core/scope/src/index.ts#L137)

```typescript
export function createScope(ctx: Context, key: ScopeKey, options?): Scope {
  const fiber = ctx.plugin(scope)
  const scoped: Context = fiber.ctx.extend({ [kScope]: key })
  return { ctx: scoped, rawDispose: fiber.dispose,
           dispose: () => (disposing ??= quiesceFiber(fiber)) }
}
// scopeTarget()：事件沿作用域链向上流动——外层组合能观察其下每个 Agent，
// 低于分发键的标记被排除：events flow up the chain, never down.
```

```text
global 全局注册          agent.ctx 专属作用域
工具 A · 工具 B · 服务 X   工具 A*（遮蔽） · 工具 C
◀ 就近查找               专属注册先被看见，同名全局注册被挡在后面
```

> 图 8-1 专属注册先被看见，同名全局注册被挡在后面，其余照常可用

一致性红利：系统提示分节、会话标题、命令面板——凡挂在注册表上的都遵守同一套两层查找。**preset**（预设）= 声明 Agent 由哪些插件构成的组合配置；标 `isolate` 则为该 Agent 单独立服务实例。克制点：只有两层，没有更深嵌套——机制给到刚好，多余自由度不给。

### 3.4 崩溃恢复与工程纪律

> [⇢ 崩溃恢复图](../.diagrams/crash-recovery.html)

**崩溃恢复**（见第 2.2.4 节）：

1. **工具启动前崩溃**：`tool not started`，可重试；
2. **工具启动后、结果写回前崩溃**：`tool outcome unknown`，不假定失败，先检查外部状态。

**沙箱与权限边界**：

发行配置**默认只允许写工作区**，超出范围就来问你。如果所有可用的限制方式都失败，系统会直接拒绝执行，不会悄悄改成不受限制的运行方式。

不过这套沙箱目前**只管文件**，它不等于网络隔离（任意网址抓取默认也没有打开）。能够编写运行时插件的 tool、以及用户自己创建的预设配置，都可以获得很高的系统能力，应该按照命令行 shell 的权限来对待。

**工程检查**：

项目已经设置了很重的工程检查：

- 核心运行时的每个源文件都要跑到 **100% 行覆盖**；
- 测试范围还包括真实模型协议快照、浏览器和跨平台沙箱。

但它仍然是**开发者预览版**，会话格式随时可能变。它适合用来研究和搭建本地 agent 的平台，还不能当成已经稳定的生产基础设施。

---

## 第 4 章 · 全景回顾

> [⇢ 全景回顾图](../.diagrams/panorama.html)

### 4.1 四层结构

```text
入口层：Web 应用 · 终端 CLI · ACP 自动化 · JSON-RPC（都进同一收件箱）
驱动层：agent-loop（Turn/Step 循环，本身薄得惊人——策略全在外围事件上）
能力层（全部插件）：LLM 适配 · 工具 · 文件系统 · Shell · 子代理 · 技能 · 工作流 · 压缩
日志层：会话日志（一切模型可见内容的来源） → 持久化 JSONL/SQLite
侧面贯穿：权限 · 沙箱 · 审批 · 超时（三道关口值守）
```

> 图 10-1 四层结构；没有一个方块是特殊的，包括画在中间的 agent-loop

### 4.2 只能带走三件事

1. **把事实和推导分开**：只追加事件日志承载全部事实，其余皆投影；把纪律做成运行时断言——文档约束会松，机制约束不会。
2. **用三角色定义能力边界**：接口/实现/使用方各归其位；接缝三角色齐备才算数。
3. **让扩展发生在事件上而非核心里**：if 配置越积越多的地方，多半缺一条 waterfall 链。

另两条小模式：注册即效果（登记与撤销成对记账）；作用域两层加遮蔽（最小机制满足按身份定制）。

### 4.3 为什么几十行 Agent 会长成运行时

一个几十行就能运行的 agent loop，为什么最后会长成一整套运行时？因为调用模型并不难，难的是让每件事都有明确归属：

- 能力由谁提供？
- 插件从什么时候开始生效？
- 副作用到底有没有发生？
- 模型实际看见过什么？
- 系统崩溃以后还能相信哪些事实？

DeepSeek Harness 的回答可以落在两点上：**插件树决定这个 agent 是谁、拥有什么；事件日志决定它经历过什么、接下来还能安全地做什么**。理解这两项设计以后，网页、SDK、子 agent、工作流和各种工具就不再是散落的功能——它们都是同一套运行时原则在不同位置上的具体实现。

### 4.4 动手路径

1. 跑一次 headless 感受最小组合
2. `--dump-config` 打印插件树，把图 10-1 和你机器上真实的树对号
3. 挑一条缝读三个包（推荐 shell，最小最完整）
4. 写一个监听 `agent/request` 的插件，给每次请求打一行日志，体会注册即效果的回退

---

## 来源

- 书：it-zhouyu/book《DeepSeek Harness架构设计.pdf》（2026-08）
- 视频：it-zhouyu《DeepSeek Harness 源码解读》字幕（2026-08）
- 代码：`deepseek-ai/deepseek-harness @ 47f9438`（本地 `D:\AI-Projects\deepseek-harness`）
- 交互架构图：[harness-architecture.html](../.diagrams/harness-architecture.html)（archify 交付，showcase 校验通过）
