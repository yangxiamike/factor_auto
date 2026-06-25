"""旧计算引擎目录结构的兼容性测试。"""

from factor_autoresearch import calculator, compute_legacy, metrics, preprocess
from factor_autoresearch.compute_legacy import calculator as legacy_calculator
from factor_autoresearch.compute_legacy import metrics as legacy_metrics
from factor_autoresearch.compute_legacy import preprocess as legacy_preprocess


def test_legacy_compute_exports_are_stable() -> None:
    """旧 engine 目录导出和根路径兼容导出保持同一对象。"""

    assert compute_legacy.FactorCalc is legacy_calculator.FactorCalc
    assert compute_legacy.MetricsResult is legacy_metrics.MetricsResult
    assert compute_legacy.compute_candidate_metrics is legacy_metrics.compute_candidate_metrics
    assert compute_legacy.preprocess_factor is legacy_preprocess.preprocess_factor


def test_root_compute_wrappers_remain_compatible() -> None:
    """根路径旧导入保持可用，避免外部调用被目录迁移打断。"""

    assert calculator.FactorCalc is legacy_calculator.FactorCalc
    assert metrics.MetricsResult is legacy_metrics.MetricsResult
    assert metrics.compute_candidate_metrics is legacy_metrics.compute_candidate_metrics
    assert preprocess.preprocess_factor is legacy_preprocess.preprocess_factor
