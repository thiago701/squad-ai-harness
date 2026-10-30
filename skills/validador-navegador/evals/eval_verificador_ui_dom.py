"""Evals executáveis do verificador determinístico de Snapshot DOM/UI (validador-navegador)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SKILL_DIR / "scripts" / "verificador_ui_dom.py"
A11Y_REF = SKILL_DIR / "references" / "acessibilidade-responsivo.md"

spec = importlib.util.spec_from_file_location("verificador_ui_dom", SCRIPT_PATH)
assert spec and spec.loader
verificador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verificador)


def test_clean_snapshot_returns_pronto() -> None:
    snapshot = {
        "viewport": {"scrollWidth": 1280, "innerWidth": 1280, "isMobile": False},
        "interactive_elements": [
            {"selector": "button.primary-cta", "width": 140, "height": 44, "accessible_name": "Salvar pedido"},
            {"selector": "a.nav-home", "width": 88, "height": 36, "accessible_name": "Início"},
        ],
        "focused_element": {"selector": "button.primary-cta", "x": 100, "y": 240, "width": 140, "height": 44},
        "sticky_overlays": [
            {"selector": "header.sticky-top", "x": 0, "y": 0, "width": 1280, "height": 64},
        ],
        "cards": [
            {"selector": ".card-1", "x": 24, "y": 120, "width": 380, "height": 260},
            {"selector": ".card-2", "x": 428, "y": 120, "width": 380, "height": 260},
        ],
    }
    report = verificador.evaluate_ui_snapshot(snapshot)
    assert report["verdict"] == "PRONTO"
    assert report["blocking_count"] == 0
    assert report["warning_count"] == 0


def test_detects_horizontal_overflow_and_wcag_target_size_violation() -> None:
    snapshot = {
        "viewport": {"scrollWidth": 430, "innerWidth": 375, "isMobile": True},
        "interactive_elements": [
            {"selector": "button.icon-close", "width": 18, "height": 18, "accessible_name": ""},
            {"selector": "button.secondary", "width": 32, "height": 32, "accessible_name": "Filtrar"},
        ],
        "focused_element": None,
        "sticky_overlays": [],
        "cards": [],
    }
    report = verificador.evaluate_ui_snapshot(snapshot)
    assert report["verdict"] == "NAO_PRONTO"
    rules = {f["rule"] for f in report["findings"]}
    assert "LAYOUT_HORIZONTAL_OVERFLOW" in rules
    assert "WCAG_4_1_2_MISSING_NAME" in rules
    assert "WCAG_2_5_8_TARGET_SIZE_MIN" in rules
    assert "MOBILE_THUMB_ZONE_TARGET" in rules


def test_detects_focus_obscured_by_sticky_header_wcag_2_4_11() -> None:
    snapshot = {
        "viewport": {"scrollWidth": 1280, "innerWidth": 1280, "isMobile": False},
        "interactive_elements": [],
        "focused_element": {"selector": "input#email", "x": 80, "y": 40, "width": 240, "height": 40},
        "sticky_overlays": [
            {"selector": "header.sticky", "x": 0, "y": 0, "width": 1280, "height": 72},
        ],
        "cards": [],
    }
    report = verificador.evaluate_ui_snapshot(snapshot)
    assert report["verdict"] == "NAO_PRONTO"
    assert report["blocking_count"] == 1
    assert report["findings"][0]["rule"] == "WCAG_2_4_11_FOCUS_OBSCURED"


def test_detects_sibling_card_alignment_drift_without_subgrid() -> None:
    snapshot = {
        "viewport": {"scrollWidth": 1280, "innerWidth": 1280, "isMobile": False},
        "interactive_elements": [],
        "focused_element": None,
        "sticky_overlays": [],
        "cards": [
            {"selector": ".plan-basic", "x": 40, "y": 200, "width": 320, "height": 280},
            {"selector": ".plan-pro", "x": 384, "y": 200, "width": 320, "height": 345},
        ],
    }
    report = verificador.evaluate_ui_snapshot(snapshot)
    assert report["verdict"] == "PRONTO"
    assert report["warning_count"] == 1
    assert report["findings"][0]["rule"] == "SUBGRID_ROW_ALIGNMENT_DRIFT"


def test_reference_documents_wcag_2_4_11_and_2_5_8_and_verifier_script() -> None:
    ref_text = A11Y_REF.read_text(encoding="utf-8")
    for token in ("2.4.11", "2.5.8", "subgrid", "verificador_ui_dom.py"):
        assert token in ref_text, f"Termo esperado ausente em acessibilidade-responsivo.md: {token}"
