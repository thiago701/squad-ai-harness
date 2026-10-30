"""convergencia -- camada de convergencia do spec-drift-check (stdlib-only).

Tecnica absorvida (reescrita, sem copia) de github/spec-kit `/converge`,
commit 3238fa9285694dc539aeb9829b337bfd6aed7317, licenca MIT:
  - toda divergencia recebe UMA de 4 classes (ausente/parcial/contradiz/nao-pedido);
  - checkbox [x] em tasks.md nao prova nada -- so codigo/teste contam como evidencia;
  - o backlog de divergencias so cresce no fim e e idempotente (mesma chave nao repete).
"""
import os
import re

CLASSES = ("ausente", "parcial", "contradiz", "nao-pedido")
REQ_RE = re.compile(r"\b(FR\d+|RN\d+|AC\d+|US\d+|REQ[-_]?[A-Za-z0-9]+)\b")
TASK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*)$")
TASK_ID_RE = re.compile(r"\b(T\d+)\b")
CHAVE_RE = re.compile(r"^- \[[ xX]\] (\S+) \((" + "|".join(CLASSES) + r")\)")
CABECALHO = "# Backlog de divergencias (append-only; gerado por spec-drift-check)\n"


def ids(texto):
    return set(REQ_RE.findall(texto or ""))


def classificar(na_spec, tem_codigo, tem_teste, contradiz=False):
    """Classe da divergencia, ou None quando o item convergiu."""
    if not na_spec:
        return "nao-pedido" if tem_codigo else None
    if contradiz:
        return "contradiz"
    if not tem_codigo:
        return "ausente"
    return None if tem_teste else "parcial"


def achado(req, classe, motivo):
    return {"req": req, "classe": classe, "motivo": motivo}


def classificar_requisitos(spec_text, src_text, tests_text):
    """Forward (ausente/parcial) + reverse (nao-pedido) por ID, nao por substring."""
    spec, src, testes = ids(spec_text), ids(src_text), ids(tests_text)
    saida = []
    for req in sorted(spec | src):
        classe = classificar(req in spec, req in src, req in testes)
        if classe:
            motivo = {"ausente": "sem codigo", "parcial": "codigo sem teste",
                      "nao-pedido": "codigo cita ID fora da spec"}[classe]
            saida.append(achado(req, classe, motivo))
    return saida


def tarefas_sem_evidencia(tasks_text, evidencia_text):
    """[x] nao e evidencia: requisito de task marcada precisa aparecer em codigo/teste."""
    evidencia, saida = ids(evidencia_text), []
    for linha in (tasks_text or "").splitlines():
        m = TASK_RE.match(linha)
        if not m or m.group(1) == " ":
            continue
        tid = TASK_ID_RE.search(m.group(2))
        for req in sorted(ids(m.group(2)) - evidencia):
            rotulo = tid.group(1) if tid else "task"
            saida.append(achado(req, "ausente", f"{rotulo} marcada [x] sem evidencia em codigo/teste"))
    return saida


def parse_achado_manual(valor):
    """--achado REQ:classe:motivo (julgamento do agente, ex.: contradiz)."""
    req, classe, motivo = (valor.split(":", 2) + ["", ""])[:3]
    if classe not in CLASSES:
        raise ValueError(f"classe invalida: {classe!r} (use {', '.join(CLASSES)})")
    return achado(req.strip(), classe, motivo.strip() or "julgamento do agente")


def deduplicar(achados):
    vistos, saida = set(), []
    for item in achados:
        chave = (item["req"], item["classe"])
        if chave not in vistos:
            vistos.add(chave)
            saida.append(item)
    return saida


def anexar_backlog(caminho, achados):
    """Append-only + idempotente. Retorna quantos itens novos entraram (0 = arquivo intocado)."""
    existente = ""
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as handle:
            existente = handle.read()
    chaves = {m.groups() for m in map(CHAVE_RE.match, existente.splitlines()) if m}
    novos = [a for a in deduplicar(achados) if (a["req"], a["classe"]) not in chaves]
    if not novos:
        return 0
    prefixo = "" if existente else CABECALHO
    if existente and not existente.endswith("\n"):
        prefixo = "\n"
    linhas = [f"- [ ] {a['req']} ({a['classe']}) {a['motivo']}\n" for a in novos]
    with open(caminho, "a", encoding="utf-8") as handle:
        handle.write(prefixo + "".join(linhas))
    return len(novos)
