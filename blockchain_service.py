"""
Blockchain Service for deploying and interacting with WrapSell contracts
"""
import os
import json
from web3 import Web3
from eth_account import Account
import logging

logger = logging.getLogger(__name__)

class BlockchainService:
    def __init__(self):
        # Configuration from environment variables
        self.rpc_url = os.getenv('RPC_URL', 'https://polygon-mainnet.infura.io/v3/YOUR_PROJECT_ID')
        self.chain_id = int(os.getenv('CHAIN_ID', '137'))  # Polygon mainnet
        self.private_key = os.getenv('DEPLOYER_PRIVATE_KEY')
        self.gas_price = int(os.getenv('GAS_PRICE', '30000000000'))  # 30 gwei
        
        if not self.private_key:
            raise ValueError("DEPLOYER_PRIVATE_KEY environment variable is required")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {self.rpc_url}")
        
        # Load deployer account
        self.deployer_account = Account.from_key(self.private_key)
        self.deployer_address = self.deployer_account.address
        
        logger.info(f"Blockchain service initialized for chain {self.chain_id}")
        logger.info(f"Deployer address: {self.deployer_address}")
    
    def load_contract_artifacts(self):
        """Load compiled contract artifacts"""
        try:
            # Get the current directory
            current_dir = os.path.dirname(__file__)
            
            # Load WrapSell contract ABI and bytecode
            with open(os.path.join(current_dir, 'abi/WrapSellTest.json'), 'r') as f:
                wrapsell_artifact = json.load(f)
            
            with open(os.path.join(current_dir, 'bytecode/WrapSell.txt'), 'r') as f:
                wrapsell_bytecode = wrapsell_artifact['bytecode']
            
            # Load WrapPool contract ABI and bytecode
            with open(os.path.join(current_dir, 'abi/WrapPool.json'), 'r') as f:
                wrappool_artifact = json.load(f)
            
            with open(os.path.join(current_dir, 'bytecode/WrapPool.txt'), 'r') as f:
                wrappool_bytecode = f.read().strip()
            
            return {
                'WrapSell': {
                    'abi': wrapsell_artifact,
                    'bytecode': wrapsell_bytecode
                },
                'WrapPool': {
                    'abi': wrappool_artifact,
                    'bytecode': wrappool_bytecode
                }
            }
        except Exception as e:
            logger.error(f"Error loading contract artifacts: {e}")
            raise
    
    def deploy_wrapsell_contract(self, 
                                name: str,
                                symbol: str, 
                                card_id: int,
                                card_name: str,
                                rarity: str,
                                estimated_value_per_card: int,
                                wrap_pool_address: str = None):
        """
        Deploy a new WrapSell contract
        
        Args:
            name: Token name
            symbol: Token symbol
            card_id: TCG card ID
            card_name: Name of the card
            rarity: Card rarity
            estimated_value_per_card: Estimated value per card in wei
            wrap_pool_address: Address of the WrapPool (optional)
        
        Returns:
            dict: Contract deployment result
        """
        try:
            artifacts = self.load_contract_artifacts()
            contract = self.w3.eth.contract(
                abi=artifacts['WrapSell']['abi'],
                bytecode=artifacts['WrapSell']['bytecode']
            )
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.deployer_address)
            
            # Build constructor arguments
            constructor_args = [
                name,
                symbol,
                card_id,
                card_name,
                rarity,
                estimated_value_per_card,
                wrap_pool_address or '0x0000000000000000000000000000000000000000'
            ]
            
            # Build transaction
            transaction = contract.constructor(*constructor_args).build_transaction({
                'chainId': self.chain_id,
                'gas': 3000000,  # Estimated gas limit
                'gasPrice': self.gas_price,
                'nonce': nonce,
                'from': self.deployer_address
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"WrapSell deployment transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if tx_receipt['status'] == 1:
                contract_address = tx_receipt['contractAddress']
                logger.info(f"WrapSell contract deployed successfully at: {contract_address}")
                
                return {
                    'success': True,
                    'contract_address': contract_address,
                    'transaction_hash': tx_hash.hex(),
                    'gas_used': tx_receipt['gasUsed'],
                    'block_number': tx_receipt['blockNumber']
                }
            else:
                logger.error("Contract deployment failed")
                return {
                    'success': False,
                    'error': 'Transaction failed',
                    'transaction_hash': tx_hash.hex()
                }
                
        except Exception as e:
            logger.error(f"Error deploying WrapSell contract: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def deploy_wrappool_contract(self,
                                name: str,
                                symbol: str,
                                owner: str,
                                collateralization_ratio: int = 150):
        """
        Deploy a new WrapPool contract
        
        Args:
            name: Pool name
            symbol: Pool symbol
            owner: Owner address
            collateralization_ratio: Minimum collateralization ratio (default 150%)
        
        Returns:
            dict: Contract deployment result
        """
        try:
            artifacts = self.load_contract_artifacts()
            wrappool_contract = self.w3.eth.contract(
                abi=artifacts['WrapPool']['abi'],
                bytecode=artifacts['WrapPool']['bytecode']
            )
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.deployer_address)
            
            # Build constructor arguments
            constructor_args = [
                name,
                symbol,
                owner,
                collateralization_ratio
            ]
            
            # Build transaction
            transaction = wrappool_contract.constructor(*constructor_args).build_transaction({
                'chainId': self.chain_id,
                'gas': 2500000,  # Estimated gas limit
                'gasPrice': self.gas_price,
                'nonce': nonce,
                'from': self.deployer_address
            })
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            logger.info(f"WrapPool deployment transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if tx_receipt['status'] == 1:
                contract_address = tx_receipt['contractAddress']
                logger.info(f"WrapPool contract deployed successfully at: {contract_address}")
                
                return {
                    'success': True,
                    'contract_address': contract_address,
                    'transaction_hash': tx_hash.hex(),
                    'gas_used': tx_receipt['gasUsed'],
                    'block_number': tx_receipt['blockNumber']
                }
            else:
                logger.error("Contract deployment failed")
                return {
                    'success': False,
                    'error': 'Transaction failed',
                    'transaction_hash': tx_hash.hex()
                }
                
        except Exception as e:
            logger.error(f"Error deploying WrapPool contract: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_contract_instance(self, contract_address: str, contract_type: str):
        """Get a contract instance for interaction"""
        try:
            artifacts = self.load_contract_artifacts()
            return self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=artifacts[contract_type]['abi']
            )
        except Exception as e:
            logger.error(f"Error getting contract instance: {e}")
            raise
    
    def associate_wrapsell_to_pool(self, wrapsell_address: str, pool_address: str):
        """Associate a WrapSell contract to a WrapPool"""
        try:
            # Get WrapPool contract instance
            pool_contract = self.get_contract_instance(pool_address, 'WrapPool')
            
            # Get current nonce
            nonce = self.w3.eth.get_transaction_count(self.deployer_address)
            
            # Build transaction to add WrapSell to pool
            transaction = pool_contract.functions.addWrapSell(
                Web3.to_checksum_address(wrapsell_address)
            ).build_transaction({
                'chainId': self.chain_id,
                'gas': 200000,
                'gasPrice': self.gas_price,
                'nonce': nonce,
                'from': self.deployer_address
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if tx_receipt['status'] == 1:
                logger.info(f"WrapSell {wrapsell_address} associated to pool {pool_address}")
                return {
                    'success': True,
                    'transaction_hash': tx_hash.hex()
                }
            else:
                return {
                    'success': False,
                    'error': 'Association transaction failed'
                }
                
        except Exception as e:
            logger.error(f"Error associating WrapSell to pool: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Global instance
blockchain_service = None

def get_blockchain_service():
    """Get or create blockchain service instance"""
    global blockchain_service
    if blockchain_service is None:
        blockchain_service = BlockchainService()
    return blockchain_service
