# 通过代码调用关系阅读插件运行机制

[English](reading-plugin-source.md) | 中文

> 逐步指南：通过追踪 Definition → Provider → Consumer 的代码关系来理解 DeepSeek Harness 插件。
>
> 以 `shell` 能力接缝为例——代码库中最小且最完整的示例。

---

## 概述

DeepSeek Harness 中的每个能力都组织为**能力接缝**（capability seam），包含三个角色：

| 角色 | 职责 | 示例（shell） |
|------|------|-------------|
| **Service Definition** | 声明接口并注册到 `ctx` 上 | `packages/shell/shell` |
| **Service Provider** | 实现接口 | `packages/shell/bash-local` |
| **Consumer** | 通过 `ctx` 调用能力 | `packages/shell/tool-bash` |

核心要点：**Consumer 从不直接 import Provider**。它们调用 `ctx.<capability>`，Cordis 将调用路由到当前挂载的 Provider。

---

## 第一步：定位三角色

在 `packages/<能力名>/` 下找到三个包：

```text
packages/shell/
├── shell/              ← Definition (the capability itself)
│   └── src/index.ts    → Abstract class ShellExecutor, declares ctx.shell
├── bash-local/         ← Provider (one implementation)
│   └── src/index.ts    → LocalBashExecutor extends ShellExecutor
├── tool-bash/          ← Consumer (model-facing tool)
│   └── src/index.ts    → Registers the `bash` tool, calls ctx.shell
```

**命名启发式规则：**
- 单独的能力名（`shell`、`fs`、`subagent`）→ Definition
- 带实现方式后缀（`bash-local`、`pwsh-sandbox`）→ Provider
- 带 `tool-` 前缀（`tool-bash`、`tool-fs`）→ Consumer

---

## 第二步：读 Definition —— 理解契约

**文件：** `packages/shell/shell/src/index.ts`

### 要关注的关键模式

**1. Context 扩展** —— 能力如何暴露：

```typescript
declare module '@deepseek-ai/cordis' {
  interface Context {
    shell: ShellExecutor    // ← every plugin can access ctx.shell
  }
}
```

**2. 抽象类** —— 接口契约：

```typescript
export abstract class ShellExecutor extends Service {
  constructor(ctx: Context) {
    super(ctx, 'shell')     // ← registers as 'shell' service
  }

  // Subclasses must implement these
  abstract run(spec: ShellExecSpec): Promise<ShellRunResult>
  abstract start(spec: ShellExecSpec): ShellProcess
}
```

**学到什么：**
- `ctx.shell` 是稳定名称；任何在 `'shell'` 下挂载的 Provider 都可被调用
- `extends Service` 表示这是 Cordis 托管的服务，卸载时自动注销
- 抽象方法 `run()` / `start()` 是 Consumer 实际调用的入口

---

## 第三步：读 Consumer —— 找到调用起点

**文件：** `packages/shell/tool-bash/src/index.ts`

### 要关注的关键模式

**1. 依赖声明** —— 这个插件需要什么：

```typescript
export const inject = ['tools', 'shell', 'systemPrompt', 'shellEnv']
//        ↑ tells Cordis: don't activate me until these services are available
```

**2. 工具注册** —— 模型如何看到这个能力：

```typescript
ctx.tools.register(defineTool({
  name: 'bash',
  // ... schema, description, renderers
  async execute(args, exec) {
    // The actual call chain starts here
    const result = await ctx.shell.run(ctx.shell.resolve({
      command: args.command,
      signal: exec.signal,
    }))
  }
}))
```

### 调用链图解

```text
Model calls bash tool
    ↓
Consumer: tool-bash.execute()
    ├── ctx.shell.resolve(request)  → normalize user args to spec
    ↓
    └── ctx.shell.run(spec)         → delegated to Provider
            ↓
        Provider: bash-local.runArgv()
            ↓
            this.ctx.subprocess.spawn()  → actual OS process
```

**学到什么：**
- Consumer 声明 `inject: ['shell']` —— Cordis 确保 shell 可用后才激活此插件
- Consumer 不直接创建进程，而是委托给 `ctx.shell.run()` —— 这就是"接缝"的含义
- 同一个 Consumer 可对接不同 Provider（本地 bash / 沙箱 bash / pwsh），零改动

