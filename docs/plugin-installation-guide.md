# DeepSeek Harness 插件安装指南

> 本文档记录了 DeepSeek Harness 社区插件的安装过程，包括 UI、视觉、插件市场、记忆系统四大类插件。
>
> 安装时间：2026-08-18

---

## 安装概览

本次共安装 **9 个插件**，分为四类：

| 类别 | 插件 | 说明 |
|------|------|------|
| **UI 三件套** | DSH Web UI · dsh-better-sidebar · dsh-cc-tui | Web UI 增强、侧边栏、终端 UI |
| **视觉三件套** | ModLens · DSH Vision Toolkit · dsh-vision-router | OCR、视觉定位、视觉路由（互补） |
| **插件市场** | dsh-market · dsh-plugin-market | 插件浏览、搜索、安装 |
| **记忆系统** | Hindsight | 长期记忆（Git 历史 + 对话 → 记忆库） |

---

## 前置条件

- DeepSeek Harness 已安装（`apps/cli/lib/bin.js` 可用）
- Node.js 22+（Hindsight 需要）
- pnpm 10+（插件依赖管理）

---

## 安装步骤

### 1. UI 三件套

#### 1.1 DSH Web UI

**功能**：Web UI 增强包（UI 扩展、工具、远程访问、皮肤）

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:zhu1090093659/dsh-web-ui
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep dsh-web-ui
# 应输出: "dsh-web-ui": "github:zhu1090093659/dsh-web-ui"
```

#### 1.2 dsh-better-sidebar

**功能**：VS Code 风格侧边栏 + 底部工作区

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:omdsh-dev/DSH-better-sidebar
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep dsh-better-sidebar
# 应输出: "dsh-better-sidebar": "github:omdsh-dev/DSH-better-sidebar"
```

#### 1.3 dsh-cc-tui

**功能**：Claude Code 风格全屏终端 UI

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:ccch1mneyyy/dsh-TUI
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep dsh-tui
# 应输出: "@deepseek-harness-tui/dsh-tui": "github:ccch1mneyyy/dsh-TUI"
```

---

### 2. 视觉三件套（互补）

#### 2.1 ModLens

**功能**：图片转结构化 OCR、布局分析、语义证据提取

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:liustack/modlens
```

**注意**：安装时可能有 bin 警告（`modlens. ENOENT`），不影响使用。

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep modlens
# 应输出: "@liustack/modlens": "github:liustack/modlens"
```

#### 2.2 DSH Vision Toolkit

**功能**：图像问答、视觉定位、UI 还原、像素对比

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:Anionex/dsh-vision-toolkit
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep vision-toolkit
# 应输出: "@anionex/dsh-vision-toolkit": "github:Anionex/dsh-vision-toolkit"
```

#### 2.3 dsh-vision-router

**功能**：视觉路由 + 像素级图像工具

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:ysr666/dsh-vision-router
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep vision-router
# 应输出: "dsh-vision-router": "github:ysr666/dsh-vision-router"
```

**互补关系**：
- **ModLens**：负责**理解图片内容**（OCR + 语义）
- **Vision Toolkit**：负责**视觉定位**（找 UI 元素、像素对比）
- **Vision Router**：负责**路由分发**（决定用哪个视觉工具）

---

### 3. 插件市场

#### 3.1 dsh-market

**功能**：插件市场（浏览、搜索、安装、更新、删除）

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:dsh-market/dsh-market
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep dshmarket
# 应输出: "dshmarket": "github:dsh-market/dsh-market"
```

#### 3.2 dsh-plugin-market

**功能**：插件市场（GitHub + npm 双源索引，Web UI + Agent 工具）

**安装**：

```bash
cd ~/.dsh/profiles/web
pnpm add github:chnjames/dsh-plugin-market
```

**验证**：

```bash
cat ~/.dsh/profiles/web/package.json | grep dsh-plugin-market
# 应输出: "dsh-plugin-market": "github:chnjames/dsh-plugin-market"
```

---

### 4. 记忆系统

#### 4.1 Hindsight

**功能**：长期记忆（Git 历史 + 对话 → 记忆库，自动召回）

**安装**：

```bash
npx @vectorize-io/hindsight-coding-agents install dsh
```

**安装位置**：
- **Skill**：`~/.agents/skills/hindsight-coding-agent`
- **配置**：`~/.hindsight/coding-agent.json`
- **插件注册**：`~/.dsh/cordis.patch.yml`

**验证**：

