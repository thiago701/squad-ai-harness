package exemplo.observabilidade;

import net.logstash.logback.mask.MaskingJsonGeneratorDecorator;
import net.logstash.logback.mask.ValueMasker;
import tools.jackson.core.JsonStreamContext;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Camada 2 (rede de segurança) para o LogstashEncoder: mascara CPF/CNPJ/PAN/e-mail/telefone/JWT/segredo=valor em
 * QUALQUER campo string do JSON, com os mesmos formatos da classe {@link Mascara} e do {@code mascara.py}.
 *
 * Por caminho (barato) para os campos conhecidos + por valor (regex validada) para o que escapou.
 * Registre: {@code <jsonGeneratorDecorator class="exemplo.observabilidade.MascaraJsonDecorator"/>}.
 *
 * NB: o pacote de JsonStreamContext muda entre Jackson 2 (com.fasterxml.jackson.core) e Jackson 3 (tools.jackson.core);
 * ajuste o import à versão do logstash-logback-encoder em uso (9.x → Jackson 2; verifique o changelog).
 */
public final class MascaraJsonDecorator extends MaskingJsonGeneratorDecorator {

    public MascaraJsonDecorator() {
        setDefaultMask("****");
        // caminhos conhecidos — segredo some inteiro
        for (String p : new String[]{"password", "senha", "secret", "token", "authorization", "api_key", "apiKey",
                                     "client_secret", "cookie", "cvv", "*/password", "*/senha", "*/token", "*/secret"}) {
            addPath(p);
        }
        // valores — validados para não corromper ids/timestamps
        addValueMasker(new MascaraPorValor());
    }

    /** ValueMasker: recebe cada valor string do JSON e devolve a versão mascarada (ou o mesmo objeto). */
    static final class MascaraPorValor implements ValueMasker {
        private static final Pattern CPF = Pattern.compile("(?<![\\d.\\-/])(\\d{3}\\.?\\d{3}\\.?\\d{3}-?\\d{2})(?![\\d\\-/])");
        private static final Pattern CNPJ = Pattern.compile("(?<!\\d)(\\d{2}\\.?\\d{3}\\.?\\d{3}/?\\d{4}-?\\d{2})(?!\\d)");
        private static final Pattern PAN = Pattern.compile("(?<![\\w.-])((?:\\d[ -]?){12,18}\\d)(?![\\w.-])");
        private static final Pattern EMAIL = Pattern.compile("\\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,})\\b");
        private static final Pattern JWT = Pattern.compile("\\beyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\b");
        private static final Pattern BEARER = Pattern.compile("(?i)(authorization\\s*[:=]\\s*(?:bearer|basic)\\s+)([A-Za-z0-9\\-._~+/=]{8,})");
        private static final Pattern URL_CRED = Pattern.compile("([a-z][a-z0-9+.-]*://[^/\\s:@]+:)([^@\\s/]+)(@)");

        @Override
        public Object mask(JsonStreamContext context, Object value) {
            if (!(value instanceof String s) || s.length() < 8) return value;
            String r = s;
            r = BEARER.matcher(r).replaceAll(m -> Matcher.quoteReplacement(m.group(1) + Mascara.token(m.group(2))));
            r = URL_CRED.matcher(r).replaceAll("$1****$3");
            r = JWT.matcher(r).replaceAll(m -> Matcher.quoteReplacement(Mascara.token(m.group(), "JWT")));
            r = substituir(r, CNPJ, Validadores::cnpjValido, Mascara::cnpj);
            r = substituir(r, CPF, Validadores::cpfValido, Mascara::cpf);
            r = substituir(r, PAN, Validadores::cartaoPlausivel, Mascara::pan);
            r = EMAIL.matcher(r).replaceAll(m -> Matcher.quoteReplacement(Mascara.email(m.group(1))));
            return r;
        }

        private static String substituir(String texto, Pattern p, java.util.function.Predicate<String> valido,
                                         java.util.function.UnaryOperator<String> mascara) {
            Matcher m = p.matcher(texto);
            StringBuilder sb = new StringBuilder();
            while (m.find()) {
                String bruto = m.group(1);
                m.appendReplacement(sb, Matcher.quoteReplacement(valido.test(bruto) ? mascara.apply(bruto) : bruto));
            }
            return m.appendTail(sb).toString();
        }
    }

    /** Validadores — evitam mascarar número de pedido, epoch e UUID (mesma lógica do mascara.py). */
    static final class Validadores {
        static boolean cpfValido(String cpf) {
            String d = cpf.replaceAll("\\D", "");
            if (d.length() != 11 || d.chars().distinct().count() == 1) return false;
            for (int n : new int[]{9, 10}) {
                int soma = 0;
                for (int i = 0; i < n; i++) soma += (d.charAt(i) - '0') * ((n + 1) - i);
                int dv = (soma * 10) % 11; if (dv == 10) dv = 0;
                if (dv != d.charAt(n) - '0') return false;
            }
            return true;
        }
        static boolean cnpjValido(String cnpj) {
            String d = cnpj.replaceAll("\\D", "");
            if (d.length() != 14 || d.chars().distinct().count() == 1) return false;
            int[] p1 = {5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2}, p2 = {6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2};
            return dv(d, p1) == d.charAt(12) - '0' && dv(d, p2) == d.charAt(13) - '0';
        }
        private static int dv(String d, int[] pesos) {
            int soma = 0;
            for (int i = 0; i < pesos.length; i++) soma += (d.charAt(i) - '0') * pesos[i];
            int r = soma % 11; return r < 2 ? 0 : 11 - r;
        }
        static boolean cartaoPlausivel(String bruto) {
            String d = bruto.replaceAll("\\D", "");
            if (!luhn(d)) return false;
            if (bruto.matches(".*[ -].*")) return d.length() >= 13 && d.length() <= 19;
            return (d.length() == 15 || d.length() == 16) && "3456".indexOf(d.charAt(0)) >= 0;
        }
        static boolean luhn(String d) {
            if (d.length() < 13 || d.length() > 19) return false;
            int total = 0; boolean alt = false;
            for (int i = d.length() - 1; i >= 0; i--) {
                int n = d.charAt(i) - '0';
                if (alt) { n *= 2; if (n > 9) n -= 9; }
                total += n; alt = !alt;
            }
            return total % 10 == 0;
        }
    }
}