---

## 第四步：读 Provider —— 理解实现

**文件：** `packages/shell/bash-local/src/index.ts`

### 要关注的关键模式

**1. 继承与注册：**

```typescript
export class LocalBashExecutor extends ShellExecutor {
  static inject = ['subprocess']    // ← depends on lower-level capability

  constructor(ctx: Context, config: Config) {
    super(ctx)                      // ← registers as ctx.shell
  }
}
```

**2. 方法实现：**

```typescript
async run(spec: ShellExecSpec): Promise<ShellRunResult> {
  return this.runArgv(spec, ['bash', '-c', spec.command])
}

protected async runArgv(spec, argv): Promise<ShellRunResult> {
  // 1. Set up timeout + cancellation
  using d = deadline(spec.signal, spec.timeoutMs, 'BASH_TIMEOUT')

  // 2. Delegate to lower-level capability
  const handle = this.ctx.subprocess.spawn(
    this.spawnSpec(spec, argv, spec.stdoutMaxBytes, d.signal)
  )

  // 3. Wait and collect output
  const outcome = await handle.done
  return { ...outcome, stdout: ..., stderr: ... }
}
```

**学到什么：**
- Provider 也声明依赖（`inject: ['subprocess']`）—— 能力层层叠加
- `extends ShellExecutor` + `super(ctx, 'shell')` → 成为 `ctx.shell` 的实现
- 实际执行委托给 `ctx.subprocess.spawn()` —— 这是另一层接缝！

---

## 第五步：追踪跨接缝调用

shell 能力本身还依赖 **subprocess** 能力：

```text
tool-bash (Consumer of shell)
    ↓ ctx.shell.run()
bash-local (Provider of shell, Consumer of subprocess)
    ↓ ctx.subprocess.spawn()
subprocess-local (Provider of subprocess)
    ↓ actual OS process creation
```

这就是文档所说的"能力层叠"——每个 Provider 同时也可以是下层能力的 Consumer。

---

## 通用阅读方法

| 步骤 | 做什么 | 看哪里 |
|------|--------|--------|
| 1 | 找三角色 | `packages/<能力名>/` 目录 |
| 2 | 读 Definition | `declare module` + 抽象类/接口 |
| 3 | 读 Consumer | `inject` 声明 + `ctx.xxx.run()` 调用 |
| 4 | 读 Provider | `extends` 实现 + 向下层委托 |
| 5 | 追事件拦截 | `ctx.on('tools/execute', ...)` 等 waterfall 监听器 |

### 快速定位调用链的命令

```bash
# Find all Definitions
grep -r "declare module.*cordis" packages/ --include="*.ts"

# Find all Consumers of a capability
grep -r "ctx\.shell\." packages/ --include="*.ts"

# Find all Providers of a capability
grep -r "extends ShellExecutor" packages/ --include="*.ts"
```

---

## 练习路径

按此顺序阅读，建立直觉：

1. **shell**（本指南）→ 理解三角色模式
2. **fs** → 与 shell 对比，看相同模式：`packages/fs/fs` + `fs-local` + `tool-fs`
3. **subagent** → 看异步委托：`packages/subagent/subagent` + `subagent-fork-in-process` + `tool-subagent`

每个都追踪：Definition 接口 → Consumer 调用点 → Provider 实现 → 下层委托。

---

## 关键架构原则

来自 `docs/architecture-map.md` §3.1：

> **能力接缝只有三角色齐备才算完整。** 只有 Definition 的包是不完整契约；只有 Provider 的包是孤儿实现；只有 Consumer 的包是有调用无被调。

> **好接缝的试金石：** Provider 的世界差异能有多大？本地进程 → 远程沙箱；进程内 → 外部产品。差距越大，接口价值越高。

> **替换任一 Provider，所有 Consumer 零改动切换。** 这就是"接缝"——一条干净的线，实现可以在此交换而无需触碰调用方。

---

## 来源参考

- `docs/architecture-map.md` §3.1 — 能力接缝：三角色定义边界
- `packages/shell/shell/src/index.ts` — Service Definition
- `packages/shell/bash-local/src/index.ts` — Provider 实现
- `packages/shell/tool-bash/src/index.ts` — Consumer 工具
