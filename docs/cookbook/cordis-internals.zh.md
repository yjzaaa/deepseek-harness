# Cordis 底层运作机制详解

[English](cordis-internals.md) | 中文

> 本文档是 [通过代码调用关系阅读插件运行机制](reading-plugin-source.md) 的续篇，深入讲解 Cordis 的运行时内核。
>
> 基于 `vendor/cordis/src/` 源码，聚焦 Context Proxy、Fiber 状态机、服务解析、inject 依赖跟踪和 effect 生命周期五个核心机制。
>
> 配套动画图集（位于仓库外层目录，不在本仓库内）：`../diagrams/cordis-core/cordis-core-animated.html`（相对仓库根向上一级），单文件、可离线直接用浏览器打开，含双主题与分步播放动画。

---

## 1. Context 是 Proxy —— 一切属性访问都走解析器

**文件：** `vendor/cordis/src/context.ts`

```typescript
export class Context {
  constructor() {
    // ...
    const self = new Proxy<this>(this, ReflectService.handler)
    // ...
    return self  // ← 返回的是 Proxy，不是原始对象
  }
}
```

**关键洞察：** 你拿到的 `ctx` 是一个 Proxy。当你写 `ctx.shell` 时，不是直接读属性，而是触发 `ReflectService.handler.get`。

这意味着：
- `ctx.shell` 可能指向不同的实现（取决于当前挂载了哪个 Provider）
- `ctx.on` 实际上转发到 `ctx.events.on`
- 未声明的属性访问会报错，而不是返回 `undefined`

---

## 2. 服务解析 —— `ctx.shell` 是怎么找到的

**文件：** `vendor/cordis/src/reflect.ts`

### 2.1 Proxy get trap

```typescript
static handler: ProxyHandler<Context> = {
  get: (target, prop, ctx: Context) => {
    // 1. 特殊属性直接返回（symbol、保留字、下划线开头）
    if (isSpecialProperty(prop)) {
      return Reflect.get(target, prop, ctx)
    }

    // 2. context 自身有该属性，直接返回
    if (Reflect.has(target, prop)) {
      return getTraceable(ctx, Reflect.get(target, prop, ctx))
    }

    // 3. 是 accessor？调用自定义 get
    const def = target.reflect.props[prop]
    if (def?.type === 'accessor') {
      return def.get.call(ctx, ctx[symbols.receiver], error)
    }

    // 4. 核心：通过 waterfall 事件解析服务
    return ctx.events.waterfall('internal/get', ctx, prop, error, () => {
      // 4.1 从当前 fiber 开始查找
      let fiber = (ctx[symbols.shadow] as Context ?? ctx).fiber
      while (true) {
        const impl = fiber.store?.[prop]
        if (impl) return getTraceable(ctx, impl.value)

        // 4.2 是强依赖但找不到？报错
        if (prop in fiber.inject) {
          throw error
        }

        // 4.3 没有 runtime？报错（未声明的属性）
        if (!fiber.runtime) throw error

        // 4.4 隔离范围变了？停止向上查找
        if (fiber.parent[symbols.isolate][prop] !== key) throw error

        // 4.5 继续向 parent fiber 查找
        fiber = fiber.parent.fiber
      }
    })
  }
}
```

### 2.2 查找路径图解

```text
ctx.shell
    ↓ Proxy get trap
    └── waterfall 'internal/get'
            ↓
        从当前 fiber 开始
            ├── 当前 fiber.store['shell'] ?
            │       ├── 有 → 返回实现值
            │       └── 无 → 继续
            ├── 是 inject 的强依赖 ?
            │       └── 是 → 报错（服务未就绪）
            ├── 有 runtime ?
            │       └── 无 → 报错（未声明的属性）
            ├── 隔离范围变了 ?
            │       └── 是 → 停止查找（跨隔离边界）
            └── 向 parent fiber 继续查找
                    ↓
                直到 root fiber
```

**学到了什么：**
- 服务查找是**沿 fiber 树向上**的，不是全局搜索
- `inject` 声明的强依赖如果没找到会报错，而不是返回 `undefined`
- `isolate` 机制控制查找边界，防止跨作用域泄漏

