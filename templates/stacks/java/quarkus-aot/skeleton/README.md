# {{project_name}} (Quarkus 3.37 / Java 25)

API REST Quarkus atual gerada pelo **MITR**: `quarkus-rest` (reativo-first)
com Jackson, dominio puro compartilhado entre os sabores Java, composicao CDI
em um unico produtor, `ExceptionMapper` central e cobertura combinada
(unit + @QuarkusTest) com gate >=90%.

```bash
mvn -B verify           # unit + @QuarkusTest + jacoco (gate)
mvn quarkus:dev         # dev mode com live reload
mvn -Dnative package    # binario nativo (build-time init ja preparado)
```
