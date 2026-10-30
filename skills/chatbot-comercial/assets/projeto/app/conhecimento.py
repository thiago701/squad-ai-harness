"""M2 — RAG. Ingestão, indexação incremental e citação obrigatória.

Chunking, embedding, store e busca híbrida vêm do `rag_kit` (n7-ai-core).
Este módulo só faz o que é do produto: ler formatos de cliente, decidir o que
precisa ser reindexado, e garantir que nenhuma resposta saia sem fonte.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from rag_kit import Document, KnowledgeBase, Passage, SearchConfig, char_ngrams, tokenize
from rag_kit.adapters import SynonymExpandingEmbedder

EXTENSOES = {".md", ".txt", ".csv", ".json", ".html", ".htm", ".pdf", ".xlsx"}
_WHATSAPP_LINHA = re.compile(
    r"^\[?(\d{1,2}/\d{1,2}/\d{2,4}),?\s+\d{1,2}:\d{2}(?::\d{2})?\]?\s*[-–]?\s*([^:]{1,60}):\s?(.*)$"
)


class _SoTexto(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._partes: list[str] = []
        self._ignorar = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in {"script", "style"}:
            self._ignorar = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._ignorar = False

    def handle_data(self, data: str) -> None:
        if not self._ignorar and data.strip():
            self._partes.append(data.strip())

    @property
    def texto(self) -> str:
        return "\n".join(self._partes)


def _de_html(bruto: str) -> str:
    parser = _SoTexto()
    parser.feed(bruto)
    return parser.texto


def _de_csv(bruto: str) -> str:
    leitor = csv.DictReader(io.StringIO(bruto))
    linhas = []
    for registro in leitor:
        pares = [f"{k}: {v}" for k, v in registro.items() if k and v]
        if pares:
            linhas.append(". ".join(pares) + ".")
    return "\n".join(linhas)


def _de_json(bruto: str) -> str:
    dados = json.loads(bruto)

    def achatar(valor: Any, prefixo: str = "") -> list[str]:
        if isinstance(valor, dict):
            saida: list[str] = []
            for k, v in valor.items():
                saida.extend(achatar(v, f"{prefixo}{k} "))
            return saida
        if isinstance(valor, list):
            saida = []
            for item in valor:
                saida.extend(achatar(item, prefixo))
            return saida
        return [f"{prefixo.strip()}: {valor}."]

    return "\n".join(achatar(dados))


def _de_whatsapp(bruto: str) -> str:
    """Export de conversa do WhatsApp → pares pergunta/resposta em texto corrido."""
    falas: list[str] = []
    for linha in bruto.splitlines():
        achado = _WHATSAPP_LINHA.match(linha.strip())
        if achado:
            autor, mensagem = achado.group(2).strip(), achado.group(3).strip()
            if mensagem and "mensagem apagada" not in mensagem.lower():
                falas.append(f"{autor}: {mensagem}")
        elif linha.strip() and falas:
            falas[-1] = f"{falas[-1]} {linha.strip()}"
    return "\n".join(falas)


def _de_pdf(caminho: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            f"{caminho.name}: leitura de PDF exige `pypdf`. "
            "Instale com `pip install -e .[pdf]` ou converta o arquivo para .md."
        ) from exc
    leitor = PdfReader(str(caminho))
    return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)


def _de_xlsx(caminho: Path) -> str:
    """Planilha → uma frase por linha, com o cabeçalho como rótulo."""
    try:
        from openpyxl import load_workbook  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            f"{caminho.name}: leitura de .xlsx exige `openpyxl`. "
            "Instale com `pip install -e .[xlsx]` ou exporte a planilha em CSV."
        ) from exc
    livro = load_workbook(caminho, read_only=True, data_only=True)
    linhas: list[str] = []
    for aba in livro.worksheets:
        celulas = aba.iter_rows(values_only=True)
        cabecalho = next(celulas, None)
        if not cabecalho:
            continue
        rotulos = [str(c).strip() if c is not None else "" for c in cabecalho]
        for linha in celulas:
            pares = [
                f"{rotulos[i]}: {valor}"
                for i, valor in enumerate(linha)
                if i < len(rotulos) and rotulos[i] and valor not in (None, "")
            ]
            if pares:
                linhas.append(f"{aba.title}. " + ". ".join(pares) + ".")
    livro.close()
    return "\n".join(linhas)


def baixar_site(url: str, *, timeout: float = 20.0) -> str:
    """Busca uma página do cliente e devolve o texto limpo.

    Uso é explícito (`seed_rag.py --url`), nunca automático: conteúdo de site é
    **dado não confiável** — entra na base como informação, jamais como
    instrução para o agente.
    """
    from urllib.parse import urlparse
    from urllib.request import Request, urlopen

    esquema = urlparse(url).scheme
    if esquema not in {"http", "https"}:
        raise ValueError(f"URL inválida (use http/https): {url!r}")
    requisicao = Request(url, headers={"User-Agent": "chatbot-comercial/0.1 (+ingestao)"})
    with urlopen(requisicao, timeout=timeout) as resposta:  # noqa: S310
        bruto = resposta.read().decode("utf-8", errors="replace")
    return _de_html(bruto)


def extrair_texto(caminho: Path) -> str:
    sufixo = caminho.suffix.lower()
    if sufixo == ".pdf":
        return _de_pdf(caminho)
    if sufixo == ".xlsx":
        return _de_xlsx(caminho)
    bruto = caminho.read_text(encoding="utf-8", errors="replace")
    if sufixo in {".html", ".htm"}:
        return _de_html(bruto)
    if sufixo == ".csv":
        return _de_csv(bruto)
    if sufixo == ".json":
        return _de_json(bruto)
    if sufixo == ".txt" and _WHATSAPP_LINHA.search(bruto[:4000] or ""):
        return _de_whatsapp(bruto)
    return bruto


def digest(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class BaseDeConhecimento:
    """Envelope do `KnowledgeBase` que sabe quais fontes estão no índice VIVO.

    Existe por causa de um erro real: o registro de "já indexado" mora no
    banco (sobrevive ao restart) mas o índice vetorial default mora em
    memória (morre no restart). Confiar só no banco deixava o índice vazio
    depois de reiniciar. `fontes` é a verdade do processo atual; o banco
    guarda o sha256 para detectar mudança de conteúdo.
    """

    def __init__(
        self, kb: KnowledgeBase, *, expandir: Any = None, ignorar: Any = frozenset()
    ):
        self._kb = kb
        self.fontes: set[str] = set()
        self.expandir = expandir
        self.ignorar = frozenset(ignorar)

    def add(self, documento: Document) -> list[Any]:
        chunks = self._kb.add(documento)
        if chunks:
            self.fontes.add(documento.source)
        return chunks

    def remove(self, fonte: str) -> int:
        self.fontes.discard(fonte)
        return self._kb.remove(fonte)

    def retrieve(self, consulta: str, **kwargs: Any) -> list[Passage]:
        return self._kb.retrieve(consulta, **kwargs)

    def count(self) -> int:
        return self._kb.count()

    def __len__(self) -> int:
        return self._kb.count()


def construir_base(config: Any, pack: Any = None) -> BaseDeConhecimento:
    sinonimos = getattr(pack, "sinonimos", None) or {}
    embedder = SynonymExpandingEmbedder(sinonimos) if sinonimos else None
    return BaseDeConhecimento(
        KnowledgeBase(
            embedder=embedder,
            config=SearchConfig(
                top_k=config.top_k,
                candidates=max(16, config.top_k * 6),
                min_score=config.score_minimo,
            ),
        ),
        expandir=embedder.expand_terms if embedder else None,
        ignorar=getattr(pack, "termos_ignorados", frozenset()),
    )


def indexar(
    base: BaseDeConhecimento,
    config: Any,
    conexao: sqlite3.Connection | None = None,
    *,
    forcar: bool = False,
) -> dict[str, Any]:
    """Incremental de verdade: pula a fonte só se ela estiver no índice vivo
    E o sha256 do arquivo bater com o último indexado.
    """
    pasta = config.dados_do_vertical
    if not pasta.exists():
        raise FileNotFoundError(f"pasta de dados não encontrada: {pasta}")

    conhecidos: dict[str, str] = {}
    if conexao is not None and not forcar:
        cursor = conexao.execute(
            "SELECT fonte, sha256 FROM fontes_indexadas WHERE tenant = ?",
            (config.tenant,),
        )
        conhecidos = {
            linha["fonte"]: linha["sha256"]
            for linha in cursor.fetchall()
            if linha["fonte"] in base.fontes
        }

    relatorio: dict[str, Any] = {"novas": [], "atualizadas": [], "inalteradas": [], "erros": []}
    for caminho in sorted(pasta.rglob("*")):
        if not caminho.is_file() or caminho.suffix.lower() not in EXTENSOES:
            continue
        fonte = caminho.stem
        try:
            texto = extrair_texto(caminho)
        except Exception as exc:
            relatorio["erros"].append(f"{caminho.name}: {exc}")
            continue
        if not texto.strip():
            relatorio["erros"].append(f"{caminho.name}: vazio")
            continue

        sha = digest(texto)
        anterior = conhecidos.get(fonte)
        if anterior == sha and not forcar:
            relatorio["inalteradas"].append(fonte)
            continue
        if anterior is not None:
            base.remove(fonte)

        chunks = base.add(
            Document(
                source=fonte,
                text=texto,
                metadata={
                    "tenant": config.tenant,
                    "vertical": config.vertical,
                    "arquivo": caminho.name,
                },
            )
        )
        (relatorio["atualizadas"] if anterior else relatorio["novas"]).append(fonte)
        if conexao is not None:
            conexao.execute(
                "INSERT INTO fontes_indexadas (tenant, fonte, sha256, chunks, indexado_em) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(tenant, fonte) DO UPDATE SET "
                "sha256=excluded.sha256, chunks=excluded.chunks, "
                "indexado_em=excluded.indexado_em",
                (config.tenant, fonte, sha, len(chunks), _agora()),
            )
    if conexao is not None:
        conexao.commit()
    relatorio["total_chunks"] = base.count()
    return relatorio


# Palavras que não ancoram nada — se a pergunta só tem isso, não há sobre o
# que responder. Lista do produto (a do rag_kit é menor e serve a outro fim).
_PARASITAS = frozenset("""
a as o os um uma uns umas de do da dos das em no na nos nas por pra para com
que e ou se meu minha meus minhas seu sua qual quais como quando onde quanto
quantos quantas eu voce voces vc vcs isso esse essa este esta isto ao aos
tem ter tenho temos ha sao esta estao pode posso podem poderia fazer faz fazem
ate sobre mais menos muito ai la ja so nao sim oi ola bom dia boa tarde noite
obrigado obrigada favor gostaria queria quero preciso saber informacao ser
seria vai vou ir dar me te nos aqui ali entao tambem porque pois entre qualquer
alguma algum tipo coisa gente pessoal ver tudo mesmo assim depois antes
funciona funcionam informar consegue poderia possui existe sabem sabe
""".split())

_ANCORA_MINIMA = 0.60


def termos_de_conteudo(
    texto: str, expandir: Any = None, ignorar: Any = frozenset()
) -> set[str]:
    """Termos que de fato ancoram uma resposta.

    `ignorar` vem do vertical-pack (`termos_ignorados`): palavras frequentes e
    inúteis daquele domínio — o nome do estabelecimento, "pousada", "serviço".
    Sem elas na lista, "tem serviço de babá na pousada?" ancorava em qualquer
    documento e o agente respondia sobre traslado.
    """
    brutos = set(expandir(texto)) if callable(expandir) else set(tokenize(texto))
    descartar = _PARASITAS | set(ignorar)
    return {t for t in brutos if len(t) >= 4 and t not in descartar}


def _parecido(a: str, b: str) -> float:
    if a == b:
        return 1.0
    ga, gb = set(char_ngrams(a, n=3)), set(char_ngrams(b, n=3))
    uniao = ga | gb
    return len(ga & gb) / len(uniao) if uniao else 0.0


def ancorado(pergunta: str, trechos: list[Passage], expandir: Any = None) -> bool:
    """Restrição 4, com dentes: o trecho recuperado tem que falar do que foi
    perguntado.

    Sem isso, uma pergunta como "vocês têm heliponto?" pontua acima do mínimo
    só pelas palavras de ligação ("vocês", "têm") e o agente responde com um
    trecho que não trata do assunto. Aqui exigimos que ao menos um termo de
    conteúdo da pergunta apareça no trecho.
    """
    if not trechos:
        return False
    alvo = termos_de_conteudo(pergunta, expandir)
    if not alvo:
        return True  # pergunta só de ligação — deixa o score decidir
    return any(_ancora_no_texto(alvo, p.text) for p in trechos)


def _ancora_no_texto(alvo: set[str], texto: str) -> bool:
    do_trecho = {t for t in tokenize(texto) if len(t) >= 4}
    return any(
        max((_parecido(termo, t) for t in do_trecho), default=0.0) >= _ANCORA_MINIMA
        for termo in alvo
    )


_FRASE = re.compile(r"(?<=[.!?])\s+|\n+")


def frases_relevantes(
    pergunta: str, texto: str, *, maximo: int = 3, expandir: Any = None
) -> tuple[str, float]:
    """Recorta do trecho as frases que respondem à pergunta.

    Existe porque o chunk é grande: um documento de FAQ inteiro pode virar um
    único chunk, e devolvê-lo cru faz a resposta começar pelo assunto errado —
    foi assim que uma correção recém-aprovada pela curadoria ficou invisível,
    escondida no fim do parágrafo.

    Continua sendo extração pura: nenhuma palavra é inventada.
    Devolve `(recorte, nota)` — a nota permite escolher entre vários trechos.
    """
    candidatas = [
        f.strip()
        for f in _FRASE.split(texto)
        if f.strip() and not f.strip().startswith("#")
    ]
    if not candidatas:
        return texto.strip(), 0.0
    alvo = termos_de_conteudo(pergunta, expandir)
    if not alvo:
        return " ".join(candidatas[:maximo]), 0.0

    def pontuar(frase: str) -> float:
        da_frase = {t for t in tokenize(frase) if len(t) >= 4}
        if not da_frase:
            return 0.0
        return sum(
            max((_parecido(termo, t) for t in da_frase), default=0.0) for termo in alvo
        ) / len(alvo)

    notas = [pontuar(f) for f in candidatas]
    melhor = max(range(len(candidatas)), key=notas.__getitem__)
    if notas[melhor] == 0.0:
        return " ".join(candidatas[:maximo]), 0.0

    fim = min(len(candidatas), melhor + maximo)
    return " ".join(candidatas[melhor:fim]), notas[melhor]


def recuperar(base: BaseDeConhecimento, pergunta: str, config: Any) -> list[Passage]:
    """Filtra por score e depois por âncora, **trecho a trecho**.

    A âncora é de cada trecho, não do conjunto: o 1º lugar do ranking pode ser
    um documento vizinho que casou só por um verbo comum. "Como funciona o
    cancelamento" trazia a sauna ("funciona") à frente da política de
    cancelamento. Descartar o trecho sem âncora e manter os demais resolve sem
    mexer no score mínimo — que é o que a `disciplina` proíbe.
    """
    trechos = [
        p for p in base.retrieve(pergunta, top_k=config.top_k)
        if p.score >= config.score_minimo
    ]
    if not trechos:
        return []
    alvo = termos_de_conteudo(pergunta, base.expandir, base.ignorar)
    if not alvo:
        return trechos
    return [p for p in trechos if _ancora_no_texto(alvo, p.text)]


def citar(trechos: list[Passage]) -> tuple[str, ...]:
    """Restrição 4 — sem fonte não há resposta. Ordem estável, sem duplicata."""
    vistas: list[str] = []
    for p in trechos:
        if p.source not in vistas:
            vistas.append(p.source)
    return tuple(vistas)
