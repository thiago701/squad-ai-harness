"""Módulo de contratos tipados e máquina de estados do pipeline — Fase E1.

Contém os 4 modelos JEV da Wave 1 de contratos (doc evolucao-dsa-2026-09-25/03),
como código determinístico estilo JevSim (US$ 0, <1 ms por decisão, stdlib pura):

- jev.contrato-artefato        -> validar_artefato()
- jev.maquina-estados-pipeline -> validar_transicao()
- jev.validador-plano          -> validar_plano()
- jev.escalonamento-humano     -> validar_escalonamento()

Doutrina (e-book SDD §5.2.1): "Regras de negócio críticas (particularmente
transições de estado) NÃO PODEM depender da boa vontade do modelo... O modelo
pode SUGERIR uma transição; o código de validação decide se a transição é
PERMITIDA."

P1-Simplicidade: stdlib apenas (json), regras explícitas por contrato. Os JSON
Schemas em contracts/artefatos/*.schema.json são a documentação canônica; os
campos obrigatórios aqui devem espelhá-los (teste anti-drift em
tests/test_contracts_validator.py).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_CONTRACTS_DIR = Path(__file__).resolve().parent

SCHEMA_VERSAO_ATUAL = 1
LIMITE_TAMANHO_CHARS = 50_000

TIPOS_ARTEFATO = ("prd", "plan", "relatorio_review", "retorno_delegacao")

# Campos obrigatórios por tipo — espelho de contracts/artefatos/*.schema.json
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "prd": ("objetivo", "criterios_aceite"),
    "plan": ("objetivo", "passos"),
    "passo": ("id", "descricao", "criterio_sucesso"),
    "relatorio_review": ("veredito", "resumo", "achados_seguranca_red", "testes_verdes"),
    "retorno_delegacao": ("status", "resumo", "evidencias", "artefatos"),
    "evidencia": ("tipo", "ref"),
}

# Retorno de delegação (Onda 2 / I6): o subagente afirma, o motor verifica.
STATUS_RETORNO_VALIDOS = ("concluido", "parcial", "bloqueado", "escalar")
TIPOS_EVIDENCIA_VALIDOS = ("comando", "teste", "arquivo", "diff", "metrica", "link")

VEREDITOS_VALIDOS = ("READY", "NOT_READY")

# Plano com oráculos (I5, plano de evolução de 11/10/2026) — espelho de plan.schema.json
TIPOS_ORACULO = ("teste", "comando", "archunit", "smoke", "contrato", "lint", "adr")
TIPOS_PASSO = ("implementacao", "arquitetura", "config", "infra", "teste", "docs", "dados")
ORACULOS_ARQUITETURA = ("smoke", "archunit", "adr")
TAMANHOS_COM_ORACULO = ("standard", "large")
TAMANHOS_PLANO = ("trivial", "small", "standard", "large")

FERRAMENTAS_DESTRUTIVAS = frozenset({
    "commit", "push", "merge", "delete", "deploy", "drop",
    "terraform_destroy", "revogar_secret",
})

# Máquina de estados — espelho de contracts/pipeline-state-machine.json
TRANSICOES: dict[str, dict[str, str]] = {}
TRANSICOES_TRIVIAL: dict[str, dict[str, str]] = {}
EVENTOS: tuple[str, ...] = ()


def _carregar_maquina_estados() -> None:
    global EVENTOS
    sm = json.loads((_CONTRACTS_DIR / "pipeline-state-machine.json").read_text(encoding="utf-8"))
    TRANSICOES.update(sm["transicoes"])
    TRANSICOES_TRIVIAL.update(sm["atalhos_trivial"])
    EVENTOS = tuple(sm["eventos"])


_carregar_maquina_estados()

ESTADOS: tuple[str, ...] = tuple(dict.fromkeys(
    list(TRANSICOES.keys()) + list(TRANSICOES_TRIVIAL.keys())))


# ---------------------------------------------------------------------------
# Verdictos tipados
# ---------------------------------------------------------------------------

@dataclass
class VereditoArtefato:
    tipo: str
    veredito: str            # CONFORME | INCONFORME_RETRY | INCONFORME_ESCALAR
    violacoes: list[dict] = field(default_factory=list)   # {campo, regra, severidade, valor, mensagem}
    schema_versao: int = SCHEMA_VERSAO_ATUAL


@dataclass
class VereditoTransicao:
    estado_atual: str
    evento: str
    destino: str | None
    transicao: str           # PERMITIDA | PROIBIDA | REQUER_GATE_HUMANO
    proximos_estados_validos: list[str] = field(default_factory=list)
    motivos_estruturados: list[dict] = field(default_factory=list)  # {regra, severidade, mensagem}
    motivo: str = ""


@dataclass
class VereditoPlano:
    valido: bool
    problemas: list[dict] = field(default_factory=list)  # {codigo, passo_id, mensagem}
    acao: str = "solicitar_revisao"                      # aceitar | solicitar_revisao


@dataclass
class VereditoEscalonamento:
    decisao: str             # AUTONOMO | APPROVAL_GATE | REVIEW_QUEUE | SAMPLING | BLOQUEADA
    razao: str = ""
    motivos_estruturados: list[dict] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# jev.contrato-artefato
# ---------------------------------------------------------------------------

def _violacao(campo: str, regra: str, severidade: str, valor, mensagem: str) -> dict:
    return {"campo": campo, "regra": regra, "severidade": severidade,
            "valor": valor, "mensagem": mensagem}


def _rejeicao_previa(tipo: str, dados, schema_versao: int) -> VereditoArtefato | None:
    """Guardas de fronteira (tipo, versão, estrutura): veredito de escalar ou None."""
    if tipo not in TIPOS_ARTEFATO:
        return VereditoArtefato(
            tipo, "INCONFORME_ESCALAR",
            [_violacao("tipo", "tipo_desconhecido", "blocker", tipo,
                       f"Tipo de artefato '{tipo}' não existe. Tipos válidos: "
                       f"{', '.join(TIPOS_ARTEFATO)}.")],
            schema_versao)

    if schema_versao != SCHEMA_VERSAO_ATUAL:
        return VereditoArtefato(
            tipo, "INCONFORME_ESCALAR",
            [_violacao("schema_versao", "schema_versao", "blocker", schema_versao,
                       f"Schema v{schema_versao} incompatível com v{SCHEMA_VERSAO_ATUAL}. "
                       "Migração de contrato deve ser declarada antes (migrations — SDD §3.11).")],
            schema_versao)

    if not isinstance(dados, dict):
        return VereditoArtefato(
            tipo, "INCONFORME_ESCALAR",
            [_violacao("estrutura", "estrutura_invalida", "blocker", type(dados).__name__,
                       f"Artefato '{tipo}' deve ser um objeto JSON; recebido "
                       f"{type(dados).__name__}. Não há retry possível.")],
            schema_versao)
    return None


def _campos_ausentes(tipo: str, dados: dict) -> list[dict]:
    """Presença física dos campos obrigatórios (vazio cai em tipo_invalido)."""
    return [
        _violacao(
            campo, "campo_obrigatorio", "necessary", None,
            f"Campo obrigatório '{campo}' ausente. Preencha com "
            f"{'uma frase objetiva' if campo == 'objetivo' else 'o valor conforme o contrato'} "
            "e reenvie o artefato.")
        for campo in REQUIRED_FIELDS[tipo]
        if campo not in dados or dados[campo] is None
    ]


def _validar_prd(dados: dict) -> list[dict]:
    violacoes: list[dict] = []
    if "objetivo" in dados:
        if not isinstance(dados["objetivo"], str):
            violacoes.append(_violacao("objetivo", "tipo_invalido", "necessary",
                                       dados["objetivo"], "objetivo deve ser string."))
        elif not dados["objetivo"].strip():
            violacoes.append(_violacao("objetivo", "tipo_invalido", "necessary",
                                       dados["objetivo"], "objetivo não pode ser vazio."))
    if "criterios_aceite" in dados:
        ca = dados["criterios_aceite"]
        if not isinstance(ca, list) or not ca or not all(isinstance(x, str) and x.strip() for x in ca):
            violacoes.append(_violacao(
                "criterios_aceite", "tipo_invalido", "necessary", ca,
                "criterios_aceite deve ser uma lista não vazia de strings não vazias."))
    return violacoes


def _validar_plan(dados: dict) -> list[dict]:
    violacoes: list[dict] = []
    passos = dados.get("passos")
    if passos is not None and (not isinstance(passos, list) or not passos):
        violacoes.append(_violacao(
            "passos", "tipo_invalido", "necessary", passos,
            "passos deve ser uma lista não vazia de passos."))
    elif isinstance(passos, list):
        for i, p in enumerate(passos):
            if not isinstance(p, dict):
                violacoes.append(_violacao(
                    f"passos[{i}]", "tipo_invalido", "necessary", p,
                    "Cada passo deve ser um objeto com id, descricao e criterio_sucesso."))
                continue
            for campo in REQUIRED_FIELDS["passo"]:
                if campo not in p or p[campo] is None:
                    violacoes.append(_violacao(
                        f"passos[{i}].{campo}", "campo_obrigatorio", "necessary", None,
                        f"Passo {i} sem '{campo}'. Todo passo precisa de id, descricao "
                        "e criterio de sucesso."))
                elif isinstance(p[campo], str) and not p[campo].strip():
                    violacoes.append(_violacao(
                        f"passos[{i}].{campo}", "tipo_invalido", "necessary", p[campo],
                        f"Campo '{campo}' do passo {i} não pode ser vazio."))
    return violacoes


def _validar_relatorio_review(dados: dict) -> tuple[list[dict], list[dict]]:
    """Retorna (violacoes, blockers)."""
    violacoes: list[dict] = []
    blockers: list[dict] = []
    v = dados.get("veredito")
    if v is not None and v not in VEREDITOS_VALIDOS:
        violacoes.append(_violacao(
            "veredito", "veredito_invalido", "necessary", v,
            f"Veredito '{v}' inválido — use READY ou NOT_READY (você enviou '{v}')."))
    if "resumo" in dados and isinstance(dados["resumo"], str) and not dados["resumo"].strip():
        violacoes.append(_violacao(
            "resumo", "tipo_invalido", "necessary", dados["resumo"],
            "resumo não pode ser vazio."))
    if "testes_verdes" in dados and not isinstance(dados["testes_verdes"], bool):
        violacoes.append(_violacao(
            "testes_verdes", "tipo_invalido", "necessary", dados["testes_verdes"],
            "testes_verdes deve ser booleano (true/false)."))
    if "achados_seguranca_red" in dados:
        r = dados["achados_seguranca_red"]
        if not isinstance(r, int) or isinstance(r, bool):
            violacoes.append(_violacao(
                "achados_seguranca_red", "tipo_invalido", "necessary", r,
                "achados_seguranca_red deve ser um inteiro >= 0."))
        elif r > 0:
            blockers.append(_violacao(
                "achados_seguranca_red", "seguranca_red", "blocker", r,
                f"{r} achado(s) 🔴 de segurança: bloqueante incondicional. "
                "Segurança nunca é negociável — escale ao engenheiro-seguranca."))
    return violacoes, blockers


def _violacao_tamanho(dados: dict) -> list[dict]:
    """SDD §4.3.4: spec que não cabe em uma página A4 = decompor."""
    try:
        tamanho = len(json.dumps(dados, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        tamanho = LIMITE_TAMANHO_CHARS + 1
    if tamanho <= LIMITE_TAMANHO_CHARS:
        return []
    return [_violacao(
        "tamanho", "tamanho_excedido", "necessary", tamanho,
        f"Artefato com {tamanho} chars excede o limite de {LIMITE_TAMANHO_CHARS}. "
        "Decomponha em artefatos menores.")]


def validar_artefato(tipo: str, dados, schema_versao: int = SCHEMA_VERSAO_ATUAL) -> VereditoArtefato:
    """Valida um artefato de handoff na fronteira da fase (fail-fast)."""
    rejeicao = _rejeicao_previa(tipo, dados, schema_versao)
    if rejeicao is not None:
        return rejeicao

    # 1. Campos obrigatórios AUSENTES; 2. tipos/enums/não-vazio (nunca duplicar achado do passo 1)
    violacoes = _campos_ausentes(tipo, dados)
    blockers: list[dict] = []
    if tipo == "prd":
        violacoes += _validar_prd(dados)
    elif tipo == "plan":
        violacoes += _validar_plan(dados)
    elif tipo == "relatorio_review":
        v, blockers = _validar_relatorio_review(dados)
        violacoes += v
    elif tipo == "retorno_delegacao":
        violacoes += _validar_retorno_delegacao(dados)

    # 3. Tamanho
    violacoes += _violacao_tamanho(dados)

    if blockers:
        return VereditoArtefato(tipo, "INCONFORME_ESCALAR", blockers + violacoes, schema_versao)
    if violacoes:
        return VereditoArtefato(tipo, "INCONFORME_RETRY", violacoes, schema_versao)
    return VereditoArtefato(tipo, "CONFORME", [], schema_versao)


def _validar_retorno_delegacao(dados: dict) -> list[dict]:
    """Regras do retorno subagente -> motor (contracts/artefatos/retorno-delegacao.schema.json).

    Tudo aqui é INCONFORME_RETRY (instrutivo): o subagente corrige e reenvia. Não há
    blocker — um retorno malformado nunca é motivo de escalar ao humano, é motivo de
    pedir o retorno certo (DISPATCH -> EVALUATE -> REFINE, até 2 follow-ups).
    """
    v: list[dict] = []
    status = dados.get("status")
    if status is not None and status not in STATUS_RETORNO_VALIDOS:
        v.append(_violacao("status", "status_invalido", "necessary", status,
                           f"status '{status}' inválido — use um de {', '.join(STATUS_RETORNO_VALIDOS)}."))
        status = None
    if "resumo" in dados and (not isinstance(dados["resumo"], str) or not dados["resumo"].strip()):
        v.append(_violacao("resumo", "tipo_invalido", "necessary", dados["resumo"],
                           "resumo deve ser string não vazia (até 3 frases)."))
    ev = dados.get("evidencias")
    if ev is not None:
        if not isinstance(ev, list):
            v.append(_violacao("evidencias", "tipo_invalido", "necessary", ev,
                               "evidencias deve ser uma lista de objetos {tipo, ref[, resultado]}."))
            ev = None
        else:
            for i, e in enumerate(ev):
                if not isinstance(e, dict):
                    v.append(_violacao(f"evidencias[{i}]", "tipo_invalido", "necessary", e,
                                       "Cada evidência deve ser um objeto com tipo e ref."))
                    continue
                for campo in REQUIRED_FIELDS["evidencia"]:
                    if campo not in e or e[campo] is None or (isinstance(e[campo], str) and not e[campo].strip()):
                        v.append(_violacao(f"evidencias[{i}].{campo}", "campo_obrigatorio", "necessary", None,
                                           f"Evidência {i} sem '{campo}'."))
                if e.get("tipo") is not None and e.get("tipo") not in TIPOS_EVIDENCIA_VALIDOS:
                    v.append(_violacao(f"evidencias[{i}].tipo", "tipo_invalido", "necessary", e.get("tipo"),
                                       f"tipo de evidência inválido — use um de {', '.join(TIPOS_EVIDENCIA_VALIDOS)}."))
    if status in ("concluido", "parcial") and ev is not None and not ev:
        v.append(_violacao("evidencias", "evidencia_ausente", "necessary", [],
                           f"status={status} exige ao menos uma evidência verificável (comando, teste, "
                           "arquivo:linha, diff, métrica). O subagente afirma, o motor verifica."))
    art = dados.get("artefatos")
    if art is not None and (not isinstance(art, list) or not all(isinstance(x, str) and x.strip() for x in art)):
        v.append(_violacao("artefatos", "tipo_invalido", "necessary", art,
                           "artefatos deve ser uma lista (pode ser vazia) de caminhos não vazios."))
    pend = dados.get("pendencias")
    if pend is not None and (not isinstance(pend, list) or not all(isinstance(x, str) and x.strip() for x in pend)):
        v.append(_violacao("pendencias", "tipo_invalido", "necessary", pend,
                           "pendencias deve ser uma lista de strings não vazias."))
    if status == "parcial" and not pend:
        v.append(_violacao("pendencias", "pendencia_ausente", "necessary", pend,
                           "status=parcial exige `pendencias` declarando o que ficou de fora."))
    motivo = dados.get("motivo")
    if status in ("bloqueado", "escalar") and (not isinstance(motivo, str) or not motivo.strip()):
        v.append(_violacao("motivo", "motivo_ausente", "necessary", motivo,
                           f"status={status} exige `motivo` não vazio (o que impediu / o que precisa de decisão)."))
    custo = dados.get("custo")
    if custo is not None:
        if not isinstance(custo, dict):
            v.append(_violacao("custo", "tipo_invalido", "necessary", custo, "custo deve ser um objeto."))
        else:
            for k in ("tokens", "turnos"):
                if k in custo and (not isinstance(custo[k], int) or isinstance(custo[k], bool) or custo[k] < 0):
                    v.append(_violacao(f"custo.{k}", "tipo_invalido", "necessary", custo[k],
                                       f"custo.{k} deve ser inteiro >= 0 e MEDIDO (nunca estimado)."))
    return v


def _vazio(valor) -> bool:
    if valor is None:
        return True
    if isinstance(valor, str):
        return not valor.strip()
    if isinstance(valor, (list, dict)):
        return len(valor) == 0
    return False


# ---------------------------------------------------------------------------
# jev.maquina-estados-pipeline
# ---------------------------------------------------------------------------

def validar_transicao(estado_atual: str, evento: str, *, tamanho: str = "standard",
                      aprovacao_humana: bool = False,
                      achados_criticos: int = 0) -> VereditoTransicao:
    """Decide se uma transição do pipeline é PERMITIDA/PROIBIDA/REQUER_GATE_HUMANO."""
    motivos: list[dict] = []
    destino: str | None = None
    transicao = "PROIBIDA"

    if estado_atual not in ESTADOS:
        return VereditoTransicao(
            estado_atual, evento, None, "PROIBIDA",
            motivos_estruturados=[_violacao(
                "estado", "estado_desconhecido", "necessary", estado_atual,
                f"Estado '{estado_atual}' não existe na máquina de estados. "
                f"Estados válidos: {', '.join(sorted(ESTADOS))}.")],
            motivo=f"Estado desconhecido: {estado_atual}")

    mapa = TRANSICOES_TRIVIAL if tamanho == "trivial" else TRANSICOES
    if evento not in EVENTOS:
        motivos.append(_violacao(
            "evento", "evento_desconhecido", "necessary", evento,
            f"Evento '{evento}' não existe no catálogo. Eventos válidos: {', '.join(EVENTOS)}."))
        return VereditoTransicao(estado_atual, evento, None, "PROIBIDA", [], motivos,
                                 motivo=f"Evento desconhecido: {evento}")
    if evento not in mapa.get(estado_atual, {}):
        validos = sorted(mapa.get(estado_atual, {}).values())
        motivos.append(_violacao(
            "evento", "transicao_ilegal", "necessary", evento,
            f"Transição '{estado_atual} --{evento}-> ?' ILEGAL. "
            f"A partir de '{estado_atual}' os destinos permitidos são: {validos or 'nenhum'}."))
        return VereditoTransicao(estado_atual, evento, None, "PROIBIDA", validos, motivos,
                                 motivo=f"Transição ilegal: {estado_atual} --{evento}-> ?")

    destino = mapa[estado_atual][evento]

    # Regra global 1: evento de gate exige aprovação humana
    if evento == "gate_aprovado" and not aprovacao_humana:
        motivos.append(_violacao(
            "gate", "gate_sem_humano", "necessary", aprovacao_humana,
            f"Transição para '{destino}' exige aprovação humana no GATE. "
            "Registre a aprovação antes de avançar (gated, not autonomous)."))
        return VereditoTransicao(estado_atual, evento, destino, "REQUER_GATE_HUMANO",
                                 sorted(mapa.get(estado_atual, {}).values()), motivos,
                                 motivo=f"Requer aprovação humana para {estado_atual} --{evento}-> {destino}")

    # Regra global 2: segurança nunca é negociável — 🔴 bloqueia commit
    if destino == "commit" and achados_criticos > 0:
        motivos.append(_violacao(
            "seguranca", "seguranca_critica", "blocker", achados_criticos,
            f"{achados_criticos} achado(s) críticos bloqueiam a transição para 'commit'. "
            "Corrija os achados 🔴 antes de qualquer avanço."))
        return VereditoTransicao(estado_atual, evento, destino, "PROIBIDA",
                                 sorted(mapa.get(estado_atual, {}).values()), motivos,
                                 motivo=f"Bloqueada por {achados_criticos} achado(s) críticos")

    transicao = "PERMITIDA"
    return VereditoTransicao(estado_atual, evento, destino, transicao,
                             sorted(mapa.get(estado_atual, {}).values()), motivos,
                             motivo=f"Transição permitida: {estado_atual} --{evento}-> {destino}")


# ---------------------------------------------------------------------------
# jev.validador-plano
# ---------------------------------------------------------------------------

def validar_plano(plano, ferramentas_permitidas: list[str] | None = None,
                  tamanho: str | None = None) -> VereditoPlano:
    """Valida o DAG do plano antes do GATE 1 (e-book DP §3.2: validar antes de executar).

    `tamanho` (ou `plano["tamanho"]`) liga as regras de oráculo do I5: em standard/large
    todo passo precisa de um oráculo executável (passo → alvo → oráculo) e um passo de
    arquitetura só aceita smoke, ArchUnit ou ADR executável. Consenso de agentes não é
    prova; o plano nasce verificável ou não chega ao humano.
    """
    problemas: list[dict] = []

    def prob(codigo: str, passo_id: str | None, mensagem: str) -> None:
        problemas.append({"codigo": codigo, "passo_id": passo_id, "mensagem": mensagem})

    if not isinstance(plano, dict) or not isinstance(plano.get("passos"), list) or not plano["passos"]:
        prob("plano_invalido", None,
             "Plano deve ser um objeto com 'passos' (lista não vazia).")
        return VereditoPlano(False, problemas)

    tamanho = tamanho or plano.get("tamanho")
    if tamanho is not None and tamanho not in TAMANHOS_PLANO:
        prob("tamanho_invalido", None,
             f"tamanho '{tamanho}' inválido — use um de {', '.join(TAMANHOS_PLANO)} (vem do preflight).")
        tamanho = None
    exige_oraculo = tamanho in TAMANHOS_COM_ORACULO

    passos = plano["passos"]
    ids: dict[str, int] = {}
    for i, p in enumerate(passos):
        if not isinstance(p, dict) or not p.get("id"):
            prob("plano_invalido", str(i), f"Passo {i} sem 'id' válido.")
            continue
        pid = str(p["id"])
        if pid in ids:
            prob("id_duplicado", pid, f"Id '{pid}' aparece mais de uma vez (passos {ids[pid]} e {i}).")
        ids[pid] = i

    for i, p in enumerate(passos):
        if not isinstance(p, dict) or not p.get("id"):
            continue
        pid = str(p["id"])
        deps = p.get("depende_de") or []
        if not isinstance(deps, list):
            deps = [deps]
        for d in deps:
            if d not in ids:
                prob("dependencia_inexistente", pid,
                     f"Passo '{pid}' depende de '{d}', que não existe no plano.")
        if "criterio_sucesso" not in p or _vazio(p.get("criterio_sucesso")):
            prob("sem_criterio_sucesso", pid,
                 f"Passo '{pid}' sem 'criterio_sucesso' — como saber que terminou certo?")
        fer = p.get("ferramenta")
        if fer and ferramentas_permitidas is not None and fer not in ferramentas_permitidas:
            prob("ferramenta_fora_allowlist", pid,
                 f"Ferramenta '{fer}' fora da allowlist: {ferramentas_permitidas}.")
        if fer in FERRAMENTAS_DESTRUTIVAS and not p.get("exige_gate"):
            prob("destrutivo_sem_gate", pid,
                 f"Passo '{pid}' usa ferramenta destrutiva '{fer}' sem 'exige_gate: true'. "
                 "Operações irreversíveis exigem gate explícito (SDD §2.3.3).")
        for codigo, msg in _problemas_oraculo(p, pid, exige_oraculo):
            prob(codigo, pid, msg)

    if _tem_ciclo(ids, passos):
        prob("ciclo_dependencias", None,
             "O grafo de dependências contém um ciclo — um DAG não pode ter ciclos.")

    valido = not problemas
    return VereditoPlano(valido, problemas, "aceitar" if valido else "solicitar_revisao")


def _problemas_oraculo(p: dict, pid: str, exige: bool) -> list[tuple[str, str]]:
    """Regras do oráculo por passo (I5). Devolve [(codigo, mensagem)]."""
    out: list[tuple[str, str]] = []
    tipo_passo = p.get("tipo_passo")
    if tipo_passo is not None and tipo_passo not in TIPOS_PASSO:
        out.append(("tipo_passo_invalido",
                    f"Passo '{pid}': tipo_passo '{tipo_passo}' inválido — use um de {', '.join(TIPOS_PASSO)}."))
        tipo_passo = None
    ora = p.get("oraculo")
    if ora is None:
        if exige:
            out.append(("sem_oraculo",
                        f"Passo '{pid}' sem 'oraculo' — em plano standard/large todo passo declara quem decide "
                        f"que ele terminou certo (teste, comando, archunit, smoke, contrato, lint ou adr). "
                        "Consenso não é prova."))
        return out
    if not isinstance(ora, dict):
        out.append(("oraculo_invalido", f"Passo '{pid}': oraculo deve ser um objeto {{tipo, ref[, esperado, comando]}}."))
        return out
    tipo = ora.get("tipo")
    ref = ora.get("ref")
    if tipo not in TIPOS_ORACULO:
        out.append(("oraculo_invalido",
                    f"Passo '{pid}': oraculo.tipo '{tipo}' inválido — use um de {', '.join(TIPOS_ORACULO)}."))
    if not isinstance(ref, str) or not ref.strip():
        out.append(("oraculo_invalido", f"Passo '{pid}': oraculo.ref vazio — aponte o teste/comando/regra/ADR."))
    if tipo == "adr":
        cmd = ora.get("comando")
        if not isinstance(cmd, str) or not cmd.strip():
            out.append(("adr_nao_executavel",
                        f"Passo '{pid}': oraculo adr sem 'comando' — um ADR só vale como oráculo quando há um "
                        "comando que verifica a decisão (ADR executável)."))
    if tipo_passo == "arquitetura" and tipo in TIPOS_ORACULO and tipo not in ORACULOS_ARQUITETURA:
        out.append(("arquitetura_sem_oraculo_executavel",
                    f"Passo '{pid}' é de arquitetura e usa oraculo '{tipo}' — decisão de arquitetura exige "
                    f"{', '.join(ORACULOS_ARQUITETURA)} (smoke, ArchUnit ou ADR executável)."))
    return out


def _tem_ciclo(ids: dict[str, int], passos: list) -> bool:
    """Detecção de ciclo por ordenação topológica (Kahn)."""
    adj: dict[str, set[str]] = {pid: set() for pid in ids}
    indegree: dict[str, int] = {pid: 0 for pid in ids}
    for p in passos:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        pid = str(p["id"])
        deps = p.get("depende_de") or []
        if not isinstance(deps, list):
            deps = [deps]
        for d in deps:
            if d in ids and d != pid:
                adj[d].add(pid)
                indegree[pid] = indegree.get(pid, 0) + 1
    fila = [pid for pid, g in indegree.items() if g == 0]
    visitados = 0
    while fila:
        atual = fila.pop()
        visitados += 1
        for viz in adj[atual]:
            indegree[viz] -= 1
            if indegree[viz] == 0:
                fila.append(viz)
    return visitados != len(ids)


# ---------------------------------------------------------------------------
# jev.escalonamento-humano
# ---------------------------------------------------------------------------

OPERACOES_DESTRUTIVAS = frozenset({
    "delete_arquivo", "terraform_destroy", "drop", "revogar_secret", "push_force",
})

LIMIAR_CONFIANCA = 0.6
LIMIAR_ESCALONAMENTO_ALERTA = 0.20


def validar_escalonamento(operacao: str, *, irreversivel: bool = False,
                          confianca: float = 1.0, fora_distribuicao: bool = False,
                          stake: str = "baixo", regulatorio: bool = False,
                          toca_seguranca: bool = False,
                          confirmacao_humana: bool = False,
                          escalonamento_historico_pct: float = 0.0) -> VereditoEscalonamento:
    """Decisão human-in-the-loop + gate de tools destrutivas (doc 03 §2.4)."""
    motivos: list[dict] = []
    alertas: list[str] = []

    # 1. Destrutiva sem confirmação humana explícita = BLOQUEADA (SDD §2.3.3)
    if operacao in OPERACOES_DESTRUTIVAS and not confirmacao_humana:
        motivos.append(_violacao(
            "confirmacao", "destrutiva_sem_confirmacao", "necessary", operacao,
            f"Operação '{operacao}' é destrutiva e exige confirmação humana explícita. "
            "Bloqueada até aprovação."))
        _registrar_alerta_maturidade(escalonamento_historico_pct, alertas)
        return VereditoEscalonamento("BLOQUEADA", f"Destrutiva '{operacao}' sem confirmação humana",
                                     motivos, alertas)

    # 2. Gatilhos de escalonamento (Harness §7.4)
    if toca_seguranca:
        motivos.append(_violacao(
            "seguranca", "seguranca_acionada", "necessary", True,
            "Ação toca auth/input/queries/cripto/secrets: acionar engenheiro-seguranca "
            "automaticamente e exigir zero achados 🔴."))
    if irreversivel:
        motivos.append(_violacao(
            "reversibilidade", "irreversivel", "necessary", True,
            "Operação irreversível: exige approval gate humano."))
    if confianca < LIMIAR_CONFIANCA:
        motivos.append(_violacao(
            "confianca", "confianca_baixa", "necessary", confianca,
            f"Confiança {confianca:.2f} abaixo do limiar {LIMIAR_CONFIANCA}: escalar."))
    if fora_distribuicao:
        motivos.append(_violacao(
            "distribuicao", "fora_distribuicao", "necessary", True,
            "Caso fora da distribuição conhecida: escalar."))
    if stake == "alto":
        motivos.append(_violacao(
            "stake", "stake_alto", "necessary", stake,
            "Stake alto: escalar."))
    if regulatorio:
        motivos.append(_violacao(
            "compliance", "regulatorio", "necessary", True,
            "Requisito regulatório: escalar."))

    _registrar_alerta_maturidade(escalonamento_historico_pct, alertas)

    if motivos:
        return VereditoEscalonamento(
            "APPROVAL_GATE",
            f"Escalonar para humano: {', '.join(m['regra'] for m in motivos)}",
            motivos, alertas)
    return VereditoEscalonamento("AUTONOMO", "Nenhum gatilho de escalonamento", [], alertas)


def _registrar_alerta_maturidade(pct: float, alertas: list[str]) -> None:
    if pct > LIMIAR_ESCALONAMENTO_ALERTA:
        alertas.append("alerta_sensors")
