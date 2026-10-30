package exemplo.bom;

// Versão CORRETA do ../ruim/PedidoService.java — passa limpa na lente LOG-xx.
// Doutrina: evento nomeado + chave=valor, placeholders, PII mascarada na origem,
// exceção como último argumento, correlação pelo MDC/ScopedValue (ver templates/).

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;

public class PedidoService {

    private static final Logger log = LoggerFactory.getLogger(PedidoService.class);

    public void autenticar(String usuario, String token) {
        // segredo nunca é logado: só a existência e os 4 finais para correlação com o IdP
        log.info("auth.token.recebido usuario_id={} token_presente={} token_sufixo={}",
                 usuario, token != null, Mascara.ultimos4(token));
        log.debug("config.carregada vars_presentes={}", Config.nomesDasVariaveis()); // nomes, nunca valores
    }

    public void criar(Cliente cliente, Pagamento pagamento) {
        // PII mascarada NA ORIGEM: Cliente.toString()/record já expõe cpf mascarado; aqui logamos ids
        log.info("pedido.criado pedido_id={} cliente_id={} cpf={} forma_pagamento={}",
                 pagamento.pedidoId(), cliente.id(), Mascara.cpf(cliente.cpf()), pagamento.tipo());
        log.info("pagamento.cartao.registrado pedido_id={} cartao={}",
                 pagamento.pedidoId(), Mascara.pan(pagamento.numeroCartao()));
    }

    public void cobrar(Pagamento pagamento) {
        try {
            gateway.cobrar(pagamento);
            log.info("pagamento.autorizado pedido_id={} valor_centavos={}", pagamento.pedidoId(), pagamento.valorCentavos());
        } catch (GatewayException e) {
            // exceção como ÚLTIMO argumento: stack trace preservado, mensagem continua pesquisável
            log.error("pagamento.falhou pedido_id={} gateway_codigo={}", pagamento.pedidoId(), e.codigo(), e);
            throw e;
        }
    }

    public void receber(HttpRequest request) {
        // campos escolhidos, nunca o request inteiro; correlação vem do filtro que popula o MDC
        log.info("http.request.recebido metodo={} rota={} correlation_id={}",
                 request.metodo(), request.rota(), MDC.get("correlation_id"));
    }
}
