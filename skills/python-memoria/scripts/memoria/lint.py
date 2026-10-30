"""Lente determinística de memória para código Python — análise por AST (stdlib pura).

Entrada: raiz + (opcional) lista de arquivos ou `--diff <ref>`. Saída: achados MEM-xx com linha e
trecho, relatório JSON, código 0 aprovado · 1 reprovado (só com `--falhar-em necessario`) · 2 inconclusivo.

Heurísticas declaradas e testadas (tests/test_python_memoria.py). Supressão só com motivo:
`# mem-ok: <motivo>` na linha ou na anterior. Arquivos de teste ficam fora por padrão (`incluir_testes`).
"""
from __future__ import annotations

import ast
import fnmatch
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .regras import NEC, POR_ID, SUG

DIRS_IGNORADOS = {
    ".git", "node_modules", ".venv", "venv", "env", "build", "dist", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "_local-artifacts", ".cache", "graphify-out", ".aws-sam", ".idea",
    "site-packages", ".tox", ".eggs",
}
_RE_SUPRESSAO = re.compile(r"#\s*mem-ok:\s*(.+?)\s*$")
_RE_NOME_CACHE = re.compile(r"(?i)cache|buffer|memo|regist|historic|history|eventos|events|fila|queue|acumul|logs?$")
_AGREGADORES = {"sum", "any", "all", "min", "max", "sorted", "set", "frozenset", "tuple", "enumerate", "zip",
                "map", "filter"}
_KW_PANDAS_OK = {"usecols", "dtype", "chunksize", "nrows", "columns", "dtype_backend", "engine", "iterator",
                 "memory_map", "low_memory"}
_LEITORES_PANDAS = {"read_csv", "read_json", "read_parquet", "read_excel", "read_sql", "read_table", "read_feather"}
_BACKPRESSURE = {"Semaphore", "BoundedSemaphore", "TaskGroup", "batched", "islice", "as_completed", "Queue"}
_RE_NOME_REGISTRO = re.compile(r"(?i)(item|linha|registro|record|row|evento|event|ponto|point|node|token|amostra|sample|"
                               r"entry|entrada|achado|finding|mensagem|message|span|frame|celula|cell|vertice|aresta|edge|"
                               r"ocorrencia|occurrence|transacao|transaction|lancamento|medicao|measurement)$")
_CREATE_TASK_ASYNC = {"asyncio", "loop", "", "tg"}
_RE_PARAM_ABERTO = re.compile(r"(?i)^(id|ids|key|chave|url|uri|path|caminho|texto|text|data|dados|valor|value|cpf|cnpj|sku|"
                              r"nome|name|email|token|query|consulta|ts|timestamp|dt|date|hora|time|payload|body|doc|"
                              r"documento|linha|line|registro|record|row|item|usuario|user|cliente|customer|pedido|order)"
                              r"(_?\w*)?$|.*(_id|_key|_url|_path|_texto|_text|_nome|_name|_valor|_value|_ts|_data|_date)$")


def _eh_teste(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    return "/tests/" in r or r.startswith("tests/") or "/test_" in r or r.startswith("test_") or r.endswith("_test.py") \
        or "/conftest.py" in r or r == "conftest.py"


@dataclass
class Achado:
    regra: str
    severidade: str
    arquivo: str
    linha: int
    trecho: str
    detalhe: str
    suprimido: bool = False
    motivo: str = ""

    def chave(self) -> tuple:
        return (self.regra, self.arquivo, self.linha)


@dataclass
class Relatorio:
    perfil: str
    raiz: str
    arquivos_analisados: int = 0
    linhas_analisadas: int = 0
    arquivos_pulados: list[str] = field(default_factory=list)
    achados: list[Achado] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    duracao_s: float = 0.0

    def ativos(self, severidade: str | None = None) -> list[Achado]:
        return [a for a in self.achados if not a.suprimido and (severidade is None or a.severidade == severidade)]

    def veredito(self, falhar_em_necessario: bool = False) -> tuple[int, str]:
        if self.arquivos_analisados == 0:
            return 2, "INCONCLUSIVO"
        if falhar_em_necessario and self.ativos(NEC):
            return 1, "REPROVADO"
        return 0, "APROVADO"


# --------------------------------------------------------------------------- #
# Utilidades AST
# --------------------------------------------------------------------------- #
def _nome(n: ast.AST) -> str:
    """Nome 'pontuado' de um Name/Attribute: pd.read_csv → 'pd.read_csv'."""
    if isinstance(n, ast.Name):
        return n.id
    if isinstance(n, ast.Attribute):
        base = _nome(n.value)
        return f"{base}.{n.attr}" if base else n.attr
    if isinstance(n, ast.Call):
        return _nome(n.func)
    return ""


def _ultimo(n: ast.AST) -> str:
    return _nome(n).rsplit(".", 1)[-1]


def _eh_str(n: ast.AST) -> bool:
    if isinstance(n, ast.JoinedStr):
        return True
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return True
    if isinstance(n, ast.Call) and _ultimo(n.func) in {"str", "format", "repr"}:
        return True
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        return _eh_str(n.left) or _eh_str(n.right)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod):      # "%s" % x
        return _eh_str(n.left)
    return False


