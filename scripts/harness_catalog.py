#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_PATH = ROOT_DIR / "config" / "harness-models.yaml"
PROFILES_PATH = ROOT_DIR / "config" / "harness-profiles.yaml"
LEGACY_PROFILE_MIGRATIONS = {
    "default": "frontier_default",
    "frontier_low_cost": "frontier_cost_guarded",
    "local_reasoning": "local_lab",
    "low_latency_apfel": "local_lab",
    "preview_nvfp4": "local_lab",
}
FRONTIER_PROVIDERS = {"google", "anthropic", "openai"}


def load_json_yaml(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bool_env(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def ollama_tags() -> dict:
    override = os.environ.get("ANGELLA_OLLAMA_TAGS_JSON")
    if override:
        try:
            return json.loads(override)
        except Exception:
            return {"models": []}
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {"models": []}


def model_present(tags: dict, model_name: str) -> bool:
    return any(item.get("name") == model_name for item in tags.get("models", []))


def apfel_healthy(base_url: str) -> bool:
    override = os.environ.get("ANGELLA_APFEL_HEALTHCHECK_OK")
    if override == "1":
        return True
    if override == "0":
        return False

    base = base_url.rstrip("/")
    candidates = [f"{base}/models", f"{base}/v1/models", base]
    for url in candidates:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            continue
    return False


def availability_for_model(model: dict, tags: dict) -> tuple[bool, list[str], bool]:
    reasons: list[str] = []
    provisionable = False

    for env_name in model.get("requires_env", []):
        if not os.environ.get(env_name):
            reasons.append(f"missing_env:{env_name}")

    for check in model.get("availability_check", []):
        if check.startswith("ollama_model:"):
            model_name = check.split(":", 1)[1]
            if not tags.get("models"):
                if model.get("auto_pull_on_bootstrap", False):
                    provisionable = True
                else:
                    reasons.append("ollama_unreachable")
            elif not model_present(tags, model_name):
                if model.get("auto_pull_on_bootstrap", False):
                    provisionable = True
                else:
                    reasons.append(f"missing_model:{model_name}")
        elif check.startswith("env_flag:"):
            expr = check.split(":", 1)[1]
            key, expected = expr.split("=", 1)
            if os.environ.get(key) != expected:
                reasons.append(f"missing_flag:{expr}")
        elif check == "apfel_health":
            base_url = os.environ.get("ANGELLA_APFEL_BASE_URL", "")
            if not base_url:
                reasons.append("missing_env:ANGELLA_APFEL_BASE_URL")
            elif not apfel_healthy(base_url):
                reasons.append("apfel_healthcheck_failed")

    enabled = not reasons
    if not enabled and provisionable and reasons == [reason for reason in reasons if reason.startswith("missing_model:")]:
        enabled = True
        reasons = []

    return enabled, reasons, provisionable


def selector_sort_key(selector: str, model: dict):
    if selector == "best_reasoning_frontier":
        return (
            model["reasoning_score"],
            model["tool_use_score"],
            model["stability_score"],
            model["priority"],
        )
    if selector == "best_coding_frontier":
        return (
            model["tool_use_score"],
            model["reasoning_score"],
            model["latency_score"],
            model["priority"],
        )
    if selector == "best_reasoning_frontier_low_cost":
        return (
            model["reasoning_score"],
            model["cost_score"],
            model["stability_score"],
            model["priority"],
        )
    if selector == "best_local_low_latency":
        return (
            model["latency_score"],
            model["tool_use_score"],
            model["stability_score"],
            model["priority"],
        )
    if selector == "best_local_fallback":
        return (
            model["reasoning_score"],
            model["stability_score"],
            model["cost_score"],
            model["priority"],
        )
    return (
        model["tool_use_score"],
        model["reasoning_score"],
        model["stability_score"],
        model["priority"],
    )


def selector_candidates(selector: str, models: list[dict], role: str) -> list[dict]:
    if selector.startswith("best_reasoning_frontier") or selector.startswith("best_coding_frontier"):
        return [m for m in models if role in m["role_support"] and m["provider"] in FRONTIER_PROVIDERS]
    if selector == "best_local_low_latency":
        return [m for m in models if role in m["role_support"] and "low_latency" in m.get("flags", [])]
    if selector == "best_local_fallback":
        return [m for m in models if role in m["role_support"] and m.get("tier") == "local"]
    return [m for m in models if role in m["role_support"]]


def choose_model(selector: str, models: list[dict], role: str, required_flags: list[str]) -> tuple[dict | None, list[dict]]:
    candidates = []
    for model in selector_candidates(selector, models, role):
        if all(flag in model.get("flags", []) for flag in required_flags):
            candidates.append(model)

    if not candidates:
        return None, []

    ordered = sorted(candidates, key=lambda item: selector_sort_key(selector, item), reverse=True)
    return ordered[0], ordered


def resolve_catalog(models: list[dict]) -> list[dict]:
    tags = ollama_tags()
    resolved = []
    for model in models:
        enabled, reasons, provisionable = availability_for_model(model, tags)
        item = dict(model)
        item["enabled"] = enabled
        item["disabled_reason"] = ",".join(reasons)
        item["provisionable"] = provisionable
        resolved.append(item)
    return resolved


def get_profile_map(profiles: list[dict]) -> dict[str, dict]:
    return {profile["id"]: profile for profile in profiles}


def get_default_profile(profiles: list[dict]) -> dict:
    for profile in profiles:
        if profile.get("default"):
            return profile
    return profiles[0]


def _legacy_profile_error(profile_id: str) -> SystemExit:
    replacement = LEGACY_PROFILE_MIGRATIONS.get(profile_id)
    if replacement:
        return SystemExit(
            f"Legacy harness profile `{profile_id}` has been removed. Use `{replacement}` instead."
        )
    return SystemExit(f"Unknown harness profile: {profile_id}")


def _frontier_reachable(resolved_models: list[dict], role: str) -> bool:
    return any(
        role in model["role_support"] and model["provider"] in FRONTIER_PROVIDERS and model["enabled"]
        for model in resolved_models
    )


def _fallback_reason(profile: dict, resolved_models: list[dict]) -> str:
    active: list[str] = []
    if _bool_env("ANGELLA_PRIVATE_MODE"):
        active.append("private_mode")
    if _bool_env("ANGELLA_FRONTIER_TOKEN_LIMITED"):
        active.append("token_limited")
    if _bool_env("ANGELLA_FRONTIER_NETWORK_BLOCKED"):
        active.append("network_blocked")
    frontier_reachable_env = os.environ.get("ANGELLA_FRONTIER_REACHABLE", "").strip().lower()
    if frontier_reachable_env in {"0", "false", "no", "off"}:
        active.append("frontier_unreachable")
    elif not _frontier_reachable(resolved_models, "worker"):
        active.append("frontier_unreachable")

    for reason in profile.get("fallback_when_any", []):
        if reason in active:
            return reason
    return ""


def resolve_selection(
    resolved_models: list[dict],
    profiles: list[dict],
    profile_id: str | None,
    lead_override: str | None,
    planner_override: str | None,
    worker_override: str | None,
) -> dict:
    if profile_id in LEGACY_PROFILE_MIGRATIONS:
        raise _legacy_profile_error(profile_id or "")

    profile = get_profile_map(profiles).get(profile_id) if profile_id else get_default_profile(profiles)
    if profile is None:
        raise _legacy_profile_error(profile_id or "")

    by_id = {model["id"]: model for model in resolved_models}

    def select(role: str, selector: str, override: str | None) -> dict:
        required_flags = profile.get("capability_flags", {}).get(f"{role}_required_flags", [])
        if override:
            selected = by_id.get(override)
            if selected is None:
                raise SystemExit(f"Unknown model id for {role}: {override}")
            if role not in selected["role_support"]:
                raise SystemExit(f"Model {override} does not support role {role}")
            if not all(flag in selected.get("flags", []) for flag in required_flags):
                raise SystemExit(f"Model {override} does not satisfy required flags for {role}")
            if not selected["enabled"]:
                raise SystemExit(f"Model {override} is unavailable: {selected['disabled_reason']}")
            return selected

        selected, _ = choose_model(selector, [model for model in resolved_models if model["enabled"]], role, required_flags)
        if selected is None:
            raise SystemExit(f"No available model resolved for {role} with selector {selector}")
        return selected

    lead = select("lead", profile["lead_selector"], lead_override)
    planner = select("planner", profile["planner_selector"], planner_override) if planner_override or profile.get("planner_selector") else lead

    fallback_reason = ""
    worker_selector = profile["worker_selector"]
    if worker_override:
        worker = select("worker", worker_selector, worker_override)
    else:
        fallback_reason = _fallback_reason(profile, resolved_models)
        if fallback_reason and profile.get("fallback_worker_selector"):
            worker_selector = profile["fallback_worker_selector"]
        worker = select("worker", worker_selector, None)

    worker_tier = profile.get("worker_tier_default", "frontier_primary")
    if worker.get("tier") == "local":
        if profile["id"] == "frontier_private_fallback":
            worker_tier = "local_fallback"
        elif profile["id"] == "local_lab":
            worker_tier = "local_augment"
        else:
            worker_tier = "local_cache"

    frontier_reachable = _frontier_reachable(resolved_models, "worker") and not _bool_env("ANGELLA_FRONTIER_NETWORK_BLOCKED")
    local_cache_enabled = bool(profile.get("local_cache_enabled", False))
    token_saver_enabled = bool(profile.get("token_saver_enabled", False))

    return {
        "profile": profile,
        "lead": lead,
        "planner": planner,
        "worker": worker,
        "capabilities": {
            "apfel_enabled": worker["id"] == "apfel_foundationmodel",
            "mlx_preview_enabled": "preview" in worker.get("flags", []),
            "nvfp4_enabled": "preview" in worker.get("flags", []),
        },
        "routing": {
            "execution_mode": profile.get("execution_mode", "frontier_primary"),
            "worker_tier": worker_tier,
            "fallback_reason": fallback_reason,
            "frontier_reachable": frontier_reachable,
            "local_cache_enabled": local_cache_enabled,
            "token_saver_enabled": token_saver_enabled,
        },
    }


def print_list_models(resolved_models: list[dict]) -> None:
    for model in resolved_models:
        status = "enabled"
        if not model["enabled"]:
            status = f"disabled ({model['disabled_reason']})"
        elif model.get("provisionable"):
            status = "enabled (will auto-pull)"

        print(
            f"{model['id']}: roles={','.join(model['role_support'])} "
            f"provider={model['goose_provider']} model={model['model']} tier={model.get('tier', 'unknown')} status={status}"
        )


def print_list_profiles(resolved_models: list[dict], profiles: list[dict]) -> None:
    for profile in profiles:
        try:
            resolved = resolve_selection(resolved_models, profiles, profile["id"], None, None, None)
            print(
                f"{profile['id']}: lead={resolved['lead']['id']} "
                f"planner={resolved['planner']['id']} worker={resolved['worker']['id']} "
                f"mode={resolved['routing']['execution_mode']} worker_tier={resolved['routing']['worker_tier']}"
            )
        except SystemExit as error:
            print(f"{profile['id']}: disabled ({error})")


def shell_escape(value: str) -> str:
    return shlex.quote(value)


def print_shell_resolution(resolution: dict) -> None:
    profile = resolution["profile"]
    lead = resolution["lead"]
    planner = resolution["planner"]
    worker = resolution["worker"]
    capabilities = resolution["capabilities"]
    routing = resolution["routing"]

    values = {
        "ANGELLA_HARNESS_PROFILE_ID": profile["id"],
        "ANGELLA_LEAD_MODEL_ID": lead["id"],
        "ANGELLA_PLANNER_MODEL_ID": planner["id"],
        "ANGELLA_WORKER_MODEL_ID": worker["id"],
        "ANGELLA_LEAD_PROVIDER": lead["goose_provider"],
        "ANGELLA_LEAD_MODEL": lead["model"],
        "ANGELLA_LEAD_CONTEXT_LIMIT": str(lead["context_limit"]),
        "ANGELLA_LEAD_TEMPERATURE": str(lead["temperature_default"]),
        "ANGELLA_PLANNER_PROVIDER": planner["goose_provider"],
        "ANGELLA_PLANNER_MODEL": planner["model"],
        "ANGELLA_PLANNER_CONTEXT_LIMIT": str(planner["context_limit"]),
        "ANGELLA_PLANNER_TEMPERATURE": str(planner["temperature_default"]),
        "ANGELLA_WORKER_PROVIDER": worker["goose_provider"],
        "ANGELLA_WORKER_MODEL": worker["model"],
        "ANGELLA_WORKER_CONTEXT_LIMIT": str(worker["context_limit"]),
        "ANGELLA_WORKER_TEMPERATURE": str(worker["temperature_default"]),
        "ANGELLA_MLX_PREVIEW_ENABLED": "true" if capabilities["mlx_preview_enabled"] else "false",
        "ANGELLA_NVFP4_ENABLED": "true" if capabilities["nvfp4_enabled"] else "false",
        "ANGELLA_APFEL_ENABLED": "true" if capabilities["apfel_enabled"] else "false",
        "ANGELLA_EXECUTION_MODE": routing["execution_mode"],
        "ANGELLA_WORKER_TIER": routing["worker_tier"],
        "ANGELLA_FALLBACK_REASON": routing["fallback_reason"],
        "ANGELLA_FRONTIER_REACHABLE": "true" if routing["frontier_reachable"] else "false",
        "ANGELLA_LOCAL_CACHE_ENABLED": "true" if routing["local_cache_enabled"] else "false",
        "ANGELLA_TOKEN_SAVER_ENABLED": "true" if routing["token_saver_enabled"] else "false",
        "ANGELLA_NON_GOALS_JSON": json.dumps(profile.get("non_goals", []), ensure_ascii=False),
        "ANGELLA_MLX_POLICY_JSON": json.dumps(profile.get("mlx_policy", {}), ensure_ascii=False),
    }

    for key, value in values.items():
        print(f"{key}={shell_escape(value)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-models")
    subparsers.add_parser("list-profiles")

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--profile")
    resolve_parser.add_argument("--lead-model")
    resolve_parser.add_argument("--planner-model")
    resolve_parser.add_argument("--worker-model")
    resolve_parser.add_argument("--format", choices=["shell", "json"], default="shell")

    args = parser.parse_args()

    models_config = load_json_yaml(MODELS_PATH)
    profiles_config = load_json_yaml(PROFILES_PATH)
    resolved_models = resolve_catalog(models_config["models"])

    if args.command == "list-models":
        print_list_models(resolved_models)
        return

    if args.command == "list-profiles":
        print_list_profiles(resolved_models, profiles_config["profiles"])
        return

    resolution = resolve_selection(
        resolved_models,
        profiles_config["profiles"],
        args.profile,
        args.lead_model,
        args.planner_model,
        args.worker_model,
    )

    if args.format == "json":
        print(json.dumps(resolution, indent=2, ensure_ascii=False))
    else:
        print_shell_resolution(resolution)


if __name__ == "__main__":
    main()
