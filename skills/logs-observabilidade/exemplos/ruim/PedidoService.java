package exemplo.ruim;

// FIXTURE SINTÉTICA — tudo aqui está ERRADO de propósito (selftest da lente LOG-xx).
// Nenhum valor é credencial real. Veja ../bom/PedidoService.java para a versão correta.

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PedidoService {

    private static final Logger log = LoggerFactory.getLogger(PedidoService.class);

    public void autenticar(String usuario, String token, String senha) {
        log.info("token=" + token);                                   // LOG-01 + LOG-12
        log.debug("autenticando usuario {} senha {}", usuario, senha); // LOG-01
        log.info("config carregada: {}", System.getenv());            // LOG-03
    }

    public void criar(Cliente cliente, Pagamento pagamento) {
        log.info("Criando pedido para o cliente informado agora");     // LOG-14 (prosa)
        log.info("cliente cpf={} email={}", cliente.getCpf(), cliente.getEmail()); // LOG-02
        log.info("cartao {}", pagamento.numeroCartao);                 // LOG-02
        System.out.println("pedido criado");                           // LOG-10
    }

    public void cobrar(Pagamento pagamento) {
        try {
            gateway.cobrar(pagamento);
        } catch (Exception e) {
            log.error("falha ao cobrar: {}", e.getMessage());          // LOG-11
            e.printStackTrace();                                       // LOG-10
        }
    }

    public void receber(HttpRequest request) {
        log.info("request recebido headers={} body={}", request.getHeaders(), request.getBody()); // LOG-13
    }
}
