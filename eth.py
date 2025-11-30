# eth.py

from web3 import Web3
from web3.middleware import geth_poa_middleware # <-- v6 格式
from web3.exceptions import TransactionNotFound
from eth_account import Account

# --- 自定义异常 ---
# 定义这些特定的异常类，可以让插件的上层代码（main.py）
# 能够通过 try...except 块捕捉到具体的错误类型，并给用户更精准的反馈。
class EthereumServiceError(Exception):
    """所有本服务相关错误的基类"""
    pass

class ConnectionError(EthereumServiceError):
    """当无法连接到以太坊RPC节点时抛出"""
    pass

class InsufficientFundsError(EthereumServiceError):
    """当ETH或代币余额不足以完成操作时抛出"""
    pass

class TransactionFailedError(EthereumServiceError):
    """当链上交易执行失败 (例如，被拒绝或回执状态为0) 时抛出"""
    pass


# --- 智能合约 ABI ---
# 将你的智能合约的完整应用程序二进制接口（ABI）粘贴在这里。
# ABI是合约的“说明书”，它告诉web3.py合约里有哪些函数以及如何调用它们。
# 这样做可以避免在代码的多个地方重复定义ABI片段，便于统一管理。
FULL_CONTRACT_ABI = [
    # --- Read-only functions (只读函数，不消耗Gas，不改变链上状态) ---
    {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[],"name":"totalSupply","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"stateMutability":"view","type":"function"},
    
    # --- Transaction functions (交易函数，会消耗Gas，改变链上状态) ---
    {"constant":False,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},
    {"constant":False,"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"constant":False,"inputs":[{"name":"amount","type":"uint256"}],"name":"burn","outputs":[],"stateMutability":"nonpayable","type":"function"}
]


class EthereumService:
    """封装所有与以太坊和智能合约交互的核心服务层"""

    def __init__(self, rpc_url: str, contract_address: str, request_timeout: int = 30):
        """
        服务初始化。
        :param rpc_url: 以太坊RPC节点的URL。
        :param contract_address: 智能合约的地址。
        :param request_timeout: 连接节点的超时时间（秒）。
        """
        if not rpc_url or not contract_address:
            raise ValueError("RPC URL 和合约地址不能为空")
            
        # 1. 初始化Web3实例，用于与以太坊网络通信
        self.w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': request_timeout}))
        
        # 2. 注入PoA中间件。对于使用PoA共识的链（如BSC, Polygon, Rinkeby测试网等）这是必需的。
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # 3. 检查是否成功连接到节点
        if not self.w3.is_connected():
            raise ConnectionError(f"无法连接到以太坊节点: {rpc_url}")
            
        # 4. 将地址转换为校验和格式，并创建合约实例
        self.contract_address = self.w3.to_checksum_address(contract_address)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=FULL_CONTRACT_ABI)

    def wait_for_transaction_receipt(self, tx_hash: str, timeout: int = 120):
        """
        等待一个交易被矿工打包，并返回其回执。这是确保交易成功的关键步骤。
        :param tx_hash: 交易的哈希值。
        :param timeout: 等待的超时时间（秒）。
        :return: 交易回执对象。
        """
        try:
            # web3.py内置的等待函数
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            # 检查回执中的 'status' 字段。 1 表示成功， 0 表示失败（交易被执行但最终被回滚）。
            if receipt['status'] == 0:
                raise TransactionFailedError(f"交易在链上执行失败 (status 0). Tx: {tx_hash}")
            return receipt
        except TransactionNotFound:
            raise TransactionFailedError(f"交易在 {timeout} 秒后仍未在链上找到. Tx: {tx_hash}")
        except Exception as e:
            raise TransactionFailedError(f"等待交易回执时发生未知错误: {e}. Tx: {tx_hash}")

    # --- 账户操作 ---
    @staticmethod
    def create_account() -> dict:
        """创建一个新的以太坊账户（公私钥对）。这是一个离线操作，不与网络交互。"""
        account = Account.create()
        return {'address': account.address, 'private_key': account.key.hex()}

    # --- ETH原生代币操作 ---
    def get_eth_balance(self, address: str) -> float:
        """查询指定地址的ETH余额。"""
        checksum_address = self.w3.to_checksum_address(address)
        balance_wei = self.w3.eth.get_balance(checksum_address)
        # 将余额从最小单位 Wei 转换为 Ether
        return float(self.w3.from_wei(balance_wei, 'ether'))

    def transfer_eth(self, from_private_key: str, to_address: str, amount_eth: float, wait_for_receipt: bool = True) -> str:
        """
        发送ETH原生代币。
        :param from_private_key: 发送方的私钥。
        :param to_address: 接收方的地址。
        :param amount_eth: 发送的ETH数量。
        :param wait_for_receipt: 是否等待交易被确认。对于关键操作（如支付Gas）应设为True。
        :return: 交易哈希。
        """
        from_account = Account.from_key(from_private_key)
        
        # 构造ETH转账交易对象
        tx = {
            'from': from_account.address,
            'to': self.w3.to_checksum_address(to_address),
            'value': self.w3.to_wei(amount_eth, 'ether'), # 将ETH数量转换为Wei
            'nonce': self.w3.eth.get_transaction_count(from_account.address), # 防止交易重放攻击的计数器
            'gas': 21000,  # ETH标准转账的Gas Limit是固定的21000
            'gasPrice': self.w3.eth.gas_price, # 从节点获取当前网络推荐的Gas价格
            'chainId': self.w3.eth.chain_id # 链ID，防止在不同链上重放交易
        }
        
        # 签名交易
        signed_tx = self.w3.eth.account.sign_transaction(tx, from_private_key)
        # 发送已签名的交易到网络
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction).hex() # <-- 关键修正点：使用 v6 语法的 rawTransaction
        
        if wait_for_receipt:
            self.wait_for_transaction_receipt(tx_hash)
            
        return tx_hash

    # --- 智能合约代币操作 ---
    def get_token_balance(self, address: str) -> int:
        """查询指定地址的合约代币余额。"""
        try:
            balance = self.contract.functions.balanceOf(self.w3.to_checksum_address(address)).call()
            # 假设代币没有小数，直接返回整数。如果有小数，需要根据`decimals`进行换算。
            return int(balance)
        except Exception as e:
            raise EthereumServiceError(f"查询代币余额失败: {e}")

    def get_token_info(self) -> dict:
        """获取代币的基本信息（名称、符号、总供应量）。"""
        try:
            name = self.contract.functions.name().call()
            symbol = self.contract.functions.symbol().call()
            total_supply = self.contract.functions.totalSupply().call()
            return {
                'name': name,
                'symbol': symbol,
                'total_supply': int(total_supply)
            }
        except Exception as e:
            raise EthereumServiceError(f"获取代币信息失败: {e}")

    def _execute_contract_transaction(self, function_call, private_key: str, wait_for_receipt: bool) -> str:
        """
        一个通用的内部辅助函数，用于估算Gas、构建、签名并发送所有合约交易。
        :param function_call: 一个已经构建好的合约函数调用对象 (e.g., self.contract.functions.transfer(...))
        :param private_key: 执行交易的账户私钥。
        :param wait_for_receipt: 是否等待交易确认。
        :return: 交易哈希。
        """
        account = Account.from_key(private_key)
        
        # 1. 准备通用的交易参数
        tx_params = {
            'from': account.address,
            'nonce': self.w3.eth.get_transaction_count(account.address),
            'gasPrice': self.w3.eth.gas_price, # 使用网络推荐的Gas价格
            'chainId': self.w3.eth.chain_id
        }
        
        # 2. 预估执行该函数调用所需的Gas Limit
        gas_estimate = function_call.estimate_gas(tx_params)
        
        # 3. 在预估值基础上增加20%作为安全缓冲。
        #    这是为了防止因交易打包前区块链状态的微小变化，导致实际Gas消耗略高于预估值而造成交易失败。
        #    Gas Limit只是上限，未用完的Gas会自动退回，所以这不会让你多花钱，但能极大提高交易成功率。
        tx_params['gas'] = int(gas_estimate * 1.2)

        # 4. 构建最终的交易对象
        transaction = function_call.build_transaction(tx_params)
        
        # 5. 签名并发送交易
        signed_tx = self.w3.eth.account.sign_transaction(transaction, private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction).hex() # <-- 关键修正点：使用 v6 语法的 rawTransaction

        # 6. (可选) 等待交易确认
        if wait_for_receipt:
            self.wait_for_transaction_receipt(tx_hash)
            
        return tx_hash

    def transfer_token(self, from_private_key: str, to_address: str, amount: int, wait_for_receipt: bool = True) -> str:
        """转账合约代币。"""
        from_account = Account.from_key(from_private_key)
        
        # 在发送交易前，先在本地快速检查余额，避免不必要的Gas消耗
        balance = self.get_token_balance(from_account.address)
        if balance < amount:
            raise InsufficientFundsError(f"代币余额不足。当前: {balance}, 需要: {amount}")

        # 构建合约的 transfer 函数调用
        transfer_function = self.contract.functions.transfer(
            self.w3.to_checksum_address(to_address), amount
        )
        
        # 使用通用函数执行交易
        return self._execute_contract_transaction(transfer_function, from_private_key, wait_for_receipt)

    def mint_token(self, owner_private_key: str, to_address: str, amount: int, wait_for_receipt: bool = True) -> str:
        """增发代币 (通常只有合约所有者可以调用)。"""
        # 构建合约的 mint 函数调用
        mint_function = self.contract.functions.mint(
            self.w3.to_checksum_address(to_address), amount
        )
        
        # 使用通用函数执行交易
        return self._execute_contract_transaction(mint_function, owner_private_key, wait_for_receipt)

    def burn_token(self, from_private_key: str, amount: int, wait_for_receipt: bool = True) -> str:
        """从调用者账户中销毁指定数量的代币。"""
        from_account = Account.from_key(from_private_key)
        
        # 同样，在发送交易前先检查余额，防止浪费Gas
        balance = self.get_token_balance(from_account.address)
        if balance < amount:
            raise InsufficientFundsError(f"代币余额不足以销毁。当前: {balance}, 尝试销毁: {amount}")

        # 构建合约的 burn 函数调用
        burn_function = self.contract.functions.burn(amount)
        
        # 使用我们通用的交易执行函数来处理后续所有步骤
        return self._execute_contract_transaction(burn_function, from_private_key, wait_for_receipt)
