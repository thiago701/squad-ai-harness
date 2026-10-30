namespace Taskbox.Dominio;

/// <summary>Porta minima definida no consumidor.</summary>
public interface IRepositorioDeTarefas
{
    void Guardar(Tarefa tarefa);
    Tarefa Concluir(string identificador);
    IReadOnlyList<Tarefa> Pendentes();
}

/// <summary>Caso de uso: unica dependencia e a porta.</summary>
public sealed class ServicoDeTarefas(IRepositorioDeTarefas repositorio)
{
    public string Criar(string tituloBruto)
    {
        var tarefa = Tarefa.Nova(tituloBruto);
        repositorio.Guardar(tarefa);
        return tarefa.Identificador;
    }

    public string Concluir(string identificador) =>
        repositorio.Concluir(identificador).Descrever();

    public IReadOnlyList<string> Pendentes() =>
        repositorio.Pendentes().Select(tarefa => tarefa.Descrever()).ToList();
}

/// <summary>Adaptador em memoria sobre a colecao de primeira classe.</summary>
public sealed class RepositorioEmMemoria : IRepositorioDeTarefas
{
    private readonly Tarefas _tarefas = new();

    public void Guardar(Tarefa tarefa) => _tarefas.Adicionar(tarefa);

    public Tarefa Concluir(string identificador) => _tarefas.Concluir(identificador);

    public IReadOnlyList<Tarefa> Pendentes() => _tarefas.Pendentes();
}
