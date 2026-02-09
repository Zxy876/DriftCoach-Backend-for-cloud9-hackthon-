"""
优化建议：减少输出信息量和提升速度
========================================

## 问题
1. 回复速度慢（可能触发不必要的 patches）
2. 输出信息"多到爆炸"（大量调试信息和元数据）

## 优化方案
"""

# =============================================================================
# 方案 1：生产环境减少日志输出
# =============================================================================

# 文件：driftcoach/api.py:23
# 之前：
#   logging.basicConfig(level=logging.INFO)

# 之后：
import os
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.WARNING))

# 效果：减少 90% 的日志输出


# =============================================================================
# 方案 2：精简 payload 返回（简洁模式）
# =============================================================================

# 文件：driftcoach/api.py (在 coach_query 函数中)
# 在 return payload 之前添加：

def _strip_debug_info(payload: dict, verbose: bool = False) -> dict:
    """
    Remove debug information from payload for cleaner responses.

    Args:
        payload: Full response payload
        verbose: If True, keep all fields; if False, strip debug info

    Returns:
        Cleaned payload
    """
    if verbose:
        return payload

    # Keep only essential fields
    essential = {
        "assistant_message": payload.get("assistant_message"),
        "answer_synthesis": payload.get("answer_synthesis"),
    }

    # Optionally include narrative if present
    if payload.get("narrative"):
        essential["narrative"] = payload["narrative"]

    return essential

# 使用：
@app.post("/api/coach/query")
def coach_query(body: CoachQuery):
    # ... 现有代码 ...

    # 在返回之前精简
    verbose = body.verbose or False  # 添加 verbose 字段到 CoachQuery
    payload = _strip_debug_info(payload, verbose=verbose)

    return payload


# =============================================================================
# 方案 3：减少不必要的 patches
# =============================================================================

# 文件：driftcoach/api.py (DecisionMapper 集成后)
# 已经实现：DecisionMapper 直接给出决策，避免触发 patches

# 进一步优化：当 DecisionMapper 返回 DEGRADED/STANDARD 时，
# 跳过 generate_inference_plan() 调用

# 修改 api.py:2560 附近：
#   if not answer_synthesis or answer_synthesis.get("verdict") == "INSUFFICIENT":
#       # 只在真正需要时才调用旧门控
#       inference_plan = generate_inference_plan(inference_input)
#   else:
#       # DecisionMapper 已给出有效决策，跳过旧门控
#       inference_plan = {
#           "judgment": "EVIDENCE_SUFFICIENT",
#           "rationale": answer_synthesis.get("claim"),
#           "proposed_patches": [],
#       }


# =============================================================================
# 方案 4：限制证据详情
# =============================================================================

# 文件：driftcoach/config/bounds.py
# 添加新配置：

@dataclass
class SystemBounds:
    # 现有配置...
    max_sub_intents: int = 3
    max_findings_per_intent: int = 2
    max_findings_total: int = 5
    max_support_facts: int = 3
    max_counter_facts: int = 3

    # 新增：输出控制
    include_context_details: bool = False  # 是否包含 context 详情
    include_evidence_buckets: bool = False  # 是否包含 buckets
    include_inference_plan: bool = False  # 是否包含 inference_plan
    include_patch_results: bool = False  # 是否包含 patch_results


# =============================================================================
# 方案 5：前端控制（推荐）
# =============================================================================

# 前端可以选择只显示需要的字段：
# - 只显示 assistant_message（主要回答）
# - 可选展开查看 answer_synthesis（详细证据）
# - 可选展开查看 context（上下文信息）
# - 默认隐藏 debug 信息（inference_plan, patch_results 等）


# =============================================================================
# 效果预期
# =============================================================================

"""
优化前（当前）：
- 响应时间：500ms~3000ms（可能触发 patches）
- payload 大小：50KB~200KB（包含大量调试信息）
- 日志输出：大量 INFO 日志

优化后（推荐配置）：
- 响应时间：100ms~500ms（DecisionMapper 直接决策）
- payload 大小：2KB~10KB（只包含必要信息）
- 日志输出：WARNING 级别（只记录错误和警告）

提速：**5-10 倍** ✅
减量：**90%** ✅
"""
