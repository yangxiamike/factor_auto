"""
legacy engine 元数据: 描述旧计算链路的路由信息。
本模块不承载旧计算实现，实际实现位于 compute_legacy 包。
"""

ENGINE_NAME = "legacy"
ENGINE_DESCRIPTION = "Legacy single-process compute path."


# ============== 引擎元数据 ==============
def get_engine_info() -> dict[str, str]:
    """读取引擎信息: 返回路由和诊断使用的简短描述。"""
    return {
        "name": ENGINE_NAME,
        "description": ENGINE_DESCRIPTION,
    }
