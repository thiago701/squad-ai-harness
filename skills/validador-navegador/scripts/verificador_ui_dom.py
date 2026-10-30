#!/usr/bin/env python3
"""Verificador determinístico de Snapshot DOM/UI para o validador-navegador (Eixos 6, 7 e 8).

Avalia métricas geométricas e de acessibilidade extraídas via preview_inspect / preview_eval:
1. Overflow horizontal da página (scrollWidth > innerWidth) -> 🔴
2. Nome acessível ausente (WCAG 4.1.2) -> 🔴
3. Tamanho mínimo de alvo interativo (WCAG 2.2 SC 2.5.8 >= 24x24px -> 🔴; mobile < 44x44px -> 🟡)
4. Foco encoberto por elementos fixos/sticky (WCAG 2.2 SC 2.4.11 Focus Not Obscured) -> 🔴
5. Alinhamento de cards vizinhos na mesma linha (detecção de ausência de CSS Subgrid) -> 🟡

Uso CLI:
  python verificador_ui_dom.py --snapshot snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WCAG_MIN_TARGET_PX = 24.0
MOBILE_ERGONOMIC_TARGET_PX = 44.0


def check_horizontal_overflow(scroll_width: float, inner_width: float) -> list[dict[str, Any]]:
    """Detecta rolagem horizontal indesejada no viewport."""
    if scroll_width <= inner_width:
        return []
    return [
        {
            "severity": "🔴",
            "axis": 6,
            "rule": "LAYOUT_HORIZONTAL_OVERFLOW",
            "message": f"Overflow horizontal detectado: scrollWidth ({scroll_width}px) > innerWidth ({inner_width}px).",
        }
    ]


def _check_single_interactive_element(
    element: dict[str, Any],
    is_mobile: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    selector = str(element.get("selector", "<unknown>"))
    width = float(element.get("width", 0.0))
    height = float(element.get("height", 0.0))
    name = element.get("accessible_name")

    if name is not None and not str(name).strip():
        findings.append(
            {
                "severity": "🔴",
                "axis": 8,
                "rule": "WCAG_4_1_2_MISSING_NAME",
                "selector": selector,
                "message": f"Controle interativo '{selector}' sem nome acessível.",
            }
        )

    if width <= 0 or height <= 0:
        return findings

    if width < WCAG_MIN_TARGET_PX or height < WCAG_MIN_TARGET_PX:
        findings.append(
            {
                "severity": "🔴",
                "axis": 8,
                "rule": "WCAG_2_5_8_TARGET_SIZE_MIN",
                "selector": selector,
                "message": (
                    f"Alvo '{selector}' ({width:.0f}x{height:.0f}px) viola o mínimo WCAG 2.2 "
                    f"de {WCAG_MIN_TARGET_PX:.0f}x{WCAG_MIN_TARGET_PX:.0f}px."
                ),
            }
        )
        return findings

    if is_mobile and (width < MOBILE_ERGONOMIC_TARGET_PX or height < MOBILE_ERGONOMIC_TARGET_PX):
        findings.append(
            {
                "severity": "🟡",
                "axis": 7,
                "rule": "MOBILE_THUMB_ZONE_TARGET",
                "selector": selector,
                "message": (
                    f"Alvo mobile '{selector}' ({width:.0f}x{height:.0f}px) abaixo do recomendado "
                    f"ergonômico de {MOBILE_ERGONOMIC_TARGET_PX:.0f}x{MOBILE_ERGONOMIC_TARGET_PX:.0f}px."
                ),
            }
        )
    return findings


def check_target_sizes(
    interactive_elements: list[dict[str, Any]],
    is_mobile: bool = False,
) -> list[dict[str, Any]]:
    """Valida nomes acessíveis (WCAG 4.1.2) e dimensões de alvos interativos (WCAG 2.5.8)."""
    findings: list[dict[str, Any]] = []
    for element in interactive_elements:
        findings.extend(_check_single_interactive_element(element, is_mobile))
    return findings


def _intersection_area(box_a: dict[str, Any], box_b: dict[str, Any]) -> float:
    ax1 = float(box_a.get("x", 0.0))
    ay1 = float(box_a.get("y", 0.0))
    ax2 = ax1 + float(box_a.get("width", 0.0))
    ay2 = ay1 + float(box_a.get("height", 0.0))

    bx1 = float(box_b.get("x", 0.0))
    by1 = float(box_b.get("y", 0.0))
    bx2 = bx1 + float(box_b.get("width", 0.0))
    by2 = by1 + float(box_b.get("height", 0.0))

    overlap_x = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_y = max(0.0, min(ay2, by2) - max(ay1, by1))
    return overlap_x * overlap_y


def check_focus_not_obscured(
    focused_box: dict[str, Any] | None,
    sticky_overlays: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Verifica se o elemento com foco de teclado está encoberto por header/footer fixo (WCAG 2.4.11)."""
    if not focused_box:
        return []

    findings: list[dict[str, Any]] = []
    focused_sel = str(focused_box.get("selector", "activeElement"))
    for overlay in sticky_overlays:
        area = _intersection_area(focused_box, overlay)
        if area > 0.0:
            overlay_sel = str(overlay.get("selector", "sticky-overlay"))
            findings.append(
                {
                    "severity": "🔴",
                    "axis": 8,
                    "rule": "WCAG_2_4_11_FOCUS_OBSCURED",
                    "selector": focused_sel,
                    "message": (
                        f"Elemento focado '{focused_sel}' está obscurecido por '{overlay_sel}' "
                        f"(área de colisão: {area:.1f}px²)."
                    ),
                }
            )
    return findings


