"""
Contract Deployment Module
Módulo para desplegar contratos WrapSell y WrapPool basándose en datos de la base de datos
"""

import os
import json
from web3 import Web3
from eth_account import Account
import psycopg2
import urllib.parse
from decimal import Decimal

class ContractDeployer:
    def __init__(self):
        # Configuración de Web3 y blockchain
        self.w3 = None
        self.account = None
        self.chain_id = None
        self.setup_web3()
        
        # Configuración de base de datos
        self.db_url = os.getenv('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL no está definido")
            
        self.url = urllib.parse.urlparse(self.db_url)
        self.DB_URL = f"dbname={self.url.path[1:]} user={self.url.username} password={self.url.password} host={self.url.hostname} port={self.url.port}"
        
    def setup_web3(self):
        """Configurar conexión Web3"""
        # RPC URL - puede ser Infura, Alchemy, o nodo local
        rpc_url = os.getenv('RPC_URL', 'http://localhost:8545')  # Default para desarrollo local
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Verificar conexión
        if not self.w3.is_connected():
            print(f"⚠️  No se pudo conectar a la blockchain en {rpc_url}")
            return
            
        # Configurar cuenta desde private key
        private_key = os.getenv('DEPLOYER_PRIVATE_KEY')
        if private_key:
            self.account = Account.from_key(private_key)
            print(f"✅ Cuenta configurada: {self.account.address}")
        else:
            print("⚠️  DEPLOYER_PRIVATE_KEY no configurado")
            
        # Chain ID
        self.chain_id = int(os.getenv('CHAIN_ID', '31337'))  # Default para Hardhat local
        print(f"✅ Chain ID: {self.chain_id}")
        
    def compile_contract(self, contract_name):
        """
        Compilar contrato usando solc (requiere instalación de solc)
        En producción, usar contratos precompilados
        """
        try:
            from solcx import compile_source, install_solc, set_solc_version
            
            # Instalar solc si no existe
            try:
                set_solc_version('0.8.20')
            except:
                install_solc('0.8.20')
                set_solc_version('0.8.20')
            
            # Leer archivo del contrato
            contract_path = os.path.join(os.path.dirname(__file__), 'contracts', f'{contract_name}.sol')
            with open(contract_path, 'r') as f:
                contract_source = f.read()
            
            # Compilar
            compiled_sol = compile_source(contract_source)
            
            # Obtener interface del contrato
            contract_interface = compiled_sol[f'<stdin>:{contract_name}']
            
            return contract_interface['abi'], contract_interface['bin']
            
        except ImportError:
            print("⚠️  py-solc-x no instalado. Usando ABIs precompilados...")
            return self.load_precompiled_contract(contract_name)
        except Exception as e:
            print(f"❌ Error compilando {contract_name}: {e}")
            return None, None
    
    def load_precompiled_contract(self, contract_name):
        """Cargar ABI y bytecode precompilados"""
        try:
            # Forzar el uso de los archivos de WrapSell, nunca WrapSellTest
            if contract_name == 'WrapSell':
                abi_path = os.path.join(os.path.dirname(__file__), 'abi', 'WrapSell.json')
                bytecode_path = os.path.join(os.path.dirname(__file__), 'bytecode', 'WrapSell.txt')
            else:
                abi_path = os.path.join(os.path.dirname(__file__), 'abi', f'{contract_name}.json')
                bytecode_path = os.path.join(os.path.dirname(__file__), 'bytecode', f'{contract_name}.txt')
            print(f"[DEBUG] ABI path usado: {abi_path}")
            print(f"[DEBUG] Bytecode path usado: {bytecode_path}")
            with open(abi_path, 'r') as f:
                abi_json = json.load(f)
                if isinstance(abi_json, dict) and 'abi' in abi_json:
                    abi = abi_json['abi']
                else:
                    abi = abi_json
            with open(bytecode_path, 'r') as f:
                bytecode = f.read().strip()
            return abi, bytecode
        except Exception as e:
            print(f"❌ Error cargando contrato precompilado {contract_name}: {e}")
            return None, None
    
    def deploy_wrapsell_contract(self, card_data):
        """
        Desplegar contrato WrapSell basado en datos de carta
        """
        if not self.w3 or not self.account:
            raise Exception("Web3 o cuenta no configurados")
            
        # Obtener ABI y bytecode
        abi, bytecode = self.compile_contract('WrapSell')
        if not abi or not bytecode:
            raise Exception("No se pudo compilar WrapSell")
            
        # Crear contrato
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Parámetros del constructor
        name = f"{card_data['name']}WrapSell"  # Ej: "Milotic ExWrapSell"
        symbol = f"W{card_data['name'].replace(' ', '')[:8].upper()}"  # Ej: "WMILOTICE"
        card_id = card_data['id']
        card_name = card_data['name']
        rarity = card_data.get('rarity', 'Common')
        estimated_value = self.w3.to_wei(card_data.get('market_value', 0.01), 'ether')
        
        # Construir transacción
        constructor_txn = contract.constructor(
            name,
            symbol,
            card_id,
            card_name,
            rarity,
            estimated_value
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 3000000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'chainId': self.chain_id
        })
        
        # Firmar y enviar transacción
        signed_txn = self.w3.eth.account.sign_transaction(constructor_txn, private_key=self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Esperar confirmación
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt.status == 1:
            print(f"✅ WrapSell desplegado: {tx_receipt.contractAddress}")
            return tx_receipt.contractAddress
        else:
            raise Exception("Falló el despliegue del contrato")
    
    def deploy_wrappool_contract(self, pool_data):
        """
        Desplegar contrato WrapPool basado en datos de pool
        """
        if not self.w3 or not self.account:
            raise Exception("Web3 o cuenta no configurados")
            
        # Obtener ABI y bytecode
        abi, bytecode = self.compile_contract('WrapPool')
        if not abi or not bytecode:
            raise Exception("No se pudo compilar WrapPool")
            
        # Crear contrato
        contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        
        # Parámetros del constructor
        name = pool_data['name']
        symbol = pool_data.get('symbol', f"{pool_data['name'][:3].upper()}USD")
        
        # Construir transacción
        constructor_txn = contract.constructor(
            name,
            symbol
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 4000000,
            'gasPrice': self.w3.to_wei('20', 'gwei'),
            'chainId': self.chain_id
        })
        
        # Firmar y enviar transacción
        signed_txn = self.w3.eth.account.sign_transaction(constructor_txn, private_key=self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        # Esperar confirmación
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if tx_receipt.status == 1:
            print(f"✅ WrapPool desplegado: {tx_receipt.contractAddress}")
            return tx_receipt.contractAddress
        else:
            raise Exception("Falló el despliegue del contrato")
    
    def get_cards_without_contracts(self):
        """Obtener cartas que no tienen contratos desplegados"""
        conn = psycopg2.connect(self.DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.id, c.name, c.card_id, c.edition, c.market_value, c.user_wallet, c.pool_id
            FROM cards c
            WHERE c.wrap_sell_address IS NULL 
            AND c.removed_at IS NULL
            AND c.market_value > 0
            ORDER BY c.market_value DESC
        """)
        
        cards = []
        for row in cur.fetchall():
            cards.append({
                'id': row[0],
                'name': row[1],
                'card_id': row[2],
                'edition': row[3],
                'market_value': float(row[4]) if row[4] else 0.01,
                'user_wallet': row[5],
                'pool_id': row[6],
                'rarity': 'Common'  # Default, se puede mejorar con datos reales
            })
        
        cur.close()
        conn.close()
        return cards
    
    def get_pools_without_contracts(self):
        """Obtener pools que no tienen contratos desplegados"""
        conn = psycopg2.connect(self.DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT cp.id, cp.name, cp.description, cp.TCG, cp.created_by
            FROM card_pools cp
            WHERE cp.wrap_pool_address IS NULL
            ORDER BY cp.created_at ASC
        """)
        
        pools = []
        for row in cur.fetchall():
            pools.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'tcg': row[3],
                'created_by': row[4],
                'symbol': f"{row[1][:3].upper()}USD"
            })
        
        cur.close()
        conn.close()
        return pools
    
    def update_card_contract_address(self, card_id, contract_address):
        """Actualizar dirección del contrato en la base de datos"""
        conn = psycopg2.connect(self.DB_URL)
        cur = conn.cursor()
        
        # Insertar en wrap_sells
        cur.execute("""
            INSERT INTO wrap_sells (
                contract_address, name, symbol, card_id, card_name, rarity, 
                estimated_value_per_card, owner_wallet
            ) SELECT 
                %s, 
                CONCAT(c.name, 'WrapSell'), 
                CONCAT('W', UPPER(REPLACE(LEFT(c.name, 8), ' ', ''))), 
                c.id, 
                c.name, 
                'Common', 
                %s, 
                c.user_wallet
            FROM cards c WHERE c.id = %s
        """, (contract_address, self.w3.to_wei(0.01, 'ether'), card_id))
        
        # Actualizar cards
        cur.execute("""
            UPDATE cards 
            SET wrap_sell_address = %s 
            WHERE id = %s
        """, (contract_address, card_id))
        
        conn.commit()
        cur.close()
        conn.close()
    
    def update_pool_contract_address(self, pool_id, contract_address):
        """Actualizar dirección del contrato de pool en la base de datos"""
        conn = psycopg2.connect(self.DB_URL)
        cur = conn.cursor()
        
        # Insertar en wrap_pools
        cur.execute("""
            INSERT INTO wrap_pools (
                contract_address, name, symbol, owner_wallet, collateralization_ratio
            ) SELECT 
                %s, 
                cp.name, 
                CONCAT(UPPER(LEFT(cp.name, 3)), 'USD'), 
                cp.created_by, 
                150
            FROM card_pools cp WHERE cp.id = %s
        """, (contract_address, pool_id))
        
        # Actualizar card_pools
        cur.execute("""
            UPDATE card_pools 
            SET wrap_pool_address = %s 
            WHERE id = %s
        """, (contract_address, pool_id))
        
        conn.commit()
        cur.close()
        conn.close()
    
    def deploy_pending_contracts(self):
        """Desplegar todos los contratos pendientes - SINCRONIZACIÓN COMPLETA"""
        results = {
            'wrapsells_deployed': [],
            'wrappools_deployed': [],
            'errors': [],
            'summary': {}
        }
        
        try:
            # Desplegar WrapSell para TODAS las cartas sin contratos
            cards = self.get_cards_without_contracts()
            print(f"📋 Encontradas {len(cards)} cartas sin contratos")
            print(f"🎯 OBJETIVO: Sincronizar TODAS las cartas de la BD con la blockchain")
            
            # Procesar TODAS las cartas (sin límite de batch)
            deployed_count = 0
            error_count = 0
            
            for i, card in enumerate(cards, 1):
                try:
                    print(f"🚀 [{i}/{len(cards)}] Desplegando contrato para '{card['name']}'...")
                    contract_address = self.deploy_wrapsell_contract(card)
                    self.update_card_contract_address(card['id'], contract_address)
                    
                    results['wrapsells_deployed'].append({
                        'card_id': card['id'],
                        'card_name': card['name'],
                        'contract_name': f"{card['name']}WrapSell",
                        'contract_address': contract_address,
                        'market_value': card['market_value']
                    })
                    deployed_count += 1
                    print(f"✅ [{i}/{len(cards)}] Contrato '{card['name']}WrapSell' desplegado: {contract_address}")
                    
                except Exception as e:
                    error_msg = f"Error desplegando WrapSell para carta '{card['name']}': {str(e)}"
                    results['errors'].append(error_msg)
                    error_count += 1
                    print(f"❌ [{i}/{len(cards)}] {error_msg}")
            
            # Resumen de WrapSells
            results['summary']['wrapsells'] = {
                'total_cards': len(cards),
                'deployed': deployed_count,
                'errors': error_count,
                'success_rate': f"{(deployed_count / len(cards) * 100):.1f}%" if cards else "0%"
            }
            
            # Desplegar WrapPool para TODOS los pools sin contratos
            pools = self.get_pools_without_contracts()
            print(f"📋 Encontrados {len(pools)} pools sin contratos")
            print(f"🎯 OBJETIVO: Sincronizar TODOS los pools de la BD con la blockchain")
            
            pool_deployed_count = 0
            pool_error_count = 0
            
            for i, pool in enumerate(pools, 1):
                try:
                    print(f"🚀 [{i}/{len(pools)}] Desplegando contrato para pool '{pool['name']}'...")
                    contract_address = self.deploy_wrappool_contract(pool)
                    self.update_pool_contract_address(pool['id'], contract_address)
                    
                    results['wrappools_deployed'].append({
                        'pool_id': pool['id'],
                        'pool_name': pool['name'],
                        'contract_address': contract_address,
                        'tcg': pool['tcg']
                    })
                    pool_deployed_count += 1
                    print(f"✅ [{i}/{len(pools)}] Pool '{pool['name']}' desplegado: {contract_address}")
                    
                except Exception as e:
                    error_msg = f"Error desplegando WrapPool para pool '{pool['name']}': {str(e)}"
                    results['errors'].append(error_msg)
                    pool_error_count += 1
                    print(f"❌ [{i}/{len(pools)}] {error_msg}")
            
            # Resumen de WrapPools
            results['summary']['wrappools'] = {
                'total_pools': len(pools),
                'deployed': pool_deployed_count,
                'errors': pool_error_count,
                'success_rate': f"{(pool_deployed_count / len(pools) * 100):.1f}%" if pools else "0%"
            }
            
            # Resumen final
            print(f"\n🎉 SINCRONIZACIÓN COMPLETADA:")
            print(f"📊 WrapSells: {deployed_count}/{len(cards)} cartas sincronizadas")
            print(f"📊 WrapPools: {pool_deployed_count}/{len(pools)} pools sincronizados")
            print(f"❌ Errores totales: {error_count + pool_error_count}")
                    
        except Exception as e:
            error_msg = f"Error general en sincronización completa: {str(e)}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results
    
    def check_synchronization_status(self):
        """Verificar el estado de sincronización entre BD y blockchain"""
        conn = psycopg2.connect(self.DB_URL)
        cur = conn.cursor()
        
        # Estadísticas de cartas
        cur.execute("SELECT COUNT(*) FROM cards WHERE removed_at IS NULL")
        total_cards = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM cards WHERE wrap_sell_address IS NOT NULL AND removed_at IS NULL")
        cards_with_contracts = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM cards WHERE wrap_sell_address IS NULL AND removed_at IS NULL")
        cards_without_contracts = cur.fetchone()[0]
        
        # Estadísticas de pools
        cur.execute("SELECT COUNT(*) FROM card_pools")
        total_pools = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM card_pools WHERE wrap_pool_address IS NOT NULL")
        pools_with_contracts = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM card_pools WHERE wrap_pool_address IS NULL")
        pools_without_contracts = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        sync_status = {
            'cards': {
                'total': total_cards,
                'with_contracts': cards_with_contracts,
                'without_contracts': cards_without_contracts,
                'sync_percentage': (cards_with_contracts / total_cards * 100) if total_cards > 0 else 0,
                'is_fully_synced': cards_without_contracts == 0
            },
            'pools': {
                'total': total_pools,
                'with_contracts': pools_with_contracts,
                'without_contracts': pools_without_contracts,
                'sync_percentage': (pools_with_contracts / total_pools * 100) if total_pools > 0 else 0,
                'is_fully_synced': pools_without_contracts == 0
            },
            'overall': {
                'is_fully_synced': cards_without_contracts == 0 and pools_without_contracts == 0
            }
        }
        
        # Mostrar resumen
        print(f"📊 ESTADO DE SINCRONIZACIÓN BD ↔ BLOCKCHAIN:")
        print(f"🃏 CARTAS: {cards_with_contracts}/{total_cards} ({sync_status['cards']['sync_percentage']:.1f}%)")
        print(f"🏊 POOLS: {pools_with_contracts}/{total_pools} ({sync_status['pools']['sync_percentage']:.1f}%)")
        
        if sync_status['overall']['is_fully_synced']:
            print(f"✅ TOTALMENTE SINCRONIZADO - Todas las entidades tienen contratos")
        else:
            print(f"⚠️  SINCRONIZACIÓN PENDIENTE:")
            if cards_without_contracts > 0:
                print(f"   • {cards_without_contracts} cartas sin contratos")
            if pools_without_contracts > 0:
                print(f"   • {pools_without_contracts} pools sin contratos")
        
        return sync_status

    def ensure_full_synchronization(self):
        """Garantizar sincronización completa entre BD y blockchain"""
        print(f"🔄 INICIANDO SINCRONIZACIÓN COMPLETA BD ↔ BLOCKCHAIN")
        
        # Verificar estado actual
        status = self.check_synchronization_status()
        
        if status['overall']['is_fully_synced']:
            print(f"✅ Ya está completamente sincronizado. No hay nada que hacer.")
            return {
                'already_synced': True,
                'status': status
            }
        
        # Ejecutar despliegue completo
        print(f"🚀 Ejecutando despliegue de contratos faltantes...")
        deployment_results = self.deploy_pending_contracts()
        
        # Verificar estado final
        print(f"🔍 Verificando estado final...")
        final_status = self.check_synchronization_status()
        
        return {
            'already_synced': False,
            'initial_status': status,
            'deployment_results': deployment_results,
            'final_status': final_status,
            'success': final_status['overall']['is_fully_synced']
        }
