#!/usr/bin/env python3
"""Auditor determinístico de Style Guide, Design Tokens (W3C DTCG), Contraste WCAG 2.2 e CSS Moderno.

Valida:
1. Árvores JSON de Design Tokens no padrão W3C DTCG ($type, $value, herança de grupo,
   resolução de aliases {a.b.c}, detecção de referências órfãs, ciclos circulares e
   violações de camada em component.*).
2. Cálculo exato de luminância relativa e razão de contraste WCAG 2.2 (AA 4.5:1 / 3.0:1 e AAA 7.0:1).
3. Linter estático de folhas de estilo CSS contra valores mágicos fora de :root,
   supressão de foco (:focus-visible), ausência de prefers-reduced-motion e cobertura
   dos 7 estados canônicos de componentes interativos.

Uso CLI:
  python auditor_style_guide_tokens.py --tokens tokens.json --css styles.css
  python auditor_style_guide_tokens.py --contrast "#0f172a" "#ffffff"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALIAS_PATTERN = re.compile(r"^\{([a-zA-Z0-9_.-]+)\}$")
HEX_COLOR_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RAW_COLOR_FUNC_PATTERN = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\s*\(")
OUTLINE_NONE_PATTERN = re.compile(r"outline\s*:\s*(?:none|0(?:px)?)\b", re.IGNORECASE)
MOTION_PATTERN = re.compile(r"(?:@keyframes\b|\btransition\s*:|\banimation\s*:)", re.IGNORECASE)
REDUCED_MOTION_PATTERN = re.compile(r"prefers-reduced-motion\s*:\s*reduce", re.IGNORECASE)

VALID_DTCG_TYPES = frozenset({
    "color",
    "dimension",
    "fontFamily",
    "fontWeight",
    "duration",
    "cubicBezier",
    "number",
    "shadow",
    "typography",
    "border",
    "transition",
    "gradient",
})

CANONICAL_STATES: dict[str, re.Pattern[str]] = {
    "default": re.compile(r"\.[a-zA-Z0-9_-]+\s*\{"),
    "hover": re.compile(r":hover\b"),
    "focus-visible": re.compile(r":focus-visible\b"),
    "active": re.compile(r":active\b"),
    "loading_busy": re.compile(r"\[aria-busy(?:=['\"]?true['\"]?)?\]"),
    "disabled": re.compile(r"(?::disabled\b|\[aria-disabled(?:=['\"]?true['\"]?)?\])"),
    "error_invalid": re.compile(r"\[aria-invalid(?:=['\"]?true['\"]?)?\]"),
}


def _collect_dtcg_nodes(
    node: dict[str, Any],
    prefix: str,
    inherited_type: str | None,
    flat_tokens: dict[str, dict[str, Any]],
    missing_types: list[str],
) -> None:
    current_type = node.get("$type", inherited_type)
    if "$value" in node:
        if not current_type or current_type not in VALID_DTCG_TYPES:
            missing_types.append(prefix)
        flat_tokens[prefix] = {
            "value": node["$value"],
            "type": current_type,
        }
        return

    for key, child in node.items():
        if key.startswith("$") or not isinstance(child, dict):
            continue
        child_prefix = f"{prefix}.{key}" if prefix else key
        _collect_dtcg_nodes(child, child_prefix, current_type, flat_tokens, missing_types)


def _resolve_single_token(
    token_path: str,
    flat_tokens: dict[str, dict[str, Any]],
    visited: list[str],
    broken_aliases: list[str],
    circular_aliases: list[str],
) -> Any:
    raw_val = flat_tokens[token_path]["value"]
    if not isinstance(raw_val, str):
        return raw_val

    match = ALIAS_PATTERN.match(raw_val.strip())
    if not match:
        return raw_val

    target_path = match.group(1)
    if target_path in visited:
        cycle_chain = " -> ".join([*visited, target_path])
        circular_aliases.append(cycle_chain)
        return raw_val

    if target_path not in flat_tokens:
        broken_aliases.append(f"{token_path} -> {{{target_path}}}")
        return raw_val

    return _resolve_single_token(
        target_path,
        flat_tokens,
        [*visited, target_path],
        broken_aliases,
        circular_aliases,
    )


def _check_component_tier_violation(
    token_path: str,
    raw_value: Any,
    token_type: str | None,
) -> bool:
    if not token_path.startswith("component."):
        return False
    if token_type != "color" or not isinstance(raw_value, str):
        return False
    return not ALIAS_PATTERN.match(raw_value.strip())


def audit_dtcg_tokens(token_tree: dict[str, Any]) -> dict[str, Any]:
    """Audita uma árvore JSON de Design Tokens segundo o padrão W3C DTCG."""
    flat_tokens: dict[str, dict[str, Any]] = {}
    missing_types: list[str] = []
    _collect_dtcg_nodes(token_tree, "", None, flat_tokens, missing_types)

    broken_aliases: list[str] = []
    circular_aliases: list[str] = []
    tier_violations: list[str] = []
    resolved_tokens: dict[str, Any] = {}

    for path, meta in flat_tokens.items():
        if _check_component_tier_violation(path, meta["value"], meta["type"]):
            tier_violations.append(path)
        resolved_tokens[path] = _resolve_single_token(
            path,
            flat_tokens,
            [path],
            broken_aliases,
            circular_aliases,
        )

    is_valid = (
        not missing_types
        and not broken_aliases
        and not circular_aliases
        and not tier_violations
    )
    return {
        "valid": is_valid,
        "token_count": len(flat_tokens),
        "resolved_tokens": resolved_tokens,
        "missing_types": sorted(set(missing_types)),
        "broken_aliases": sorted(set(broken_aliases)),
        "circular_aliases": sorted(set(circular_aliases)),
        "tier_violations": sorted(set(tier_violations)),
    }


def _parse_hex_rgb(hex_color: str) -> tuple[float, float, float]:
    cleaned = hex_color.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) != 6:
        raise ValueError(f"Cor hexadecimal inválida: {hex_color}")
    r = int(cleaned[0:2], 16) / 255.0
    g = int(cleaned[2:4], 16) / 255.0
    b = int(cleaned[4:6], 16) / 255.0
    return r, g, b


def _channel_luminance(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Calcula a luminância relativa WCAG 2.2 de uma cor hexadecimal."""
    r, g, b = _parse_hex_rgb(hex_color)
    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Calcula a razão de contraste WCAG 2.2 entre primeiro plano e fundo."""
    lum_a = relative_luminance(fg_hex)
    lum_b = relative_luminance(bg_hex)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def calculate_apca_lc(fg_hex: str, bg_hex: str) -> float:
    """Calcula o contraste perceptual direcional APCA 0.98G (Lc, WCAG 3.0 Draft)."""
    r_t, g_t, b_t = _parse_hex_rgb(fg_hex)
    r_b, g_b, b_b = _parse_hex_rgb(bg_hex)

    y_txt = 0.2126729 * (r_t ** 2.4) + 0.7151522 * (g_t ** 2.4) + 0.0721750 * (b_t ** 2.4)
    y_bg = 0.2126729 * (r_b ** 2.4) + 0.7151522 * (g_b ** 2.4) + 0.0721750 * (b_b ** 2.4)

    blk_thrs = 0.022
    blk_clmp = 1.414
    if y_txt < blk_thrs:
        y_txt += (blk_thrs - y_txt) ** blk_clmp
    if y_bg < blk_thrs:
        y_bg += (blk_thrs - y_bg) ** blk_clmp

    if abs(y_bg - y_txt) < 0.0005:
        return 0.0

    scale_bow = 1.14
    lo_offset = 0.027

    if y_bg > y_txt:
        sapc = ((y_bg ** 0.56) - (y_txt ** 0.57)) * scale_bow
        lc = 0.0 if sapc < 0.1 else (sapc - lo_offset) * 100.0
        return round(-abs(lc), 1)

    sapc = ((y_txt ** 0.62) - (y_bg ** 0.65)) * scale_bow
    lc = 0.0 if sapc < 0.1 else (sapc - lo_offset) * 100.0
    return round(abs(lc), 1)


def evaluate_wcag_contrast(
    fg_hex: str,
    bg_hex: str,
    is_large_text: bool = False,
    is_ui_component: bool = False,
) -> dict[str, Any]:
    """Avalia conformidade WCAG 2.2 AA/AAA e contraste perceptual APCA Lc para um par de cores."""
    ratio = contrast_ratio(fg_hex, bg_hex)
    apca_lc = calculate_apca_lc(fg_hex, bg_hex)
    abs_lc = abs(apca_lc)
    aa_threshold = 3.0 if (is_large_text or is_ui_component) else 4.5
    aaa_threshold = 4.5 if is_large_text else 7.0
    apca_min = 30.0 if is_ui_component else (45.0 if is_large_text else 60.0)
    return {
        "foreground": fg_hex,
        "background": bg_hex,
        "ratio": ratio,
        "aa_threshold": aa_threshold,
        "aaa_threshold": aaa_threshold,
        "aa_pass": ratio >= aa_threshold,
        "aaa_pass": ratio >= aaa_threshold,
        "apca_lc": apca_lc,
        "apca_min_lc": apca_min,
        "apca_pass": abs_lc >= apca_min,
        "apca_fluent_body": abs_lc >= 75.0,
    }


def _strip_root_and_comments(css_text: str) -> str:
    without_comments = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    return re.sub(r":root\s*\{[^}]*\}", "", without_comments, flags=re.DOTALL)


SCALE_ZERO_PATTERN = re.compile(r"\bscale\(\s*0(?:\.0+)?\s*\)", re.IGNORECASE)
LAYOUT_THRASH_TRANSITION_PATTERN = re.compile(
    r"transition(?:-property)?\s*:[^;]*\b(width|height|top|left|margin|padding)\b",
    re.IGNORECASE,
)


def audit_css_style_guide(
    css_text: str,
    require_interactive_states: bool = False,
) -> dict[str, Any]:
    """Audita CSS de componentes contra valores mágicos e lacunas de acessibilidade/estados/movimento."""
    component_css = _strip_root_and_comments(css_text)
    magic_hex = HEX_COLOR_PATTERN.findall(component_css)
    magic_funcs = RAW_COLOR_FUNC_PATTERN.findall(component_css)
    magic_colors = sorted(set(magic_hex + [fn.rstrip("(").strip() for fn in magic_funcs]))

    has_outline_none = bool(OUTLINE_NONE_PATTERN.search(component_css))
    has_focus_visible = bool(CANONICAL_STATES["focus-visible"].search(component_css))
    outline_suppressed = has_outline_none and not has_focus_visible

    has_motion = bool(MOTION_PATTERN.search(component_css))
    has_reduced_motion = bool(REDUCED_MOTION_PATTERN.search(css_text))
    missing_reduced_motion = has_motion and not has_reduced_motion

    has_scale_zero = bool(SCALE_ZERO_PATTERN.search(component_css))
    layout_thrash_props = sorted(set(LAYOUT_THRASH_TRANSITION_PATTERN.findall(component_css)))

    present_states = [
        state for state, pattern in CANONICAL_STATES.items() if pattern.search(component_css)
    ]
    missing_states = [
        state for state in CANONICAL_STATES if state not in present_states
    ]

    states_ok = (not missing_states) if require_interactive_states else True
    is_valid = (
        not magic_colors
        and not outline_suppressed
        and not missing_reduced_motion
        and states_ok
    )

    return {
        "valid": is_valid,
        "magic_colors": magic_colors,
        "outline_suppressed": outline_suppressed,
        "missing_reduced_motion": missing_reduced_motion,
        "scale_zero_anti_pattern": has_scale_zero,
        "layout_thrashing_transitions": layout_thrash_props,
        "present_states": present_states,
        "missing_states": missing_states,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditor de Style Guide e Design Tokens W3C DTCG")
    parser.add_argument("--tokens", type=Path, help="Caminho para arquivo JSON de tokens W3C DTCG")
    parser.add_argument("--css", type=Path, help="Caminho para arquivo CSS a auditar")
    parser.add_argument(
        "--require-states",
        action="store_true",
        help="Exigir presença dos 7 estados canônicos de componentes interativos no CSS",
    )
    parser.add_argument(
        "--contrast",
        nargs=2,
        metavar=("FG_HEX", "BG_HEX"),
        help="Calcula contraste WCAG 2.2 entre duas cores hexadecimais",
    )
    args = parser.parse_args(argv)

    exit_code = 0
    output: dict[str, Any] = {}

    if args.tokens:
        tree = json.loads(args.tokens.read_text(encoding="utf-8"))
        token_report = audit_dtcg_tokens(tree)
        output["tokens_report"] = token_report
        if not token_report["valid"]:
            exit_code = 1

    if args.css:
        css_content = args.css.read_text(encoding="utf-8")
        css_report = audit_css_style_guide(css_content, require_interactive_states=args.require_states)
        output["css_report"] = css_report
        if not css_report["valid"]:
            exit_code = 1

    if args.contrast:
        contrast_report = evaluate_wcag_contrast(args.contrast[0], args.contrast[1])
        output["contrast_report"] = contrast_report
        if not contrast_report["aa_pass"]:
            exit_code = 1

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