def _kwargs(call: ast.Call) -> set[str]:
    return {k.arg for k in call.keywords if k.arg}


def _contem_nomes(node: ast.AST, nomes: set[str]) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in nomes:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in nomes:
            return True
    return False


def _muta(nome: str, corpo: list[ast.stmt]) -> bool:
    """O corpo altera o contêiner `nome`? (del x[k], x[k] = v, x.pop/clear/update/…)."""
    for st in corpo:
        for sub in ast.walk(st):
            if isinstance(sub, ast.Delete):
                for t in sub.targets:
                    if isinstance(t, ast.Subscript) and _nome(t.value) == nome:
                        return True
            if isinstance(sub, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                alvos = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
                for t in alvos:
                    if isinstance(t, ast.Subscript) and _nome(t.value) == nome:
                        return True
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and _nome(sub.func.value) == nome \
                    and sub.func.attr in {"pop", "popitem", "clear", "update", "setdefault", "remove", "discard", "append", "add"}:
                return True
    return False


# --------------------------------------------------------------------------- #
# Visitor
# --------------------------------------------------------------------------- #
class _Visitor(ast.NodeVisitor):
    def __init__(self, rel: str, linhas: list[str], add):
        self.rel, self.linhas, self.add = rel, linhas, add
        self.loop = 0
        self.funcoes: list[ast.AST] = []
        self.excecoes: list[str] = []
        self.classes: list[ast.ClassDef] = []
        self.dataclasses_sem_slots: dict[str, tuple[int, int]] = {}   # nome → (linha, campos)
        self.instanciadas_em_loop: set[str] = set()

    # --- contexto -------------------------------------------------------- #
    def _em_loop(self, node, corpo_attrs=("body", "orelse")):
        self.loop += 1
        for attr in corpo_attrs:
            for st in getattr(node, attr, []) or []:
                self.visit(st)
        self.loop -= 1

    def visit_For(self, node: ast.For):
        self._regras_for(node)
        self.visit(node.target)
        self.visit(node.iter)
        self._em_loop(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While):
        self.visit(node.test)
        self._em_loop(node)

    def _comp(self, node):
        self.loop += 1
        self.generic_visit(node)
        self.loop -= 1

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comp

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._regra_cache(node)
        self.funcoes.append(node)
        loop_antes, self.loop = self.loop, 0          # corpo de função não herda o loop externo
        self.generic_visit(node)
        self.loop = loop_antes
        self.funcoes.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        self._regra_dataclass(node)
        self.classes.append(node)
        self.generic_visit(node)
        self.classes.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        if node.name:
            self.excecoes.append(node.name)
            self.generic_visit(node)
            self.excecoes.pop()
        else:
            self.generic_visit(node)

    # --- regras ---------------------------------------------------------- #
    def _regras_for(self, node: ast.For):
        it = node.iter
        if isinstance(it, ast.ListComp):
            self.add("MEM-19", node.lineno, "lista intermediária só para iterar — use expressão geradora")
        if isinstance(it, ast.Call) and _nome(it.func) == "list" and it.args and isinstance(it.args[0], ast.Call) \
                and _ultimo(it.args[0].func) in {"keys", "values", "items"}:
            alvo = _nome(it.args[0].func.value) if isinstance(it.args[0].func, ast.Attribute) else ""
            if alvo and not _muta(alvo, node.body):
                self.add("MEM-06", node.lineno, f"`list({alvo}.{_ultimo(it.args[0].func)}())` só para iterar — itere a view")

    def _regra_cache(self, node):
        params = [a.arg for a in node.args.args + node.args.kwonlyargs if a.arg not in {"self", "cls"}]
        aberto = [p for p in params if _RE_PARAM_ABERTO.search(p)]
        # domínio fechado (ex.: _rx(padrao) só com padrões do próprio código) → 🔵; domínio aberto → 🟡
        sev = NEC if aberto else SUG
        sufixo = f" (parâmetro de domínio aberto: {', '.join(aberto)})" if aberto else " (domínio parece fechado: confirme o nº de valores distintos)"
        for d in node.decorator_list:
            nome = _ultimo(d)
            if nome == "cache":
                self.add("MEM-01", node.lineno, "`@cache` nunca descarta entradas — cresce sem limite" + sufixo, sev)
            elif nome == "lru_cache":
                maxsize_none = isinstance(d, ast.Call) and any(
                    k.arg == "maxsize" and isinstance(k.value, ast.Constant) and k.value.value is None for k in d.keywords)
                em_metodo = bool(self.classes) and node.args.args and node.args.args[0].arg in {"self", "cls"}
                if maxsize_none:
                    self.add("MEM-01", node.lineno, "`lru_cache(maxsize=None)` é ilimitado" + sufixo, sev)
                elif em_metodo:
                    self.add("MEM-01", node.lineno, "`lru_cache` em método: cada `self` fica preso no cache global da classe")

    def _regra_dataclass(self, node: ast.ClassDef):
        for d in node.decorator_list:
            if _ultimo(d) != "dataclass":
                continue
            kws = {k.arg: k.value for k in d.keywords} if isinstance(d, ast.Call) else {}
            slots = kws.get("slots")
            if isinstance(slots, ast.Constant) and slots.value is True:
                return
            campos = sum(1 for st in node.body if isinstance(st, ast.AnnAssign))
            if campos >= 4:
                self.dataclasses_sem_slots[node.name] = (node.lineno, campos)

    def visit_Call(self, node: ast.Call):
        func = node.func
        nome, ult = _nome(func), _ultimo(func)
        if self.loop and isinstance(func, ast.Name):
            self.instanciadas_em_loop.add(func.id)
        # MEM-02 arquivo inteiro
        if ult == "readlines":
            self.add("MEM-02", node.lineno, "`readlines()` materializa o arquivo inteiro — itere o arquivo")
        if ult in {"splitlines", "split"} and isinstance(func, ast.Attribute) and isinstance(func.value, ast.Call) \
                and _ultimo(func.value.func) == "read":
            self.add("MEM-02", node.lineno, "`read().splitlines()` — duas cópias do arquivo em memória")
        # MEM-04 lista materializada em agregador
        if isinstance(func, ast.Name) and func.id in _AGREGADORES and len(node.args) >= 1:
            idx = 1 if func.id in {"map", "filter"} else 0
            if len(node.args) > idx and isinstance(node.args[idx], ast.ListComp):
                self.add("MEM-04", node.lineno, f"`{func.id}([...])` — troque por expressão geradora `{func.id}(... for ...)`")
        # NB: `"".join([...])` NÃO é penalizado: str.join precisa do tamanho e converte gerador em lista de qualquer forma.
        # MEM-07 deepcopy em loop
        if ult == "deepcopy" and self.loop:
            self.add("MEM-07", node.lineno, "`deepcopy` dentro de loop")
        # MEM-08/09/10 pandas
        if ult in _LEITORES_PANDAS and nome.split(".")[0] in {"pd", "pandas"}:
            if not (_kwargs(node) & _KW_PANDAS_OK):
                self.add("MEM-08", node.lineno, f"`{nome}` sem dtype/usecols/chunksize/columns/dtype_backend")
        if ult == "iterrows":
            self.add("MEM-09", node.lineno, "`iterrows()` cria uma Series por linha — vetorize ou `itertuples`")
        if self.loop and (nome in {"pd.concat", "pandas.concat"} or
                          (ult == "copy" and isinstance(func, ast.Attribute) and re.search(r"(?i)df|frame", _nome(func.value) or ""))):
            self.add("MEM-10", node.lineno, f"`{nome}` dentro de loop — acumule e concatene uma vez")
        # MEM-11 download/upload inteiro
        if ult == "write" and len(node.args) == 1:
            a = node.args[0]
            if (isinstance(a, ast.Attribute) and a.attr == "content") or (isinstance(a, ast.Call) and _ultimo(a.func) == "read"):
                self.add("MEM-11", node.lineno, "corpo inteiro em memória antes de gravar — use stream/iter_content/fileobj")
        # MEM-14 hash de arquivo inteiro
        if nome.startswith("hashlib.") and node.args and isinstance(node.args[0], ast.Call) and _ultimo(node.args[0].func) == "read":
            self.add("MEM-14", node.lineno, "hash sobre `read()` inteiro — `hashlib.file_digest` ou blocos")
        if ult == "update" and node.args and isinstance(node.args[0], ast.Call) and _ultimo(node.args[0].func) == "read":
            self.add("MEM-14", node.lineno, "`update(read())` — leia em blocos de 1 MiB")
        # MEM-15 exceção guardada
        if self.excecoes and ult in {"append", "add", "put", "put_nowait", "insert"}:
            for a in node.args:
                if isinstance(a, ast.Name) and a.id in self.excecoes:
                    self.add("MEM-15", node.lineno, f"exceção `{a.id}` guardada em coleção — segura traceback e frames; guarde str/repr")
        # MEM-16 gather sem backpressure / create_task em loop
        if ult == "gather" and any(isinstance(a, ast.Starred) and isinstance(a.value, (ast.ListComp, ast.GeneratorExp)) for a in node.args):
            if not (self.funcoes and _contem_nomes(self.funcoes[-1], _BACKPRESSURE)):
                self.add("MEM-16", node.lineno, "`gather(*[...])` sem Semaphore/TaskGroup — todas as tarefas vivas ao mesmo tempo")
        if ult in {"create_task", "ensure_future"} and self.loop \
                and (nome.rsplit(".", 1)[0] if "." in nome else "") in _CREATE_TASK_ASYNC \
                and not (self.funcoes and _contem_nomes(self.funcoes[-1], _BACKPRESSURE)):
            self.add("MEM-16", node.lineno, "`create_task` em loop sem backpressure")
        # MEM-17 Pool / Queue
        if ult == "Pool" and "maxtasksperchild" not in _kwargs(node):
            self.add("MEM-17", node.lineno, "`Pool` sem `maxtasksperchild` — worker que vaza vive para sempre")
        if ult == "Queue" and not node.args and "maxsize" not in _kwargs(node) and nome.split(".")[0] in {"Queue", "queue", "asyncio", "multiprocessing", "mp"}:
            self.add("MEM-17", node.lineno, "`Queue()` sem `maxsize` — produtor sem backpressure")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        if isinstance(node.value, ast.Call) and _nome(node.value.func) == "sorted":
            s = node.slice
            if (isinstance(s, ast.Constant) and s.value == 0) or \
               (isinstance(s, ast.UnaryOp) and isinstance(s.op, ast.USub) and isinstance(s.operand, ast.Constant) and s.operand.value == 1):
                self.add("MEM-18", node.lineno, "`sorted(x)[0|-1]` copia e ordena tudo — `min`/`max`")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign):
        if self.loop and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name) and _eh_str(node.value):
            self.add("MEM-05", node.lineno, f"`{node.target.id} += <str>` em loop — acumule em lista e `join`")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        if self.loop and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            if isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add) and isinstance(v.left, ast.Name) \
                    and v.left.id == node.targets[0].id and isinstance(v.right, (ast.List, ast.ListComp)):
                self.add("MEM-05", node.lineno, f"`{v.left.id} = {v.left.id} + [...]` em loop — use `append`/`extend`")
        self.generic_visit(node)



