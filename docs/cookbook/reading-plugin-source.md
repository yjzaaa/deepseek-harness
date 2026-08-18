# How to Read Plugin Mechanisms Through Code Call Chains

English | [中文](reading-plugin-source.zh.md)

> A step-by-step guide to understanding DeepSeek Harness plugins by tracing Definition → Provider → Consumer relationships through the source code.
>
> Based on the `shell` capability seam — the smallest and most complete example in the codebase.

---

## Overview

Every capability in DeepSeek Harness is organized as a **capability seam** comprising three roles:

| Role | Responsibility | Example (shell) |
|------|---------------|-----------------|
| **Service Definition** | Declares the interface and registers it on `ctx` | `packages/shell/shell` |
| **Service Provider** | Implements the interface | `packages/shell/bash-local` |
| **Consumer** | Calls the capability through `ctx` | `packages/shell/tool-bash` |

The key insight: **Consumers never import Providers directly**. They call `ctx.<capability>`, and Cordis routes the call to whichever Provider is currently mounted.

---

## Step 1: Locate the Three Roles

Find the three packages for a given capability under `packages/<capability>/`:

```text
packages/shell/
├── shell/              ← Definition (the capability itself)
│   └── src/index.ts    → Abstract class ShellExecutor, declares ctx.shell
├── bash-local/         ← Provider (one implementation)
│   └── src/index.ts    → LocalBashExecutor extends ShellExecutor
├── tool-bash/          ← Consumer (model-facing tool)
│   └── src/index.ts    → Registers the `bash` tool, calls ctx.shell
```

**Naming heuristic:**
- Capability name alone (`shell`, `fs`, `subagent`) → Definition
- Suffix with implementation (`bash-local`, `pwsh-sandbox`) → Provider
- Prefix with `tool-` (`tool-bash`, `tool-fs`) → Consumer

---

## Step 2: Read the Definition — Understand the Contract

**File:** `packages/shell/shell/src/index.ts`

### Key patterns to look for

**1. Context extension** — how the capability is exposed:

```typescript
declare module '@deepseek-ai/cordis' {
  interface Context {
    shell: ShellExecutor    // ← every plugin can access ctx.shell
  }
}
```

**2. Abstract class** — the interface contract:

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

**What you learn:**
- `ctx.shell` is a stable name; any Provider mounting under `'shell'` becomes callable
- `extends Service` means Cordis manages lifecycle (auto-unregister on unload)
- Abstract methods (`run`, `start`) are the entry points Consumers actually use

---

## Step 3: Read the Consumer — Find the Call Origin

**File:** `packages/shell/tool-bash/src/index.ts`

### Key patterns to look for

**1. Dependency declaration** — what this plugin needs:

```typescript
export const inject = ['tools', 'shell', 'systemPrompt', 'shellEnv']
//        ↑ tells Cordis: don't activate me until these services are available
```

**2. Tool registration** — how the model sees this capability:

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

### Call chain diagram

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

**What you learn:**
- Consumer declares `inject: ['shell']` — Cordis ensures shell is available before activating this plugin
- Consumer never creates processes directly; it delegates to `ctx.shell.run()`
- The same Consumer works with any Provider (local bash, sandbox bash, pwsh) without code changes

---

## Step 4: Read the Provider — Understand the Implementation

**File:** `packages/shell/bash-local/src/index.ts`

### Key patterns to look for

**1. Inheritance and registration**:

```typescript
export class LocalBashExecutor extends ShellExecutor {
  static inject = ['subprocess']    // ← depends on lower-level capability

  constructor(ctx: Context, config: Config) {
    super(ctx)                      // ← registers as ctx.shell
  }
}
```

**2. Method implementation**:

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

**What you learn:**
- Provider also declares dependencies (`inject: ['subprocess']`) — capability layers stack
- `extends ShellExecutor` + `super(ctx, 'shell')` → becomes the implementation of `ctx.shell`
- Actual execution delegates to `ctx.subprocess.spawn()` — another seam!

---

## Step 5: Trace Cross-Seam Calls

The shell seam itself depends on the **subprocess** seam:

```text
tool-bash (Consumer of shell)
    ↓ ctx.shell.run()
bash-local (Provider of shell, Consumer of subprocess)
    ↓ ctx.subprocess.spawn()
subprocess-local (Provider of subprocess)
    ↓ actual OS process creation
```

This is "capability layering" — each Provider is simultaneously a Consumer of lower-level capabilities.

---

## General Reading Method

| Step | Action | Look at |
|------|--------|---------|
| 1 | Find three roles | `packages/<capability>/` directory |
| 2 | Read Definition | `declare module` + abstract class |
| 3 | Read Consumer | `inject` declaration + `ctx.xxx.run()` calls |
| 4 | Read Provider | `extends` implementation + delegation downward |
| 5 | Trace events | `ctx.on('tools/execute', ...)` waterfall listeners |

### Quick grep commands

```bash
# Find all Definitions
grep -r "declare module.*cordis" packages/ --include="*.ts"

# Find all Consumers of a capability
grep -r "ctx\.shell\." packages/ --include="*.ts"

# Find all Providers of a capability
grep -r "extends ShellExecutor" packages/ --include="*.ts"
```

---

## Practice Path

Follow this sequence to build intuition:

1. **shell** (this guide) → Understand the three-role pattern
2. **fs** → Compare with shell; same pattern: `packages/fs/fs` + `fs-local` + `tool-fs`
3. **subagent** → See async delegation: `packages/subagent/subagent` + `subagent-fork-in-process` + `tool-subagent`

For each, trace: Definition interface → Consumer call site → Provider implementation → lower-level delegation.

---

## Key Architectural Principles

From `docs/architecture-map.md` §3.1:

> **A capability seam is complete only when all three roles exist.** A package with just a Definition is an incomplete contract; a package with just a Provider is an orphan implementation; a package with just a Consumer is a caller with no callee.

> **The test of a good seam:** how different can the Provider worlds be? Local process → remote sandbox; in-process → external product. The wider the gap, the more valuable the interface.

> **Replace any Provider, all Consumers switch with zero changes.** This is the "seam" — a clean line where implementations can be swapped without touching callers.

---

## Source References

- `docs/architecture-map.md` §3.1 — Capability seams: three roles define boundaries
- `packages/shell/shell/src/index.ts` — Service Definition
- `packages/shell/bash-local/src/index.ts` — Provider implementation
- `packages/shell/tool-bash/src/index.ts` — Consumer tool
