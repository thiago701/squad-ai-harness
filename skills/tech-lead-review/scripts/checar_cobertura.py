"""Auditoria de cobertura de um relatório de review (stdlib, determinístico).

Rejeita o relatório que não declara o que foi e o que NÃO foi revisado, para que
"nenhum achado" nunca seja lido como "tudo coberto". Técnica reescrita da fase de
auditoria pré-conclusão do `find-bugs` de getsentry/skills (Apache-2.0, @f57ada2).

Formato esperado (Markdown, dentro do relatório):

    ### Cobertura
    Revisado: src/a.py, src/b.py
    Não revisado: src/gen/x.py (motivo: código gerado)
    Categorias:
    - simplicidade: limpo
    - segurança: achado
    - performance: não verificado (motivo: sem carga de referência)
    ...
    Veredito: APROVADO

Uso: python checar_cobertura.py RELATORIO.md ARQUIVO_ALTERADO [...]   (exit 0 = aceito)
"""
import re
import sys
import unicodedata

CATEGORIAS = ("simplicidade", "performance", "custo", "seguranca", "negocio", "arquitetura")
STATUS = ("achado", "limpo", "nao verificado")
ALIASES = {"p1": "simplicidade", "p2": "performance", "p3": "custo"}
VEREDITOS_DE_APROVACAO = ("APROVADO",)  # inclui APROVADO COM DEBT / APROVADO_COM_RESSALVAS


def _norm(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower().strip()


def _itens(linha):
    """'a.py, b.py (motivo: x)' -> [('a.py', ''), ('b.py', 'x')]; 'nenhum' -> []."""
    corpo = linha.split(":", 1)[1].strip()
    if _norm(corpo) in ("", "nenhum", "-"):
        return []
    itens = []
    for parte in re.split(r",\s*(?![^()]*\))", corpo):
        m = re.match(r"\s*([^\s(]+)\s*(?:\((?:motivo:)?\s*([^)]*)\))?", parte)
        if m:
            itens.append((m.group(1), (m.group(2) or "").strip()))
    return itens


def _secao(relatorio):
    m = re.search(r"^#{2,4}\s*Cobertura\b.*$", relatorio, re.M | re.I)
    if not m:
        return None
    resto = relatorio[m.end():]
    fim = re.search(r"^#{1,4}\s", resto, re.M)
    return resto[: fim.start()] if fim else resto


def validar(relatorio, arquivos_alterados):
    """Retorna (aceito, motivos_de_rejeicao)."""
    secao = _secao(relatorio)
    if secao is None:
        return False, ["sem secao de Cobertura: 'nenhum achado' sem cobertura declarada"]
    motivos, revisados, nao_revisados, categorias = [], [], [], {}
    for linha in secao.splitlines():
        chave = _norm(linha.lstrip("-* "))
        if chave.startswith("revisado:"):
            revisados += _itens(linha)
        elif chave.startswith("nao revisado:"):
            nao_revisados += _itens(linha)
        elif ":" in chave:
            nome, valor = chave.split(":", 1)
            nome = ALIASES.get(nome, nome)
            if nome in CATEGORIAS:
                categorias[nome] = valor.strip()
    declarados = {a for a, _ in revisados} | {a for a, _ in nao_revisados}
    motivos += [f"arquivo alterado sem declaracao: {a}" for a in arquivos_alterados
                if a not in declarados]
    motivos += [f"nao revisado sem motivo: {a}" for a, m in nao_revisados if not m]
    lacunas = [a for a, _ in nao_revisados]
    for nome in CATEGORIAS:
        valor = categorias.get(nome)
        status = next((s for s in STATUS if valor is not None and valor.startswith(s)), None)
        if status is None:
            motivos.append(f"categoria sem status: {nome}")
        elif status == "nao verificado":
            lacunas.append(nome)
            if "motivo" not in valor:
                motivos.append(f"categoria nao verificada sem motivo: {nome}")
    veredito = re.search(r"^\W*Veredito\W*:?\s*\**\s*([A-Z_ ]+)", relatorio, re.M | re.I)
    texto_veredito = veredito.group(1).strip().upper() if veredito else ""
    if lacunas and texto_veredito.startswith(VEREDITOS_DE_APROVACAO):
        motivos.append("aprovacao com lacuna de cobertura: use NAO_VERIFICADO "
                       f"({', '.join(lacunas)})")
    return not motivos, motivos


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        aceito, motivos = validar(fh.read(), argv[2:])
    print("COBERTURA: ACEITA" if aceito else "COBERTURA: REJEITADA")
    for m in motivos:
        print(f"  - {m}")
    return 0 if aceito else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
