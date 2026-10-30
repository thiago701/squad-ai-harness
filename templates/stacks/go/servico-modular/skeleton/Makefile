GO ?= go
COBERTURA_MINIMA ?= 90
check: vet test
vet:
	$(GO) vet ./...
test:
	$(GO) test ./... -coverprofile=cobertura.out
	@$(GO) tool cover -func=cobertura.out | tail -1
	@total=$$($(GO) tool cover -func=cobertura.out | tail -1 | grep -o '[0-9.]*%' | tr -d '%'); \
	 ok=$$(echo "$$total >= $(COBERTURA_MINIMA)" | bc); \
	 if [ "$$ok" != "1" ]; then echo "cobertura $$total% < $(COBERTURA_MINIMA)%"; exit 1; fi
build:
	CGO_ENABLED=0 $(GO) build -trimpath -ldflags="-s -w" -o bin/taskbox ./cmd/taskbox
run: build
	./bin/taskbox
