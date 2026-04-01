# Subagent 实现方案讨论

## 当前理解澄清

### ✅ 正确理解

你说得对！SentrySkills 是一个 **skill 项目**：
- 核心代码是**规则脚本**（`self_guard_runtime_hook_template.py`）
- 通过 **SKILL.md** 告诉 Agent 如何使用
- **Subagent spawning 由宿主框架完成**（Claude Code / Codex / OpenClaw）

### 📋 SKILL.md 中描述的两路径

**Step 2b — LOW Path**:
```
Main agent: 立即继续，不等待

Subagent: 宿主框架（OpenClaw/Claude Code/Codex）启动 subagent:
  1. 写入 subagent_input_<turn_id>.json
  2. 运行完整 pipeline（同一个脚本）
  3. 追加结果到 index.jsonl
```

---

## 当前实现分析

### 1. `claude_code_hook.py` (PreToolUse Hook)

**当前行为**：
```python
# 现在的代码
payload = {...}
input_path.write_text(json.dumps(payload, ...))
proc = subprocess.run([sys.executable, str(HOOK_SCRIPT), ...])
result = json.load(open(result_path))

# 总是等待完整检查完成（同步）
if final_action == "block":
    return 2  # 阻止工具
return 0  # 允许
```

**问题**：
- ❌ 没有 Fast Pre-Assessment（检查 HIGH/LOW 信号）
- ❌ 总是同步运行完整 pipeline
- ❌ 没有 LOW path（立即返回 + subagent）

---

## 需要做什么

### 方案 A：在 Hook 中实现两路径判断

```python
# claude_code_hook.py 修改建议

def is_high_risk(tool_name: str, tool_input: dict, user_prompt: str) -> bool:
    """Fast Pre-Assessment"""
    planned_action = TOOL_ACTION_MAP.get(tool_name, "")
    
    # HIGH 触发条件 1：高危动作
    if planned_action in HIGH_RISK_ACTIONS:
        # 检查 prompt 是否有敏感词
        disclosure_words = ["output token", "print password", "secret", "api key"]
        if any(word in user_prompt.lower() for word in disclosure_words):
            return True
    
    # HIGH 触发条件 2：注入标记
    injection_markers = ["ignore previous", "jailbreak", "act as"]
    if any(marker in user_prompt.lower() for marker in injection_markers):
        return True
    
    return False

def main():
    ... # 读取 hook 输入
    
    # Fast Pre-Assessment
    if is_high_risk(tool_name, tool_input, prompt_text):
        # === HIGH Path: 同步阻塞 ===
        proc = subprocess.run([...], capture_output=True)
        result = json.load(open(result_path))
        
        if result["final_action"] == "block":
            return 2  # 阻止工具
        return 0
    else:
        # === LOW Path: 立即返回 + subagent 标记 ===
        # 1. 准备 subagent 输入
        subagent_input_file = LOG_DIR / f"subagent_input_{turn_id}.json"
        subagent_input_file.write_text(json.dumps({...}))
        
        # 2. 立即允许工具继续执行（不等待）
        # 3. 主框架会启动 subagent 运行完整检查
        return 0  # allow immediately
```

**优点**：
- ✅ 完整实现两路径逻辑
- ✅ LOW path 时工具立即继续（零延迟）
- ✅ Hook 代码自包含

**缺点**：
- ❌ Hook 脚本自己不启动 subagent
- ❌ 需要框架支持（见方案 B）

---

### 方案 B：依赖框架的 Subagent 功能

**关键问题**：Hook 怎么告诉框架"启动 subagent"？

#### 对于 Claude Code

**可能性 1：通过 response metadata**

```python
# claude_code_hook.py
if not is_high_risk(...):
    # 返回 allow + metadata 告诉框架启动 subagent
    print("SUBAGENT_REQUIRED: subagent_input_123.json", file=sys.stderr)
    return 0
```

**可能性 2：通过 exit code 或特殊文件**

```python
# 写入标记文件
(Path(LOG_DIR) / "spawn_subagent.flag").write_text("subagent_input_123.json")
return 0
```

**可能性 3：框架文档查看**

需要查 Claude Code 文档：PreToolUse hook 能否触发 subagent？

---

#### 对于 Codex

