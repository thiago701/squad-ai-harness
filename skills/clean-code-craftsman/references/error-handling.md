# Tratamento de Erros

> "Tratamento de erros é importante, mas se ele obscurece a lógica, está errado."

Tratamento de erros é uma área onde o pragmatismo encontra a teoria com força. Em código real, **muito** do que você escreve é "o que fazer quando algo der errado". A questão é: como tratar erros sem afogar a lógica principal em ifs e checagens?

## Use exceções, não códigos de retorno

```
// Ruim — códigos de retorno forçam verificação encadeada
public class DeviceController {
    public void sendShutDown() {
        DeviceHandle handle = getHandle(DEV1);
        if (handle != DeviceHandle.INVALID) {
            retrieveDeviceRecord(handle);
            if (record.getStatus() != DEVICE_SUSPENDED) {
                pauseDevice(handle);
                clearDeviceWorkQueue(handle);
                closeDevice(handle);
            } else {
                logger.log("Dispositivo suspenso. Não pode ser desligado");
            }
        } else {
            logger.log("Handle inválido para: " + DEV1);
        }
    }
}
```

A lógica principal está soterrada em `if`s. O caminho feliz não é claro.

```
// Bom — exceções separam o caminho feliz do tratamento
public class DeviceController {
    public void sendShutDown() {
        try {
            tryToShutDown();
        } catch (DeviceShutDownError e) {
            logger.log(e);
        }
    }

    private void tryToShutDown() throws DeviceShutDownError {
        DeviceHandle handle = getHandle(DEV1);
        DeviceRecord record = retrieveDeviceRecord(handle);
        pauseDevice(handle);
        clearDeviceWorkQueue(handle);
        closeDevice(handle);
    }
}
```

Quem lê `tryToShutDown` vê a lógica fluindo. Os erros são tratados em uma camada separada.

## Escreva o try-catch-finally primeiro

Quando você sabe que algo pode falhar, escreva o `try-catch-finally` **antes** da lógica:

```
@Test(expected = StorageException.class)
public void retrieveSectionShouldThrowOnInvalidFileName() {
    sectionStore.retrieveSection("invalid - file");
}

// Implementação inicial — sem disparar
public List<RecordedGrip> retrieveSection(String sectionName) {
    return new ArrayList<RecordedGrip>();
}
```

O teste falha. Agora você implementa o suficiente para dispará-lo:

```
public List<RecordedGrip> retrieveSection(String sectionName) {
    try {
        FileInputStream stream = new FileInputStream(sectionName);
    } catch (Exception e) {
        throw new StorageException("retrieval error", e);
    }
    return new ArrayList<RecordedGrip>();
}
```

Tratamento de erro **define o escopo**. Comece com ele e adicione lógica feliz depois.

> "Tente escrever testes que forçam exceções, e então adicione comportamento ao seu handler para satisfazer os testes."

## Use exceções não-checadas (em Java)

Java tem dois tipos: checadas (devem ser declaradas) e não-checadas (não precisam).

Exceções checadas são tentadoras — parecem rigorosas. Mas:
1. Elas violam o princípio Open/Closed: adicionar uma exceção em um método de baixo nível obriga **todos os métodos no caminho** a declararem ou tratarem.
2. Encapsulação quebra: detalhes de implementação vazam para a interface pública.
3. Em sistemas grandes, o esforço de manter as listas de exceções é enorme — sem retorno proporcional.

Conclusão: **prefira exceções não-checadas** (RuntimeException) na maioria dos casos. C#, Python, Ruby, e Scala não têm checadas e não sentem falta.

## Forneça contexto com exceções

```
// Ruim — só joga e some
throw new IOException();

// Bom — diz o que falhou e por quê
throw new IOException("Falha ao abrir conexão com BD '" + dbName + "': " + cause.getMessage());
```

Inclua:
- A operação que falhou.
- O tipo de falha.
- Informação suficiente para diagnóstico.