---

## 3. Fiber 状态机 —— 插件的生命周期

**文件：** `vendor/cordis/src/fiber.ts`

### 3.1 四个状态

```typescript
export enum FiberState {
  PENDING = 'pending',       // 依赖未就绪，等待中
  LOADING = 'loading',       // 正在执行 apply()
  ACTIVE = 'active',         // 运行中，所有服务可用
  UNLOADING = 'unloading',   // 正在卸载，调用 disposers
  // DISPOSED / FAILED 是隐式状态（uid === null 或有 _error）
}
```

### 3.2 状态转换图

```text
创建 Fiber
    ↓
PENDING（依赖检查中）
    ↓ 所有 inject 依赖就绪
LOADING（执行 apply()）
    ↓ apply() 成功
ACTIVE（运行中）
    ↓ 依赖变化 / 配置更新 / 手动停止
UNLOADING（逆序调用 disposers）
    ↓ 卸载完成
PENDING（等待重新激活）
    ↓ 依赖再次就绪
LOADING → ACTIVE
```

### 3.3 关键代码：_refresh() 检查依赖

```typescript
_refresh() {
  let epoch: string | boolean = false
  epoch = ''
  for (const name of Object.keys(this.inject)) {
    const impl = this._store[name]
    if (!impl) {
      epoch = INACTIVE    // ← 有依赖缺失，停在 PENDING
      break
    }
    epoch += ':' + impl.fiber.uid  // ← 依赖就绪，记录 provider 的 uid
  }
  this._setEpoch(epoch)
}
```

**epoch 的作用：** 是一个"指纹字符串"，由所有依赖的 fiber uid 拼接而成。如果任何一个依赖的 provider 变了（uid 变了），epoch 就变了，触发重新加载。

### 3.4 关键代码：_setEpoch() 驱动状态转换

```typescript
private _setEpoch(epoch: string) {
  const oldEpoch = this._runner.epoch
  if (epoch === oldEpoch) return  // ← 没变，什么都不做

  this._runner.epoch = epoch
  if (this.inertia) return  // ← 正在加载/卸载中，排队

  this._updateState(() => {
    if (epoch !== INACTIVE && oldEpoch === INACTIVE) {
      // 从 PENDING → ACTIVE：开始加载
      this.inertia = this._reload()
      return FiberState.LOADING
    } else {
      // 从 ACTIVE → PENDING：开始卸载
      this.inertia = this._unload()
      return FiberState.UNLOADING
    }
  })
}
```

### 3.5 关键代码：_reload() 激活插件

```typescript
private async _reload() {
  this.store = { ...this._store }  // ← 复制依赖快照

  try {
    // 1. 解析配置（schema 验证）
    this.config = this._resolveConfig(this._config)

    // 2. 执行插件的 apply()
    await this._execute(this._runner)

    this._error = undefined
  } catch (reason) {
    this.ctx.logger.error(reason)
    this._error = reason  // ← 记录错误，进入 FAILED 状态
    this._runner.epoch = INACTIVE
  }

  // 3. 状态更新
  this._updateState(() => {
    if (this._runner.epoch === oldEpoch) {
      this.inertia = undefined  // ← 加载完成，进入 ACTIVE
    } else {
      this.inertia = this._unload()  // ← epoch 变了，重新卸载
      return FiberState.UNLOADING
    }
  })
}
```

### 3.6 关键代码：_unload() 卸载插件

```typescript
private async _unload() {
  // 1. 逆序调用所有 disposers（后注册的先清理）
  await Promise.all(this._disposables.clear().map(async (dispose) => {
    try {
      await runDisposable(dispose)
    } catch (reason) {
      this.ctx.logger.error(reason)
    }
  }))

  this.store = undefined  // ← 清空服务引用

  // 2. 检查是否需要重新加载
  this._updateState(() => {
    if (this._runner.epoch === INACTIVE) {
      this.inertia = undefined  // ← 停在 PENDING
    } else {
      this.inertia = this._reload()  // ← 自动重新加载
      return FiberState.LOADING
    }
  })
}
```

