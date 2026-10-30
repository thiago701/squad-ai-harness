#!/usr/bin/env python3
"""Gate de cobertura Quarkus: uniao per-classe (max) dos dois relatorios jacoco.

Por que: o QuarkusClassLoader transforma classes; o exec do agente unit e o
relatorio do quarkus-jacoco enxergam conjuntos diferentes. A uniao per-classe
usa a MELHOR medicao de cada classe (sem dupla contagem dentro da classe).
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MINIMO = 90.0
FONTES = ["target/site/jacoco/jacoco.xml", "target/jacoco-report/jacoco.xml"]


def por_classe(caminho):
    if not Path(caminho).is_file():
        return {}
    resultado = {}
    for cls in ET.parse(caminho).getroot().iter("class"):
        linha = next((c for c in cls.findall("counter") if c.get("type") == "LINE"), None)
        if linha is not None:
            resultado[cls.get("name")] = (int(linha.get("covered")), int(linha.get("missed")))
    return resultado


def main():
    fontes = [por_classe(f) for f in FONTES]
    classes = set().union(*[set(f) for f in fontes])
    cobertas = perdidas = 0
    for nome in sorted(classes):
        medicoes = [f[nome] for f in fontes if nome in f]
        cov, miss = max(medicoes, key=lambda par: par[0] / max(1, par[0] + par[1]))
        cobertas += cov
        perdidas += miss
    total = cobertas + perdidas
    pct = round(100 * cobertas / total, 2) if total else 0.0
    print(f"cobertura (uniao per-classe): {cobertas}/{total} = {pct}%")
    return 0 if pct >= MINIMO else 1


if __name__ == "__main__":
    sys.exit(main())
