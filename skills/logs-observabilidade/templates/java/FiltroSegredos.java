package exemplo.observabilidade;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.turbo.TurboFilter;
import ch.qos.logback.core.spi.FilterReply;
import org.slf4j.LoggerFactory;
import org.slf4j.Marker;

import java.util.regex.Pattern;

/**
 * Barreira 2.2 (references/filtro-segredos.md): segredo NÃO é mascarado — é NEGADO antes de formatar,
 * e o bloqueio vira evento de segurança auditável (logger "seguranca") para alimentar métrica + alerta.
 *
 * Registre em logback-spring.xml: {@code <turboFilter class="exemplo.observabilidade.FiltroSegredos"/>}.
 * PII (CPF, e-mail…) NÃO passa por aqui: é mascarada pelo MascaraJsonDecorator / Mascara na origem.
 */
public final class FiltroSegredos extends TurboFilter {

    private static final org.slf4j.Logger SEGURANCA = LoggerFactory.getLogger("seguranca");

    // famílias do gitleaks + chave=valor genérica — mantenha em sincronia com scripts/logs_obs/mascara.py
    private static final Pattern SEGREDO = Pattern.compile(
        "(?i)(?:authorization\\s*[:=]\\s*(?:bearer|basic|token)\\s+[A-Za-z0-9\\-._~+/=]{8,}"
        + "|\\beyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}\\b"
        + "|\\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[0-9A-Z]{16}\\b"
        + "|-----BEGIN [A-Z ]*PRIVATE KEY-----"
        + "|\\bgh[pousr]_[A-Za-z0-9]{36,}\\b|\\bxox[baprs]-[A-Za-z0-9-]{10,}\\b|\\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\\b"
        + "|[a-z][a-z0-9+.-]*://[^/\\s:@]+:[^@\\s/]{3,}@"
        + "|\\b(?:senha|password|passwd|pwd|secret|client_secret|api[_-]?key|access[_-]?key|secret[_-]?key|"
        + "private[_-]?key|auth[_-]?token|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|cvv|cvc)"
        + "\\b\\s*[:=]\\s*[\"']?(?![*\\[<$]|null\\b|none\\b|true\\b|false\\b)[^\\s\"',;&)}\\]]{3,})");

    @Override
    public FilterReply decide(Marker marker, Logger logger, Level level, String format, Object[] params, Throwable t) {
        if (logger.getName().equals("seguranca")) return FilterReply.NEUTRAL;   // evita recursão
        if (format != null && SEGREDO.matcher(format).find()) return bloquear(logger, "formato");
        if (params != null) {
            for (Object p : params) {
                if (p != null && !(p instanceof Throwable) && SEGREDO.matcher(String.valueOf(p)).find()) {
                    return bloquear(logger, "argumento");
                }
            }
        }
        if (t != null && t.getMessage() != null && SEGREDO.matcher(t.getMessage()).find()) {
            return bloquear(logger, "excecao");   // ex.: SDK que ecoa a URL com credencial na mensagem
        }
        return FilterReply.NEUTRAL;
    }

    private static FilterReply bloquear(Logger origem, String onde) {
        // o evento de segurança NÃO carrega o conteúdo bloqueado — só a localização, para corrigir a origem
        SEGURANCA.warn("log.segredo.bloqueado logger={} onde={}", origem.getName(), onde);
        return FilterReply.DENY;
    }
}