**学到了什么：**
- Fiber 是插件的运行时实例，管理状态和生命周期
- `epoch` 是依赖指纹，变化触发重新加载
- 卸载时**逆序**调用 disposers，保证后注册的先清理
- 卸载后如果 epoch 不是 INACTIVE，**自动重新加载**（热更新）

---

## 4. inject 依赖跟踪 —— 服务未就绪时插件等待

**文件：** `vendor/cordis/src/registry.ts` 和 `vendor/cordis/src/fiber.ts`

### 4.1 声明依赖

```typescript
// Consumer 声明：我需要 shell 和 tools
export const inject = ['shell', 'tools']

// 或带配置的对象形式
export const inject = {
  shell: { timeoutMs: 30000 },  // 拦截配置
  tools: null,                   // 无拦截配置
}
```

### 4.2 Fiber 构造时解析 inject

```typescript
// fiber.ts 构造函数
const injectEntries = Object.entries(this.inject)
if (injectEntries.length) {
  this.ctx[Context.intercept] = Object.create(parent[Context.intercept])
  for (const [name, config] of injectEntries) {
    if (isNullable(config)) continue  // ← 可选依赖：不拦截
    this.ctx[Context.intercept][name] = config  // ← 强依赖：记录拦截配置
  }
}
```

### 4.3 依赖变化时通知

```typescript
// reflect.ts notify()
notify(names: string[]) {
  for (const runtime of this.ctx.registry.values()) {
    for (const fiber of runtime.fibers) {
      let hasUpdate = false
      for (const name of names) {
        if (!(name in fiber.inject)) continue  // ← 不依赖该服务，跳过
        fiber._checkImpl(name)  // ← 检查实现是否可用
        hasUpdate = true
      }
      if (hasUpdate) {
        fiber._refresh()  // ← 刷新 epoch，可能触发加载/卸载
      }
    }
  }
}
```

**学到了什么：**
- `inject` 告诉 Cordis："我需要这些服务，等它们就绪再激活我"
- 服务注册（provide）时自动通知所有依赖它的 fiber
- 可选依赖用 `ctx.get('name')` 查询，不会阻塞加载
- 强依赖缺失时 fiber 停在 PENDING，就绪后自动进入 ACTIVE

---

## 5. effect —— 注册即效果，卸载即清理

**文件：** `vendor/cordis/src/fiber.ts`

### 5.1 ctx.effect() 核心逻辑

```typescript
effect(execute: () => Effect, label = 'anonymous') {
  this.assertActive()  // ← 已卸载的 fiber 拒绝新 effect

  const disposables: Disposable[] = []
  let disposing = false

  const dispose = () => {
    if (disposing) return
    disposing = true
    // 逆序调用所有 disposers
    for (const disposable of disposables.splice(0).reverse()) {
      runDisposable(disposable)
    }
  }

  const runner: EffectRunner = {
    execute,
    epoch: true,
    collect: (dispose) => {
      disposables.push(dispose)  // ← 收集 disposer
    },
  }

  // 立即执行 effect body
  this._execute(runner)

  return dispose  // ← 返回 disposer，可手动调用或等卸载时自动调用
}
```

### 5.2 effect 的多种返回形式

```typescript
// 形式 1：返回函数（最常见）
ctx.effect(() => {
  const listener = () => { /* ... */ }
  window.addEventListener('click', listener)
  return () => window.removeEventListener('click', listener)  // ← disposer
})

// 形式 2：返回 Promise<函数>
ctx.effect(async () => {
  const conn = await createConnection()
  return () => conn.close()
})

// 形式 3：生成器（逐个注册）
ctx.effect(function* () {
  yield () => cleanupA()
  yield () => cleanupB()
})
```

### 5.3 _execute() 处理不同返回类型

```typescript
private _execute<T>(runner: EffectRunner<T>) {
  const effect: Effect = runner.execute.call(this)

  if (typeof effect === 'function') {
    // 返回函数 → 直接作为 disposer
    return runner.collect(effect)
  } else if ('then' in effect) {
    // 返回 Promise → 等 resolve 后再收集
    return effect.then(safeCollect)
  } else if (Symbol.iterator in effect) {
    // 返回 Iterable → 逐个收集
    const iter = effect[Symbol.iterator]()
    while (true) {
      const result = iter.next()
      safeCollect(result.value)
      if (result.done) return
    }
  }
  // ...
}
```

