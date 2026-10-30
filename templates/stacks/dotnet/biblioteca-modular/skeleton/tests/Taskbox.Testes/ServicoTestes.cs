using Taskbox.Dominio;
using Xunit;

namespace Taskbox.Testes;

public class ServicoTestes
{
    [Fact]
    public void Fluxo_completo_criar_listar_concluir()
    {
        var servico = new ServicoDeTarefas(new RepositorioEmMemoria());
        var identificador = servico.Criar("escrever adr");
        Assert.Equal(["[ ] escrever adr"], servico.Pendentes());
        Assert.Equal("[x] escrever adr", servico.Concluir(identificador));
        Assert.Empty(servico.Pendentes());
        Assert.Throws<TituloInvalido>(() => servico.Criar("ab"));
        Assert.Throws<TarefaInexistente>(() => servico.Concluir("fantasma"));
    }
}
