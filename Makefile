.PHONY: all build test gate bench clean

BINARY_NAME=squad-harness
ifeq ($(OS),Windows_NT)
	BINARY_EXT=.exe
else
	BINARY_EXT=
endif

all: build test gate

build:
	CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o $(BINARY_NAME)$(BINARY_EXT) ./cmd/squad-harness

test:
	CGO_ENABLED=0 go test -v ./...

gate: build
	./$(BINARY_NAME)$(BINARY_EXT) gate

bench: build
	./$(BINARY_NAME)$(BINARY_EXT) bench

clean:
	rm -f $(BINARY_NAME) $(BINARY_NAME).exe coverage.out
