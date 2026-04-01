# SentrySkills 流程分析：当前实现状态

## 完整设计流程（你描述的）

```
┌─────────────────────────────────────────────────────┐
│ Step 1: 规则判断（基于检测规则）                   │
│  ┌──────────────────────────────────────────────┐   │
│  │ preflight_decision  → allow/downgrade/block  │   │
│  │ runtime_decision    → continue/stop/downgrade│   │
│  │ output_guard       → allow/downgrade/block    │   │
│  └──────────────────────────────────────────────┘   │
│                      ↓                             │
│            final_action: allow/downgrade/block      │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ Step 2: 大模型判断（Agent 的决策）                  │
│  • 如果 block → 拒绝执行                           │
│  • 如果 allow/downgrade → 准备响应                  │
│  • 在响应前，Agent 需要判断风险等级               │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ Step 3: 大模型预判风险                              │
│  ┌────────────────┬────────────────────────────┐   │
│  │ 3.1 风险较低   │  3.2 风险较高              │   │
│  │  └──────────────┴────────────────────────────┘   │
│  │  ↓              │ ↓                          │
│  │  Subagent 监控  │  同进程检查                  │
│  │  (异步后台)     │  (同步阻塞)                  │
│  └────────────────┴────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│ Step 4: 执行完毕写日志                            │
│  • ./sentry_skill_log/logs/*.json                  │
│  • ./sentry_skill_log/index.jsonl                  │
│  • ./sentry_skill_log/hook_result_*.json            │
└─────────────────────────────────────────────────────┘
```

---

## ✅ 当前实现状态

### Step 1: 规则判断 - **已完整实现** ✅

**代码位置**: `shared/scripts/self_guard_runtime_hook_template.py`

```python
# 第 2160 行
def preflight_decision(user_prompt, planned_actions, ...)
    # 33+ 检测规则
    # 返回: allow/downgrade/block

# 第 2432 行  
def runtime_decision(runtime_events, sources, ...)
    # 运行时事件检查
    # 返回: continue/stop/downgrade

# 第 2614 行
def output_guard(candidate_response, sensitivity_state, ...)
    # 输出守卫（敏感信息检测）
    # 返回: allow/downgrade/block
```

**综合决策**（第 2879 行）:
```python
final_action = decide_final_action(preflight, runtime, output)
# 综合三阶段结果，返回最终决策
```

✅ **状态**: 规则判断系统完整

---

### Step 2: 大模型判断 - **在 SKILL.md 中描述** ✅

**代码位置**: `using-sentryskills/SKILL.md`

在 SKILL.md 中，我们告诉 Agent：

```markdown
## Execution Requirements

1. Run Fast Pre-Assessment on user_prompt + planned_actions
   → 检查 HIGH risk signals

2a. HIGH signal → run full pipeline synchronously
    - Write input.json
    - Run script
    - Read result.json
    - Include self_guard_path: synchronous

2b. No HIGH signal → proceed immediately + spawn subagent
    - Include self_guard_path: async-subagent
```

✅ **状态**: 通过 SKILL.md 告诉 Agent 如何判断和执行

---

### Step 3: 大模型预判风险 - **部分实现** ⚠️

#### 3.1 风险较低 → Subagent 监控

**文档位置**: `using-sentryskills/SKILL.md`

```markdown
### Step 2b — LOW Path (parallel, non-blocking)

**Subagent**: the host framework (OpenClaw / Claude Code / Codex) 
launches a subagent that:
  1. Writes task context to subagent_input_<turn_id>.json
  2. Runs the full pipeline
  3. Appends result to index.jsonl
```

**当前状态**: ⚠️ **部分实现**
- ✅ 文档已描述
- ❌ Hook 代码中**未实现**快速预判
- ❌ 未准备 subagent 输入格式
- ❌ 未与框架 subagent 功能集成

#### 3.2 风险较高 → 同进程检查

**文档位置**: `using-sentryskills/SKILL.md`

```markdown
### Step 2a — HIGH Path (synchronous, blocking)

1. Write task context to input.json
2. Run full pipeline synchronously
3. Read result.json
4. final_action = block → refuse
```

**当前状态**: ✅ **已实现**
- ✅ `self_guard_runtime_hook_template.py` 完整实现
- ✅ 支持 `--input` 和 `--out` 参数
- ✅ 返回 allow/downgrade/block

---

### Step 4: 执行完毕写日志 - **已实现** ✅

**日志文件**:
- `./sentry_skill_log/logs/*.json` - 详细执行日志
- `./sentry_skill_log/index.jsonl` - 事件日志（需添加 subagent 结果）
- `./sentry_skill_log/hook_result_*.json` - Hook 执行结果
- `./sentry_skill_log/.self_guard_state/*.json` - 会话状态

**代码位置**: 
- 第 718 行：`def emit_event(...)` - 事件日志
- 第 3105 行：JSONL 写入
- 第 3124 行：会话状态保存

✅ **状态**: 日志系统完整

---

