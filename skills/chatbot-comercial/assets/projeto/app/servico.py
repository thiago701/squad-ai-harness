"""Montagem do monólito modular — um objeto que costura M1..M5.

Restrição 2: monólito modular. Os módulos conversam por chamada de função,
não por rede. Extrair qualquer um deles para serviço próprio exige
justificativa escrita em `docs/adr/`.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from . import conhecimento, dashboard, db
from .agente import Agente, Entrada, Resposta
from .auditoria import Lgpd, Trilha
from .config import Config
from .curadoria import Curadoria
from .ferramentas import CalendarioLocal, Ferramentas
from .leads import RepositorioLeads, extrair_lead
from .llm import RespostaExtrativa, construir_llm
from .vertical import VerticalPack


@dataclass
class Servico:
    config: Config
    conexao: Any
    pack: VerticalPack
    base: Any
    agente: Agente
    trilha: Trilha
    leads: RepositorioLeads
    curadoria: Curadoria
    lgpd: Lgpd

    # -- ciclo de vida ------------------------------------------------------

    @staticmethod
    def montar(config: Config | None = None) -> Servico:
        cfg = config or Config.do_ambiente()
        cfg.preparar_diretorios()

        conexao = db.conectar(cfg.banco)
        db.migrar(conexao)

        pack = VerticalPack.carregar(
            cfg.pack_do_vertical, estabelecimento=cfg.estabelecimento
        )
        base = conhecimento.construir_base(cfg, pack)
        conhecimento.indexar(base, cfg, conexao)

        leads = RepositorioLeads(conexao, cfg.tenant)
        ferramentas = Ferramentas(
            pack,
            CalendarioLocal(cfg.dados_do_vertical / "ocupacao.json"),
            raiz_dados=cfg.dados_do_vertical,
        )
        agente = Agente(
            pack=pack,
            base=base,
            llm=construir_llm(cfg, expandir=base.expandir),
            config=cfg,
            ferramentas=ferramentas,
        )
        return Servico(
            config=cfg,
            conexao=conexao,
            pack=pack,
            base=base,
            agente=agente,
            trilha=Trilha(conexao, cfg),
            leads=leads,
            curadoria=Curadoria(conexao, cfg),
            lgpd=Lgpd(conexao, cfg),
        )

    def reindexar(self, base: Any = None, *, forcar: bool = True) -> dict[str, Any]:
        alvo = base if base is not None else self.base
        return conhecimento.indexar(alvo, self.config, self.conexao, forcar=forcar)

    # -- caminho quente -----------------------------------------------------

    def responder(self, entrada: Entrada) -> Resposta:
        """Um turno completo: teto de custo → agente → trilha → lead."""
        inicio = time.perf_counter()
        custos = self.trilha.custos(entrada.sessao)
        degradado = custos.conversa_estourada or custos.mes_estourado

        if degradado:
            resposta = self.agente.responder(
                entrada, llm=RespostaExtrativa(expandir=self.base.expandir)
            )
            resposta.motivo = resposta.motivo or (
                "teto_conversa" if custos.conversa_estourada else "teto_mes"
            )
        else:
            resposta = self.agente.responder(entrada)

        # Latência do TURNO inteiro (guard + triagem + retrieval + modelo) —
        # é esse número que o dono do estabelecimento sente, não o do provedor.
        resposta.latencia_ms = (time.perf_counter() - inicio) * 1000
        correlacao = entrada.message_id or uuid.uuid4().hex
        self.trilha.registrar(
            sessao=entrada.sessao,
            correlacao=correlacao,
            canal=entrada.canal,
            pergunta=entrada.texto,
            resposta=resposta,
        )
        lead = extrair_lead(
            entrada.texto,
            sessao=entrada.sessao,
            canal=entrada.canal,
            intencao=resposta.intencao,
            usuario=entrada.usuario,
            pack=self.pack,
        )
        if lead is not None and self.lgpd.consentido(lead.contato_hash):
            self.leads.salvar(lead)
        return resposta

    # -- leituras do painel -------------------------------------------------

    def painel(self, *, dias: int = 30) -> dict[str, Any]:
        return {
            "tenant": self.config.tenant,
            "vertical": self.pack.rotulo,
            "metricas": dashboard.metricas(self.conexao, self.config.tenant, dias=dias),
            "top_sem_resposta": dashboard.top_sem_resposta(
                self.conexao, self.config.tenant, dias=dias
            ),
            "leads": self.leads.listar(limite=25),
            "curadoria_pendente": self.curadoria.pendentes(),
            "custo_por_tenant": dashboard.custo_por_tenant(self.conexao, dias=dias),
            "chunks_indexados": self.base.count(),
        }