def _regra_cache_global(tree: ast.Module, add) -> None:
    """MEM-12 — contêiner global com nome de cache/buffer, mutado em função, sem descarte no módulo."""
    candidatos: dict[str, int] = {}
    for st in tree.body:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            alvos = st.targets if isinstance(st, ast.Assign) else [st.target]
            for t in alvos:
                if isinstance(t, ast.Name) and _RE_NOME_CACHE.search(t.id):
                    v = st.value
                    if isinstance(v, (ast.Dict, ast.List, ast.Set)) or (isinstance(v, ast.Call) and _ultimo(v.func) in
                                                                      {"dict", "list", "set", "defaultdict", "OrderedDict"}):
                        candidatos[t.id] = st.lineno
    if not candidatos:
        return
    mutado: set[str] = set()
    descarta: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = _nome(node.func.value)
            if base in candidatos:
                if node.func.attr in {"append", "add", "setdefault", "extend", "update", "insert"}:
                    mutado.add(base)
                if node.func.attr in {"pop", "popitem", "clear", "remove", "discard"}:
                    descarta.add(base)
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            alvos = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in alvos:
                if isinstance(t, ast.Subscript) and _nome(t.value) in candidatos:
                    mutado.add(_nome(t.value))
        if isinstance(node, ast.Delete):
            for t in node.targets:
                if isinstance(t, ast.Subscript) and _nome(t.value) in candidatos:
                    descarta.add(_nome(t.value))
    for nome, linha in candidatos.items():
        if nome in mutado and nome not in descarta:
            add("MEM-12", linha, f"`{nome}` global cresce em função e nada o esvazia — defina limite/TTL ou deque(maxlen)")