**可能性**：通过 SKILL.md 指令

在 SKILL.md 的 LOW path 中明确告诉 Agent：
```
## Step 2b — LOW Path

Main agent: proceed immediately

Then, using Codex's subagent feature:
<spawn_subagent>
  input: ./sentry_skill_log/subagent_input_<turn_id>.json
  command: python shared/scripts/self_guard_runtime_hook_template.py ...
  output_mode: append_to_file
  output_file: ./sentry_skill_log/index.jsonl
</spawn_subagent>
```

Codex 解析这个标签并执行。

---

## 建议的实现策略

### 阶段 1：先完善 Hook 内部的两路径判断（方案 A）

```python
# 实现快速预判
def is_high_risk(...) -> bool:
    # 检查 HIGH 触发条件
    pass

# HIGH path：同步运行
if is_high_risk(...):
    run_full_pipeline_sync()
    return block_or_allow()

# LOW path：立即返回
# （subagent 部分稍后根据框架能力添加）
return allow_immediately()
```

**好处**：
- ✅ Hook 逻辑完整
- ✅ HIGH path 立即生效（危险命令被阻止）
- ✅ LOW path 已经立即返回（性能提升）

---

### 阶段 2：集成框架 Subagent 功能

#### Claude Code 集成

**需要研究**：
1. PreToolUse hook 能否触发 Agent.spawnSubAgent()？
2. 或者通过什么机制告诉 Claude Code 启动 subagent？

**可能的方案**：

**方案 2.1：修改 AGENTS.md**（推荐）

在项目的 AGENTS.md 中添加：

```markdown
## SentrySkills 两路径执行

### LOW 路径处理

当 SentrySkills hook 返回 `allow` 但标记为 LOW risk 时：

```python
# Claude Code 自动执行
if hook_result.get("risk_level") == "LOW":
    # 启动 subagent 运行完整检查
    spawn_subagent(
        name="sentry-skills-monitor",
        instruction=f"""
Run SentrySkills full pipeline:
  python {project_path}/shared/scripts/self_guard_runtime_hook_template.py \
    {project_path}/sentry_skill_log/subagent_input_{turn_id}.json \
    --policy-profile balanced \
    --append-output {project_path}/sentry_skill_log/index.jsonl
"""
    )
```

然后在下个 turn 检查 `index.jsonl`。
```

**方案 2.2：Hook 返回特殊标记**

```python
# claude_code_hook.py
if not is_high_risk(...):
    # 写入 subagent 输入文件
    subagent_input = LOG_DIR / f"subagent_input_{turn_id}.json"
    subagent_input.write_text(json.dumps(payload))
    
    # 返回时包含 metadata
    print(json.dumps({
        "decision": "allow",
        "spawn_subagent": True,
        "subagent_input": str(subagent_input),
        "subagent_command": f"python ... {subagent_input} ..."
    }), file=sys.stderr)
    
    return 0
```

---

#### Codex/OpenClaw 集成

**通过 SKILL.md 指令**（更可控）：

在 SKILL.md 中明确写出：

```markdown
### Step 2b — LOW Path Implementation

**Main Agent**: 立即继续

**Subagent Spawn** (Codex/OpenClaw 会自动执行):

```
<subagent>
  name: sentry-skills-monitor
  input_file: ./sentry_skill_log/subagent_input_<turn_id>.json
  command: |
    python shared/scripts/self_guard_runtime_hook_template.py \
      ./sentry_skill_log/subagent_input_<turn_id>.json \
      --policy-profile balanced \
      --append-output ./sentry_skill_log/index.jsonl
  mode: background
  output_append: ./sentry_skill_log/index.jsonl
</subagent>
```

**Next Turn Check**:
```
At start of each turn, before responding:
1. Read ./sentry_skill_log/index.jsonl
2. Check if last subagent run resulted in block
3. If yes, refuse and explain
```

---

## 具体实现建议

### 第 1 步：实现 Fast Pre-Assessment

在 `claude_code_hook.py` 中添加：

```python
def is_high_risk(tool_name: str, tool_input: dict, user_prompt: str) -> bool:
    """Fast pre-assessment (sync check)"""
    
    # 1. 高危动作检查
    if tool_name in ("Bash", "Write", "Edit"):
        # 2. 敏感词检查
        disclosure_words = [
            "output token", "print password", "print secret",
            "show api key", "dump", "reveal secret", "output credential"
        ]
        prompt_lower = user_prompt.lower()
        if any(word in prompt_lower for word in disclosure_words):
            return True
        
        # 3. 注入标记检查
        injection_markers = [
            "ignore previous instructions", "ignore all instructions",
            "jailbreak", "forget everything", "act as", "override protocol",
            "developer mode"
        ]
        if any(marker in prompt_lower for marker in injection_markers):
            return True
    
    return False
