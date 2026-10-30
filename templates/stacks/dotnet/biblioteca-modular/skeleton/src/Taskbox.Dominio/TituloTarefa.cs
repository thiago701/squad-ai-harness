namespace Taskbox.Dominio;

/// <summary>Primitivo encapsulado: valido por construcao.</summary>
public readonly record struct TituloTarefa
{
    public string Valor { get; }

    private TituloTarefa(string valor) => Valor = valor;

    public static TituloTarefa Criar(string bruto)
    {
        var limpo = bruto.Trim();
        if (limpo.Length is < 3 or > 120)
        {
            throw new TituloInvalido("titulo deve ter entre 3 e 120 caracteres");
        }
        return new TituloTarefa(limpo);
    }
}
