FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY . .
RUN dotnet publish src/Taskbox.Dominio -c Release -o /app
FROM mcr.microsoft.com/dotnet/runtime-deps:10.0-noble-chiseled
USER app
COPY --from=build /app /app
