"""Borda CLI: traduz erros de dominio em saida honesta (handler central)."""
from __future__ import annotations

import argparse
import sys

from taskbox.adaptadores.registro import registrador
from taskbox.adaptadores.repositorio_memoria import RepositorioEmMemoria
from taskbox.aplicacao.servico import ServicoDeTarefas
from taskbox.dominio.tarefa import ErroDeDominio

LOG = registrador("taskbox.cli")


def _executar(servico: ServicoDeTarefas, argumentos: argparse.Namespace) -> str:
    if argumentos.comando == "criar":
        return servico.criar(argumentos.titulo)
    if argumentos.comando == "concluir":
        return servico.concluir(argumentos.identificador)
    return "\n".join(servico.pendentes()) or "(sem pendencias)"


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="{{project_name}}")
    sub = parser.add_subparsers(dest="comando", required=True)
    criar = sub.add_parser("criar")
    criar.add_argument("titulo")
    concluir = sub.add_parser("concluir")
    concluir.add_argument("identificador")
    sub.add_parser("listar")
    return parser


def main(argv: list[str] | None = None) -> int:
    argumentos = montar_parser().parse_args(argv)
    servico = ServicoDeTarefas(RepositorioEmMemoria())
    try:
        print(_executar(servico, argumentos))
    except ErroDeDominio as erro:
        LOG.error(str(erro))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
