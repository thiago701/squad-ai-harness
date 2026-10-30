"""Contrato de concorrência, lease por módulo e RecursionGuard — Onda 4 / I11.

Mecanismos determinísticos (stdlib pura, 0 token de API) que o motor do squad-pipeline
consulta ANTES de despachar um subagente:

- concorrencia_max            -> validar_concorrencia()          (quantos em paralelo)
- lease por módulo exclusivo  -> adquirir_lease()/liberar_lease() (um escritor por vez)
- profundidade_max_delegacao  -> RecursionGuard.entrar()          (profundidade e ciclo)
- sem_progresso / escalonar   -> MonitorProgresso.avaliar() + evento_sli()

Doutrina (a mesma de contracts/validator.py): o modelo pode SUGERIR um despacho; o código
decide se ele é PERMITIDO. Cada decisão volta como veredito tipado com mensagem instrutiva
(o que impediu e o que fazer em seguida).

Limites declarados: leases são arquivos JSON cooperativos dentro da raiz do repositório —
não são lock de SO, não valem entre máquinas e não impedem escrita de quem ignora o
protocolo. A janela entre ler e gravar um lease não é atômica (a gravação em si é).

P1-Simplicidade: stdlib apenas. contracts/concorrencia.json é a documentação canônica; as
constantes abaixo a espelham (teste anti-drift em tests/test_concorrencia.py).

CLI:  python -m contracts.concorrencia {lease|progresso|validar|contrato} ...  (ver --help)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

_CONTRACTS_DIR = Path(__file__).resolve().parent
CAMINHO_CONTRATO = _CONTRACTS_DIR / "concorrencia.json"

# Espelho de contracts/concorrencia.json (defaults quando o arquivo falta ou é inválido)
SCHEMA = "concorrencia-v1"
CONCORRENCIA_MAX = 3
PROFUNDIDADE_MAX_DELEGACAO = 3
LEASE_TTL_S = 900
SEM_PROGRESSO_APOS_S = 600
ESCALONAR_APOS_SEM_PROGRESSO = 2
MODULOS_EXCLUSIVOS: tuple[str, ...] = ("memory/", "governance/registry/", ".claude/pipeline/")

CAMPOS_INT = ("concorrencia_max", "profundidade_max_delegacao", "lease_ttl_s",
              "sem_progresso_apos_s", "escalonar_apos_sem_progresso")

# Eventos sli-v1 emitidos por este módulo (memory/sli-schema.md)
EVENTOS_SLI = ("sem_progresso", "escalonamento", "lease_negado", "recursao_bloqueada")
CAMPOS_SLI = ("ts", "run_id", "evento", "tool", "query", "ns", "bytes_context", "latency_ms",
              "tokens", "camada_modelo", "ctx_level", "recall_miss", "fonte")
TOOL_SLI = "camada-0/contracts.concorrencia"
FONTE_SLI = "script:camada-0/concorrencia"
NS_SLI = ".claude/pipeline/"

_FMT_TS = "%Y-%m-%dT%H:%M:%SZ"
_SEGMENTO_INVALIDO = re.compile(r'[<>:"|?*\x00-\x1f]')
_NOME_MAX = 150


# ---------------------------------------------------------------------------
# Vereditos tipados
# ---------------------------------------------------------------------------

@dataclass
class VereditoLease:
    veredito: str            # ADQUIRIDO | RENOVADO | TOMADO | LIBERADO | NEGADO
    regra: str
    mensagem: str
    dados: dict = field(default_factory=dict)


@dataclass
class VereditoConcorrencia:
    veredito: str            # PERMITIDO | AGUARDAR
    regra: str
    mensagem: str
    dados: dict = field(default_factory=dict)


@dataclass
class VereditoRecursao:
    veredito: str            # PERMITIDO | BLOQUEADO
    regra: str
    mensagem: str
    dados: dict = field(default_factory=dict)


class _EntradaInvalida(ValueError):
    """Entrada fora do contrato (slug, módulo, dono, ttl...). Carrega a `regra` do veredito."""

    def __init__(self, regra: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.regra = regra


# ---------------------------------------------------------------------------
# Tempo e escrita atômica
# ---------------------------------------------------------------------------

def _utc(agora: datetime | None = None) -> datetime:
    """`agora` injetável (testes). Naive é lido como UTC; precisão de segundos."""
    if agora is None:
        agora = datetime.now(timezone.utc)
    elif agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    else:
        agora = agora.astimezone(timezone.utc)
    return agora.replace(microsecond=0)


def _fmt(agora: datetime | None = None) -> str:
    return _utc(agora).strftime(_FMT_TS)


def _parse(texto: str) -> datetime:
    return datetime.strptime(texto, _FMT_TS).replace(tzinfo=timezone.utc)


def _escrever_atomico(destino: Path, conteudo: str) -> None:
    """Arquivo temporário na mesma pasta + os.replace: o leitor nunca vê meia gravação."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, prefix=destino.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(conteudo)
        os.replace(tmp, destino)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------

