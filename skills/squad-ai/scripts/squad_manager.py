"""
Squad AI — Gerenciador de Equipe Multi-Agente
==============================================
Script para automação do gerenciamento de atividades, comunicação,
métricas e coordenação entre agentes da squad de desenvolvimento.

Genérico e reutilizável em qualquer projeto — sem dependência de
serviços proprietários, naming interno ou conhecimento tácito.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SKILL_ROOT.parent.parent

PASTA_SQUAD = SKILL_ROOT / ".antigravity" / "equipe"
PASTA_SKILLS = REPO_ROOT / "skills"


def escrever_texto_lf(caminho: Path, conteudo: str, modo: str = "w") -> None:
    with caminho.open(modo, encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)

FASES_VALIDAS = ["discovery", "design", "build", "test", "review", "deliver"]

ESTADOS_VALIDOS = [
    "PENDENTE",
    "EM_PLANEJAMENTO",
    "APROVADO",
    "EM_PROGRESSO",
    "EM_REVISÃO",
    "CONCLUIDO",
    "BLOQUEADO",
    "CANCELADO",
]

def _carregar_agentes_conhecidos(diretorio: Path) -> list[str]:
    agentes = []
    if not diretorio.exists():
        return agentes
    for item in diretorio.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            agentes.append(item.name)
    return agentes

# Gerado dinamicamente a partir do disco (pastas de skills; catalogo canonico: governance/registry/registry.json — ADR-010).
AGENTES_CONHECIDOS = _carregar_agentes_conhecidos(PASTA_SKILLS)


class SquadManager:
    """Gerenciador central da Squad AI.

    Responsável por toda a infraestrutura de comunicação,
    atividades, métricas e coordenação entre agentes.
    """

    def __init__(
        self,
        diretorio_base: str | Path = PASTA_SQUAD,
        diretorio_skills: str | Path = PASTA_SKILLS,
    ):
        self._base = Path(diretorio_base)
        self._skills_dir = Path(diretorio_skills)
        self._registro = self._base / "registro_atividades.json"
        self._caixa_entrada = self._base / "caixa_entrada"
        self._travas = self._base / "travas"
        self._aviso_geral = self._base / "aviso_geral.msg"
        self._decisoes = self._base / "decisoes"
        self._artefatos = self._base / "artefatos"
        self._metricas = self._base / "metricas"

    # ─── Infraestrutura ──────────────────────────────────────────

    def iniciar(self) -> None:
        """Monta toda a infraestrutura necessária para a squad."""
        for pasta in [
            self._caixa_entrada,
            self._travas,
            self._decisoes,
            self._artefatos,
            self._metricas,
        ]:
            pasta.mkdir(parents=True, exist_ok=True)

        # Pastas de artefatos por fase
        for fase in FASES_VALIDAS:
            (self._artefatos / f"fase-{FASES_VALIDAS.index(fase) + 1}-{fase}").mkdir(
                exist_ok=True
            )

        if not self._registro.exists():
            conteudo = {
                "projeto": {"nome": "", "tecnologia": "", "modo": "sequencial"},
                "fase_atual": "discovery",
                "atividades": [],
                "integrantes": [],
                "historico_fases": [],
            }
            self._salvar_json(self._registro, conteudo)

        if not self._aviso_geral.exists():
            escrever_texto_lf(self._aviso_geral, "")

        print("[OK] Infraestrutura da Squad AI preparada com sucesso.")
        print(f"     Diretório base: {self._base}")

    def limpar(self) -> None:
        """Limpa infraestrutura para novo projeto (preserva decisoes/)."""
        import shutil

        for pasta in [self._caixa_entrada, self._travas, self._metricas]:
            if pasta.exists():
                shutil.rmtree(pasta)
            pasta.mkdir(parents=True, exist_ok=True)

        # Limpa artefatos mas recria estrutura
        if self._artefatos.exists():
            shutil.rmtree(self._artefatos)
        self._artefatos.mkdir(parents=True, exist_ok=True)
        for fase in FASES_VALIDAS:
            (self._artefatos / f"fase-{FASES_VALIDAS.index(fase) + 1}-{fase}").mkdir(
                exist_ok=True
            )

        # Reseta registro
        conteudo = {
            "projeto": {"nome": "", "tecnologia": "", "modo": "sequencial"},
            "fase_atual": "discovery",
            "atividades": [],
            "integrantes": [],
            "historico_fases": [],
        }
        self._salvar_json(self._registro, conteudo)
        escrever_texto_lf(self._aviso_geral, "")

        print("[OK] Infraestrutura limpa para novo projeto (decisoes/ preservado).")

    # ─── Atividades ──────────────────────────────────────────────

    def criar_atividade(
        self,
        titulo: str,
        responsavel: str,
        pre_requisitos: str = "",
        fase: str = "discovery",
    ) -> dict:
        """Registra uma nova atividade com fase e pré-requisitos."""
        if fase not in FASES_VALIDAS:
            print(f"[ERRO] Fase '{fase}' inválida. Use: {FASES_VALIDAS}")
            return {}

        dados = self._carregar_json(self._registro)
        deps = [int(p) for p in pre_requisitos.split(",") if p.strip()]

        nova = {
            "id": len(dados["atividades"]) + 1,
            "titulo": titulo,
            "estado": "PENDENTE",
            "plano_validado": False,
            "responsavel": responsavel,
            "agentes_envolvidos": [responsavel],
            "fase": fase,
            "pre_requisitos": deps,
            "criado_em": datetime.now().isoformat(),
            "atualizado_em": datetime.now().isoformat(),
            "notas": [],
        }

        dados["atividades"].append(nova)
        self._salvar_json(self._registro, dados)

        print(f"[OK] Atividade #{nova['id']} ({titulo}) → {responsavel} [Fase: {fase}]")
        return nova

    def atualizar_estado(self, id_atividade: int, novo_estado: str) -> None:
        """Atualiza o estado de uma atividade."""
        if novo_estado not in ESTADOS_VALIDOS:
            print(f"[ERRO] Estado '{novo_estado}' inválido. Use: {ESTADOS_VALIDOS}")
            return

        dados = self._carregar_json(self._registro)
        for ativ in dados["atividades"]:
            if ativ["id"] == id_atividade:
                estado_anterior = ativ["estado"]
                ativ["estado"] = novo_estado
                ativ["atualizado_em"] = datetime.now().isoformat()
                ativ["notas"].append(
                    f"{datetime.now().isoformat()}: {estado_anterior} → {novo_estado}"
                )
                self._salvar_json(self._registro, dados)
                print(f"[OK] #{id_atividade}: {estado_anterior} → {novo_estado}")
                return

        print(f"[ERRO] Atividade #{id_atividade} não encontrada.")

    def listar(self, fase: Optional[str] = None) -> None:
        """Lista atividades, opcionalmente filtradas por fase."""
        dados = self._carregar_json(self._registro)
        atividades = dados["atividades"]

        if fase:
            atividades = [a for a in atividades if a.get("fase") == fase]

        if not atividades:
            print("Nenhuma atividade encontrada.")
            return

        fase_atual = dados.get("fase_atual", "?")
        print(f"\n  Fase atual: {fase_atual.upper()}")
        print("  " + "─" * 60)

        for a in atividades:
            deps = f" (deps: {a['pre_requisitos']})" if a["pre_requisitos"] else ""
            print(
                f"  #{a['id']:02d} [{a['estado']:14s}] {a['titulo']}"
                f" → {a['responsavel']} [{a['fase']}]{deps}"
            )

    # ─── Fases ───────────────────────────────────────────────────

    def avancar_fase(self) -> None:
        """Avança para a próxima fase se critérios forem atendidos."""
        dados = self._carregar_json(self._registro)
        fase_atual = dados.get("fase_atual", "discovery")
        idx = FASES_VALIDAS.index(fase_atual)

        # Verificar se todas as atividades da fase atual estão concluídas
        atividades_fase = [
            a for a in dados["atividades"] if a.get("fase") == fase_atual
        ]
        pendentes = [a for a in atividades_fase if a["estado"] != "CONCLUIDO"]

        if pendentes:
            print(f"[ERRO] {len(pendentes)} atividade(s) pendente(s) na fase {fase_atual}:")
            for p in pendentes:
                print(f"  #{p['id']} [{p['estado']}] {p['titulo']}")
            return

        if idx >= len(FASES_VALIDAS) - 1:
            print("[OK] Todas as fases concluídas! Projeto finalizado.")
            return

        nova_fase = FASES_VALIDAS[idx + 1]
        dados["historico_fases"].append(
            {
                "fase": fase_atual,
                "concluida_em": datetime.now().isoformat(),
                "atividades_concluidas": len(atividades_fase),
            }
        )
        dados["fase_atual"] = nova_fase
        self._salvar_json(self._registro, dados)
        print(f"[OK] Fase avançada: {fase_atual.upper()} → {nova_fase.upper()}")

    def status_fase(self) -> None:
        """Mostra status da fase atual."""
        dados = self._carregar_json(self._registro)
        fase = dados.get("fase_atual", "discovery")
        atividades = [a for a in dados["atividades"] if a.get("fase") == fase]

        total = len(atividades)
        concluidas = len([a for a in atividades if a["estado"] == "CONCLUIDO"])
        em_progresso = len([a for a in atividades if a["estado"] == "EM_PROGRESSO"])
        bloqueadas = len([a for a in atividades if a["estado"] == "BLOQUEADO"])

        print(f"\n  FASE ATUAL: {fase.upper()}")
        print(f"  Atividades: {concluidas}/{total} concluídas")
        print(f"  Em progresso: {em_progresso}")
        print(f"  Bloqueadas: {bloqueadas}")
        print(f"  Progresso: {(concluidas/total*100) if total else 0:.0f}%")

    # ─── Comunicação ─────────────────────────────────────────────

    def comunicado_geral(self, remetente: str, conteudo: str) -> None:
        """Transmite mensagem para toda a squad."""
        comunicado = {
            "remetente": remetente,
            "categoria": "COMUNICADO_GERAL",
            "conteudo": conteudo,
            "enviado_em": datetime.now().isoformat(),
        }
        escrever_texto_lf(
            self._aviso_geral,
            json.dumps(comunicado, ensure_ascii=False) + "\n",
            modo="a",
        )
        print(f"[OK] Comunicado geral transmitido por {remetente}.")

    def mensagem_direta(self, remetente: str, destinatario: str, conteudo: str) -> None:
        """Envia mensagem à caixa de entrada de um agente."""
        mensagem = {
            "remetente": remetente,
            "conteudo": conteudo,
            "enviado_em": datetime.now().isoformat(),
        }
        destino = self._caixa_entrada / f"{destinatario}.msg"
        escrever_texto_lf(
            destino,
            json.dumps(mensagem, ensure_ascii=False) + "\n",
            modo="a",
        )
        print(f"[OK] Mensagem: {remetente} → {destinatario}")

    def ler_mensagens(self, agente: str) -> None:
        """Lê mensagens da caixa de entrada de um agente."""
        arquivo = self._caixa_entrada / f"{agente}.msg"
        if not arquivo.exists() or arquivo.stat().st_size == 0:
            print(f"  Caixa de {agente}: vazia.")
            return

        print(f"\n  Mensagens para {agente}:")
        print("  " + "─" * 50)
        for linha in arquivo.read_text(encoding="utf-8").strip().splitlines():
            msg = json.loads(linha)
            print(f"  [{msg['enviado_em'][:16]}] {msg['remetente']}: {msg['conteudo']}")

    # ─── Validação ───────────────────────────────────────────────

    def validar_skills(self, skills_csv: str) -> None:
        """Verifica se as skills informadas existem no diretorio canonico de skills."""
        skills = [s.strip() for s in skills_csv.split(",")]

        encontradas = []
        ausentes = []

        for skill in skills:
            skill_path = self._skills_dir / skill / "SKILL.md"
            if skill_path.exists():
                encontradas.append(skill)
            else:
                ausentes.append(skill)

        print(f"\n  Skills validadas: {len(encontradas)}/{len(skills)}")
        for s in encontradas:
            print(f"  ✓ {s}")
        for s in ausentes:
            print(f"  ✗ {s} (NÃO ENCONTRADA)")

        if ausentes:
            print(f"\n  [AVISO] {len(ausentes)} skill(s) ausente(s).")

    # ─── Métricas ────────────────────────────────────────────────

    def registrar_metricas(self, metricas_json: str) -> None:
        """Registra métricas de qualidade do projeto."""
        metricas = json.loads(metricas_json)
        metricas["registrado_em"] = datetime.now().isoformat()

        arquivo = self._metricas / "qualidade.json"
        historico = []
        if arquivo.exists():
            historico = json.loads(arquivo.read_text(encoding="utf-8"))

        historico.append(metricas)
        self._salvar_json(arquivo, historico)
        print("[OK] Métricas registradas.")

    def relatorio(self) -> None:
        """Gera relatório resumido do projeto."""
        dados = self._carregar_json(self._registro)
        projeto = dados.get("projeto", {})
        atividades = dados["atividades"]
        fase = dados.get("fase_atual", "?")
        historico = dados.get("historico_fases", [])

        total = len(atividades)
        concluidas = len([a for a in atividades if a["estado"] == "CONCLUIDO"])

        print("\n  ═══════════════════════════════════════")
        print("       RELATÓRIO — SQUAD AI")
        print("  ═══════════════════════════════════════")
        print(f"  Projeto:    {projeto.get('nome', 'N/D')}")
        print(f"  Tecnologia: {projeto.get('tecnologia', 'N/D')}")
        print(f"  Modo:       {projeto.get('modo', 'sequencial')}")
        print(f"  Fase atual: {fase.upper()}")
        print(f"  Atividades: {concluidas}/{total} concluídas")
        print(f"  Fases OK:   {len(historico)}/{len(FASES_VALIDAS)}")

        print("\n  Por fase:")
        for f in FASES_VALIDAS:
            ativs = [a for a in atividades if a.get("fase") == f]
            ok = len([a for a in ativs if a["estado"] == "CONCLUIDO"])
            marker = "●" if f == fase else ("✓" if ok == len(ativs) and ativs else "○")
            print(f"  {marker} {f.upper():12s} → {ok}/{len(ativs)} concluídas")

    # ─── ADRs ────────────────────────────────────────────────────

    def criar_adr(self, numero: int, titulo: str, conteudo: str) -> None:
        """Cria um Architecture Decision Record."""
        arquivo = self._decisoes / f"ADR-{numero:03d}-{titulo.lower().replace(' ', '-')}.md"
        escrever_texto_lf(arquivo, conteudo)
        print(f"[OK] ADR-{numero:03d} criado: {titulo}")

    # ─── Travas ──────────────────────────────────────────────────

    def travar(self, arquivo: str, agente: str) -> None:
        """Cria trava de edição para um arquivo."""
        lock = self._travas / f"{arquivo.replace('/', '_')}.lock"
        if lock.exists():
            info = json.loads(lock.read_text(encoding="utf-8"))
            print(f"[ERRO] Arquivo '{arquivo}' já travado por {info['agente']}")
            return

        escrever_texto_lf(
            lock,
            json.dumps(
                {"agente": agente, "arquivo": arquivo, "desde": datetime.now().isoformat()}
            ),
        )
        print(f"[OK] Trava criada: {arquivo} por {agente}")

    def destravar(self, arquivo: str) -> None:
        """Remove trava de edição."""
        lock = self._travas / f"{arquivo.replace('/', '_')}.lock"
        if lock.exists():
            lock.unlink()
            print(f"[OK] Trava removida: {arquivo}")
        else:
            print(f"[INFO] Nenhuma trava para: {arquivo}")

    # ─── Utilitários ─────────────────────────────────────────────

    def _carregar_json(self, caminho: Path) -> dict | list:
        return json.loads(caminho.read_text(encoding="utf-8"))

    def _salvar_json(self, caminho: Path, dados) -> None:
        escrever_texto_lf(caminho, json.dumps(dados, indent=2, ensure_ascii=False))


def principal():
    """Ponto de entrada CLI."""
    mgr = SquadManager()

    if len(sys.argv) < 2:
        print("Squad AI — Gerenciador de Equipe")
        print("=" * 40)
        print("Comandos disponíveis:")
        print("  iniciar                              Prepara infraestrutura")
        print("  limpar                               Limpa para novo projeto")
        print("  criar_atividade <titulo> <resp> [deps] [fase]")
        print("  atualizar_estado <id> <estado>       Atualiza estado")
        print("  listar [fase]                        Lista atividades")
        print("  avancar_fase                         Avança para próxima fase")
        print("  status_fase                          Status da fase atual")
        print("  comunicado_geral <rem> <msg>         Broadcast")
        print("  mensagem_direta <rem> <dest> <msg>   Mensagem 1-a-1")
        print("  ler_mensagens <agente>               Lê caixa de entrada")
        print("  validar_skills <skill1,skill2,...>    Valida skills")
        print("  registrar_metricas <json>            Registra métricas")
        print("  relatorio                            Relatório do projeto")
        print("  travar <arquivo> <agente>            Cria trava de edição")
        print("  destravar <arquivo>                  Remove trava")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "iniciar":
        mgr.iniciar()
    elif cmd == "limpar":
        mgr.limpar()
    elif cmd == "criar_atividade":
        if len(sys.argv) < 4:
            print("Uso: criar_atividade <titulo> <responsavel> [deps] [fase]")
            sys.exit(1)
        titulo = sys.argv[2]
        resp = sys.argv[3]
        deps = sys.argv[4] if len(sys.argv) > 4 else ""
        fase = sys.argv[5] if len(sys.argv) > 5 else "discovery"
        mgr.criar_atividade(titulo, resp, deps, fase)
    elif cmd == "atualizar_estado":
        if len(sys.argv) < 4:
            print("Uso: atualizar_estado <id> <estado>")
            sys.exit(1)
        mgr.atualizar_estado(int(sys.argv[2]), sys.argv[3])
    elif cmd == "listar":
        fase = sys.argv[2] if len(sys.argv) > 2 else None
        mgr.listar(fase)
    elif cmd == "avancar_fase":
        mgr.avancar_fase()
    elif cmd == "status_fase":
        mgr.status_fase()
    elif cmd == "comunicado_geral":
        if len(sys.argv) < 4:
            print("Uso: comunicado_geral <remetente> <conteudo>")
            sys.exit(1)
        mgr.comunicado_geral(sys.argv[2], sys.argv[3])
    elif cmd == "mensagem_direta":
        if len(sys.argv) < 5:
            print("Uso: mensagem_direta <rem> <dest> <msg>")
            sys.exit(1)
        mgr.mensagem_direta(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "ler_mensagens":
        if len(sys.argv) < 3:
            print("Uso: ler_mensagens <agente>")
            sys.exit(1)
        mgr.ler_mensagens(sys.argv[2])
    elif cmd == "validar_skills":
        if len(sys.argv) < 3:
            print("Uso: validar_skills <skill1,skill2,...>")
            sys.exit(1)
        mgr.validar_skills(sys.argv[2])
    elif cmd == "registrar_metricas":
        if len(sys.argv) < 3:
            print("Uso: registrar_metricas '<json>'")
            sys.exit(1)
        mgr.registrar_metricas(sys.argv[2])
    elif cmd == "relatorio":
        mgr.relatorio()
    elif cmd == "travar":
        if len(sys.argv) < 4:
            print("Uso: travar <arquivo> <agente>")
            sys.exit(1)
        mgr.travar(sys.argv[2], sys.argv[3])
    elif cmd == "destravar":
        if len(sys.argv) < 3:
            print("Uso: destravar <arquivo>")
            sys.exit(1)
        mgr.destravar(sys.argv[2])
    else:
        print(f"[ERRO] Comando '{cmd}' não reconhecido.")
        sys.exit(1)


if __name__ == "__main__":
    principal()
