#!/bin/bash

# Script para extraer ABIs y bytecode de los contratos compilados por Hardhat
# Ejecutar desde la raíz del proyecto WrapSell

echo "🔄 Extrayendo ABIs y bytecode de contratos..."

# Crear directorios si no existen
mkdir -p wrap-backend/abi
mkdir -p wrap-backend/bytecode

# Función para extraer ABI y bytecode de un contrato
extract_contract() {
    local contract_name=$1
    local artifact_path="contract/artifacts/contracts/${contract_name}.sol/${contract_name}.json"
    
    if [ -f "$artifact_path" ]; then
        echo "✅ Extrayendo $contract_name..."
        
        # Extraer ABI
        jq '.abi' "$artifact_path" > "wrap-backend/abi/${contract_name}.json"
        
        # Extraer bytecode
        jq -r '.bytecode' "$artifact_path" > "wrap-backend/bytecode/${contract_name}.txt"
        
        echo "   - ABI guardado en wrap-backend/abi/${contract_name}.json"
        echo "   - Bytecode guardado en wrap-backend/bytecode/${contract_name}.txt"
    else
        echo "❌ No se encontró el artifact de $contract_name en $artifact_path"
        echo "   Asegúrate de compilar los contratos primero con: cd contract && npx hardhat compile"
    fi
}

# Extraer contratos principales
extract_contract "WrapSell"
extract_contract "WrapPool"

echo ""
echo "✅ Proceso completado!"
echo ""
echo "Para usar el deployer automático:"
echo "1. Configura las variables de entorno en wrap-backend/.env:"
echo "   - RPC_URL=http://localhost:8545  # O tu RPC de red"
echo "   - DEPLOYER_PRIVATE_KEY=0x...     # Clave privada del deployer"
echo "   - CHAIN_ID=31337                 # Chain ID de tu red"
echo ""
echo "2. Instala las dependencias Python:"
echo "   cd wrap-backend && pip install -r requirements.txt"
echo ""
echo "3. Usa la API para desplegar contratos:"
echo "   POST /contracts/deploy/pending"
echo "   POST /contracts/deploy/wrapsell"
echo "   POST /contracts/deploy/wrappool"
