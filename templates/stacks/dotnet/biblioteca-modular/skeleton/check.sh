#!/bin/bash
# Gate: build + testes + cobertura >=90% (parse do cobertura.xml do coverlet)
set -euo pipefail
dotnet test tests/Taskbox.Testes --collect:"XPlat Code Coverage" --nologo -v q
xml=$(ls -t tests/Taskbox.Testes/TestResults/*/coverage.cobertura.xml | head -1)
taxa=$(grep -o 'line-rate="[0-9.]*"' "$xml" | head -1 | grep -o '[0-9.]*')
pct=$(python3 -c "print(round(float('$taxa')*100, 2))")
echo "cobertura de linhas: ${pct}%"
python3 -c "exit(0 if float('$taxa') >= 0.90 else 1)" || { echo "cobertura < 90%"; exit 1; }
