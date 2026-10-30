FROM ghcr.io/graalvm/native-image-community:25 AS build
WORKDIR /src
COPY . .
RUN ./mvnw -B -Pnative package || mvn -B -Pnative package
FROM gcr.io/distroless/base-debian12
COPY --from=build /src/target/taskbox /taskbox
USER 65534
ENTRYPOINT ["/taskbox"]
