"""Evals executáveis do auditor de Style Guide, Design Tokens W3C DTCG e Contraste WCAG 2.2."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SKILL_DIR / "scripts" / "auditor_style_guide_tokens.py"
SKILL_MD = SKILL_DIR / "SKILL.md"
STYLE_GUIDE_REF = SKILL_DIR / "references" / "style-guide-design-system.md"

spec = importlib.util.spec_from_file_location("auditor_style_guide_tokens", SCRIPT_PATH)
assert spec and spec.loader
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


def test_valid_dtcg_3_tier_token_tree() -> None:
    tree = {
        "primitive": {
            "color": {
                "$type": "color",
                "neutral-50": {"$value": "#f8fafc"},
                "neutral-900": {"$value": "#0f172a"},
                "brand-600": {"$value": "#1d4ed8"},
            },
            "space": {
                "$type": "dimension",
                "2": {"$value": "16px"},
            },
        },
        "semantic": {
            "surface": {
                "$type": "color",
                "card": {"$value": "{primitive.color.neutral-50}"},
            },
            "interactive": {
                "$type": "color",
                "primary": {"$value": "{primitive.color.brand-600}"},
            },
        },
        "component": {
            "button": {
                "bg": {"$type": "color", "$value": "{semantic.interactive.primary}"},
                "padding": {"$type": "dimension", "$value": "{primitive.space.2}"},
            },
        },
    }
    report = auditor.audit_dtcg_tokens(tree)
    assert report["valid"] is True
    assert report["token_count"] == 8
    assert report["resolved_tokens"]["component.button.bg"] == "#1d4ed8"
    assert report["resolved_tokens"]["component.button.padding"] == "16px"
    assert report["missing_types"] == []
    assert report["broken_aliases"] == []
    assert report["circular_aliases"] == []
    assert report["tier_violations"] == []


def test_dtcg_detects_broken_and_circular_aliases_and_tier_violations() -> None:
    tree = {
        "primitive": {
            "a": {"$type": "color", "$value": "{primitive.b}"},
            "b": {"$type": "color", "$value": "{primitive.a}"},
            "untyped": {"$value": "12px"},
        },
        "semantic": {
            "ghost": {"$type": "color", "$value": "{primitive.nonexistent}"},
        },
        "component": {
            "card": {
                "bg": {"$type": "color", "$value": "#ff0055"},
            },
        },
    }
    report = auditor.audit_dtcg_tokens(tree)
    assert report["valid"] is False
    assert "primitive.untyped" in report["missing_types"]
    assert "semantic.ghost -> {primitive.nonexistent}" in report["broken_aliases"]
    assert any("primitive.a -> primitive.b -> primitive.a" in c for c in report["circular_aliases"])
    assert "component.card.bg" in report["tier_violations"]


def test_wcag_contrast_calculation_aa_and_aaa() -> None:
    high_contrast = auditor.evaluate_wcag_contrast("#0f172a", "#ffffff")
    assert high_contrast["ratio"] > 15.0
    assert high_contrast["aa_pass"] is True
    assert high_contrast["aaa_pass"] is True

    low_contrast = auditor.evaluate_wcag_contrast("#94a3b8", "#ffffff")
    assert low_contrast["ratio"] < 3.0
    assert low_contrast["aa_pass"] is False
    assert low_contrast["aaa_pass"] is False

    ui_component = auditor.evaluate_wcag_contrast("#64748b", "#ffffff", is_ui_component=True)
    assert ui_component["ratio"] >= 3.0
    assert ui_component["aa_pass"] is True


def test_css_linter_catches_magic_colors_outline_none_and_missing_reduced_motion() -> None:
    bad_css = """
    :root {
      --color-surface-card: #ffffff;
    }
    .btn {
      background: #3b82f6;
      color: rgb(255, 255, 255);
      outline: none;
      transition: transform 200ms ease;
    }
    """
    report = auditor.audit_css_style_guide(bad_css, require_interactive_states=True)
    assert report["valid"] is False
    assert "#3b82f6" in report["magic_colors"]
    assert "rgb" in report["magic_colors"]
    assert report["outline_suppressed"] is True
    assert report["missing_reduced_motion"] is True
    assert "focus-visible" in report["missing_states"]


def test_css_linter_passes_clean_7_state_component() -> None:
    clean_css = """
    :root {
      --color-primary: #1d4ed8;
      --color-focus: #3b82f6;
      --color-error: #dc2626;
    }
    .btn {
      background: var(--color-primary);
      transition: transform var(--duration-fast) ease;
    }
    .btn:hover { filter: brightness(1.05); }
    .btn:focus-visible { outline: 2px solid var(--color-focus); }
    .btn:active { transform: scale(0.98); }
    .btn[aria-busy="true"] { pointer-events: none; }
    .btn:disabled, .btn[aria-disabled="true"] { opacity: 0.5; }
    .btn[aria-invalid="true"] { border-color: var(--color-error); }
    @media (prefers-reduced-motion: reduce) {
      .btn { transition: none; }
    }
    """
    report = auditor.audit_css_style_guide(clean_css, require_interactive_states=True)
    assert report["valid"] is True
    assert report["magic_colors"] == []
    assert report["outline_suppressed"] is False
    assert report["missing_reduced_motion"] is False
    assert report["missing_states"] == []


def test_skill_and_reference_document_oklch_and_zero_js_css() -> None:
    skill_text = SKILL_MD.read_text(encoding="utf-8")
    ref_text = STYLE_GUIDE_REF.read_text(encoding="utf-8")
    assert "OKLCH" in skill_text
    assert "auditor_style_guide_tokens.py" in skill_text
    for term in ("OKLCH", "light-dark(", "subgrid", "position-anchor", "@starting-style", "tabular-nums"):
        assert term in ref_text, f"Termo ausente em style-guide-design-system.md: {term}"