Cada exceção é uma oportunidade de ajudar (ou frustrar) o engenheiro de plantão às 3h da manhã.

## Defina classes de exceção em termos das necessidades de quem chama

Um erro comum: criar tipos de exceção espelhando a fonte (`SQLException`, `IOException`, `NetworkException`). O **chamador** raramente se importa com a fonte — ele se importa com **o que fazer**.

```
// Ruim — chamador precisa tratar cada fonte
ACMEPort port = new ACMEPort(12);
try {
    port.open();
} catch (DeviceResponseException e) {
    reportPortError(e);
} catch (ATM1212UnlockedException e) {
    reportPortError(e);
} catch (GMXError e) {
    reportPortError(e);
}
```

Cada `catch` faz a mesma coisa, e cada novo tipo adiciona um caso. **Embrulhe** o serviço externo:

```
LocalPort port = new LocalPort(12);
try {
    port.open();
} catch (PortDeviceFailure e) {
    reportError(e);
}
```

Onde `LocalPort` traduz exceções da biblioteca externa em uma única `PortDeviceFailure`. Vantagens:
- Lógica de cliente fica simples.
- Você desacopla da biblioteca externa (pode trocá-la sem reescrever clientes).
- Você melhora os testes (pode mockar `LocalPort` mais facilmente).

## Defina o fluxo normal

> "Quando você se pega tratando uma situação como exceção que poderia ser tratada como caso normal, considere o **Special Case Pattern**."

```
// Tratamento via exceção
try {
    MealExpenses expenses = expenseReportDAO.getMeals(employee.getID());
    m_total += expenses.getTotal();
} catch (MealExpensesNotFound e) {
    m_total += getMealPerDiem();
}
```

O caller faz lógica de negócio dentro de um `catch`. Pior, repete em todo lugar que precisa do mesmo cálculo.

```
// Special case — sem exceção, sem lógica de fallback no caller
m_total += expenseReportDAO.getMeals(employee.getID()).getTotal();
```

Onde `getMeals` retorna `MealExpenses` real **ou** uma `PerDiemMealExpenses` (special case) que retorna o per diem como total. O caller não precisa saber a diferença.

## Não retorne null

`null` é o erro de bilhão de dólares (Tony Hoare). Cada vez que você retorna `null`, está armando uma armadilha:
- Quem chama precisa lembrar de checar.
- Quando esquece, NPE.
- O código fica cheio de `if (x != null)`.

Alternativas:
- **Retorne uma lista vazia** quando o método retorna lista.
- **Retorne `Optional<T>`** (Java 8+) — explicita ausência.
- **Retorne um special case object** (vide acima).
- **Lance uma exceção** se o caso é genuinamente excepcional.

```
// Ruim
List<Employee> employees = getEmployees();
if (employees != null) {
    for (Employee e : employees) { totalPay += e.getPay(); }
}

// Bom — getEmployees() devolve Collections.emptyList() quando não há
for (Employee e : getEmployees()) { totalPay += e.getPay(); }
```

## Não passe null

Se passar `null` como argumento força o método a checar e a tratar como caso especial, **não passe**. Use:
- Sobrecargas com diferentes assinaturas.
- Objetos null/special case.
- Lance exceção em vez de aceitar null.

Métodos públicos não deveriam aceitar null — sua presença é um defeito de design.

## Conclusão

Tratamento de erros é responsabilidade — uma das que mais distingue código profissional de código amador. Em sistemas robustos:
- Exceções estruturadas substituem códigos de retorno.
- Tratamento é **separado** da lógica feliz, geralmente em um nível acima.
- Exceções carregam contexto suficiente para diagnóstico.
- `null` não circula — em nenhuma direção.

Tudo isso é integrado quando você faz **tratamento de erro como uma única coisa que a função pode fazer** — separada da lógica de negócio que é a outra coisa que outras funções fazem.
