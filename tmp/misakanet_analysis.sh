#!/bin/bash
REPO_URL="https://api.github.com/repos/Ikalus1988/MisakaNet"
TMP_DIR="/tmp/misakanet_repo"

# Limpar diretório temporário se existir
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

# Baixar o repositório como ZIP
echo "Baixando repositório..."
curl -sL "$REPO_URL/archive/refs/heads/main.zip" -o "$TMP_DIR/repo.zip"

# Extrair
cd "$TMP_DIR" && unzip -q repo.zip
cd "MisakaNet-main" || exit 1

# Encontrar arquivos relevantes
echo "=== Procurando por openTools ==="
grep -rn "openTools" . --include="*.py" --include="*.js" --include="*.ts" --include="*.json" --include="*.yaml" --include="*.yml" 2>/dev/null

echo ""
echo "=== Procurando por preflight ==="
grep -rn "preflight" . --include="*.py" --include="*.js" --include="*.ts" --include="*.json" --include="*.yaml" --include="*.yml" 2>/dev/null

echo ""
echo "=== Procurando por submit_intake ==="
grep -rn "submit_intake" . --include="*.py" --include="*.js" --include="*.ts" --include="*.json" --include="*.yaml" --include="*.yml" 2>/dev/null

echo ""
echo "=== Procurando por Unauthorized ==="
grep -rn "Unauthorized" . --include="*.py" --include="*.js" --include="*.ts" --include="*.json" --include="*.yaml" --include="*.yml" 2>/dev/null

echo ""
echo "=== Estrutura de pastas ==="
find . -type f -name "*.py" | head -30
find . -type f -name "*.js" | head -30
find . -type f -name "*.ts" | head -30
find . -type f -name "*.json" | head -30
find . -type f -name "*.yaml" -o -name "*.yml" | head -30

echo ""
echo "=== Arquivos na raiz ==="
ls -la
