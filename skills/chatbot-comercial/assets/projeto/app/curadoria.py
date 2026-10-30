"""M4 — retreinamento: curadoria → aprovação humana → versão → rollback.

Invariante (restrição do M4): **nunca reindexa sem aprovação humana**.
`aplicar()` levanta erro se o item não estiver aprovado, e a aprovação exige
identificar quem aprovou. Toda aplicação cria uma versão nova e nomeada da
base; rollback é restaurar uma versão anterior e reindexar.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .auditoria import agora
from .privacidade import redigir


class AprovacaoAusente(RuntimeError):
    """Tentativa de aplicar mudança na base sem aprovação humana."""


@dataclass(frozen=True, slots=True)
class ItemCuradoria:
    id: int
    pergunta: str
    resposta_ruim: str
    motivo: str
    fonte_alvo: str
    texto_proposto: str
    status: str


class Curadoria:
    def __init__(self, conexao: sqlite3.Connection, config: Any):
        self._conexao = conexao
        self._config = config

    # -- fila ---------------------------------------------------------------

    def marcar_ruim(
        self,
        *,
        interacao_id: int | None,
        pergunta: str,
        resposta_ruim: str = "",
        motivo: str = "",
    ) -> int:
        cursor = self._conexao.execute(
            "INSERT INTO curadoria (ts, tenant, interacao_id, pergunta, resposta_ruim, "
            "motivo, status) VALUES (?,?,?,?,?,?,'pendente')",
            (
                agora(), self._config.tenant, interacao_id,
                redigir(pergunta), redigir(resposta_ruim), motivo,
            ),
        )
        self._conexao.commit()
        return int(cursor.lastrowid or 0)

    def propor(self, item_id: int, *, fonte_alvo: str, texto_proposto: str) -> None:
        if not fonte_alvo.strip() or not texto_proposto.strip():
            raise ValueError("proposta precisa de fonte-alvo e texto.")
        self._conexao.execute(
            "UPDATE curadoria SET fonte_alvo = ?, texto_proposto = ?, status = 'proposto' "
            "WHERE id = ? AND tenant = ?",
            (fonte_alvo.strip(), texto_proposto.strip(), item_id, self._config.tenant),
        )
        self._conexao.commit()

    def pendentes(self) -> list[dict[str, Any]]:
        cursor = self._conexao.execute(
            "SELECT * FROM curadoria WHERE tenant = ? AND status IN ('pendente','proposto') "
            "ORDER BY id DESC",
            (self._config.tenant,),
        )
        return [dict(linha) for linha in cursor.fetchall()]

    # -- gate humano --------------------------------------------------------

    def aprovar(self, item_id: int, *, aprovado_por: str) -> None:
        if not aprovado_por.strip():
            raise AprovacaoAusente("aprovação exige identificar quem aprovou.")
        linha = self._buscar(item_id)
        if linha["status"] != "proposto":
            raise ValueError("só é possível aprovar item com proposta preenchida.")
        self._conexao.execute(
            "UPDATE curadoria SET status='aprovado', aprovado_por=?, decidido_em=? WHERE id=?",
            (aprovado_por.strip(), agora(), item_id),
        )
        self._conexao.commit()

    def rejeitar(self, item_id: int, *, aprovado_por: str) -> None:
        self._conexao.execute(
            "UPDATE curadoria SET status='rejeitado', aprovado_por=?, decidido_em=? WHERE id=?",
            (aprovado_por.strip(), agora(), item_id),
        )
        self._conexao.commit()

    # -- aplicação + versão -------------------------------------------------

    def aplicar(self, item_id: int, base: Any, *, reindexar: Any) -> dict[str, Any]:
        """Aplica a proposta na base. Falha alto se não houver aprovação."""
        linha = self._buscar(item_id)
        if linha["status"] != "aprovado":
            raise AprovacaoAusente(
                f"item {item_id} está '{linha['status']}'. "
                "Reindexação sem aprovação humana é proibida."
            )

        versao_id = self.versionar(
            rotulo=f"curadoria-{item_id}",
            descricao=f"aplicou proposta em {linha['fonte_alvo']}",
            aprovado_por=linha["aprovado_por"],
        )

        alvo = self._config.dados_do_vertical / f"{linha['fonte_alvo']}.md"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("a", encoding="utf-8") as arquivo:
            arquivo.write(f"\n\n{linha['texto_proposto'].strip()}\n")

        relatorio = reindexar(base)
        self._conexao.execute(
            "UPDATE curadoria SET status='aplicado', versao_id=? WHERE id=?",
            (versao_id, item_id),
        )
        self._conexao.commit()
        return {"versao_id": versao_id, "reindexacao": relatorio}

    def versionar(self, *, rotulo: str, descricao: str, aprovado_por: str) -> int:
        """Snapshot da pasta de dados. Barato e suficiente para rollback."""
        self._config.versoes.mkdir(parents=True, exist_ok=True)
        carimbo = agora().replace(":", "").replace("-", "")
        destino = self._config.versoes / f"{rotulo}-{carimbo}"
        shutil.copytree(self._config.dados_do_vertical, destino, dirs_exist_ok=True)
        self._conexao.execute("UPDATE base_versoes SET ativo = 0 WHERE tenant = ?",
                              (self._config.tenant,))
        cursor = self._conexao.execute(
            "INSERT INTO base_versoes (ts, tenant, rotulo, descricao, caminho, "
            "aprovado_por, ativo) VALUES (?,?,?,?,?,?,1)",
            (agora(), self._config.tenant, rotulo, descricao, str(destino), aprovado_por),
        )
        self._conexao.commit()
        return int(cursor.lastrowid or 0)

    def versoes(self) -> list[dict[str, Any]]:
        cursor = self._conexao.execute(
            "SELECT * FROM base_versoes WHERE tenant = ? ORDER BY id DESC",
            (self._config.tenant,),
        )
        return [dict(linha) for linha in cursor.fetchall()]

    def rollback(self, versao_id: int, base: Any, *, reindexar: Any) -> dict[str, Any]:
        linha = self._conexao.execute(
            "SELECT * FROM base_versoes WHERE id = ? AND tenant = ?",
            (versao_id, self._config.tenant),
        ).fetchone()
        if linha is None:
            raise ValueError(f"versão {versao_id} não existe.")
        origem = Path(linha["caminho"])
        if not origem.exists():
            raise FileNotFoundError(f"snapshot ausente: {origem}")

        destino = self._config.dados_do_vertical
        shutil.rmtree(destino, ignore_errors=True)
        shutil.copytree(origem, destino)
        self._conexao.execute("UPDATE base_versoes SET ativo = 0 WHERE tenant = ?",
                              (self._config.tenant,))
        self._conexao.execute("UPDATE base_versoes SET ativo = 1 WHERE id = ?", (versao_id,))
        self._conexao.execute("DELETE FROM fontes_indexadas WHERE tenant = ?",
                              (self._config.tenant,))
        self._conexao.commit()
        return {"versao_id": versao_id, "reindexacao": reindexar(base)}

    def _buscar(self, item_id: int) -> sqlite3.Row:
        linha = self._conexao.execute(
            "SELECT * FROM curadoria WHERE id = ? AND tenant = ?",
            (item_id, self._config.tenant),
        ).fetchone()
        if linha is None:
            raise ValueError(f"item de curadoria {item_id} não existe.")
        return linha
