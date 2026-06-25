"""
compute engine v1 元数据: 描述新计算链路的路由信息。
本模块不承载 v1 计算实现，实际实现位于 compute_v1 包。
"""

ENGINE_NAME = "v1"
ENGINE_DESCRIPTION = "Compute engine v1 with explicit routing and parallel helpers."


# ============== 引擎元数据 ==============
def get_engine_info() -> dict[str, str]:
    """读取引擎信息: 返回路由和诊断使用的简短描述。"""
    return {
        "name": ENGINE_NAME,
        "description": ENGINE_DESCRIPTION,
    }
