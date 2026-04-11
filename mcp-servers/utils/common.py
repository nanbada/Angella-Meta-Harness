import json
from typing import Any

from mcp import types

SUPPORTED_METRICS = (
    "tokens_per_second",
    "build_time",
    "latency_ms",
    "bundle_size",
)
LOWER_IS_BETTER_METRICS = {"build_time", "latency_ms", "bundle_size"}


def build_benchmark_payload(
    *,
    success: bool,
    metric_key: str,
    metric_value: float,
    duration_seconds: float,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
    aux_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "metric_key": metric_key,
        "metric_value": round(float(metric_value), 4),
        "duration_seconds": round(float(duration_seconds), 3),
        "exit_code": int(exit_code),
        "stdout_tail": stdout[-1500:] if stdout else "",
        "stderr_tail": stderr[-800:] if stderr else "",
        "aux_metrics": aux_metrics or {},
    }


def compare_metrics_payload(
    baseline: float,
    current: float,
    metric_key: str,
    threshold_percent: float = 1.0,
) -> dict[str, Any]:
    lower_is_better = metric_key in LOWER_IS_BETTER_METRICS

    if baseline == 0:
        improvement_percent = 100.0 if current != 0 else 0.0
    elif lower_is_better:
        improvement_percent = ((baseline - current) / baseline) * 100
    else:
        improvement_percent = ((current - baseline) / baseline) * 100

    is_improved = improvement_percent >= threshold_percent

    return {
        "success": True,
        "metric_key": metric_key,
        "baseline": baseline,
        "current": current,
        "threshold_percent": threshold_percent,
        "improvement_percent": round(improvement_percent, 2),
        "is_improved": is_improved,
        "verdict": "KEEP" if is_improved else "REVERT",
        "direction": "lower_is_better" if lower_is_better else "higher_is_better",
    }


def text_response(payload: dict[str, Any]) -> list[types.TextContent]:
    return [
        types.TextContent(
            type="text",
            text=json.dumps(payload, indent=2, ensure_ascii=False),
        )
    ]
