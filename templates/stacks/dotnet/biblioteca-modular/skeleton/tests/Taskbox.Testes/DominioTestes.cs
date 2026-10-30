using Taskbox.Dominio;
using Xunit;

namespace Taskbox.Testes;

public class DominioTestes
{
    [Theory]
    [InlineData("ab")]
    [InlineData("  a  ")]
    public void Titulo_invalido_lanca_erro_tipado(string bruto) =>
        Assert.Throws<TituloInvalido>(() => TituloTarefa.Criar(bruto));

    [Fact]
    public void Titulo_normaliza_espacos()
    {
        Assert.Equal("comprar cafe", TituloTarefa.Criar("  comprar cafe  ").Valor);
        Assert.Throws<TituloInvalido>(() => TituloTarefa.Criar(new string('x', 121)));
    }

    [Fact]
    public void Tarefa_imutavel_concluir_devolve_nova()
    {
        var original = Tarefa.Nova("estudar dotnet");
        var concluida = original.Concluir();
        Assert.True(original.Pendente);
        Assert.False(concluida.Pendente);
        Assert.Equal(original.Identificador, concluida.Identificador);
        Assert.StartsWith("[x]", concluida.Descrever());
    }

    [Fact]
    public void Colecao_de_primeira_classe_controla_conjunto()
    {
        var tarefas = new Tarefas();
        var tarefa = Tarefa.Nova("revisar pr");
        tarefas.Adicionar(tarefa);
        Assert.Equal(1, tarefas.Total);
        tarefas.Concluir(tarefa.Identificador);
        Assert.Empty(tarefas.Pendentes());
        Assert.Throws<TarefaInexistente>(() => tarefas.Concluir("fantasma"));
    }
}
