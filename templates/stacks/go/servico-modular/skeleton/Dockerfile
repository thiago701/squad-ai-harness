FROM golang:1.26-alpine AS build
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /taskbox ./cmd/taskbox
FROM scratch
COPY --from=build /taskbox /taskbox
USER 65534
ENTRYPOINT ["/taskbox"]
