namespace Taskbox.Dominio;

/// <summary>Colecao de primeira classe: o comportamento do conjunto mora aqui.</summary>
public sealed class Tarefas
{
    private readonly Dictionary<string, Tarefa> _itens = [];

    public void Adicionar(Tarefa tarefa) => _itens[tarefa.Identificador] = tarefa;

    public Tarefa Concluir(string identificador)
    {
        if (!_itens.TryGetValue(identificador, out var existente))
        {
            throw new TarefaInexistente(identificador);
        }
        var concluida = existente.Concluir();
        _itens[identificador] = concluida;
        return concluida;
    }

    public IReadOnlyList<Tarefa> Pendentes() =>
        _itens.Values.Where(tarefa => tarefa.Pendente).ToList();

    public int Total => _itens.Count;
}