# --------------------------------------------------------------------------- #
# Análise de arquivo e orquestração
# --------------------------------------------------------------------------- #
def analisar_fonte(rel: str, texto: str) -> tuple[list[Achado], str | None]:
    linhas = texto.splitlines()
    achados: list[Achado] = []

    def add(regra: str, linha: int, detalhe: str, severidade: str | None = None):
        r = POR_ID[regra]
        idx = max(0, linha - 1)
        trecho = linhas[idx].strip() if idx < len(linhas) else ""
        a = Achado(regra, severidade or r.severidade, rel, linha, trecho[:160], detalhe)
        for j in (idx, idx - 1):
            if 0 <= j < len(linhas):
                m = _RE_SUPRESSAO.search(linhas[j])
                if m and len(m.group(1).strip()) >= 5:
                    a.suprimido, a.motivo = True, m.group(1).strip()
                    break
        if a.chave() not in {x.chave() for x in achados}:
            achados.append(a)

    try:
        tree = ast.parse(texto, filename=rel)
    except (SyntaxError, ValueError) as e:
        return [], f"{rel}: não analisável ({e.__class__.__name__} linha {getattr(e, 'lineno', '?')})"
    v = _Visitor(rel, linhas, add)
    v.visit(tree)
    for nome, (linha, campos) in v.dataclasses_sem_slots.items():
        if nome in v.instanciadas_em_loop or _RE_NOME_REGISTRO.search(nome):
            self_sinal = "instanciada em loop" if nome in v.instanciadas_em_loop else "nome de registro em massa"
            add("MEM-13", linha, f"dataclass `{nome}` com {campos} campos sem `slots=True` ({self_sinal})")
    _regra_cache_global(tree, add)
    achados.sort(key=lambda a: (a.linha, a.regra))
    return achados, None


