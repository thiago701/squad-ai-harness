FROM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /src
COPY . .
RUN mvn -B -q -DskipTests package
FROM eclipse-temurin:25-jre
RUN useradd --system aplicacao
USER aplicacao
COPY --from=build /src/target/*.jar /app/aplicacao.jar
HEALTHCHECK CMD curl -sf http://127.0.0.1:8080/health || exit 1
ENTRYPOINT ["java", "-jar", "/app/aplicacao.jar"]
