# db.py
import datetime
from sqlalchemy import create_engine, Column, BigInteger, String, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base

# 声明一个所有数据模型都会继承的基类
Base = declarative_base()

class Wallet(Base):
    """
    定义 'wallets' 表的结构，映射到 Python 的 Wallet 类。
    这被称为 ORM (Object-Relational Mapping)。
    """
    __tablename__ = 'wallets'
    
    # 字段定义
    qq_id = Column(BigInteger, primary_key=True, comment="用户的QQ号，作为主键")
    eth_address = Column(String, unique=True, nullable=False, comment="绑定的以太坊地址")
    
    # 警告：在生产环境中，强烈建议对私钥进行加密存储，而非明文。
    # 这里为了简化，我们暂时使用明文。
    eth_private_key = Column(String, unique=True, nullable=False, comment="绑定的以太坊私钥")
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow, comment="账户创建时间")
    last_check_in = Column(DateTime, nullable=True, comment="用户上一次签到的时间")

class DatabaseManager:
    """
    一个辅助类，用于管理数据库连接和会话。
    这使得在 main.py 中的调用更简洁。
    """
    def __init__(self, db_url: str):
        # 根据配置文件中的连接字符串创建数据库引擎
        self.engine = create_engine(db_url)
        # 让 SQLAlchemy 根据我们的模型定义，自动创建表（如果表不存在）
        Base.metadata.create_all(self.engine)
        # 创建一个会话工厂，用于后续的数据库操作
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        """获取一个新的数据库会话"""
        return self.Session()
