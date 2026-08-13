"""Pure, deterministic forecasting search policy for Foundry kernel execution."""

from __future__ import annotations

import hashlib
import json
from typing import Any


class PolicyContractError(ValueError):
    """Raised when the bounded forecasting policy input is unsafe or incomplete."""


def _require_sha256(value: object, field: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise PolicyContractError(f"{field} must be a lowercase SHA-256")
    return text


def build_policy(request: dict[str, Any]) -> dict[str, Any]:
    """Return candidate policy only; model execution and approval remain in Foundry."""
    if request.get("schema_version") != "autoresearch-policy-input/v1":
        raise PolicyContractError("unsupported schema_version")
    if request.get("task_type") != "forecasting":
        raise PolicyContractError("predictor policy requires task_type=forecasting")
    study_id = str(request.get("study_id") or "")
    target = str(request.get("target_column") or "")
    inputs = tuple(str(item) for item in request.get("input_pool") or ())
    windows = tuple(request.get("windows") or ())
    horizons = tuple(int(item) for item in request.get("forecast_horizons") or ())
    budget = request.get("budget") or {}
    if not study_id or not target or not inputs:
        raise PolicyContractError("study_id, target_column, and input_pool are required")
    if target in inputs:
        raise PolicyContractError("target leakage: target_column is present in input_pool")
    if len(inputs) != len(set(inputs)):
        raise PolicyContractError("input_pool must be unique")
    if len(windows) < 2:
        raise PolicyContractError("self-consistency requires at least two fixed windows")
    if not horizons or any(value <= 0 for value in horizons):
        raise PolicyContractError("forecasting requires strictly positive t+0 horizons")
    for field in ("input_asset_sha256", "target_definition_sha256", "acceptance_sha256"):
        _require_sha256(request.get(field), field)
    maximum = int(budget.get("max_candidates", 0))
    if maximum < 1:
        raise PolicyContractError("budget.max_candidates must be positive")

    candidates: list[dict[str, Any]] = []
    for horizon in sorted(set(horizons)):
        candidates.append(_candidate("full", inputs, horizon, windows))
        if request.get("enable_input_ablation", True):
            for removed in reversed(inputs):
                remaining = tuple(item for item in inputs if item != removed)
                if remaining:
                    candidates.append(_candidate(f"without-{removed}", remaining, horizon, windows))
    candidates = candidates[:maximum]
    fingerprint = hashlib.sha256(
        json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": "autoresearch-policy-result/v1",
        "status": "needs_human",
        "policy_name": "predictor-bounded-search",
        "policy_version": "v1",
        "task_type": "forecasting",
        "study_id": study_id,
        "request_fingerprint": fingerprint,
        "facts": [
            {"kind": "fixed_windows", "count": len(windows)},
            {"kind": "candidate_budget", "count": maximum},
        ],
        "candidates": candidates,
        "issues": [],
        "next_actions": [
            {"code": "execute_via_fde_kernel_provider"},
            {"code": "await_data_modeling_engineer_selection"},
        ],
    }


def _candidate(
    label: str, inputs: tuple[str, ...], horizon: int, windows: tuple[object, ...]
) -> dict[str, Any]:
    return {
        "candidate_id": f"h{horizon}-{label}",
        "input_columns": list(inputs),
        "forecast_horizon": horizon,
        "window_ids": [str(window["window_id"]) for window in windows],
        "kernel_config": {
            "task_type": "forecasting",
            "input_columns": list(inputs),
            "forecast_horizon": horizon,
        },
    }
