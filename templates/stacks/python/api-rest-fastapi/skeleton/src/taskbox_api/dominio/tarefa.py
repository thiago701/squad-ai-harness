"""Value objects e entidade do dominio (validacao na construcao)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass


class ErroDeDominio(Exception):
    """Base para violacoes de regra de negocio."""


class TituloInvalido(ErroDeDominio):
    pass


class TarefaInexistente(ErroDeDominio):
    pass


@dataclass(frozen=True)
class TituloTarefa:
    """Primitivo encapsulado: titulo valido por construcao."""

    valor: str

    def __post_init__(self) -> None:
        limpo = self.valor.strip()
        if not 3 <= len(limpo) <= 120:
            raise TituloInvalido("titulo deve ter entre 3 e 120 caracteres")
        object.__setattr__(self, "valor", limpo)


@dataclass(frozen=True)
class Tarefa:
    """Entidade imutavel: concluir devolve nova versao."""

    identificador: str
    titulo: TituloTarefa
    concluida: bool = False

    @staticmethod
    def nova(titulo: str) -> "Tarefa":
        return Tarefa(identificador=str(uuid.uuid4()), titulo=TituloTarefa(titulo))

    def concluir(self) -> "Tarefa":
        return Tarefa(self.identificador, self.titulo, True)

    def descrever(self) -> str:
        marcador = "x" if self.concluida else " "
        return f"[{marcador}] {self.titulo.valor}"
