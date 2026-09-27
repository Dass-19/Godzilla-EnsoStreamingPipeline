#!/usr/bin/env bash
# Hook Git pre-commit: valida tests y linters antes de permitir el commit

set -e

echo "=== [PRE-COMMIT HOOK] Verificando linter y contratos ==="

# 1. Verificar Linting
if command -v ruff &> /dev/null; then
    echo "[+] Ejecutando ruff check..."
    ruff check .
elif command -v python &> /dev/null; then
    python -m ruff check .
fi

# 2. Verificar Tests de Contrato
if command -v pytest &> /dev/null; then
    echo "[+] Ejecutando tests de contrato..."
    pytest tests/test_contracts.py -q
elif command -v python &> /dev/null; then
    python -m pytest tests/test_contracts.py -q
fi

echo "=== [PRE-COMMIT HOOK] Todas las validaciones pasaron exitosamente ==="
