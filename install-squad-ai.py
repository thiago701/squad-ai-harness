#!/usr/bin/env python3
"""Squad AI — instalador do ecossistema de skills para o diretório `.claude/`.

CPU-first, **stdlib pura**, **offline**, multiplataforma (Windows/Linux/macOS),
**idempotente**, com **backup + rollback + manifesto + verify**. Princípio gated:
nunca apaga nem sobrescreve sem backup; arquivos sensíveis e conteúdo de
terceiros exigem --force.

**Porta de segurança fail-closed (aplicada a cada skill importada):**
1. bloco "Linha de Defesa de Prompt" obrigatório no SKILL.md (mesma régua do
   `scripts/security/propagar_defesa.py`);
2. frontmatter `name` precisa bater com o nome da pasta;
3. pré-screen estático da casa (`scripts/security/skill_prescreen.py`, subset do
   NVIDIA SkillSpector): achado HIGH/CRITICAL (zero-width, código perigoso,
   outbound) BLOQUEIA; MEDIUM/LOW (prosa defensiva) só avisa;
4. destino já ocupado por conteúdo que este instalador não criou (manifesto
   anterior) = conteúdo de terceiros: preservado; substitui só com --force
   (sempre com backup).

Descobre o ecossistema por varredura (não hardcode): skills em `skills/` e na raiz
(dedup com precedência), além de agents/commands/templates/workflows/memory/docs.
Instalação seletiva por perfil do `manifest.json`: `--perfil backend-java`.

Subcomandos:
  plan      Mostra o que seria feito (dry-run) + veredito da porta de segurança. Não escreve nada.
  install   Instala/atualiza no destino, com backup do que for sobrescrito.
  verify    Confere os arquivos instalados contra o manifesto (hash).
  rollback  Restaura o último backup (ou --backup TS) e remove o que foi criado.
  index     (Re)gera o índice navegável de skills por domínio.
  detectar        Lista os destinos principais presentes (.claude · .dsh · RAI CLI) e outras
                  ferramentas agênticas instaladas, com sugestão de onde instalar (só sugere).
  instalar-todos  Instala em TODOS os destinos de uma vez (em paralelo), cada um com backup e
                  manifesto próprios: --destinos auto (default: os principais presentes na
                  máquina) ou lista (claude,dsh,rai,agents,codex,qwen,cline,...).
  estacao         Configura a máquina para a Squad: diagnostica CPU · GPU · NPU (Intel, NVIDIA,
                  AMD, Apple), recomenda runtime (OpenVINO ou ONNX Runtime CUDA), pacotes pinados,
                  slots de CPU, orçamento de VRAM e os degraus JEV (JevSim · encoder neural · LLM
                  local). Só lê, a menos de --aplicar (venv ~/.squad-ai/venv-neural + perfil
                  ~/.squad-ai/workstation.json + modelo; --calibrar mede; --ativar-neural liga).

Destinos: ~/.claude · ~/.dsh · %LOCALAPPDATA%/RAI/CLI (ou ~/.resolveai) recebem o pacote
completo (skills/, agents/, commands/...). Ferramentas que só leem skills (Codex, Qwen, Cline,
~/.agents/skills...) recebem só <nome>/SKILL.md; o manifesto/backup delas fica em
~/.squad-ai/instalacoes/<id>/ para a ferramenta não ler cópias antigas como skills.
Override de caminhos: ~/.squad-ai/destinos.json.

Ex.: python install-squad-ai.py plan --target ~/.claude
     python install-squad-ai.py install --target ./.claude
     python install-squad-ai.py install --target ~/.claude --perfil backend-java
     python install-squad-ai.py detectar
     python install-squad-ai.py instalar-todos                      # .claude/.dsh/RAI presentes
     python install-squad-ai.py instalar-todos --destinos claude,dsh,codex
     python install-squad-ai.py estacao                             # diagnóstico (não instala nada)
     python install-squad-ai.py estacao --aplicar --calibrar        # configura e mede a máquina
     python install-squad-ai.py instalar-todos --destinos claude,codex,gemini --so-detectados   # rotina diária
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "1.0"
BACKUP_DIR = ".squad-backups"
MANIFEST = "squad-ai-manifest.json"
LOG = "squad-ai-install.log"
REPORT = "squad-ai-install-report.md"
INDEX = "SKILLS-INDEX.md"

DEFAULT_PROFILE = {
    "schema": SCHEMA,
    "exclude": ["_local-artifacts", ".git", "node_modules", "target",
                "__pycache__", ".pytest_cache", ".ruff_cache", ".squad-backups"],
    "sensitive": [".env"],
    "skill_sources": ["skills", "."],  # precedência: o 1º que define um nome vence
    "files": {
        "agents":    [{"glob": ".claude/agents/*.md", "strip": ".claude/agents"}],
        "commands":  [{"glob": "commands/*.md", "strip": "commands"},
                      {"glob": ".claude/commands/*.md", "strip": ".claude/commands"}],
        "templates": [{"glob": "templates/*.md", "strip": "templates"}],
        "workflows": [{"glob": "orchestration/**/*", "strip": "orchestration"}],
        "memory":    [{"glob": "memory/**/*", "strip": "memory"}],
        "docs":      [{"glob": "ARCHITECTURE.md", "strip": "."},
                      {"glob": "RULES.md", "strip": "."},
                      {"glob": "SECURITY.md", "strip": "."}],
    },
}

DOMAINS = [  # (substring no nome da skill, domínio) — primeira correspondência vence
    ("arquiteto-minimalista", "arquitetura"), ("arquiteto-cloud", "arquitetura"),
    ("arquiteto-ia", "multiagentes"), ("arquiteto-performance", "arquitetura"),
    ("arquiteto-dados", "backend"), ("clean-architect", "arquitetura"),
    ("clean-code", "revisão de código"), ("tech-lead", "revisão de código"),
    ("modernizer", "revisão de código"),
    ("java", "backend"), ("spring", "backend"), ("lambda", "backend"),
    ("serverless", "backend"), ("banco", "backend"),
    ("golang", "backend"), ("go-cloud", "backend"), ("go-concurrency", "backend"),
    ("go-error", "backend"), ("go-performance", "backend"),
    ("rust-pro", "backend"), ("rust-async", "backend"), ("rust-unsafe", "backend"),
    ("rust-performance", "backend"), ("rust-error", "backend"),
    ("frontend", "frontend"),
    ("qualidade", "testes"), ("verificacao", "testes"), ("traceability", "testes"),
    ("sonar", "testes"),
    ("documentacao", "documentação"), ("markitdown", "documentação"),
    ("devops", "devops"), ("iac", "devops"), ("localstack", "devops"),
    ("datadog", "devops"), ("dd-", "devops"),
    ("seguranca", "segurança"), ("auditoria", "segurança"),
    ("mcp", "mcp"), ("crewai", "multiagentes"), ("squad", "multiagentes"),
    ("orchestr", "multiagentes"), ("conductor", "multiagentes"),
    ("memoria", "rag"), ("rag", "rag"),
    ("aprendizado", "produtividade"), ("compactacao", "produtividade"),
    ("spec-", "produtividade"), ("especificacao", "documentação"),
]


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ts_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(name: str) -> str:
    low = name.lower()
    for needle, domain in DOMAINS:
        if needle in low:
            return domain
    return "produtividade"


@dataclass
class Item:
    target_rel: str   # caminho relativo ao .claude/ destino (sempre POSIX)
    src: Path
    category: str
    skill: str | None = None


@dataclass
class Summary:
    installed: list = field(default_factory=list)
    updated: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    sensitive: list = field(default_factory=list)
    backups: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)
    blocked: list = field(default_factory=list)     # (skill, motivo) — porta de segurança
    foreign: list = field(default_factory=list)    # conteúdo de terceiros preservado (exige --force)
    warnings: list = field(default_factory=list)   # avisos de pré-screen (MEDIUM/LOW)
    orphans: list = field(default_factory=list)    # instalados por nós, sumiram da fonte, ficaram
    pruned: list = field(default_factory=list)     # órfãos removidos com --podar (backup feito)


class Log:
    def __init__(self, path: Path | None, quiet: bool = False):
        self.path = path
        self.quiet = quiet
        self.lines: list[str] = []

    def __call__(self, msg: str) -> None:
        line = f"[{iso_now()}] {msg}"
        self.lines.append(line)
        if not self.quiet:
            # Windows/cp1252 pode falhar com símbolos Unicode como ↑ (U+2191).
            # Mantém o log em UTF-8 e faz fallback seguro apenas na saída do console.
            try:
                print(msg)
            except UnicodeEncodeError:
                enc = getattr(sys.stdout, "encoding", None) or "utf-8"
                safe = msg.encode(enc, errors="replace").decode(enc, errors="replace")
                print(safe)

    def flush(self) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def _excluded(rel_parts, exclude) -> bool:
    return any(part in exclude for part in rel_parts)


def load_profile(config_path: str | None) -> dict:
    if not config_path:
        return DEFAULT_PROFILE
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    prof = dict(DEFAULT_PROFILE)
    prof.update(data)
    return prof


def _has_skill_md(d: Path) -> bool:
    """Valida por ENUMERAÇÃO (não por is_file, que mente em alguns mounts):
    o dir só é uma skill se SKILL.md aparece como filho real e legível."""
    try:
        return any(c.name == "SKILL.md" and c.is_file() for c in d.iterdir())
    except OSError:
        return False


def discover_skills(source: Path, profile: dict):
    exclude = set(profile["exclude"])
    seen: dict[str, Path] = {}
    dups: list[str] = []
    for label in profile["skill_sources"]:
        root = source if label == "." else source / label
        if not root.exists():
            continue
        for child in sorted(p for p in root.iterdir() if p.is_dir()):
            if child.name in exclude:
                continue
            if not _has_skill_md(child):
                continue  # ignora cópia incompleta/stale; deixa a outra raiz vencer
            if child.name in seen:
                dups.append(f"{child.name} (ignorado em '{label}/'; vence '{seen[child.name].parent.name or '.'}/')")
                continue
            seen[child.name] = child
    return seen, dups


def discover(source: Path, profile: dict):
    exclude = set(profile["exclude"])
    items: list[Item] = []
    skills, dups = discover_skills(source, profile)
    for name, sdir in skills.items():
        base = sdir.resolve()  # resolve symlinks: skills/<x> pode ser link p/ a raiz
        for f in sorted(base.rglob("*")):
            if f.is_file() and not _excluded(f.relative_to(base).parts, exclude):
                rel = f"skills/{name}/{f.relative_to(base).as_posix()}"
                items.append(Item(rel, f, "skills", name))
    for category, rules in profile["files"].items():
        for rule in rules:
            glob, strip = rule["glob"], rule["strip"]
            base = source if strip == "." else source / strip
            for f in sorted(source.glob(glob)):
                if not f.is_file():
                    continue
                if _excluded(f.relative_to(source).parts, exclude):
                    continue
                within = f.name if strip == "." else f.relative_to(base).as_posix()
                items.append(Item(f"{category}/{within}", f, category))
    # dedup por target_rel (mantém o 1º)
    uniq: dict[str, Item] = {}
    for it in items:
        uniq.setdefault(it.target_rel, it)
    return list(uniq.values()), dups, skills


def plan(items, target: Path, profile: dict, prev_paths: set | None = None):
    sensitive = set(profile["sensitive"])
    actions = []
    for it in items:
        dst = target / it.target_rel
        if Path(it.target_rel).name in sensitive:
            actions.append((it, "SENSITIVE"))
        elif not dst.exists():
            actions.append((it, "NEW"))
        elif sha256_file(dst) == sha256_file(it.src):
            actions.append((it, "SAME"))
        elif prev_paths is not None and it.target_rel not in prev_paths:
            # destino existe, difere da fonte e NAO foi instalado por este
            # instalador (fora do manifesto anterior) => conteudo de terceiros
            actions.append((it, "FOREIGN"))
        else:
            actions.append((it, "UPDATE"))
    return actions


FRONTMATTER_NAME_RE = re.compile(r"^name:\s*['\"]?(?P<name>[A-Za-z0-9_.-]+)", re.M)


def _frontmatter_name(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    m = FRONTMATTER_NAME_RE.search(text[3:end])
    return m.group("name") if m else None


def _tem_defesa(text: str) -> bool:
    """Mesma régua do propagador (`propagar_defesa.py::_skills_sem_defesa`)."""
    low = text.lower()
    return "linha de defesa de prompt" in low or "defesa de prompt" in low


def _prescreen_skill(sdir: Path):
    """Pré-screen estático reutilizando o instrumento da casa
    (`scripts/security/skill_prescreen.py` — subset do NVIDIA SkillSpector).
    HIGH/CRITICAL => bloqueadores; MEDIUM/LOW => avisos (mesma calibração do
    scanner: código perigoso bloqueia, prosa defensiva só avisa)."""
    import importlib.util

    prescreen_path = Path(__file__).resolve().parent / "scripts" / "security" / "skill_prescreen.py"
    spec = importlib.util.spec_from_file_location("skill_prescreen", prescreen_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, mod)
    spec.loader.exec_module(mod)

    blockers: list[str] = []
    warnings: list[str] = []
    for f in sorted(p for p in sdir.rglob("*") if p.is_file()):
        try:
            findings = mod.scan_file(f, sdir)
        except OSError:
            continue
        for fd in findings:
            entry = f"{f.name}:{fd.line} [{fd.rule} {fd.severity}] {fd.excerpt[:60]}"
            if fd.severity in ("HIGH", "CRITICAL"):
                blockers.append(entry)
            else:
                warnings.append(entry)
    return blockers, warnings


def auditar_skills(skills: dict) -> tuple[dict, list]:
    """Porta de segurança fail-closed sobre o conjunto de skills a instalar.

    Retorna (bloqueados, avisos):
    - bloqueados: {nome: [motivo, ...]} — defesa ausente, frontmatter name !=
      pasta, ou achado HIGH/CRITICAL de pré-screen => a skill NÃO é instalada.
    - avisos: [texto, ...] — achados MEDIUM/LOW de pré-screen (prosa defensiva).
    """
    blocked: dict[str, list] = {}
    warnings: list[str] = []
    for name, sdir in sorted(skills.items()):
        motivos: list[str] = []
        md = sdir / "SKILL.md"
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            motivos.append("SKILL.md ilegível")
            blocked[name] = motivos
            continue
        if not _tem_defesa(text):
            motivos.append("sem bloco 'Linha de Defesa de Prompt'")
        declarado = _frontmatter_name(text)
        if declarado is None:
            motivos.append("frontmatter sem campo name")
        elif declarado != name:
            motivos.append(f"frontmatter name '{declarado}' != pasta '{name}'")
        blockers, warns = _prescreen_skill(sdir)
        motivos.extend(f"pré-screen: {b}" for b in blockers)
        warnings.extend(f"{name}: {w}" for w in warns)
        if motivos:
            blocked[name] = motivos
    return blocked, warnings


def _prev_manifest_paths(target: Path) -> set | None:
    """`target` aqui é o diretório de METADADOS (= destino, exceto no layout só-skills)."""
    mpath = target / MANIFEST
    if not mpath.exists():
        return set()  # primeira instalação: nada é "nosso" ainda
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
        return {e["target_rel"] for e in data.get("items", []) if "target_rel" in e}
    except (json.JSONDecodeError, OSError):
        return None  # manifesto ilegível: tratar tudo como alheio (conservador)


def _load_perfis(source: Path) -> dict | None:
    mp = source / "manifest.json"
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8")).get("perfis", {})
    except (json.JSONDecodeError, OSError):
        return None


def _resolver_perfil(perfis: dict, nome: str, _visto: frozenset = frozenset()) -> list[str]:
    if nome in _visto:
        raise ValueError(f"ciclo de herança em perfis: {nome}")
    p = perfis.get(nome)
    if p is None:
        raise KeyError(nome)
    out: list[str] = []
    for base in p.get("herda", []) or []:
        out += _resolver_perfil(perfis, base, _visto | {nome})
    for ref in p.get("skills", []) or []:
        leaf = ref.replace("\\", "/").split("/")[-1]
        if leaf not in out:
            out.append(leaf)
    return out


def aplicar_layout(items, layout: str):
    """'completo' = pacote do .claude; 'skills' = só <nome>/... (pasta de skills da ferramenta)."""
    if layout == "completo":
        return items
    if layout != "skills":
        raise ValueError(f"layout desconhecido: {layout}")
    return [Item(it.target_rel[len("skills/"):], it.src, it.category, it.skill)
            for it in items if it.category == "skills"]


def _bdir_livre(meta: Path) -> tuple[str, Path]:
    """Pasta de backup desta execução; nunca reaproveita a de outra no mesmo segundo."""
    ts = base = ts_now()
    n = 1
    while (meta / BACKUP_DIR / ts).exists():
        n += 1
        ts = f"{base}-{n}"
    return ts, meta / BACKUP_DIR / ts


def _orfaos(meta: Path, todos_itens) -> list[dict]:
    """Entradas do manifesto anterior (só o que ESTE instalador pôs lá) que a fonte não
    fornece mais. Compara com a fonte inteira, não com o perfil: fora do perfil não é órfão."""
    mpath = meta / MANIFEST
    if not mpath.exists():
        return []
    try:
        antigos = json.loads(mpath.read_text(encoding="utf-8")).get("items", [])
    except (json.JSONDecodeError, OSError):
        return []  # manifesto ilegível: não poda nada (conservador)
    atuais = {it.target_rel for it in todos_itens}
    return [e for e in antigos if e.get("target_rel") and e["target_rel"] not in atuais]


def _remover_pastas_vazias(pasta: Path, raiz: Path) -> None:
    while pasta != raiz and raiz in pasta.parents and not any(pasta.iterdir()):
        pasta.rmdir()
        pasta = pasta.parent


def _podar(orfaos: list[dict], target: Path, bdir: Path, backup_rec: dict, s: Summary, log) -> None:
    """Remove órfãos inalterados (sha256 igual ao do manifesto), com backup; o resto fica."""
    for e in orfaos:
        rel, dst = e["target_rel"], target / e["target_rel"]
        if dst.exists() and sha256_file(dst) != e.get("sha256"):
            s.orphans.append(rel)
            log(f"  ⊘ órfão alterado localmente, preservado: {rel}")
            continue
        if dst.exists():
            bpath = bdir / rel
            bpath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, bpath)
            dst.unlink()
            backup_rec["podados"].append(rel)
            _remover_pastas_vazias(dst.parent, target)
            log(f"  - podado (backup feito): {rel}")
        s.pruned.append(rel)


def do_install(source, target, profile, force, log, allowed_skills=None,
               layout: str = "completo", meta: Path | None = None, podar: bool = False) -> Summary:
    """`meta` = onde ficam manifesto e backups (default: o próprio destino).
    `podar` = remove (com backup) o que este instalador pôs e a fonte não tem mais."""
    meta = meta or target
    items, dups, skills = discover(source, profile)
    items = aplicar_layout(items, layout)
    orfaos = _orfaos(meta, items)
    if allowed_skills is not None:
        skills = {n: s for n, s in skills.items() if n in allowed_skills}
        items = [it for it in items if it.category != "skills" or it.skill in allowed_skills]
    blocked, warnings = auditar_skills(skills)
    for name, motivos in blocked.items():
        for motivo in motivos:
            log(f"  ✗ BLOQUEADO (não instalado) — {name}: {motivo}")
    # skills bloqueadas saem do conjunto: não são copiadas nem entram no manifesto
    items = [it for it in items if it.category != "skills" or it.skill not in blocked]
    prev_paths = _prev_manifest_paths(meta)
    actions = plan(items, target, profile, prev_paths)
    s = Summary(duplicates=dups)
    ts, bdir = _bdir_livre(meta)
    backup_rec = {"ts": ts, "overwritten": [], "created": [], "podados": []}
    for it, action in actions:
        dst = target / it.target_rel
        if it.category == "skills" and it.skill in blocked:
            continue
        if action == "SENSITIVE" and not force:
            s.sensitive.append(it.target_rel)
            log(f"  ~ sensível, preservado (use --force p/ sobrescrever): {it.target_rel}")
            continue
        if action == "SAME":
            s.skipped.append(it.target_rel)
            continue
        if action == "FOREIGN" and not force:
            s.foreign.append(it.target_rel)
            log(f"  ⊘ conteúdo de terceiros preservado (use --force p/ substituir): {it.target_rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if action in ("UPDATE", "FOREIGN", "SENSITIVE"):
            bpath = bdir / it.target_rel
            bpath.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, bpath)
            backup_rec["overwritten"].append(it.target_rel)
            s.backups.append(it.target_rel)
            shutil.copy2(it.src, dst)
            s.updated.append(it.target_rel)
            log(f"  ↑ atualizado (backup feito): {it.target_rel}")
        else:  # NEW
            backup_rec["created"].append(it.target_rel)
            shutil.copy2(it.src, dst)
            s.installed.append(it.target_rel)
            log(f"  + instalado: {it.target_rel}")
    if podar:
        _podar(orfaos, target, bdir, backup_rec, s, log)
    else:
        s.orphans = [e["target_rel"] for e in orfaos if (target / e["target_rel"]).exists()]
    if s.orphans and not podar:
        log(f"  ⊘ {len(s.orphans)} arquivo(s) órfão(s): saíram da fonte e continuam instalados "
            "(rode com --podar para remover com backup)")
    if backup_rec["overwritten"] or backup_rec["created"] or backup_rec["podados"]:
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "backup-manifest.json").write_text(
            json.dumps(backup_rec, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_manifest(source, target, items, profile, meta, remover=set(s.pruned))
    s.blocked = [f"{n}: {'; '.join(m)}" for n, m in blocked.items()]
    s.warnings = warnings
    return s


def _write_manifest(source, target, items, profile, meta: Path | None = None, remover: set = frozenset()):
    meta = meta or target
    entries = []
    for it in items:
        dst = target / it.target_rel
        if dst.exists():
            entries.append({
                "category": it.category, "skill": it.skill,
                "target_rel": it.target_rel,
                "sha256": sha256_file(dst), "bytes": dst.stat().st_size,
                "source_rel": it.src.relative_to(source).as_posix(),
            })
    # MERGE com o manifesto anterior: instalação por perfil não pode apagar a
    # memória do que já foi instalado por outra chamada (senão o guarda FOREIGN
    # trata o conteúdo nosso como "terceiros"). Upsert por target_rel.
    mpath = meta / MANIFEST
    por_alvo = {e["target_rel"]: e for e in entries}
    if mpath.exists():
        try:
            antigo = json.loads(mpath.read_text(encoding="utf-8"))
            for e in antigo.get("items", []):
                por_alvo.setdefault(e.get("target_rel"), e)
        except (json.JSONDecodeError, OSError):
            pass
    merged = sorted((e for e in por_alvo.values() if e.get("target_rel") not in remover),
                    key=lambda e: e.get("target_rel", ""))
    manifest = {
        "schema": profile["schema"], "generated_at": iso_now(),
        "os": platform.system(), "source": str(source),
        "counts": {"items": len(merged)},
        "items": merged,
    }
    meta.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def do_verify(target, log, meta: Path | None = None) -> int:
    mpath = (meta or target) / MANIFEST
    if not mpath.exists():
        log(f"[X] manifesto ausente em {mpath} — nada instalado?")
        return 2
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    ok = missing = drift = 0
    for e in manifest["items"]:
        dst = target / e["target_rel"]
        if not dst.exists():
            missing += 1
            log(f"  [X] AUSENTE: {e['target_rel']}")
        elif sha256_file(dst) != e["sha256"]:
            drift += 1
            log(f"  ! ALTERADO: {e['target_rel']}")
        else:
            ok += 1
    log(f"verify: {ok} OK · {missing} ausentes · {drift} alterados (de {len(manifest['items'])})")
    return 0 if (missing == 0 and drift == 0) else 1


def do_rollback(target, which, log, meta: Path | None = None) -> int:
    root = (meta or target) / BACKUP_DIR
    if not root.exists() or not any(root.iterdir()):
        log("✗ sem backups para reverter.")
        return 2
    sets = sorted(p.name for p in root.iterdir() if p.is_dir())
    ts = which or sets[-1]
    bdir = root / ts
    rec_path = bdir / "backup-manifest.json"
    if not rec_path.exists():
        log(f"✗ backup '{ts}' sem manifesto.")
        return 2
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    restored = removed = 0
    for rel in rec["overwritten"]:
        src = bdir / rel
        if src.exists():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / rel)
            restored += 1
    for rel in rec["created"]:
        f = target / rel
        if f.exists():
            f.unlink()
            removed += 1
    for rel in rec.get("podados", []):
        src = bdir / rel
        if src.exists():
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / rel)
            restored += 1
    log(f"rollback '{ts}': {restored} restaurados · {removed} criados removidos.")
    return 0


def do_baseline(source, profile, out: Path) -> dict:
    """Snapshot de integridade da FONTE: hash por arquivo + fingerprint agregado.
    Reusa discover()/sha256_file(); determinístico (mesma fonte ⇒ mesmo aggregate_sha256)."""
    items, dups, skills = discover(source, profile)
    entries = []
    for it in sorted(items, key=lambda x: x.target_rel):
        if it.src.exists():
            entries.append({
                "target_rel": it.target_rel, "category": it.category, "skill": it.skill,
                "source_rel": it.src.relative_to(source).as_posix(),
                "sha256": sha256_file(it.src), "bytes": it.src.stat().st_size,
            })
    agg = hashlib.sha256(
        "\n".join(f"{e['target_rel']}:{e['sha256']}" for e in entries).encode("utf-8")
    ).hexdigest()
    manifest = {
        "_comment": "Baseline de integridade do ecossistema Squad AI (snapshot da FONTE). "
                    "Regenere com: python install-squad-ai.py baseline. "
                    "'aggregate_sha256' é o fingerprint único do conjunto.",
        "schema": profile["schema"], "kind": "source-baseline", "generated_at": iso_now(),
        "counts": {"items": len(entries), "skills": len(skills), "duplicates_flagged": len(dups)},
        "aggregate_sha256": agg, "duplicates": dups, "items": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" explícito: modo texto no Windows escreveria CRLF (gate test_no_crlf)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def do_baseline_check(source, profile, manifest_path: Path) -> int:
    """Gate de integridade: compara o aggregate_sha256 atual da fonte com o versionado.
    0 = íntegro · 1 = drift · 2 = baseline ausente. Não escreve nada permanente
    (arquivo temporário dentro da própria fonte — sandbox-safe)."""
    import os
    if not manifest_path.exists():
        print(f"X baseline ausente: {manifest_path} (rode `baseline` p/ criar)")
        return 2
    stored = json.loads(manifest_path.read_text(encoding="utf-8")).get("aggregate_sha256")
    tmp = source / f".squad-baseline-check-{os.getpid()}.json"
    cur = do_baseline(source, profile, tmp)
    try:
        tmp.unlink()
    except OSError:
        pass
    cur_agg = cur["aggregate_sha256"]
    if cur_agg == stored:
        print(f"OK baseline integro: aggregate_sha256={cur_agg[:16]}... ({cur['counts']['items']} itens)")
        return 0
    print(f"X DRIFT de integridade: working-tree={cur_agg[:16]}... vs versionado={str(stored)[:16]}...")
    print("  -> rode `python install-squad-ai.py baseline` e versione o squad-ai-manifest.json atualizado.")
    return 1


def do_index(source, target, profile, log, allowed_skills=None) -> Path:
    _, _, skills = discover(source, profile)
    if allowed_skills is not None:
        skills = {n: s for n, s in skills.items() if n in allowed_skills}
    by_domain: dict[str, list] = {}
    for name, sdir in sorted(skills.items()):
        desc = _read_description(sdir / "SKILL.md")
        by_domain.setdefault(classify(name), []).append((name, desc))
    lines = ["# Índice de Skills da Squad AI (por domínio)", "",
             f"> Gerado por `install-squad-ai.py index` em {iso_now()} · {len(skills)} skills.", ""]
    for domain in sorted(by_domain):
        lines.append(f"## {domain}")
        lines.append("")
        for name, desc in by_domain[domain]:
            lines.append(f"- **{name}** — {desc}")
        lines.append("")
    out = target / INDEX
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    log(f"índice gerado: {out} ({len(skills)} skills em {len(by_domain)} domínios)")
    return out


def _read_description(skill_md: Path) -> str:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "(sem descrição)"
    lines = text.splitlines()
    in_fm = False
    for i, line in enumerate(lines):
        if line.strip() == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and line.lower().startswith("description:"):
            val = line.split(":", 1)[1].strip()
            if val[:1] in (">", "|") or val == "":
                # bloco YAML: junta as linhas mais indentadas seguintes
                base_indent = len(line) - len(line.lstrip())
                parts = []
                for nxt in lines[i + 1:]:
                    if nxt.strip() == "":
                        continue
                    if (len(nxt) - len(nxt.lstrip())) <= base_indent:
                        break
                    parts.append(nxt.strip())
                val = " ".join(parts).strip()
            else:
                val = val.strip('"').strip("'")
            return (val[:157] + "...") if len(val) > 160 else (val or "(sem descrição)")
    return "(sem descrição)"


def write_report(target, summary: Summary, log):
    L = ["# Relatório de Instalação — Squad AI", "",
         f"- **Data:** {iso_now()}", f"- **SO:** {platform.system()}",
         f"- **Destino:** `{target}`", "",
         "## Resumo", "",
         f"- Instalados (novos): **{len(summary.installed)}**",
         f"- Atualizados: **{len(summary.updated)}**",
         f"- Ignorados (idênticos): **{len(summary.skipped)}**",
         f"- Sensíveis preservados: **{len(summary.sensitive)}**",
         f"- Backups criados: **{len(summary.backups)}**",
         f"- Duplicidades sinalizadas: **{len(summary.duplicates)}**",
         f"- Órfãos (saíram da fonte, ainda instalados): **{len(summary.orphans)}**",
         f"- Podados (com backup): **{len(summary.pruned)}**", ""]
    if summary.orphans:
        L += ["## Órfãos (rode com --podar para remover com backup)", ""]
        L += [f"- `{x}`" for x in summary.orphans] + [""]
    if summary.duplicates:
        L += ["## Duplicidades (sinalizadas, não instaladas em duplicata)", ""]
        L += [f"- {d}" for d in summary.duplicates] + [""]
    if summary.blocked:
        L += ["## Bloqueados pela porta de segurança (NÃO instalados)", ""]
        L += [f"- `{x}`" for x in summary.blocked] + [""]
    if summary.foreign:
        L += ["## Conteúdo de terceiros preservado (use --force p/ substituir)", ""]
        L += [f"- `{x}`" for x in summary.foreign] + [""]
    if summary.warnings:
        L += ["## Avisos de pré-screen (MEDIUM/LOW — prosa defensiva, não bloqueia)", ""]
        L += [f"- `{x}`" for x in summary.warnings[:40]] + [""]
        if len(summary.warnings) > 40:
            L += [f"- … +{len(summary.warnings) - 40} avisos (ver log).", ""]
    if summary.sensitive:
        L += ["## Sensíveis preservados (use --force p/ sobrescrever)", ""]
        L += [f"- `{x}`" for x in summary.sensitive] + [""]
    L += ["## Recomendações pós-instalação", "",
          "1. Rode `verify` para confirmar integridade (hash vs manifesto).",
          "2. Confira o índice: `SKILLS-INDEX.md`.",
          "3. Em caso de problema, `rollback` restaura o estado anterior.",
          "4. Reinstale a qualquer momento — é idempotente (só muda o que mudou).", ""]
    out = target / REPORT
    out.write_text("\n".join(L), encoding="utf-8")
    log(f"relatório: {out}")
    return out


# ── destinos: .claude · .dsh · RAI CLI + outras ferramentas agênticas ──────────
# Pastas globais de skills conferidas na documentação oficial de cada ferramenta em 01/10/2026
# (Copilot, Gemini CLI, Cursor, OpenCode, Windsurf/Devin, Codex, Qwen Code, Cline, Antigravity).
PRIMARIOS = [
    {"id": "claude", "nome": "Claude Code / Cowork", "raizes": ["~/.claude"]},
    {"id": "dsh", "nome": "DeepSeek harness (DSH)", "raizes": ["~/.dsh"]},
    {"id": "rai", "nome": "Resolve AI CLI (RAI)",
     "raizes": ["%LOCALAPPDATA%/RAI/CLI", "~/AppData/Local/RAI/CLI", "~/.resolveai"]},
]
# le: pastas globais que a ferramenta TAMBÉM lê — se já instalamos lá, não sugerimos de novo.
OUTRAS = [
    {"id": "agents", "nome": "Pasta interoperável ~/.agents/skills", "skills": "~/.agents/skills",
     "detecta": [], "le": [], "nota": "uma cópia atende Copilot, Gemini CLI, Cursor, OpenCode e Windsurf"},
    {"id": "codex", "nome": "OpenAI Codex CLI", "skills": "~/.codex/skills",
     "detecta": ["~/.codex", "cmd:codex"], "le": []},
    {"id": "copilot", "nome": "GitHub Copilot", "skills": "~/.copilot/skills",
     "detecta": ["~/.copilot"], "le": ["agents"]},
    {"id": "gemini", "nome": "Gemini CLI", "skills": "~/.gemini/skills",
     "detecta": ["~/.gemini/settings.json", "cmd:gemini"], "le": ["agents"]},
    {"id": "antigravity", "nome": "Google Antigravity", "skills": "~/.gemini/config/skills",
     "detecta": ["~/.antigravity", "~/.antigravity-ide", "%LOCALAPPDATA%/antigravity", "cmd:agy"], "le": []},
    {"id": "cursor", "nome": "Cursor", "skills": "~/.cursor/skills",
     "detecta": ["~/.cursor"], "le": ["claude", "agents", "codex"]},
    {"id": "windsurf", "nome": "Windsurf / Devin Desktop", "skills": "~/.codeium/windsurf/skills",
     "detecta": ["~/.codeium/windsurf", "~/.windsurf", "~/.config/devin", "~/.devin"], "le": ["agents"]},
    {"id": "opencode", "nome": "OpenCode", "skills": "~/.config/opencode/skills",
     "detecta": ["~/.config/opencode", "%LOCALAPPDATA%/OpenCode", "%LOCALAPPDATA%/ai.opencode.desktop",
                 "cmd:opencode"], "le": ["claude", "agents"]},
    {"id": "qwen", "nome": "Qwen Code", "skills": "~/.qwen/skills",
     "detecta": ["~/.qwen", "%LOCALAPPDATA%/qwen-code", "cmd:qwen"], "le": []},
    {"id": "cline", "nome": "Cline", "skills": "~/.cline/skills", "detecta": ["~/.cline"], "le": []},
]
# detectadas, mas sem pasta de skills documentada: só aparecem no relatório.
SEM_PADRAO = [
    {"id": "kimi", "nome": "Kimi Code", "detecta": ["~/.kimi-code"]},
    {"id": "grok", "nome": "Grok CLI", "detecta": ["~/.grok"]},
    {"id": "cagent", "nome": "Docker cagent", "detecta": ["~/.cagent"]},
    {"id": "fugu", "nome": "Fugu", "detecta": ["~/.fugu"]},
    {"id": "crewai", "nome": "CrewAI (framework)", "detecta": ["%LOCALAPPDATA%/CrewAI"]},
]
CONFIG_DESTINOS = "destinos.json"     # em ~/.squad-ai/


def _squad_home(home: Path) -> Path:
    return Path(os.environ.get("SQUAD_AI_HOME") or home / ".squad-ai")


def _expandir(caminho: str, home: Path) -> Path:
    if caminho.startswith("%LOCALAPPDATA%"):
        base = os.environ.get("LOCALAPPDATA") if home == Path.home() else None
        base = Path(base) if base else home / "AppData" / "Local"
        return base / caminho[len("%LOCALAPPDATA%/"):]
    if caminho.startswith("~/"):
        return home / caminho[2:]
    return Path(caminho).expanduser()


def _config_destinos(home: Path) -> dict:
    p = _squad_home(home) / CONFIG_DESTINOS
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _existe(alvo: str, home: Path, which) -> bool:
    if alvo.startswith("cmd:"):
        return bool(which(alvo[4:]))
    return _expandir(alvo, home).exists()


def detectar_destinos(home: Path | None = None, which=shutil.which) -> dict:
    """Nunca levanta. Primários presentes/ausentes + outras ferramentas com sugestão."""
    home = Path(home or Path.home())
    cfg = _config_destinos(home)
    prim = []
    for d in PRIMARIOS:
        raiz_cfg = (cfg.get(d["id"]) or {}).get("raiz")
        cands = [raiz_cfg] if raiz_cfg else d["raizes"]
        achada = next((_expandir(c, home) for c in cands if _expandir(c, home).exists()), None)
        prim.append({"id": d["id"], "nome": d["nome"], "raiz": str(achada or _expandir(cands[0], home)),
                     "presente": achada is not None, "layout": (cfg.get(d["id"]) or {}).get("layout", "completo")})
    presentes = {p["id"] for p in prim if p["presente"]}
    outras = []
    for o in OUTRAS:
        if o["id"] == "agents":
            continue
        por = [a for a in o["detecta"] if _existe(a, home, which)]
        if not por:
            continue
        cobertos = [x for x in o["le"] if x in presentes]
        outras.append({"id": o["id"], "nome": o["nome"], "detectado_por": por, "skills": str(_expandir(o["skills"], home)),
                       "le": o["le"], "ja_coberto_por": cobertos,
                       "instalado": (_expandir(o["skills"], home)).exists()})
    sugestoes = []
    usa_agents = [o for o in outras if "agents" in o["le"] and not o["ja_coberto_por"]]
    if usa_agents:
        sugestoes.append({"id": "agents", "skills": str(_expandir("~/.agents/skills", home)),
                          "motivo": "lida por " + ", ".join(o["nome"] for o in usa_agents)})
    for o in outras:
        if o["ja_coberto_por"] or "agents" in o["le"]:
            continue
        sugestoes.append({"id": o["id"], "skills": o["skills"], "motivo": f"{o['nome']} detectado"})
    sem = [{"id": s["id"], "nome": s["nome"]} for s in SEM_PADRAO
           if any(_existe(a, home, which) for a in s["detecta"])]
    return {"primarios": prim, "outras": outras, "sugestoes": sugestoes, "sem_padrao": sem}


def resolver_destinos(sel: str, home: Path | None = None, which=shutil.which,
                      so_detectados: bool = False) -> list[dict]:
    """'auto' = primários presentes; senão lista de ids. Cada destino: id, alvo, layout, meta.

    `so_detectados=True` (uso em rotina): da lista pedida, fica só o destino cuja ferramenta existe nesta máquina
    (primário com a raiz presente; outra ferramenta com algum sinal de `detecta`) — nunca cria pasta de ferramenta
    que não está instalada. `agents` conta como detectado quando alguma ferramenta que o lê foi detectada."""
    home = Path(home or Path.home())
    det = detectar_destinos(home, which)
    if so_detectados and sel not in ("auto", ""):
        presentes = {p["id"] for p in det["primarios"] if p["presente"]}
        detectadas = {o["id"] for o in det["outras"]}
        if any("agents" in o["le"] for o in det["outras"]) or _expandir("~/.agents/skills", home).exists():
            detectadas.add("agents")
        pedidos = [x.strip() for x in sel.split(",") if x.strip()]
        conhecidos = {p["id"] for p in PRIMARIOS} | {x["id"] for x in OUTRAS} | {
            e.get("id") for e in _config_destinos(home).get("extras", []) if isinstance(e, dict)}
        desconhecidos = [x for x in pedidos if x not in conhecidos]
        if desconhecidos:
            raise KeyError(f"destino desconhecido: {', '.join(desconhecidos)}")
        sel = ",".join(x for x in pedidos if x in presentes or x in detectadas)
        if not sel:
            return []
    prim = {p["id"]: p for p in det["primarios"]}
    cfg = _config_destinos(home)
    extras = {e["id"]: e for e in cfg.get("extras", []) if isinstance(e, dict) and e.get("id")}
    ids = [p["id"] for p in det["primarios"] if p["presente"]] if sel in ("auto", "") else \
        [x.strip() for x in sel.split(",") if x.strip()]
    out = []
    for i in ids:
        if i in prim:
            out.append({"id": i, "alvo": Path(prim[i]["raiz"]), "layout": prim[i]["layout"], "meta": None})
            continue
        o = next((x for x in OUTRAS if x["id"] == i), None) or extras.get(i)
        if o is None:
            raise KeyError(f"destino desconhecido: {i} (conhecidos: "
                           f"{', '.join([p['id'] for p in PRIMARIOS] + [x['id'] for x in OUTRAS] + list(extras))})")
        alvo = _expandir(o.get("skills") or o.get("raiz"), home)
        layout = o.get("layout", "skills")
        meta = _squad_home(home) / "instalacoes" / i if layout == "skills" else None
        out.append({"id": i, "alvo": alvo, "layout": layout, "meta": meta})
    return out


def instalar_todos(source, destinos: list[dict], profile, force, allowed_skills=None,
                   quiet: bool = False, paralelo: bool = True, podar: bool = False) -> dict:
    """Instala em cada destino (em paralelo — destinos independentes). Uma falha não derruba os outros."""
    from concurrent.futures import ThreadPoolExecutor

    def um(d):
        meta = d["meta"] or d["alvo"]
        log = Log(meta / LOG, quiet)
        try:
            d["alvo"].mkdir(parents=True, exist_ok=True)
            meta.mkdir(parents=True, exist_ok=True)
            log(f"[{d['id']}] INSTALL · destino={d['alvo']} · layout={d['layout']}")
            s = do_install(source, d["alvo"], profile, force, lambda m: log(f"[{d['id']}] {m.strip()}"),
                           allowed_skills, d["layout"], d["meta"], podar)
            if d["layout"] == "completo":
                do_index(source, d["alvo"], profile, lambda m: None, allowed_skills)
            write_report(meta, s, lambda m: None)
            return d["id"], {"ok": True, "novos": len(s.installed), "atualizados": len(s.updated),
                             "iguais": len(s.skipped), "bloqueados": len(s.blocked),
                             "terceiros": len(s.foreign), "orfaos": len(s.orphans),
                             "podados": len(s.pruned), "alvo": str(d["alvo"]), "meta": str(meta)}
        except Exception as e:  # um destino quebrado não impede os outros
            log(f"[{d['id']}] ✗ falhou: {type(e).__name__}: {e}")
            return d["id"], {"ok": False, "erro": f"{type(e).__name__}: {e}", "alvo": str(d["alvo"])}
        finally:
            log.flush()

    if paralelo and len(destinos) > 1:
        with ThreadPoolExecutor(max_workers=len(destinos)) as ex:
            res = dict(ex.map(um, destinos))
    else:
        res = dict(um(d) for d in destinos)
    return res


def _imprimir_deteccao(det: dict) -> None:
    print("Destinos principais:")
    for p in det["primarios"]:
        print(f"  [{'x' if p['presente'] else ' '}] {p['id']:<8} {p['nome']:<26} {p['raiz']}")
    if det["outras"]:
        print("Outras ferramentas agênticas detectadas:")
        for o in det["outras"]:
            cob = f" (já lê {', '.join(o['ja_coberto_por'])} — não precisa instalar de novo)" if o["ja_coberto_por"] else ""
            print(f"  - {o['nome']:<26} skills em {o['skills']}{cob}")
    if det["sem_padrao"]:
        print("Detectadas sem pasta de skills documentada: " + ", ".join(s["nome"] for s in det["sem_padrao"]))
    if det["sugestoes"]:
        ids = ",".join([p["id"] for p in det["primarios"] if p["presente"]] + [s["id"] for s in det["sugestoes"]])
        print("Sugestão (só instala se você pedir):")
        for s in det["sugestoes"]:
            print(f"  + {s['id']:<8} → {s['skills']}  ({s['motivo']})")
        print(f"  comando: python install-squad-ai.py instalar-todos --destinos {ids}")


def _cmd_estacao(args, source: Path) -> int:
    """Diagnóstico CPU · GPU · NPU + recomendação; com --aplicar, configura a máquina."""
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    try:
        from scripts.accel import estacao
    except ImportError as e:
        print(f"✗ módulo de estação indisponível em {source}: {e}", file=sys.stderr)
        return 2
    diag = estacao.diagnosticar()
    rec = estacao.recomendar(diag)
    if args.json:
        print(json.dumps({"diagnostico": diag, "recomendacao": rec}, ensure_ascii=False, indent=1))
    else:
        print(estacao.resumo(diag, rec))
    if not args.aplicar:
        if not args.json:
            print("\nNada foi instalado. Para configurar: python install-squad-ai.py estacao --aplicar "
                  "[--calibrar] [--testes] [--ativar-neural]")
        return 0
    return estacao.aplicar(diag, rec, source, card=args.card, model_dir=args.model_dir, calibrar=args.calibrar,
                           rapido=args.rapido, testes=args.testes, ativar_neural=args.ativar_neural)


def _resolve_target(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    return (Path.home() / ".claude").resolve()


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Instalador do ecossistema Squad AI (.claude, .dsh, RAI CLI e outros)")
    ap.add_argument("command", choices=["plan", "install", "verify", "rollback", "index", "baseline",
                                        "detectar", "instalar-todos", "estacao"])
    ap.add_argument("--destinos", default="auto",
                    help="instalar-todos: auto (principais presentes) ou lista claude,dsh,rai,agents,codex,...")
    ap.add_argument("--json", action="store_true", help="detectar: saída JSON")
    ap.add_argument("--source", help="raiz do repo Squad AI (default: pasta do script)")
    ap.add_argument("--target", help="destino .claude (default: ~/.claude)")
    ap.add_argument("--config", help="JSON de perfil de exportação (opcional)")
    ap.add_argument("--perfil", help="perfil do manifest.json (instalação seletiva; default: tudo)")
    ap.add_argument("--backup", help="timestamp do backup p/ rollback (default: o último)")
    ap.add_argument("--out", help="caminho do manifesto baseline (default: <source>/squad-ai-manifest.json)")
    ap.add_argument("--check", action="store_true", help="baseline: só compara aggregate_sha256 com o versionado (gate CI; nao escreve)")
    ap.add_argument("--force", action="store_true", help="sobrescreve arquivos sensíveis e conteúdo de terceiros (sempre com backup)")
    ap.add_argument("--podar", action="store_true",
                    help="install/instalar-todos: remove, com backup, o que este instalador pôs e a fonte não tem mais")
    ap.add_argument("--so-detectados", action="store_true",
                    help="instalar-todos: da lista --destinos, instala só nas ferramentas presentes nesta máquina "
                         "(para rotina diária: não cria pasta de ferramenta não instalada)")
    ap.add_argument("--quiet", action="store_true")
    est = ap.add_argument_group("estacao (CPU · GPU · NPU)")
    est.add_argument("--aplicar", action="store_true", help="estacao: instala venv/pacotes, grava o perfil e baixa o modelo")
    est.add_argument("--calibrar", action="store_true", help="estacao --aplicar: mede cada dispositivo e grava a política")
    est.add_argument("--rapido", action="store_true", help="estacao --calibrar: calibração curta")
    est.add_argument("--testes", action="store_true", help="estacao --aplicar: roda os testes do caminho neural")
    est.add_argument("--ativar-neural", action="store_true", help="estacao --aplicar: grava SQUAD_EMBEDDER=neural")
    est.add_argument("--card", default="multilingual-e5-small", help="estacao: modelo de embedding (card)")
    est.add_argument("--model-dir", help="estacao: pasta com o modelo baixado pelo navegador")
    return ap



def _perfil_allowed(args, source: Path):
    """(allowed_skills, rc): rc != None quando o perfil pedido é inválido (já reportado em stderr)."""
    if not args.perfil:
        return None, None
    perfis = _load_perfis(source)
    if perfis is None:
        print(f"✗ manifest.json não encontrado em {source} (perfis indisponíveis).", file=sys.stderr)
        return None, 2
    try:
        return set(_resolver_perfil(perfis, args.perfil)), None
    except KeyError:
        print(f"✗ perfil '{args.perfil}' não existe. Perfis: {', '.join(sorted(perfis))}", file=sys.stderr)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
    return None, 2


def _cmd_detectar(args) -> int:
    det = detectar_destinos()
    if args.json:
        print(json.dumps(det, ensure_ascii=False, indent=1))
    else:
        _imprimir_deteccao(det)
    return 0


def _cmd_instalar_todos(args, source: Path, profile, allowed_skills) -> int:
    try:
        destinos = resolver_destinos(args.destinos, so_detectados=args.so_detectados)
    except KeyError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    if not destinos and args.so_detectados:
        print(f"· nenhuma das ferramentas pedidas ({args.destinos}) está instalada nesta máquina — nada a fazer.")
        return 0
    if not destinos:
        print("✗ nenhum destino principal presente (.claude, .dsh, RAI CLI). Use --destinos claude para criar.",
              file=sys.stderr)
        return 2
    res = instalar_todos(source, destinos, profile, args.force, allowed_skills, args.quiet,
                         podar=args.podar)
    print("Resumo por destino:")
    for i, r in res.items():
        if r["ok"]:
            print(f"  ✓ {i:<8} +{r['novos']} novos · ↑{r['atualizados']} · ={r['iguais']} · "
                  f"✗{r['bloqueados']} bloqueados · ⊘{r['terceiros']} de terceiros · "
                  f"-{r['podados']} podados · {r['alvo']}")
        else:
            print(f"  ✗ {i:<8} {r['erro']}")
    orfaos = sum(r.get("orfaos", 0) for r in res.values())
    if orfaos:
        print(f"Órfãos: {orfaos} arquivo(s) saíram da fonte e continuam instalados — "
              "rode de novo com --podar para remover (com backup; `rollback` desfaz).")
    det = detectar_destinos()
    feitos = {d["id"] for d in destinos}
    pend = [s_ for s_ in det["sugestoes"] if s_["id"] not in feitos]
    if pend:
        print("Também dá para instalar em: " + ", ".join(f"{s_['id']} ({s_['motivo']})" for s_ in pend))
    return 0 if all(r["ok"] for r in res.values()) else 1


def _cmd_plan(args, source: Path, target: Path, profile, allowed_skills) -> int:
    log = Log(None, args.quiet)
    items, dups, skills = discover(source, profile)
    if allowed_skills is not None:
        skills = {n: s for n, s in skills.items() if n in allowed_skills}
        items = [it for it in items if it.category != "skills" or it.skill in allowed_skills]
    blocked, warnings = auditar_skills(skills)
    prev_paths = _prev_manifest_paths(target)
    actions = plan(items, target, profile, prev_paths)
    from collections import Counter
    c = Counter(a for _, a in actions)
    log(f"PLAN (dry-run) · fonte={source} · destino={target}"
        + (f" · perfil={args.perfil}" if args.perfil else ""))
    log(f"  skills={len(skills)} · itens={len(items)} · "
        f"NEW={c.get('NEW',0)} UPDATE={c.get('UPDATE',0)} SAME={c.get('SAME',0)} "
        f"SENSITIVE={c.get('SENSITIVE',0)} FOREIGN={c.get('FOREIGN',0)} · duplicidades={len(dups)}")
    log(f"  porta de segurança: {len(blocked)} bloqueada(s) · {len(warnings)} aviso(s)")
    for name, motivos in blocked.items():
        log(f"  ✗ BLOQUEADO — {name}: {'; '.join(motivos)}")
    for d in dups:
        log(f"  dup: {d}")
    return 0


def _cmd_baseline(args, source: Path, profile) -> int:
    out = Path(args.out).expanduser().resolve() if args.out else (source / "squad-ai-manifest.json")
    if args.check:
        return do_baseline_check(source, profile, out)
    m = do_baseline(source, profile, out)
    if not args.quiet:
        c = m["counts"]
        print(f"baseline: {c['items']} itens · {c['skills']} skills · "
              f"agg={m['aggregate_sha256'][:16]}… -> {out}")
    return 0


def _cmd_install(args, source: Path, target: Path, profile, allowed_skills) -> int:
    log = Log(target / LOG, args.quiet)
    log(f"INSTALL · fonte={source} · destino={target} · SO={platform.system()}"
        + (f" · perfil={args.perfil}" if args.perfil else ""))
    target.mkdir(parents=True, exist_ok=True)
    summary = do_install(source, target, profile, args.force, log, allowed_skills, podar=args.podar)
    do_index(source, target, profile, log, allowed_skills)
    write_report(target, summary, log)
    log(f"OK: +{len(summary.installed)} novos · ↑{len(summary.updated)} atualizados · "
        f"={len(summary.skipped)} idênticos · ✗{len(summary.blocked)} bloqueados · "
        f"⊘{len(summary.foreign)} de terceiros preservados · backups={len(summary.backups)} · "
        f"órfãos={len(summary.orphans)} · podados={len(summary.pruned)}")
    log.flush()
    return 0


def _cmd_com_log(args, source: Path, target: Path, profile, allowed_skills) -> int:
    """verify · rollback · index: compartilham o log em <target>/LOG, descarregado ao fim."""
    log = Log(target / LOG, args.quiet)
    if args.command == "verify":
        rc = do_verify(target, log)
    elif args.command == "rollback":
        rc = do_rollback(target, args.backup, log)
    else:
        do_index(source, target, profile, log, allowed_skills)
        rc = 0
    log.flush()
    return rc


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = _build_parser().parse_args(argv)

    source = Path(args.source).expanduser().resolve() if args.source else Path(__file__).resolve().parent
    target = _resolve_target(args.target)
    profile = load_profile(args.config)

    if source == target:
        print("✗ source e target não podem ser o mesmo diretório.", file=sys.stderr)
        return 2

    allowed_skills, rc = _perfil_allowed(args, source)
    if rc is not None:
        return rc

    cmd = args.command
    if cmd == "estacao":
        return _cmd_estacao(args, source)
    if cmd == "detectar":
        return _cmd_detectar(args)
    if cmd == "instalar-todos":
        return _cmd_instalar_todos(args, source, profile, allowed_skills)
    if cmd == "plan":
        return _cmd_plan(args, source, target, profile, allowed_skills)
    if cmd in ("verify", "rollback", "index"):
        return _cmd_com_log(args, source, target, profile, allowed_skills)
    if cmd == "baseline":
        return _cmd_baseline(args, source, profile)
    return _cmd_install(args, source, target, profile, allowed_skills)


if __name__ == "__main__":
    raise SystemExit(main()) 