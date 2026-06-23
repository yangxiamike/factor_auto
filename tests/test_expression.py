from dataclasses import replace

import pytest

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.expression import (
    ExpressionMetadata,
    ExpressionValidationError,
    ExpressionValidator,
)
from factor_autoresearch.operators import OPERATOR_REGISTRY


def _candidate(expression: str, lookback_days: int = 5) -> Candidate:
    return Candidate(
        candidate_id="fa_expr",
        name="expression",
        expression=expression,
        expected_direction="positive",
        hypothesis="test",
        category="momentum",
        lookback_days=lookback_days,
        created_at="2026-06-22",
        notes="test",
    )


def test_expression_validator_returns_metadata(test_config) -> None:
    validator = ExpressionValidator(test_config, OPERATOR_REGISTRY)
    metadata = validator.validate_candidate(
        _candidate("cs_rank(ts_mean(close_hfq, 5) - delay(open_hfq, 1))", 5)
    )
    assert metadata == ExpressionMetadata(complexity_score=8, inferred_lookback=5)


def test_expression_validator_rejects_small_declared_lookback(test_config) -> None:
    validator = ExpressionValidator(test_config, OPERATOR_REGISTRY)
    with pytest.raises(ExpressionValidationError, match="declared lookback_days"):
        validator.validate_candidate(_candidate("ts_mean(close_hfq, 5)", 3))


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        ("foo_bar", "unknown field"),
        ("abs(foo_bar)", "unknown field"),
        ("not_allowed(close_hfq)", "unknown function"),
        ("log(close_hfq, 3)", "expects exactly one argument"),
        ("delay(close_hfq)", "expects two arguments"),
        ("delay(close_hfq, 2)", "invalid window"),
        ("delay(close_hfq, True)", "window arguments must be integer constants"),
        ("abs(close_hfq, x=1)", "keyword arguments are not allowed"),
        ("close_hfq.real", "unsupported expression node"),
        ("close_hfq[0]", "unsupported expression node"),
        ("lambda x: x", "unsupported expression node"),
        ("[close_hfq for _ in range(1)]", "unsupported expression node"),
        ("open_hfq + True", "only numeric constants are allowed"),
    ],
)
def test_expression_validator_rejects_unsafe_or_invalid_syntax(
    test_config, expression: str, message: str
) -> None:
    validator = ExpressionValidator(test_config, OPERATOR_REGISTRY)
    with pytest.raises(ExpressionValidationError, match=message):
        validator.validate_candidate(_candidate(expression, 20))


def test_expression_validator_checks_registry_presence(test_config) -> None:
    config = replace(test_config, allowed_functions=["abs", "log"])
    validator = ExpressionValidator(config, {"abs": OPERATOR_REGISTRY["abs"]})
    with pytest.raises(ExpressionValidationError, match="unsupported function: log"):
        validator.validate_candidate(_candidate("log(close_hfq)", 5))
