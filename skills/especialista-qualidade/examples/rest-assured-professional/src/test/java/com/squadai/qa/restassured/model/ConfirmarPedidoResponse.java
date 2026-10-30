package com.squadai.qa.restassured.model;

import java.math.BigDecimal;

/**
 * POJO tipado da resposta de confirmação. Desserializar para um tipo (em vez de navegar
 * o JSON com strings) dá segurança de compilação e melhora a legibilidade das asserções.
 * Em Java 25 isto seria um {@code record}; aqui é POJO por causa do Java 11 do sandbox.
 */
public class ConfirmarPedidoResponse {

    private long pedidoId;
    private String status;
    private String confirmadoEm;
    private BigDecimal valorTotal;

    public ConfirmarPedidoResponse() {
    }

    public long getPedidoId() {
        return pedidoId;
    }

    public void setPedidoId(long pedidoId) {
        this.pedidoId = pedidoId;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getConfirmadoEm() {
        return confirmadoEm;
    }

    public void setConfirmadoEm(String confirmadoEm) {
        this.confirmadoEm = confirmadoEm;
    }

    public BigDecimal getValorTotal() {
        return valorTotal;
    }

    public void setValorTotal(BigDecimal valorTotal) {
        this.valorTotal = valorTotal;
    }
}