def _arquivos_git(raiz: Path, ref: str | None) -> list[Path] | None:
    if not (raiz / ".git").exists():
        return None
    argv = ["git", "diff", "--name-only", "--diff-filter=ACMR", ref] if ref else \
           ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.py"]
    try:
        saida = subprocess.run(argv, cwd=raiz, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if saida.returncode != 0:
        return None
    sep = b"\0" if "-z" in argv else b"\n"
    nomes = [n.decode("utf-8", "replace") for n in saida.stdout.split(sep) if n]
    if ref:
        try:
            extra = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=raiz,
                                   capture_output=True, timeout=120)
            nomes += [n.decode("utf-8", "replace") for n in extra.stdout.split(b"\n") if n]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return [raiz / n for n in nomes if n.endswith(".py")]


def _ignorado(rel: str, ignorar: list[str]) -> bool:
    rel = rel.replace("\\", "/")
    if any(p in DIRS_IGNORADOS for p in rel.split("/")[:-1]):
        return True
    return any(fnmatch.fnmatch(rel, pad) or fnmatch.fnmatch(rel, pad.rstrip("/*") + "/*") for pad in ignorar)


def _iterar(raiz: Path, ignorar: list[str]):
    via_git = _arquivos_git(raiz, None)
    if via_git is not None:
        for p in via_git:
            if not _ignorado(os.path.relpath(p, raiz), ignorar):
                yield p
        return
    for atual, dirs, files in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in DIRS_IGNORADOS and not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                p = Path(atual) / f
                if not _ignorado(os.path.relpath(p, raiz), ignorar):
                    yield p


