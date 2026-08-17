# 计划：每个章节都有专属图

## 目标

让 `docs/architecture-map.md` 的每个章节（和部分关键小节）都有自己专属的 HTML 图，不再共享或瞎连。

## 现状

| 已有图 | 内容 | 当前被链接到 |
|--------|------|-------------|
| cordis-kernel.html | Cordis 内核六概念 | 第 1 章 |
| harness-architecture.html | 主架构图（全插件） | 第 2 章、3.1、第 4 章 |
| turn-step.html | Turn/Step 时序 | 2.2.1 agent-loop、3.2 |
| tool-pipeline.html | 工具三道关口 | 2.2.3 tools |
| plugin-lifecycle.html | 插件生命周期 | 1.6 fiber + effect |

**问题**：
- harness-architecture.html 被 3 个章节共享（第 2 章、3.1、第 4 章）
- turn-step.html 被 2 个小节共享（2.2.1、3.2）
- 3.3 作用域、3.4 崩溃恢复、2.2.4 session 没有专属图

## 目标对应关系

### 第 1 章 · Cordis 基座（运行时内核）
- **专属图**：`cordis-kernel.html`（已有）
- 覆盖：plugin / context / service / inject / fiber / events / bundle / profile

### 第 2 章 · 插件生态（一切皆插件）
- **专属图**：`plugin-ecosystem.html`（新建）
- 内容：插件树组合（bundle → profile → patch）+ 平行插件分类（核心/入口/能力）
- 替代：现在用的 harness-architecture.html（太泛）

### 第 3 章 · 插件怎么协作
- **专属图**：`collaboration-patterns.html`（新建）
- 内容：能力接缝三角色 + 会话日志事件溯源 + 作用域遮蔽 + 崩溃恢复
- 替代：现在用的 harness-architecture.html 和 turn-step.html（都不对口）

### 第 4 章 · 全景回顾
- **专属图**：`panorama.html`（新建）
- 内容：四层结构 + 为什么几十行 Agent 会长成运行时
- 替代：现在用的 harness-architecture.html（太泛）

## 关键小节专属图（可选）

| 小节 | 专属图 | 优先级 |
|------|--------|--------|
| 2.2.1 agent-loop | turn-step.html（已有） | 高 |
| 2.2.3 tools | tool-pipeline.html（已有） | 高 |
| 2.2.4 session | session-log.html（新建） | 中 |
| 3.1 能力接缝 | capability-seam.html（新建） | 中 |
| 3.3 作用域 | scope-shadowing.html（新建） | 中 |
| 3.4 崩溃恢复 | crash-recovery.html（新建） | 低 |

## 实施步骤

### 阶段 1：补 4 张章节专属图（必需）

1. **plugin-ecosystem.html**（第 2 章）
   - 类型：architecture
   - 内容：插件树三层组合 + 平行插件分类
   - 参考：harness-architecture.json 的 components，但重新组织

2. **collaboration-patterns.html**（第 3 章）
   - 类型：architecture 或 composite
   - 内容：四宫格或流程图：能力接缝 → 会话日志 → 作用域 → 崩溃恢复

3. **panorama.html**（第 4 章）
   - 类型：architecture
   - 内容：四层结构 + 关键结论

### 阶段 2：补 4 张小节专属图（可选）

4. **session-log.html**（2.2.4、3.2）
   - 类型：sequence 或 lifecycle
   - 内容：事件流 → surface → 模型历史

5. **capability-seam.html**（3.1）
   - 类型：architecture
   - 内容：Service Definition / Provider / Consumer 三角色

6. **scope-shadowing.html**（3.3）
   - 类型：architecture
   - 内容：global 层 vs agent.ctx 层，同名遮蔽

7. **crash-recovery.html**（3.4）
   - 类型：lifecycle 或 sequence
   - 内容：两种崩溃场景：tool not started vs tool outcome unknown

### 阶段 3：更新文档链接

- 每个章节只链接自己的专属图
- 去掉重复和瞎连的链接
- 小节链接小节图（如果有）

### 阶段 4：重建 harness-full.html

- 加入新图到导航
- 更新路由和键盘快捷键

## 工作量估计

- 必需：4 张章节图 + 文档链接更新 + harness-full.html 重建 ≈ 2-3 小时
- 可选：4 张小节图 ≈ 2-3 小时
- 总计：4-6 小时

## 优先级建议

**P0（必需）**：
1. plugin-ecosystem.html（第 2 章）
2. collaboration-patterns.html（第 3 章）
3. panorama.html（第 4 章）

**P1（推荐）**：
4. session-log.html（2.2.4、3.2）
5. capability-seam.html（3.1）

**P2（可选）**：
6. scope-shadowing.html（3.3）
7. crash-recovery.html（3.4）

先做 P0，让每个章节都有专属图；再做 P1/P2，让关键小节也有专属图。
