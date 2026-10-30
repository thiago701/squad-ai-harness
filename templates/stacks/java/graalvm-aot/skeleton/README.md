# {{project_name}} (Java 25 + GraalVM Native Image)

CLI nativa gerada pelo **MITR**: records com compact constructor, hierarquia
selada de erros, colecao de primeira classe, zero reflexao — compila para
binario nativo com `--no-fallback` sem configuracao extra.

```bash
mvn -B verify            # JUnit 5 + jacoco check >=90% (gate)
mvn -B -Pnative package  # binario nativo ./target/taskbox
./target/taskbox         # startup em milissegundos
```