**学到了什么：**
- `ctx.effect()` 是 Cordis 的核心生命周期原语
- 注册和清理**成对记账**，卸载时自动逆序清理
- 支持同步/异步/生成器多种返回形式
- 已卸载的 fiber 拒绝新 effect，防止清理时注册新资源

---

## 6. ctx.provide() —— 服务注册与通知

**文件：** `vendor/cordis/src/reflect.ts`

```typescript
provide(name: string, value?: any, check?: () => boolean) {
  return this.ctx.fiber.effect(() => {
    // 1. 声明属性类型
    this.props[name] = { type: 'service' }

    // 2. 获取隔离 key（每个服务名一个 symbol）
    this.ctx.root[symbols.isolate][name] ??= Symbol(name)
    const key = this.ctx[symbols.isolate][name]

    // 3. 创建实现记录
    const impl: Impl = { name, value, fiber: this.ctx.fiber, check }

    // 4. 注册到 store
    this.store[key] = impl
    this.ctx.fiber.store![name] = impl

    // 5. 如果 fiber 已激活，通知所有依赖方
    if (this.ctx.fiber.state === FiberState.ACTIVE) {
      this.notify([name])
    }

    // 6. 返回 disposer（注销服务）
    return async () => {
      delete this.store[key]
      const fibers = this.notify([name])  // ← 通知依赖方：服务没了
      await Promise.allSettled(fibers.map(fiber => fiber.await()))
      delete this.ctx.fiber.store![name]
    }
  })
}
```

**学到了什么：**
- `provide()` 内部也是 `effect()`，所以服务注册自动参与生命周期
- 服务注册时通知所有依赖它的 fiber，触发它们的 `_refresh()`
- 服务注销时也通知依赖方，让它们进入 UNLOADING → PENDING
- `check` 函数可以动态控制服务是否对依赖方可见

---

## 7. 完整调用链回顾

以 `tool-bash` 调用 `ctx.shell.run()` 为例：

```text
1. Consumer 代码：
   const result = await ctx.shell.run(...)
                      ↓ Proxy get

2. ReflectService.handler.get('shell'):
   └── waterfall 'internal/get'
       └── 沿 fiber 树查找 'shell' 实现
           └── 找到 bash-local 提供的 ShellExecutor
               ↓ 返回 LocalBashExecutor 实例

3. Consumer 调用 .run():
   LocalBashExecutor.run(spec)
   └── this.runArgv(spec, ['bash', '-c', ...])
       └── this.ctx.subprocess.spawn(...)
           ↓ 又是 Proxy get → 查找 subprocess 服务

4. 返回结果层层上抛
```

---

## 8. 调试技巧

### 8.1 查看 fiber 状态

```typescript
// 在插件中打印当前 fiber 信息
console.log(ctx.fiber.name)      // 插件名
console.log(ctx.fiber.state)     // pending / loading / active / unloading
console.log(ctx.fiber.uid)       // 唯一标识
```

### 8.2 查看已注册服务

```typescript
// 查看当前 context 中所有可用服务
for (const key of Reflect.ownKeys(ctx.reflect.store)) {
  const impl = ctx.reflect.store[key as symbol]
  console.log(impl.name, 'provided by', impl.fiber.name)
}
```

### 8.3 追踪 effect

```typescript
// 查看 fiber 上注册的所有 effect
const effects = ctx.fiber.getEffects()
for (const effect of effects) {
  console.log(effect.label, effect.children.length, 'children')
}
```

---

## 来源参考

- `vendor/cordis/src/context.ts` — Context 类和 Proxy 构造
- `vendor/cordis/src/reflect.ts` — ReflectService（服务解析、provide、get）
- `vendor/cordis/src/fiber.ts` — Fiber 状态机和生命周期
- `vendor/cordis/src/registry.ts` — 插件注册表和 inject 解析
- `docs/architecture-map.md` §1 — Cordis 基座（运行时内核）