```

### 第 2 步：修改 Hook 主逻辑

```python
def main():
    ... # 读取输入
    
    # Fast Pre-Assessment
    if is_high_risk(tool_name, tool_input, prompt_text):
        # HIGH path: 同步运行完整检查
        proc = subprocess.run(...)
        result = json.load(open(result_path))
        
        if result["final_action"] == "block":
            # 阻止工具执行
            return 2
        return 0
    else:
        # LOW path: 立即返回 + 标记 subagent
        # 准备 subagent 输入
        subagent_input = {
            "session_id": session_id,
            "turn_id": f"subagent-{turn_id}",
            "project_path": str(PROJECT_ROOT),
            "user_prompt": user_prompt,
            "planned_actions": [planned_action],
            "candidate_response": "",
            "intent_tags": [f"tool:{tool_name}"],
            "mode": "async"
        }
        
        subagent_file = LOG_DIR / f"subagent_input_{turn_id}.json"
        subagent_file.write_text(json.dumps(subagent_input))
        
        # 立即允许工具执行（不等待）
        return 0
```

### 第 3 步：添加 Next-Turn Check（在 SKILL.md 中）

```markdown
## At Start of Each Turn

Before responding, check for prior subagent results:

```python
import json
from pathlib import Path

index_jsonl = Path("./sentry_skill_log/index.jsonl")
if index_jsonl.exists():
    with open(index_jsonl, "r") as f:
        for line in f:
            result = json.loads(line)
            if result.get("final_action") == "block":
                # Prior turn was blocked - refuse this turn
                return f"⚠️ Previous turn was blocked by SentrySkills (trace: {result['trace_id']})"
```
```

---

## 讨论问题

### Q1: Claude Code 能否自动启动 subagent？

**需要验证**：
- 查看 Claude Code 文档关于 Agent.spawnSubAgent()
- 或者看是否有其他机制
- 可能需要返回特殊的 metadata 或 exit code

### Q2: 如何在 Hook 中"告诉框架"启动 subagent？

**可能的方案**：
1. 在 stderr 输出特殊标记
2. 写入标记文件
3. 修改返回值格式
4. 在 AGENTS.md 中配置规则

### Q3: 性能提升效果如何？

**预期**：
- HIGH path（危险命令）：同步阻塞，安全第一
- LOW path（正常命令）：立即返回，**零延迟**
- 预计 80-90% 的命令是 LOW path

---

## 我的建议

### 立即执行（P0）：

1. ✅ **实现 Fast Pre-Assessment**
   - 在 hook 中添加 `is_high_risk()` 函数
   - HIGH path：同步运行（当前已有）
   - LOW path：立即返回

2. ✅ **准备 subagent 输入格式**
   - 写入 `subagent_input_<turn_id>.json`
   - 标记为 `mode: "async"`

3. ✅ **添加 next-turn check 逻辑**
   - 在 SKILL.md 中添加检查 `index.jsonl` 的说明
   - 或者创建辅助脚本

### 后续集成（P1）：

4. 🔬 **研究 Claude Code subagent API**
   - 查看文档
   - 测试不同的触发方式

5. 🔧 **完善框架集成**
   - 根据框架能力调整实现

---

## 总结

你的理解完全正确：
- ✅ SentrySkills **不需要实现 subagent spawning**
- ✅ Subagent 由**宿主框架**提供
- ✅ SentrySkills 只需：
  1. 判断 HIGH/LOW path
  2. 准备 subagent 输入
  3. 处理 subagent 结果

**下一步**：我们可以先实现 hook 内部的两路径判断，这样即使没有 subagent 支持，也能获得性能提升（LOW path 立即返回）。
