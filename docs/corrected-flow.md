# 正确的流程理解：SentrySkills 的定位

## 🔄 正确的流程

```
┌─────────────────────────────────────────────────────┐
│ Step 1: SentrySkills 规则判断 ✅                   │
│  ┌──────────────────────────────────────────────┐   │
│  │ 代码：self_guard_runtime_hook_template.py   │   │
│  │  • preflight_decision（33+ 规则）            │   │
│  │  • runtime_decision（运行时检查）            │   │
│  │  • output_guard（输出守卫）                  │   │
│  └──────────────────────────────────────────────┘   │
│  输出：allow / downgrade / block                    │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ Step 2: 框架（Claude Code/Codex）的内在判断          │
│  • 框架根据 SentrySkills 的结果 + prompt           │
│  • 自己判断风险等级                               │
│  • 决定：同步检查 vs subagent 监控               │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ Step 3: 框架执行 SentrySkills 检查                 │
│  ┌────────────────┬────────────────────────────┐   │
│  │ 3.1 LOW risk    │  3.2 HIGH risk            │   │
│  │  ↓              │ ↓                          │   │
│  │ Subagent 监控   │  框架直接调用             │   │
│  │  （框架负责）   │  SentrySkills 脚本         │   │
│  └────────────────┴────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ Step 4: 执行完毕写日志 ✅                         │
└─────────────────────────────────────────────────────┘
```

---

## ✅ SentrySkills 的真正职责

### 我们负责的：

1. **提供规则引擎** ✅
   - 33+ 检测规则
   - 三阶段检查逻辑
   - allow/downgrade/block 决策

2. **指引框架如何使用** ✅
   - 通过 SKILL.md 告诉 Agent：
     - 什么时候运行检查
     - 怎么调用脚本
     - 怎么解读结果

3. **准备标准输入格式** ✅
   - `input.json` 格式
   - `subagent_input_*.json` 格式
   - `result.json` 输出格式

4. **日志记录** ✅
   - 事件日志
   - 会话状态
   - Hook 结果

### 框架负责的：

1. **大模型预判**（框架的内在判断）
2. **决定同步 vs 异步**（框架的调度逻辑）
3. **Subagent spawning**（框架的能力）

---

## 📋 当前实现对应

| 步骤 | 负责方 | 状态 | 说明 |
|------|--------|------|------|
| Step 1 | SentrySkills | ✅ 完整 | 规则引擎已实现 |
| Step 2 | 框架 | - | 框架自己判断 |
| Step 3.1 | 框架 | - | 框架启动 subagent |
| Step 3.2 | 框架 | ✅ 可调用 | 脚本准备好被调用 |
| Step 4 | SentrySkills | ✅ 完整 | 日志系统已实现 |

---

## 🎯 当前缺失的是什么？

### ❌ 缺失：SKILL.md 中的快速预判指引

**当前 SKILL.md** 的问题：

1. **快速预判规则不够明确**
   ```markdown
   # 当前描述
   ### Step 1 — Fast Pre-Assessment
   Check user_prompt + planned_actions for HIGH-risk signals
   
   HIGH triggers:
   - planned_actions contains: execute_command, write_file...
   - user_prompt contains: output token, print password...
   ```

2. **框架不知道何时用 subagent**
   - 缺少明确的决策树
   - 缺少代码示例

### ✅ 应该补充的

在 `using-sentryskills/SKILL.md` 中添加：

```markdown
## Decision Guide for Framework

### Risk Assessment Matrix

| Condition | Risk Level | Execution Mode |
|-----------|------------|----------------|
| `execute_command` +敏感词 | HIGH | 同步阻塞 |
| `write_file` +敏感路径 | HIGH | 同步阻塞 |
| 注入标记 | HIGH | 同步阻塞 |
| 其他情况 | LOW | Subagent 异步 |

### Implementation for Frameworks

For Claude Code:
```python
# In your AGENTS.md or hook configuration
if is_high_risk(user_prompt, planned_actions):
    run_sync()  # 调用 SentrySkills 同步检查
else:
    spawn_subagent_async()  # 启动 subagent 异步检查
```

For Codex/OpenClaw:
```xml
<!-- In your config -->
<sentryskills mode="auto">
  <condition>
    <high-risk>
      <has_action>execute_command</has_action>
      <contains_prompt>output token</contains_prompt>
    </high-risk>
    <execution>sync</execution>
  </condition>
</sentryskills>
```

---

## 🚀 正确的下一步

### 不是在代码中实现快速预判！

而是：**在 SKILL.md 中提供更清晰的指引**

让框架（Claude Code/Codex）能够：
1. 理解什么是 HIGH risk
2. 知道什么时候用同步检查
3. 知道什么时候用 subagent

### 具体任务

**Task 1**: 更新 `using-sentryskills/SKILL.md`

添加更明确的决策树：

```markdown
## Risk Assessment Decision Tree

For framework implementers:

```
Start
  ↓
Is tool in [execute_command, write_file, delete_file, batch_modify, network_call]?
  ↓ Yes
  └─ Contains敏感词 OR 注入标记?
       ├─ Yes → HIGH Risk → Synchronous Check
       └─ No  → MEDIUM Risk → Synchronous Check
  ↓ No
  └─ LOW Risk → Async Subagent Monitor
```

**Task 2**: 提供清晰的接口说明

告诉框架：
- 同步模式怎么调用
- 异步模式怎么调用
- 输入文件格式
- 输出文件格式

**Task 3**: 提供示例配置

为每个框架（Claude Code/Codex/OpenClaw）提供：
- 配置示例
- 代码示例
- 集成步骤

---

## 💡 关键理解

### SentrySkills 是"规则库 + 指南"

- **规则库**：`self_guard_runtime_hook_template.py`
- **指南**：`SKILL.md` 告诉 Agent 怎么用规则

### 框架是"执行引擎"

- 框架理解指南
- 框架做风险预判
- 框架决定同步/异步
- 框架调用规则库

### 类比

就像：
- **SentrySkills** = 交通法规 + 红绿灯规则
- **框架** = 司机 + 路况判断
- **规则** = "红灯停，绿灯行"
- **执行** = 司机看到红灯停，看到绿灯行

---

## 总结

**当前完成度**：

| 组件 | 状态 |
|------|------|
| 规则引擎（Step 1） | ✅ 100% |
| 框架预判（Step 2） | - | 框架负责 |
| Subagent 执行（Step 3） | - | 框架负责 |
| 日志系统（Step 4） | ✅ 100% |

**我们需要的补充**：
1. ✅ 规则引擎已完整
2. ⚠️ 需要更清晰的 SKILL.md 指引
3. ⚠️ 需要框架集成示例
4. ✅ 日志系统已完整

**下一步重点**：
- 优化 SKILL.md 文档
- 提供框架集成示例
- 而不是在代码中实现"快速预判"（那是框架的事）
