# main.py
import datetime
import json
import random
from typing import Optional

# --- AstrBot Core Imports ---
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.api.event.filter import PermissionType
from astrbot.core.message.components import At

# --- 自定义模块导入 ---
# 根据你的文件名 (eth.py, db.py) 进行导入
from .eth import EthereumService, ConnectionError, InsufficientFundsError, TransactionFailedError
from .db import DatabaseManager, Wallet

# --- 全局常量 ---
HELP_MESSAGE = """
===============
💎 以太坊QQ钱包 💎
===============
/帮助 - 显示此帮助菜单
/注册 (或 /开户) - 创建你的链上钱包
/余额 - 查询你的代币和ETH余额
/我的账户 - 显示你的钱包地址
/货币 - 查看代币名称、符号和总供应量
/转账 <数量> @某人 - 给QQ好友转账
/提现 <数量> <你的外部地址> - 将代币提到你自己的钱包
/签到 - 每日签到领取代币
/排行榜 - 查看代币持有者排行
"""

@register("eth_wallet", "GuJi08233", "基于以太坊的QQ代币钱包", "1.0.1", "https://github.com/GuJi08233/astrbot_plugin_token_wallet")
class EthWalletPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        """
        插件初始化函数，在插件加载时执行。
        负责读取配置、初始化数据库和以太坊服务。
        """
        super().__init__(context)
        self.config = config
        self.eth_service = None
        self.db_manager = None

        try:
            # 1. 初始化以太坊服务
            self.eth_service = EthereumService(
                rpc_url=config.get("rpc_node_url"),
                contract_address=config.get("contract_address")
            )
            # 2. 初始化数据库管理器
            self.db_manager = DatabaseManager(db_url=config.get("database_url"))
            logger.info("✅ 以太坊钱包插件加载成功，已连接节点和数据库。")

        except ConnectionError as e:
            logger.critical(f"❌ 插件加载失败: 无法连接到以太坊节点! 请检查'rpc_node_url'配置。错误: {e}")
        except Exception as e:
            logger.error(f"❌ 插件加载失败，请检查配置或环境。错误: {e}")

    # --- 辅助方法 ---

    def _get_check_in_reward(self) -> int:
        """根据配置解析并返回一个带权重随机的签到奖励数量"""
        rewards_config_str = self.config.get("daily_check_in_reward")
        try:
            rewards_table = json.loads(rewards_config_str)
            population = [item['amount'] for item in rewards_table]
            weights = [item['weight'] for item in rewards_table]
            return random.choices(population, weights=weights, k=1)[0]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"解析签到奖励配置失败: {e}. 将返回默认值 1。")
            return 1

    async def _get_at_qq(self, event: AstrMessageEvent) -> Optional[str]:
        """从消息链中解析出第一个被@的用户QQ号。"""
        for seg in event.get_messages():
            if isinstance(seg, At):
                return str(seg.qq)
        return None

    # --- 用户命令 ---

    @filter.command("帮助")
    async def help_command(self, event: AstrMessageEvent):
        yield event.plain_result(HELP_MESSAGE)

    @filter.command("注册", alias={"开户"})
    async def register_command(self, event: AstrMessageEvent):
        if not self.eth_service or not self.db_manager:
            yield event.plain_result("❌ 插件初始化失败，请联系管理员检查后台日志。")
            return

        qq_id = int(event.get_sender_id())
        session = self.db_manager.get_session()
        
        try:
            existing_wallet = session.query(Wallet).filter_by(qq_id=qq_id).first()
            if existing_wallet:
                yield event.plain_result(f"🤔 你已经注册过了，无需重复注册。\n你的地址是: {existing_wallet.eth_address}")
                return
            
            yield event.plain_result("⌛ 正在为你创建链上账户并转入初始Gas费，请稍候...")
            
            new_account = self.eth_service.create_account()
            
            owner_pk = self.config.get("owner_private_key")
            gas_fee = self.config.get("registration_gas_fee_eth", 0.1)
            if owner_pk and gas_fee > 0:
                tx_hash = self.eth_service.transfer_eth(owner_pk, new_account['address'], gas_fee)
                logger.info(f"为新用户 {qq_id} 转账 {gas_fee} ETH 成功, Tx: {tx_hash}")
            
            new_wallet = Wallet(
                qq_id=qq_id,
                eth_address=new_account['address'],
                eth_private_key=new_account['private_key']
            )
            session.add(new_wallet)
            session.commit()

            yield event.plain_result(f"🎉 注册成功！\n你的专属钱包地址是:\n{new_account['address']}\n已为你转入 {gas_fee} ETH 作为初始Gas费。")

        except TransactionFailedError as e:
            logger.error(f"用户 {qq_id} 注册失败，Gas费转账失败: {e}")
            session.rollback()
            yield event.plain_result(f"❌ 注册失败：初始Gas费转账失败，请联系管理员。")
        except Exception as e:
            logger.error(f"用户 {qq_id} 注册失败: {e}")
            session.rollback()
            yield event.plain_result(f"❌ 注册失败，发生内部错误，请联系管理员。")
        finally:
            session.close()

    @filter.command("余额")
    async def balance_command(self, event: AstrMessageEvent):
        qq_id = int(event.get_sender_id())
        session = self.db_manager.get_session()
        wallet = session.query(Wallet).filter_by(qq_id=qq_id).first()
        session.close()

        if not wallet:
            yield event.plain_result("你还没有注册，请先发送 /注册")
            return
            
        try:
            yield event.plain_result("⌛ 正在查询链上余额，请稍候...")
            token_balance = self.eth_service.get_token_balance(wallet.eth_address)
            eth_balance = self.eth_service.get_eth_balance(wallet.eth_address)
            yield event.plain_result(f"查询成功！\n💰 代币余额: {token_balance}\n⛽ Gas (ETH): {eth_balance:.6f}")
        except Exception as e:
            logger.error(f"查询余额失败 for {qq_id}: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试。")

    @filter.command("我的账户")
    async def my_account_command(self, event: AstrMessageEvent):
        qq_id = int(event.get_sender_id())
        session = self.db_manager.get_session()
        wallet = session.query(Wallet).filter_by(qq_id=qq_id).first()
        session.close()

        if not wallet:
            yield event.plain_result("你还没有注册，请先发送 /注册")
            return
        
        yield event.plain_result(f"你的钱包地址是:\n{wallet.eth_address}")

    @filter.command("货币")
    async def token_info_command(self, event: AstrMessageEvent):
        if not self.eth_service:
            yield event.plain_result("❌ 插件初始化失败，请联系管理员检查后台日志。")
            return
            
        try:
            yield event.plain_result("⌛ 正在查询代币信息，请稍候...")
            token_info = self.eth_service.get_token_info()
            yield event.plain_result(
                f"代币信息查询成功！\n"
                f"🏷️ 名称: {token_info['name']}\n"
                f"🔤 符号: {token_info['symbol']}\n"
                f"💎 总供应量: {token_info['total_supply']}"
            )
        except Exception as e:
            logger.error(f"查询代币信息失败: {e}")
            yield event.plain_result("❌ 查询失败，请稍后再试。")

    @filter.command("转账")
    async def transfer_command(self, event: AstrMessageEvent, amount: int):
        target_qq_id = await self._get_at_qq(event)
        if not target_qq_id:
            yield event.plain_result("❌ 请@一位要转账的用户。格式：/转账 数量 @用户")
            return
            
        if amount <= 0:
            yield event.plain_result("❌ 转账数量必须大于0！")
            return

        sender_qq_id = int(event.get_sender_id())
        if sender_qq_id == int(target_qq_id):
            yield event.plain_result("🤔 不能给自己转账哦。")
            return

        yield event.plain_result(f"⌛ 正在准备向用户 {target_qq_id} 转账 {amount} 代币，请稍候...")
        
        session = self.db_manager.get_session()
        try:
            sender_wallet = session.query(Wallet).filter_by(qq_id=sender_qq_id).first()
            receiver_wallet = session.query(Wallet).filter_by(qq_id=int(target_qq_id)).first()
            
            if not sender_wallet:
                yield event.plain_result("❌ 错误：您还没有注册钱包，请先使用 /注册。")
                return
            if not receiver_wallet:
                yield event.plain_result(f"❌ 错误：对方用户 ({target_qq_id}) 还没有注册钱包。")
                return

            tx_hash = self.eth_service.transfer_token(sender_wallet.eth_private_key, receiver_wallet.eth_address, amount)
            yield event.plain_result(f"✅ 转账成功！\n您已向 {target_qq_id} 转账 {amount}。\n交易哈希: `{tx_hash}`")
        except InsufficientFundsError:
            yield event.plain_result(f"❌ 转账失败：您的代币余额不足！")
        except TransactionFailedError as e:
            logger.error(f"转账失败 from {sender_qq_id} to {target_qq_id}: {e}")
            yield event.plain_result(f"❌ 转账失败：交易在链上执行失败，资金已退回。")
        except Exception as e:
            logger.error(f"转账时发生未知错误: {e}")
            yield event.plain_result(f"❌ 转账失败，发生内部错误。")
        finally:
            session.close()

    @filter.command("提现")
    async def withdraw_command(self, event: AstrMessageEvent, amount: int, address: str):
        if not self.eth_service.w3.is_address(address):
            yield event.plain_result(f"❌ `{address}` 不是一个有效的以太坊地址。")
            return
        
        if amount <= 0:
            yield event.plain_result("❌ 提现数量必须大于0！")
            return
        
        qq_id = int(event.get_sender_id())
        session = self.db_manager.get_session()
        try:
            wallet = session.query(Wallet).filter_by(qq_id=qq_id).first()
            if not wallet:
                yield event.plain_result("❌ 错误：您还没有注册钱包，请先使用 /注册。")
                return
            
            yield event.plain_result(f"⌛ 正在向地址 {address} 提现 {amount} 代币，请稍候...")
            tx_hash = self.eth_service.transfer_token(wallet.eth_private_key, address, amount)
            yield event.plain_result(f"✅ 提现成功！\n交易哈希: `{tx_hash}`")
        except InsufficientFundsError:
            yield event.plain_result(f"❌ 提现失败：您的代币余额不足！")
        except Exception as e:
            logger.error(f"提现失败 for {qq_id}: {e}")
            yield event.plain_result(f"❌ 提现失败，发生内部错误。")
        finally:
            session.close()

    @filter.command("签到")
    async def check_in_command(self, event: AstrMessageEvent):
        qq_id = int(event.get_sender_id())
        session = self.db_manager.get_session()
        try:
            wallet = session.query(Wallet).filter_by(qq_id=qq_id).first()
            if not wallet:
                yield event.plain_result("你还没有注册，请先发送 /注册")
                return
            
            today = datetime.datetime.utcnow().date()
            if wallet.last_check_in and wallet.last_check_in.date() == today:
                yield event.plain_result("🤔 你今天已经签过到了，明天再来吧！")
                return
            
            reward_amount = self._get_check_in_reward()
            yield event.plain_result(f"⌛ 正在为你签到并发送奖励，请稍候...")
            
            owner_pk = self.config.get("owner_private_key")
            if not owner_pk:
                yield event.plain_result("❌ 管理员未配置奖励私钥，无法发放奖励。")
                return

            tx_hash = self.eth_service.mint_token(owner_pk, wallet.eth_address, reward_amount)
            wallet.last_check_in = datetime.datetime.utcnow()
            session.commit()
            
            yield event.plain_result(f"🎉 签到成功！你获得了 {reward_amount} 代币奖励！")
        except Exception as e:
            session.rollback()
            logger.error(f"用户 {qq_id} 签到失败: {e}")
            yield event.plain_result(f"❌ 签到失败，发生内部错误。")
        finally:
            session.close()

    @filter.command("排行榜")
    async def rank_command(self, event: AstrMessageEvent):
        yield event.plain_result("⌛ 正在查询全服余额并生成排行榜，这可能需要一点时间...")
        session = self.db_manager.get_session()
        try:
            wallets = session.query(Wallet).all()
            if not wallets:
                yield event.plain_result("目前还没有用户注册。")
                return
                
            balances = []
            for wallet in wallets:
                try:
                    balance = self.eth_service.get_token_balance(wallet.eth_address)
                    balances.append((wallet.qq_id, balance))
                except Exception:
                    # 查询失败的用户暂时不计入排行
                    continue
            
            # 按余额降序排序
            sorted_balances = sorted(balances, key=lambda item: item[1], reverse=True)
            
            rank_text = "🏆 代币富豪榜 🏆\n\n"
            for i, (qq_id, balance) in enumerate(sorted_balances[:10]): # 取前10名
                rank_text += f"第 {i+1} 名: {qq_id} - 💰 {balance}\n"
            
            yield event.plain_result(rank_text)

        except Exception as e:
            logger.error(f"生成排行榜失败: {e}")
            yield event.plain_result("❌ 生成排行榜时发生错误。")
        finally:
            session.close()

    # --- 管理员命令 ---

    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("增发")
    async def mint_command(self, event: AstrMessageEvent, amount: int, address: str):
        if not self.eth_service.w3.is_address(address):
            yield event.plain_result(f"❌ `{address}` 不是一个有效的以太坊地址。")
            return
            
        if amount <= 0:
            yield event.plain_result("❌ 增发数量必须大于0！")
            return
            
        try:
            owner_pk = self.config.get("owner_private_key")
            if not owner_pk:
                yield event.plain_result("❌ 管理员私钥未在配置中设置！")
                return
                
            yield event.plain_result(f"⌛ 正在向 {address} 增发 {amount} 代币...")
            tx_hash = self.eth_service.mint_token(owner_pk, address, amount)
            yield event.plain_result(f"✅ 增发成功！\n交易哈希: `{tx_hash}`")
        except Exception as e:
            logger.error(f"增发失败: {e}")
            yield event.plain_result(f"❌ 增发失败，请检查后台日志。")
