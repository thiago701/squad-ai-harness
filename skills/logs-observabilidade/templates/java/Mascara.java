package exemplo.observabilidade;

import java.util.regex.Pattern;

/**
 * Mascaramento canônico da Squad — mesmo formato do {@code scripts/logs_obs/mascara.py} (oráculo dos testes).
 * Sem dependências. Use NA ORIGEM (toString/serializer) e no decorator do encoder (rede de segurança).
 *
 * <pre>
 *   cpf       529.982.247-25            → ***.982.247-**
 *   cnpj      11.222.333/0001-81        → **.222.333/0001-**
 *   pan       4111 1111 1111 1111       → **** **** **** 1111   (manterBin → 411111******1111, PCI 3.4.1 máximo)
 *   email     thiago.silva@exemplo.com  → t***********@exemplo.com
 *   telefone  +55 (83) 99999-1234       → +55 (83) *****-1234
 *   token     eyJhbGci…6789             → [TOKEN:****6789]
 * </pre>
 */
public final class Mascara {

    private static final Pattern NAO_DIGITO = Pattern.compile("\\D");
    private static final String TOTAL = "****";

    private Mascara() {}

    public static String cpf(String cpf) {
        if (cpf == null) return null;
        String d = NAO_DIGITO.matcher(cpf).replaceAll("");
        return d.length() == 11 ? "***." + d.substring(3, 6) + "." + d.substring(6, 9) + "-**" : TOTAL;
    }

    public static String cnpj(String cnpj) {
        if (cnpj == null) return null;
        String d = NAO_DIGITO.matcher(cnpj).replaceAll("");
        return d.length() == 14 ? "**." + d.substring(2, 5) + "." + d.substring(5, 8) + "/" + d.substring(8, 12) + "-**" : TOTAL;
    }

    public static String pan(String pan) { return pan(pan, false); }

    /** {@code manterBin} só com necessidade de negócio documentada (roteamento por bandeira). */
    public static String pan(String pan, boolean manterBin) {
        if (pan == null) return null;
        String d = NAO_DIGITO.matcher(pan).replaceAll("");
        if (d.length() < 13 || d.length() > 19) return TOTAL;
        if (manterBin) return d.substring(0, 6) + "*".repeat(d.length() - 10) + d.substring(d.length() - 4);
        return "**** **** **** " + d.substring(d.length() - 4);
    }

    public static String email(String email) {
        if (email == null) return null;
        int at = email.indexOf('@');
        if (at <= 0) return TOTAL;
        return email.charAt(0) + "*".repeat(Math.max(3, at - 1)) + email.substring(at);
    }

    public static String telefone(String tel) {
        if (tel == null) return null;
        String d = NAO_DIGITO.matcher(tel).replaceAll("");
        boolean pais = d.startsWith("55") && (d.length() == 12 || d.length() == 13);
        if (pais) d = d.substring(2);
        if (d.length() < 10) return TOTAL;
        return (pais ? "+55 " : "") + "(" + d.substring(0, 2) + ") " + "*".repeat(d.length() - 6) + "-" + d.substring(d.length() - 4);
    }

    /** Segredo some; 4 finais permitem correlacionar com o IdP/cofre sem expor. */
    public static String token(String valor) { return token(valor, "TOKEN"); }

    public static String token(String valor, String rotulo) {
        if (valor == null) return null;
        String cauda = valor.length() >= 12 ? valor.substring(valor.length() - 4) : "";
        return "[" + rotulo + ":****" + cauda + "]";
    }

    public static String ultimos4(String valor) { return token(valor); }

    /** Anti log forging (CWE-117) para valores vindos de fora que precisam ir a layout de texto. */
    public static String semCrlf(String valor) {
        return valor == null ? null : valor.replace("\r", "\\r").replace("\n", "\\n");
    }
}