def _contrato_default() -> dict:
    return {
        "schema": SCHEMA,
        "concorrencia_max": CONCORRENCIA_MAX,
        "profundidade_max_delegacao": PROFUNDIDADE_MAX_DELEGACAO,
        "lease_ttl_s": LEASE_TTL_S,
        "sem_progresso_apos_s": SEM_PROGRESSO_APOS_S,
        "escalonar_apos_sem_progresso": ESCALONAR_APOS_SEM_PROGRESSO,
        "modulos_exclusivos": list(MODULOS_EXCLUSIVOS),
    }


def _inteiro_positivo(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def carregar_contrato(caminho: str | Path | None = None) -> dict:
    """Lê contracts/concorrencia.json. Nunca levanta por arquivo ausente ou inválido.

    Devolve os campos do contrato + `origem`: "arquivo" (lido) ou "default" (constantes do
    módulo). Valores inválidos de um campo caem no default daquele campo; o motivo vai em
    `avisos`. Schema diferente de `concorrencia-v1` descarta o arquivo inteiro.
    """
    alvo = Path(caminho) if caminho is not None else CAMINHO_CONTRATO
    contrato = _contrato_default()
    contrato["origem"] = "default"
    try:
        bruto = json.loads(alvo.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return contrato
    except (OSError, ValueError) as exc:
        contrato["avisos"] = [f"contrato ilegível em {alvo} ({type(exc).__name__}); usando defaults."]
        return contrato
    if not isinstance(bruto, dict) or bruto.get("schema") != SCHEMA:
        schema = bruto.get("schema") if isinstance(bruto, dict) else type(bruto).__name__
        contrato["avisos"] = [f"schema '{schema}' em {alvo} é incompatível com '{SCHEMA}'; usando defaults."]
        return contrato

    avisos: list[str] = []
    for campo in CAMPOS_INT:
        if campo not in bruto:
            continue
        if _inteiro_positivo(bruto[campo]):
            contrato[campo] = bruto[campo]
        else:
            avisos.append(f"{campo}={bruto[campo]!r} inválido (esperado inteiro > 0); usando {contrato[campo]}.")
    if "modulos_exclusivos" in bruto:
        mods = bruto["modulos_exclusivos"]
        try:
            if not isinstance(mods, list) or not all(isinstance(m, str) and _segmentos(m) for m in mods):
                raise _EntradaInvalida("modulo_invalido", "lista inválida")
            contrato["modulos_exclusivos"] = list(mods)
        except _EntradaInvalida:
            avisos.append("modulos_exclusivos inválido (esperado lista de caminhos relativos); usando o default.")
    contrato["origem"] = "arquivo"
    if avisos:
        contrato["avisos"] = avisos
    return contrato


# ---------------------------------------------------------------------------
# Módulo e slug
# ---------------------------------------------------------------------------

def _segmentos(modulo) -> list[str]:
    if not isinstance(modulo, str) or not modulo.strip():
        raise _EntradaInvalida("modulo_invalido",
                               "Módulo vazio. Informe o caminho do módulo relativo à raiz do repositório (ex.: 'memory/').")
    bruto = modulo.strip().replace("\\", "/")
    if bruto.startswith("/"):
        raise _EntradaInvalida("modulo_invalido",
                               f"Módulo '{modulo}' é absoluto. Use caminho relativo à raiz do repositório (ex.: 'memory/').")
    segs = [s for s in bruto.split("/") if s not in ("", ".")]
    if not segs:
        raise _EntradaInvalida("modulo_invalido", f"Módulo '{modulo}' não aponta para nenhum caminho.")
    if ".." in segs:
        raise _EntradaInvalida("modulo_invalido",
                               f"Módulo '{modulo}' contém '..'. O lease só vale dentro da raiz: use o caminho direto (ex.: 'memory/').")
    for s in segs:
        if _SEGMENTO_INVALIDO.search(s):
            raise _EntradaInvalida("modulo_invalido",
                                   f"Módulo '{modulo}' tem caractere não permitido em '{s}' (< > : \" | ? * ou controle).")
    return segs


def normalizar_modulo(modulo: str) -> str:
    """Nome de arquivo do lease: barras viram '__' ('governance/registry/' -> 'governance__registry').

    Levanta ValueError para módulo vazio, absoluto, com '..' ou com caractere inválido. Módulos
    cujos nomes já contenham '__' podem colidir com outro caminho: a colisão só nega (nunca libera).
    """
    nome = "__".join(_segmentos(modulo))
    if len(nome) > _NOME_MAX:
        raise _EntradaInvalida("modulo_invalido", f"Módulo '{modulo}' é longo demais ({len(nome)} > {_NOME_MAX} caracteres).")
    return nome


def modulo_exclusivo(modulo: str, contrato: dict | None = None) -> str | None:
    """Raiz exclusiva (como escrita no contrato) que cobre `modulo`, ou None se não for exclusivo.

    Peça o lease da RAIZ devolvida (ex.: 'memory/'), não do subcaminho: o lease é por nome de
    módulo e não detecta conflito entre pai e filho.
    """
    contrato = contrato if contrato is not None else carregar_contrato()
    try:
        segs = _segmentos(modulo)
    except _EntradaInvalida:
        return None
    for excl in contrato["modulos_exclusivos"]:
        alvo = _segmentos(excl)
        if segs[:len(alvo)] == alvo:
            return excl
    return None


def _validar_slug(slug) -> str:
    if (not isinstance(slug, str) or not slug.strip() or slug in (".", "..")
            or "/" in slug or "\\" in slug or _SEGMENTO_INVALIDO.search(slug)):
        raise _EntradaInvalida("slug_invalido",
                               f"Slug {slug!r} inválido. Use o nome da pasta em .claude/pipeline/ (um segmento, sem barras).")
    return slug


def _pasta_pipeline(raiz, slug) -> Path:
    return Path(raiz) / ".claude" / "pipeline" / _validar_slug(slug)


def caminho_progresso(raiz, slug) -> Path:
    """Estado do MonitorProgresso persistido: .claude/pipeline/<slug>/progresso.json."""
    return _pasta_pipeline(raiz, slug) / "progresso.json"


# ---------------------------------------------------------------------------
# Lease por módulo
# ---------------------------------------------------------------------------

@dataclass
class Lease:
    modulo: str              # forma canônica com '/' (ex.: 'governance/registry')
    dono: str
    adquirido_em: str        # ISO-8601 UTC, ex.: 2026-10-11T12:00:00Z
    expira_em: str
    run_id: str | None = None
    tomado_de: str | None = None   # dono anterior, quando o lease vencido foi tomado

    def como_dict(self) -> dict:
        d = {"modulo": self.modulo, "dono": self.dono}
        if self.run_id is not None:
            d["run_id"] = self.run_id
        d["adquirido_em"] = self.adquirido_em
        d["expira_em"] = self.expira_em
        if self.tomado_de is not None:
            d["tomado_de"] = self.tomado_de
        return d

    @classmethod
    def de_dict(cls, d) -> "Lease":
        if not isinstance(d, dict):
            raise ValueError("o lease não é um objeto JSON")
        for campo in ("modulo", "dono", "adquirido_em", "expira_em"):
            if not isinstance(d.get(campo), str) or not d[campo]:
                raise ValueError(f"campo '{campo}' ausente ou inválido")
        _parse(d["adquirido_em"])
        _parse(d["expira_em"])
        return cls(d["modulo"], d["dono"], d["adquirido_em"], d["expira_em"],
                   d.get("run_id"), d.get("tomado_de"))

    def expirado(self, agora: datetime | None = None) -> bool:
        return _utc(agora) >= _parse(self.expira_em)

    def restante_s(self, agora: datetime | None = None) -> int:
        return max(0, int((_parse(self.expira_em) - _utc(agora)).total_seconds()))


def _alvo_lease(raiz, slug, modulo) -> tuple[str, Path]:
    pasta = _pasta_pipeline(raiz, slug) / "leases"
    segs = _segmentos(modulo)
    return "/".join(segs), pasta / f"{normalizar_modulo(modulo)}.lease.json"


def _ler_lease(arquivo: Path) -> Lease | None:
    """None se não há lease; ValueError se o arquivo existe mas não é um lease legível."""
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError(f"{arquivo.name}: {type(exc).__name__}") from exc
    try:
        return Lease.de_dict(json.loads(texto))
    except ValueError as exc:
        raise ValueError(f"{arquivo.name}: {exc}") from exc


def _lease_ilegivel(arquivo: Path, exc: ValueError) -> VereditoLease:
    return VereditoLease(
        "NEGADO", "lease_ilegivel",
        f"O arquivo de lease {arquivo} está ilegível ({exc}). O motor não assume posse de estado que não "
        "consegue ler: confira quem escrevia nesse módulo e remova o arquivo manualmente antes de tentar de novo.",
        {"arquivo": str(arquivo)})


def adquirir_lease(raiz, slug: str, modulo: str, dono: str, ttl_s: int | None = None,
                   agora: datetime | None = None, *, run_id: str | None = None,
                   contrato: dict | None = None) -> VereditoLease:
    """Adquire (ou renova/toma) o lease do `modulo` para `dono`.

    ADQUIRIDO: módulo livre. RENOVADO: o mesmo dono adquiriu de novo (estende a validade).
    TOMADO: o lease de outro dono estava vencido (grava `tomado_de`). NEGADO: lease ativo de
    outro dono, lease ilegível ou entrada inválida (slug, módulo, dono, ttl) — esses casos nunca
    levantam; só uma falha de E/S do SO ao gravar propaga como OSError.
    """
    agora_dt = _utc(agora)
    try:
        canonico, arquivo = _alvo_lease(raiz, slug, modulo)
        if not isinstance(dono, str) or not dono.strip():
            raise _EntradaInvalida("dono_invalido", "Dono vazio. Identifique quem vai escrever no módulo (nome do agente ou run).")
        if ttl_s is None:
            ttl_s = (contrato if contrato is not None else carregar_contrato())["lease_ttl_s"]
        if not _inteiro_positivo(ttl_s):
            raise _EntradaInvalida("ttl_invalido", f"ttl_s={ttl_s!r} inválido. Informe segundos como inteiro > 0.")
    except _EntradaInvalida as exc:
        return VereditoLease("NEGADO", exc.regra, str(exc))

    try:
        atual = _ler_lease(arquivo)
    except ValueError as exc:
        return _lease_ilegivel(arquivo, exc)

    expira = _fmt(agora_dt + timedelta(seconds=ttl_s))
    if atual is None:
        novo = Lease(canonico, dono, _fmt(agora_dt), expira, run_id)
        veredito, regra = "ADQUIRIDO", "lease_livre"
        mensagem = f"Lease de '{canonico}' adquirido por '{dono}' até {expira}."
    elif atual.dono == dono:
        inicio = _fmt(agora_dt) if atual.expirado(agora_dt) else atual.adquirido_em
        novo = Lease(canonico, dono, inicio, expira, run_id or atual.run_id, atual.tomado_de)
        veredito, regra = "RENOVADO", "lease_renovado"
        mensagem = f"Lease de '{canonico}' renovado por '{dono}' até {expira}."
    elif atual.expirado(agora_dt):
        novo = Lease(canonico, dono, _fmt(agora_dt), expira, run_id, tomado_de=atual.dono)
        veredito, regra = "TOMADO", "lease_expirado"
        mensagem = (f"Lease de '{canonico}' estava vencido ({atual.expira_em}); tomado de '{atual.dono}' "
                    f"por '{dono}' até {expira}.")
    else:
        return VereditoLease(
            "NEGADO", "lease_ativo_de_outro_dono",
            f"Módulo '{canonico}' está sob lease de '{atual.dono}' até {atual.expira_em} "
            f"(restam {atual.restante_s(agora_dt)} s). Não escreva nele agora: aguarde a liberação ou o "
            "vencimento, ou delegue outra tarefa que não toque esse módulo.",
            {"modulo": canonico, "dono_atual": atual.dono, "expira_em": atual.expira_em,
             "restante_s": atual.restante_s(agora_dt), "arquivo": str(arquivo)})

    _escrever_atomico(arquivo, json.dumps(novo.como_dict(), ensure_ascii=False, indent=2) + "\n")
    return VereditoLease(veredito, regra, mensagem, {**novo.como_dict(), "arquivo": str(arquivo)})


def liberar_lease(raiz, slug: str, modulo: str, dono: str,
                  agora: datetime | None = None) -> VereditoLease:
    """Libera o lease do `modulo`. Só o dono libera um lease ativo; vencido, qualquer um remove.

    Idempotente: sem lease, devolve LIBERADO (regra `lease_inexistente`).
    """
    agora_dt = _utc(agora)
    try:
        canonico, arquivo = _alvo_lease(raiz, slug, modulo)
    except _EntradaInvalida as exc:
        return VereditoLease("NEGADO", exc.regra, str(exc))
    try:
        atual = _ler_lease(arquivo)
    except ValueError as exc:
        return _lease_ilegivel(arquivo, exc)
    if atual is None:
        return VereditoLease("LIBERADO", "lease_inexistente",
                             f"Não havia lease de '{canonico}'; nada a liberar.", {"modulo": canonico})
    if atual.dono != dono and not atual.expirado(agora_dt):
        return VereditoLease(
            "NEGADO", "lease_de_outro_dono",
            f"O lease de '{canonico}' pertence a '{atual.dono}', não a '{dono}'. Só o dono libera um lease "
            f"ativo; ele vence sozinho em {atual.expira_em}.",
            {"modulo": canonico, "dono_atual": atual.dono, "expira_em": atual.expira_em})
    arquivo.unlink(missing_ok=True)
    regra = "lease_liberado" if atual.dono == dono else "lease_expirado_removido"
    return VereditoLease("LIBERADO", regra, f"Lease de '{canonico}' liberado (dono anterior: '{atual.dono}').",
                         {"modulo": canonico, "dono_anterior": atual.dono})


def leases_ativos(raiz, slug: str, agora: datetime | None = None) -> list[Lease]:
    """Leases não vencidos de `.claude/pipeline/<slug>/leases/`, ordenados por módulo.

    Arquivos ilegíveis são ignorados aqui (adquirir_lease os trata como NEGADO). Levanta
    ValueError se o slug for inválido.
    """
    agora_dt = _utc(agora)
    pasta = _pasta_pipeline(raiz, slug) / "leases"
    if not pasta.is_dir():
        return []
    ativos = []
    for arquivo in sorted(pasta.glob("*.lease.json")):
        try:
            lease = _ler_lease(arquivo)
        except ValueError:
            continue
        if lease is not None and not lease.expirado(agora_dt):
            ativos.append(lease)
    return sorted(ativos, key=lambda x: x.modulo)


# ---------------------------------------------------------------------------
# Concorrência máxima
# ---------------------------------------------------------------------------

def validar_concorrencia(ativos: int, contrato: dict | None = None) -> VereditoConcorrencia:
    """PERMITIDO se `ativos` < concorrencia_max; senão AGUARDAR (não despache, espere um retorno)."""
    contrato = contrato if contrato is not None else carregar_contrato()
    limite = contrato["concorrencia_max"]
    if not isinstance(ativos, int) or isinstance(ativos, bool) or ativos < 0:
        return VereditoConcorrencia(
            "AGUARDAR", "ativos_invalido",
            f"Contagem de subagentes ativos inválida ({ativos!r}). Sem contagem confiável não há despacho: "
            "informe um inteiro >= 0.", {"ativos": ativos, "limite": limite})
    dados = {"ativos": ativos, "limite": limite, "vagas": max(0, limite - ativos)}
    if ativos < limite:
        return VereditoConcorrencia(
            "PERMITIDO", "concorrencia_max",
            f"{ativos} ativo(s) de {limite} permitidos: há {limite - ativos} vaga(s).", dados)
    return VereditoConcorrencia(
        "AGUARDAR", "concorrencia_max",
        f"{ativos} subagente(s) ativo(s) atingem o limite concorrencia_max={limite}. Não despache agora: "
        "espere o retorno de um subagente em andamento e reavalie.", dados)


# ---------------------------------------------------------------------------
# RecursionGuard
# ---------------------------------------------------------------------------

class RecursionGuard:
    """Guarda de delegação em memória: profundidade máxima e ciclos.

    Cada run registrado guarda sua cadeia (da raiz até ele). Raiz = profundidade 0; o primeiro
    subagente = 1. Um `pai_run_id` desconhecido é tratado como raiz da cadeia. Chame `entrar` a
    cada despacho e `sair` quando o subagente devolver o retorno.
    """

    def __init__(self, contrato: dict | None = None) -> None:
        self._contrato = contrato if contrato is not None else carregar_contrato()
        self._cadeias: dict[str, list[str]] = {}

    def entrar(self, run_id: str, pai_run_id: str | None = None,
               profundidade: int | None = None) -> VereditoRecursao:
        """PERMITIDO registra o run na pilha; BLOQUEADO não registra nada.

        `profundidade` explícita substitui a calculada pela cadeia (para quem rastreia a
        profundidade fora deste processo); a detecção de ciclo continua valendo.
        """
        limite = self._contrato["profundidade_max_delegacao"]
        if not isinstance(run_id, str) or not run_id.strip():
            return VereditoRecursao("BLOQUEADO", "run_id_invalido",
                                    "run_id vazio. Todo despacho precisa de um run_id para ser rastreado.",
                                    {"run_id": run_id, "limite": limite})
        cadeia_pai = list(self._cadeias.get(pai_run_id, [pai_run_id])) if pai_run_id else []
        dados = {"run_id": run_id, "pai_run_id": pai_run_id, "limite": limite, "cadeia": cadeia_pai + [run_id]}

        if run_id in cadeia_pai or run_id in self._cadeias:
            rastro = " → ".join(cadeia_pai + [run_id])
            motivo = ("é ancestral de si mesmo" if run_id in cadeia_pai
                      else "já está ativo na pilha (registrado antes sem `sair`)")
            return VereditoRecursao(
                "BLOQUEADO", "ciclo_de_delegacao",
                f"Ciclo de delegação: '{run_id}' {motivo} (cadeia: {rastro}). Um subagente não delega de volta "
                "para um run da própria cadeia: devolva o resultado ao pai ou retorne status=escalar.",
                {**dados, "profundidade": len(cadeia_pai)})

        if profundidade is None:
            profundidade = len(cadeia_pai)
        elif not isinstance(profundidade, int) or isinstance(profundidade, bool) or profundidade < 0:
            return VereditoRecursao("BLOQUEADO", "profundidade_invalida",
                                    f"profundidade={profundidade!r} inválida. Informe um inteiro >= 0 "
                                    "(orquestrador = 0).", {**dados, "profundidade": profundidade})
        dados["profundidade"] = profundidade

        if profundidade > limite:
            return VereditoRecursao(
                "BLOQUEADO", "profundidade_max_delegacao",
                f"Delegação na profundidade {profundidade} excede profundidade_max_delegacao={limite} "
                f"(cadeia: {' → '.join(dados['cadeia'])}). Não delegue de novo: conclua no nível atual ou "
                "devolva status=escalar com o motivo.", dados)

        self._cadeias[run_id] = cadeia_pai + [run_id]
        return VereditoRecursao("PERMITIDO", "profundidade_ok",
                                f"Despacho de '{run_id}' na profundidade {profundidade} de {limite} permitidos.", dados)

    def sair(self, run_id: str) -> int:
        """Remove o run e os descendentes registrados sob ele; devolve quantos saíram da pilha."""
        saindo = [r for r, cadeia in self._cadeias.items() if run_id in cadeia]
        for r in saindo:
            del self._cadeias[r]
        return len(saindo)


# ---------------------------------------------------------------------------
# Monitor de progresso
# ---------------------------------------------------------------------------

class MonitorProgresso:
    """Detecta run sem progresso a partir do último marco registrado.

    A cada janela inteira de `sem_progresso_apos_s` sem novo marco conta uma ocorrência; um novo
    marco zera tudo. As ocorrências derivam só do último marco e do relógio — repetir `avaliar`
    não as infla. Com `caminho`, o estado persiste em JSON (uso pela CLI, entre processos).
    """

    def __init__(self, contrato: dict | None = None, caminho: str | Path | None = None) -> None:
        self._contrato = contrato if contrato is not None else carregar_contrato()
        self._caminho = Path(caminho) if caminho is not None else None
        self._runs: dict[str, dict] = {}
        if self._caminho is not None and self._caminho.exists():
            self._carregar()

    def _carregar(self) -> None:
        try:
            runs = json.loads(self._caminho.read_text(encoding="utf-8"))["runs"]
            for reg in runs.values():
                if not isinstance(reg["marco"], str):
                    raise TypeError("marco")
                _parse(reg["ts"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"Estado de progresso ilegível em {self._caminho} ({type(exc).__name__}). "
                             "Remova o arquivo para reiniciar os marcos dos runs.") from exc
        self._runs = runs

    def _salvar(self) -> None:
        if self._caminho is not None:
            _escrever_atomico(self._caminho, json.dumps(
                {"schema": SCHEMA, "runs": self._runs}, ensure_ascii=False, indent=1) + "\n")

    def registrar(self, run_id: str, marco: str, agora: datetime | None = None) -> None:
        """Registra um marco de progresso (ex.: retorno de subagente) e zera as ocorrências."""
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id vazio: informe o run que progrediu.")
        if not isinstance(marco, str) or not marco.strip():
            raise ValueError("marco vazio: descreva o que mudou (ex.: 'retorno do subagente X').")
        self._runs[run_id] = {"marco": marco, "ts": _fmt(agora), "emitidas": 0}
        self._salvar()

    def _ocorrencias(self, idade_s: int) -> int:
        limite = self._contrato["sem_progresso_apos_s"]
        return max(0, (idade_s - 1) // limite)   # idade > k*limite  =>  k ocorrências

    def avaliar(self, run_id: str, agora: datetime | None = None) -> dict:
        """{"status": progredindo|sem_progresso|escalonar..., "sem_progresso_s", "ocorrencias", "marco"}.

        status: `sem_progresso` quando o último marco é mais antigo que `sem_progresso_apos_s`;
        `escalonar` quando as ocorrências consecutivas chegam a `escalonar_apos_sem_progresso`.
        Run sem marco registrado não tem base de comparação: volta `progredindo` com marco None.
        """
        reg = self._runs.get(run_id)
        if reg is None:
            return {"status": "progredindo", "sem_progresso_s": 0, "ocorrencias": 0, "marco": None}
        idade = max(0, int((_utc(agora) - _parse(reg["ts"])).total_seconds()))
        ocorrencias = self._ocorrencias(idade)
        if ocorrencias >= self._contrato["escalonar_apos_sem_progresso"]:
            status = "escalonar"
        elif ocorrencias >= 1:
            status = "sem_progresso"
        else:
            status = "progredindo"
        return {"status": status, "sem_progresso_s": idade, "ocorrencias": ocorrencias, "marco": reg["marco"]}

    def eventos_pendentes(self, run_id: str, agora: datetime | None = None) -> list[str]:
        """Eventos SLI ainda não emitidos para o run, e os marca como emitidos (idempotente).

        Uma ocorrência abaixo do limiar gera `sem_progresso`; a que alcança
        `escalonar_apos_sem_progresso` gera `escalonamento`; ocorrências além do limiar não
        geram evento novo.
        """
        reg = self._runs.get(run_id)
        if reg is None:
            return []
        ocorrencias = self.avaliar(run_id, agora)["ocorrencias"]
        limiar = self._contrato["escalonar_apos_sem_progresso"]
        eventos = []
        for n in range(reg.get("emitidas", 0) + 1, ocorrencias + 1):
            if n < limiar:
                eventos.append("sem_progresso")
            elif n == limiar:
                eventos.append("escalonamento")
        if ocorrencias > reg.get("emitidas", 0):
            reg["emitidas"] = ocorrencias
            self._salvar()
        return eventos


# ---------------------------------------------------------------------------
# SLI (sli-v1)
# ---------------------------------------------------------------------------

def evento_sli(evento: str, run_id: str, detalhe: str, slug: str | None = None,
               agora: datetime | None = None) -> dict:
    """Linha sli-v1 completa (13 campos) para um evento deste módulo.

    Campos desconhecidos ficam None (nunca estimados). `ns` é `.claude/pipeline/` e, com `slug`,
    `.claude/pipeline/<slug>/`. `detalhe` vira `query` (truncado em 500) e nunca deve conter
    segredo.
    """
    if evento not in EVENTOS_SLI:
        raise ValueError(f"Evento '{evento}' desconhecido. Eventos válidos: {', '.join(EVENTOS_SLI)}.")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id vazio: o schema sli-v1 exige run_id string.")
    ns = NS_SLI if slug is None else f"{NS_SLI}{_validar_slug(slug)}/"
    return {
        "ts": _fmt(agora),
        "run_id": run_id,
        "evento": evento,
        "tool": TOOL_SLI,
        "query": str(detalhe)[:500],
        "ns": ns,
        "bytes_context": None,
        "latency_ms": None,
        "tokens": None,
        "camada_modelo": "camada-0",
        "ctx_level": None,
        "recall_miss": None,
        "fonte": FONTE_SLI,
    }


def anexar_sli(caminho: str | Path, linha: dict) -> None:
    """Acrescenta a linha ao fim do JSONL (append-only; nunca reescreve o que já existe)."""
    faltando = [c for c in CAMPOS_SLI if c not in linha]
    if faltando:
        raise ValueError(f"Linha sli-v1 sem os campos obrigatórios: {', '.join(faltando)}.")
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(linha, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _iso_utc(texto: str) -> datetime:
    try:
        return _utc(datetime.fromisoformat(texto.replace("Z", "+00:00")))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"data inválida '{texto}' (use ISO-8601, ex.: 2026-10-11T12:00:00Z)") from exc


def _saida(args, texto: str, dados: dict, falha: bool) -> int:
    print(json.dumps(dados, ensure_ascii=False) if args.json else texto)
    return 1 if falha else 0


def _sli(args, evento: str, run_id: str, detalhe: str) -> None:
    caminho = Path(args.sli)
    if not caminho.is_absolute():
        caminho = Path(args.raiz) / caminho
    anexar_sli(caminho, evento_sli(evento, run_id, detalhe, slug=args.slug, agora=args.agora))


def _cmd_lease_adquirir(args) -> int:
    v = adquirir_lease(args.raiz, args.slug, args.modulo, args.dono, ttl_s=args.ttl_s, agora=args.agora,
                       run_id=args.run_id, contrato=args.contrato_dict)
    if args.sli and v.regra in ("lease_ativo_de_outro_dono", "lease_ilegivel"):
        _sli(args, "lease_negado", args.run_id or args.dono, v.mensagem)
    return _saida(args, f"{v.veredito} {v.regra}: {v.mensagem}", asdict(v), v.veredito == "NEGADO")


def _cmd_lease_liberar(args) -> int:
    v = liberar_lease(args.raiz, args.slug, args.modulo, args.dono, agora=args.agora)
    return _saida(args, f"{v.veredito} {v.regra}: {v.mensagem}", asdict(v), v.veredito == "NEGADO")


def _cmd_lease_listar(args) -> int:
    ativos = leases_ativos(args.raiz, args.slug, agora=args.agora)
    texto = ("nenhum lease ativo" if not ativos else f"{len(ativos)} lease(s) ativo(s): " + "; ".join(
        f"{x.modulo} (dono {x.dono}, até {x.expira_em})" for x in ativos))
    return _saida(args, texto, {"leases": [x.como_dict() for x in ativos]}, False)


def _cmd_progresso_registrar(args) -> int:
    monitor = MonitorProgresso(args.contrato_dict, caminho_progresso(args.raiz, args.slug))
    monitor.registrar(args.run_id, args.marco, agora=args.agora)
    dados = {"run_id": args.run_id, "marco": args.marco, "ts": _fmt(args.agora)}
    return _saida(args, f"registrado run={args.run_id} marco={args.marco!r} em={dados['ts']}", dados, False)


def _cmd_progresso_avaliar(args) -> int:
    monitor = MonitorProgresso(args.contrato_dict, caminho_progresso(args.raiz, args.slug))
    res = monitor.avaliar(args.run_id, agora=args.agora)
    if args.sli:
        c = args.contrato_dict
        for evento in monitor.eventos_pendentes(args.run_id, agora=args.agora):
            if evento == "escalonamento":
                detalhe = (f"{res['ocorrencias']} ocorrência(s) consecutiva(s) de sem_progresso (limiar "
                           f"{c['escalonar_apos_sem_progresso']}): parar e enfileirar decisão humana; "
                           f"último marco: {res['marco']!r}")
            else:
                detalhe = (f"sem novo marco há {res['sem_progresso_s']}s (janela {c['sem_progresso_apos_s']}s); "
                           f"último marco: {res['marco']!r}")
            _sli(args, evento, args.run_id, detalhe)
    texto = (f"{res['status']} run={args.run_id} sem_progresso_s={res['sem_progresso_s']} "
             f"ocorrencias={res['ocorrencias']} marco={res['marco']!r}")
    return _saida(args, texto, {"run_id": args.run_id, **res}, res["status"] == "escalonar")


def _cmd_validar(args) -> int:
    v = validar_concorrencia(args.ativos, args.contrato_dict)
    return _saida(args, f"{v.veredito} {v.regra}: {v.mensagem}", asdict(v), v.veredito != "PERMITIDO")


def _cmd_contrato(args) -> int:
    c = args.contrato_dict
    texto = " ".join(f"{k}={c[k]}" for k in ("origem", "schema", *CAMPOS_INT)) \
        + " modulos_exclusivos=" + ",".join(c["modulos_exclusivos"])
    return _saida(args, texto, c, False)


def _parser() -> argparse.ArgumentParser:
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--raiz", default=".", help="raiz do repositório (default: .)")
    comum.add_argument("--json", action="store_true", help="saída em JSON em vez de uma linha")
    comum.add_argument("--agora", type=_iso_utc, default=None, help="relógio fixo ISO-8601 UTC (testes/auditoria)")
    comum.add_argument("--contrato", default=None, help="caminho alternativo do concorrencia.json")
    comum.add_argument("--sli", nargs="?", const="memory/sli.jsonl", default=None,
                       help="acrescenta o evento ao SLI (default: <raiz>/memory/sli.jsonl)")

    def folha(pai, nome: str, func, slug_obrigatorio: bool, ajuda: str | None = None) -> argparse.ArgumentParser:
        p = pai.add_parser(nome, parents=[comum], help=ajuda)
        p.add_argument("--slug", required=slug_obrigatorio, default=None, help="pasta em .claude/pipeline/")
        p.set_defaults(func=func)
        return p

    ap = argparse.ArgumentParser(prog="python -m contracts.concorrencia", description=__doc__.splitlines()[0])
    grupos = ap.add_subparsers(dest="grupo", required=True)

    lease = grupos.add_parser("lease", help="lease por módulo").add_subparsers(dest="acao", required=True)
    p = folha(lease, "adquirir", _cmd_lease_adquirir, True)
    p.add_argument("--modulo", required=True)
    p.add_argument("--dono", required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--ttl-s", type=int, default=None)
    p = folha(lease, "liberar", _cmd_lease_liberar, True)
    p.add_argument("--modulo", required=True)
    p.add_argument("--dono", required=True)
    folha(lease, "listar", _cmd_lease_listar, True)

    prog = grupos.add_parser("progresso", help="marcos de progresso").add_subparsers(dest="acao", required=True)
    p = folha(prog, "registrar", _cmd_progresso_registrar, True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--marco", required=True)
    p = folha(prog, "avaliar", _cmd_progresso_avaliar, True)
    p.add_argument("--run-id", required=True)

    p = folha(grupos, "validar", _cmd_validar, False, "concorrencia_max")
    p.add_argument("--ativos", type=int, required=True, help="subagentes ativos agora")
    folha(grupos, "contrato", _cmd_contrato, False, "mostra o contrato vigente")
    return ap


def main(argv: list[str] | None = None) -> int:
    """Exit 0 = ok; 1 = NEGADO/AGUARDAR/escalonar; 2 = erro de uso ou de estado."""
    args = _parser().parse_args(argv)
    args.contrato_dict = carregar_contrato(args.contrato)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