```bash
cat ~/.hindsight/coding-agent.json
# 应包含 Hindsight 配置

cat ~/.dsh/cordis.patch.yml | grep hindsight
# 应包含 hindsight 插件注册
```

**特性**：
- **自动捕获**：Git 历史 + 对话自动流入记忆库
- **知识页面**：自动生成架构、约定、决策的 wiki
- **跨 Agent 共享**：Claude Code、Codex、Cursor 等 10+ Agent 都能用
- **一键安装**：`npx @vectorize-io/hindsight-coding-agents install dsh`

---

## 一键安装脚本

```bash
#!/bin/bash
# DeepSeek Harness 插件一键安装脚本

cd ~/.dsh/profiles/web

# UI 三件套
pnpm add github:zhu1090093659/dsh-web-ui
pnpm add github:omdsh-dev/DSH-better-sidebar
pnpm add github:ccch1mneyyy/dsh-TUI

# 视觉三件套（互补）
pnpm add github:liustack/modlens
pnpm add github:Anionex/dsh-vision-toolkit
pnpm add github:ysr666/dsh-vision-router

# 插件市场
pnpm add github:dsh-market/dsh-market
pnpm add github:chnjames/dsh-plugin-market

# 记忆系统（Hindsight）
npx @vectorize-io/hindsight-coding-agents install dsh

echo "全部插件安装完成！"
echo "启动方式: cd /d/AI-Projects/deepseek-harness && node apps/cli/lib/bin.js web"
```

---

## 验证安装

### 查看已安装插件

```bash
cat ~/.dsh/profiles/web/package.json | grep -A 20 "dependencies"
```

**预期输出**：

```json
"dependencies": {
  "@anionex/dsh-vision-toolkit": "github:Anionex/dsh-vision-toolkit",
  "@deepseek-harness-tui/dsh-tui": "github:ccch1mneyyy/dsh-TUI",
  "@liustack/modlens": "github:liustack/modlens",
  "dsh-better-sidebar": "github:omdsh-dev/DSH-better-sidebar",
  "dsh-plugin-market": "github:chnjames/dsh-plugin-market",
  "dsh-vision-router": "github:ysr666/dsh-vision-router",
  "dsh-web-ui": "github:zhu1090093659/dsh-web-ui",
  "dshmarket": "github:dsh-market/dsh-market"
}
```

### 启动 Web UI

```bash
cd /d/AI-Projects/deepseek-harness
node apps/cli/lib/bin.js web
```

然后在浏览器打开 `http://127.0.0.1:3080`，即可看到所有插件。

---

## 常见问题

### 1. 安装超时

**问题**：`pnpm add github:xxx` 超时

**解决**：增加超时时间或使用代理

```bash
pnpm add github:xxx --timeout 180000
```

### 2. bin 警告

**问题**：`Failed to create bin at ... modlens. ENOENT`

**解决**：不影响使用，可忽略

### 3. Hindsight 安装失败

**问题**：`npx @vectorize-io/hindsight-coding-agents install dsh` 失败

**解决**：检查 Node.js 版本（需要 22+）

```bash
node --version  # 应 >= 22.0.0
```

---

## 插件清单

| 插件 | 类型 | 仓库 | 说明 |
|------|------|------|------|
| DSH Web UI | UI | zhu1090093659/dsh-web-ui | Web UI 增强包 |
| dsh-better-sidebar | UI | omdsh-dev/DSH-better-sidebar | VS Code 风格侧边栏 |
| dsh-cc-tui | UI | ccch1mneyyy/dsh-TUI | Claude Code 风格终端 UI |
| ModLens | 视觉 | liustack/modlens | OCR + 语义分析 |
| DSH Vision Toolkit | 视觉 | Anionex/dsh-vision-toolkit | 视觉定位 + UI 还原 |
| dsh-vision-router | 视觉 | ysr666/dsh-vision-router | 视觉路由 |
| dsh-market | 市场 | dsh-market/dsh-market | 插件市场 |
| dsh-plugin-market | 市场 | chnjames/dsh-plugin-market | 插件市场（双源） |
| Hindsight | 记忆 | vectorize-io/hindsight-coding-agents | 长期记忆 |

---

## 参考资料

- **插件市场**：https://dshbase.com/plugins/directory/
- **GitHub Topic**：`dsh-plugin`
- **Hindsight 文档**：https://hindsight.vectorize.io/
- **DeepSeek Harness 文档**：https://deepseek.com/harness/en/