def check_sibling_card_alignment(
    card_boxes: list[dict[str, Any]],
    row_tolerance_px: float = 4.0,
    height_tolerance_px: float = 2.0,
) -> list[dict[str, Any]]:
    """Detecta desalinhamento vertical entre cards da mesma linha (ausência de CSS Subgrid)."""
    if len(card_boxes) < 2:
        return []

    rows: list[list[dict[str, Any]]] = []
    for card in sorted(card_boxes, key=lambda c: (float(c.get("y", 0.0)), float(c.get("x", 0.0)))):
        placed = False
        card_y = float(card.get("y", 0.0))
        for row in rows:
            row_y = float(row[0].get("y", 0.0))
            if abs(card_y - row_y) <= row_tolerance_px:
                row.append(card)
                placed = True
                break
        if not placed:
            rows.append([card])

    findings: list[dict[str, Any]] = []
    for row in rows:
        if len(row) < 2:
            continue
        bottoms = [float(c.get("y", 0.0)) + float(c.get("height", 0.0)) for c in row]
        drift = max(bottoms) - min(bottoms)
        if drift > height_tolerance_px:
            selectors = [str(c.get("selector", "card")) for c in row]
            findings.append(
                {
                    "severity": "🟡",
                    "axis": 6,
                    "rule": "SUBGRID_ROW_ALIGNMENT_DRIFT",
                    "selectors": selectors,
                    "message": (
                        f"Cards na mesma linha ({', '.join(selectors)}) apresentam diferença de base "
                        f"de {drift:.1f}px — considere usar 'grid-template-rows: subgrid'."
                    ),
                }
            )
    return findings


def evaluate_ui_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Avalia um snapshot completo do navegador e emite veredito PRONTO ou NAO_PRONTO."""
    viewport = snapshot.get("viewport", {})
    scroll_width = float(viewport.get("scrollWidth", 1280.0))
    inner_width = float(viewport.get("innerWidth", 1280.0))
    is_mobile = bool(viewport.get("isMobile", inner_width <= 480.0))

    findings: list[dict[str, Any]] = []
    findings.extend(check_horizontal_overflow(scroll_width, inner_width))
    findings.extend(check_target_sizes(snapshot.get("interactive_elements", []), is_mobile=is_mobile))
    findings.extend(
        check_focus_not_obscured(
            snapshot.get("focused_element"),
            snapshot.get("sticky_overlays", []),
        )
    )
    findings.extend(check_sibling_card_alignment(snapshot.get("cards", [])))

    blocking = [f for f in findings if f["severity"] == "🔴"]
    warnings = [f for f in findings if f["severity"] == "🟡"]
    verdict = "PRONTO" if not blocking else "NAO_PRONTO"

    return {
        "verdict": verdict,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificador determinístico de Snapshot DOM/UI")
    parser.add_argument("--snapshot", type=Path, required=True, help="Arquivo JSON com o snapshot DOM")
    args = parser.parse_args(argv)

    data = json.loads(args.snapshot.read_text(encoding="utf-8"))
    report = evaluate_ui_snapshot(data)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verdict"] == "PRONTO" else 1


if __name__ == "__main__":
    sys.exit(main())