## 🔍 关键发现

### 当前实现状态总结

| 步骤 | 状态 | 说明 |
|------|------|------|
| **Step 1: 规则判断** | ✅ 完整 | 三阶段检查全部实现 |
| **Step 2: 大模型判断** | ✅ 通过 SKILL.md | Agent 遵循 SKILL.md 指令执行 |
| **Step 3.1: LOW path** | ⚠️ **未实现** | Hook 中缺少快速预判 |
| **Step 3.2: HIGH path** | ✅ 已实现 | 同步阻塞检查 |
| **Step 4: 写日志** | ✅ 完整 | 多格式日志支持 |

---

## ⚠️ 最关键的缺失

### 缺失：快速预判（Fast Pre-Assessment）

**问题**：`claude_code_hook.py` 当前实现

```python
# 当前代码（简化）
def main():
    payload = {...}
    input_path.write(json.dumps(payload))
    
    # ❌ 总是运行完整检查（同步）
    proc = subprocess.run([python, hook_script, input_path])
    result = json.load(open(result_path))
    
    if result["final_action"] == "block":
        return 2  # block
    return 0  # allow
```

**缺少**：

1. **快速预判函数**
   ```python
   def is_high_risk(tool_name, tool_input, prompt):
       # 检查高危动作 + 敏感词 + 注入标记
       return True/False
   ```

2. **两路径分支**
   ```python
   if is_high_risk(...):
       # HIGH path: 同步运行（当前已有）
       run_full_pipeline_sync()
   else:
       # LOW path: 立即返回 + 准备 subagent
       prepare_subagent_input()
       return 0  # 立即返回，不等待
   ```

---

## 🎯 我们当前在哪个步骤？

### 答案：**Step 3.1 的准备阶段**

**具体来说**：

✅ **已完成**：
- Step 1: 规则判断系统 ✅
- Step 2: 通过 SKILL.md 指导 Agent ✅
- Step 3.2: HIGH path 同步检查 ✅
- Step 4: 日志系统 ✅

⚠️ **进行中**：
- Step 3.1: LOW path 的**准备工作**
  - 缺少快速预判函数
  - 缺少两路径分支逻辑
  - 缺少 subagent 输入准备

❌ **未开始**：
- Step 3.1: Subagent 与框架集成
- Step 3.1: Next-turn check 逻辑

---

## 📋 完成度评估

| 组件 | 完成度 | 说明 |
|------|--------|------|
| 规则引擎 | 100% | 三阶段全部实现 |
| 日志系统 | 100% | 多格式日志支持 |
| HIGH path | 100% | 同步阻塞完整实现 |
| LOW path - 框架集成 | 0% | 未开始（需要研究框架 API） |
| LOW path - 快速预判 | 0% | **P0 任务** |
| Next-turn check | 0% | P1 任务 |
| 测试覆盖 | 0% | P0 任务 |

**整体完成度**: ~60%

---

## 🚀 下一步行动

### 立即执行（P0）

**1. 实现快速预判**（1-2 小时）

在 `claude_code_hook.py` 中添加：

```python
def is_high_risk(tool_name: str, tool_input: dict, user_prompt: str) -> bool:
    """Fast pre-assessment - sync check only"""
    
    # 规则 1: 高危动作 + 敏感词
    if tool_name in ("Bash", "Write", "Edit"):
        sensitive_words = [
            "output token", "print password", "secret",
            "api key", "show credential", "dump", "reveal"
        ]
        prompt_lower = user_prompt.lower()
        if any(word in prompt_lower for word in sensitive_words):
            return True
    
    # 规则 2: 注入标记
    injection_markers = [
        "ignore previous instructions", "jailbreak", 
        "forget everything", "act as", "override protocol",
        "developer mode"
    ]
    if any(marker in prompt_lower for marker in injection_markers):
        return True
    
    return False
```

**2. 添加两路径分支**（1 小时）

```python
def main():
    ... # 读取输入
    
    # Fast Pre-Assessment
    if is_high_risk(tool_name, tool_input, prompt_text):
        # === HIGH Path ===
        run_full_pipeline_sync(...)
        # 返回 block/allow
    else:
        # === LOW Path ===
        # 准备 subagent 输入
        subagent_input_file = LOG_DIR / f"subagent_input_{turn_id}.json"
        subagent_input_file.write_text(json.dumps({...}))
        
        # 立即返回（不等待检查完成）
        return 0
```

---

## 总结

**当前状态**: 
- 我们在 **Step 3.1 的准备阶段**
- 核心规则引擎完整（Step 1, 3.2, 4）
- 缺少的是**快速预判和两路径分支**

**下一步**: 
1. 实现 `is_high_risk()` 函数
2. 修改 hook 主逻辑支持两路径
3. 研究框架 subagent 集成

**预计工作量**:
- 快速预判实现：1-2 小时
- 两路径逻辑：1 小时
- 框架集成研究：2-4 小时

**总时间**: 4-7 小时完成 P0 任务
