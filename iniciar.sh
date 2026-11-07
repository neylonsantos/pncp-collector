#!/usr/bin/env bash
# ==============================================================================
# Script de Inicialização - PNCP Collector & Analyzer
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

PORT=8000

echo ""
echo "=================================================================="
echo "  🚀 PNCP Collector & Analyzer (Mestrado Lab)"
echo "  Sistema de Captura e Mineração de Editais Governamentais"
echo "=================================================================="
echo "  📂 Diretório: $DIR"
echo "  🌐 URL da Aplicação: http://localhost:$PORT"
echo "=================================================================="
echo ""

# Tenta abrir o navegador automaticamente se xdg-open estiver disponível e houver display gráfico
if command -v xdg-open > /dev/null && [ -n "$DISPLAY" ]; then
    (sleep 1 && xdg-open "http://localhost:$PORT" 2>/dev/null) &
fi

exec python3 app.py