def executar(raiz: Path, *, arquivos: list[Path] | None = None, diff: str | None = None,
             perfil: str = "review", ignorar: list[str] | None = None, incluir_testes: bool = False) -> Relatorio:
    t0 = time.perf_counter()
    raiz = raiz.resolve()
    ignorar = list(ignorar or [])
    rel_ = Relatorio(perfil=perfil, raiz=str(raiz))
    if diff:
        arquivos = _arquivos_git(raiz, diff)
        if arquivos is None:
            rel_.notas.append("git diff indisponível")
            return rel_
    candidatos = arquivos if arquivos is not None else list(_iterar(raiz, ignorar))
    for p in candidatos:
        p = Path(p)
        if not p.is_absolute():
            p = raiz / p
        if not p.is_file() or p.suffix != ".py":
            continue
        rel = os.path.relpath(p, raiz).replace("\\", "/")
        if arquivos is not None and _ignorado(rel, ignorar):
            continue
        if not incluir_testes and _eh_teste(rel):
            continue
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            rel_.arquivos_pulados.append(f"{rel} ({e.__class__.__name__})")
            continue
        achados, nota = analisar_fonte(rel, texto)
        if nota:
            rel_.arquivos_pulados.append(nota)
            continue
        rel_.arquivos_analisados += 1
        rel_.linhas_analisadas += texto.count("\n") + 1
        if perfil == "observacional":
            achados = [a for a in achados if a.severidade == NEC]   # só o que vira débito; sugestões ficam para o review
        rel_.achados += achados
    rel_.achados.sort(key=lambda a: ({NEC: 0, SUG: 1}.get(a.severidade, 2), a.arquivo, a.linha))
    rel_.duracao_s = round(time.perf_counter() - t0, 3)
    return rel_


# --------------------------------------------------------------------------- #
# Apresentação
# --------------------------------------------------------------------------- #
def para_json(rel_: Relatorio, falhar_em_necessario: bool) -> dict:
    codigo, veredito = rel_.veredito(falhar_em_necessario)
    por_regra: dict[str, int] = {}
    for a in rel_.ativos():
        por_regra[a.regra] = por_regra.get(a.regra, 0) + 1
    return {
        "skill": "python-memoria", "versao": "1.0.0", "perfil": rel_.perfil, "raiz": rel_.raiz,
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"), "duracao_s": rel_.duracao_s,
        "arquivos_analisados": rel_.arquivos_analisados, "linhas_analisadas": rel_.linhas_analisadas,
        "arquivos_pulados": rel_.arquivos_pulados, "veredito": veredito, "codigo_saida": codigo,
        "contagem": {"necessario": len(rel_.ativos(NEC)), "sugestao": len(rel_.ativos(SUG)),
                     "suprimidos": len([a for a in rel_.achados if a.suprimido]),
                     "por_1k_linhas": round(1000 * len(rel_.ativos()) / max(1, rel_.linhas_analisadas), 2)},
        "por_regra": dict(sorted(por_regra.items())),
        "achados": [asdict(a) for a in rel_.achados], "notas": rel_.notas,
    }


def imprimir(rel_: Relatorio, falhar_em_necessario: bool, *, maximo: int = 80) -> None:
    codigo, veredito = rel_.veredito(falhar_em_necessario)
    print(f"python-memoria · perfil={rel_.perfil} · arquivos={rel_.arquivos_analisados} · "
          f"linhas={rel_.linhas_analisadas} · {rel_.duracao_s}s")
    por_regra: dict[str, int] = {}
    for a in rel_.ativos():
        por_regra[a.regra] = por_regra.get(a.regra, 0) + 1
    if por_regra:
        print("  por regra: " + ", ".join(f"{k}={v}" for k, v in sorted(por_regra.items())))
        print(f"  densidade: {1000 * len(rel_.ativos()) / max(1, rel_.linhas_analisadas):.2f} achados / 1k linhas")
    for a in rel_.achados[:maximo]:
        marca = f"(suprimido: {a.motivo})" if a.suprimido else ""
        print(f"  {a.severidade} {a.regra} {a.arquivo}:{a.linha} — {a.detalhe} {marca}")
        print(f"      › {a.trecho}")
    if len(rel_.achados) > maximo:
        print(f"  … +{len(rel_.achados) - maximo} achados (ver relatório JSON)")
    for n in rel_.arquivos_pulados[:10]:
        print(f"  ⚠ pulado: {n}")
    for n in rel_.notas:
        print(f"  ⚠ {n}")
    if codigo == 2:
        print("::inconclusivo:: nenhum arquivo analisável — não conta como verificado")
    print(f"RESULTADO: {veredito}")
