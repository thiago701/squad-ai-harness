namespace Taskbox.Dominio;

/// <summary>Base das violacoes de regra de negocio (tipadas, testaveis).</summary>
public abstract class ErroDeDominio(string mensagem) : Exception(mensagem);

public sealed class TituloInvalido(string mensagem) : ErroDeDominio(mensagem);

public sealed class TarefaInexistente(string identificador)
    : ErroDeDominio($"tarefa {identificador} nao encontrada");
