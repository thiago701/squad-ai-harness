namespace Taskbox.Dominio;

/// <summary>Entidade imutavel: Concluir devolve nova versao (with).</summary>
public sealed record Tarefa(string Identificador, TituloTarefa Titulo, bool Concluida)
{
    public static Tarefa Nova(string tituloBruto) =>
        new(Guid.NewGuid().ToString("N"), TituloTarefa.Criar(tituloBruto), false);

    public Tarefa Concluir() => this with { Concluida = true };

    public bool Pendente => !Concluida;

    public string Descrever()
    {
        var marcador = Concluida ? "x" : " ";
        return $"[{marcador}] {Titulo.Valor}";
    }
}
