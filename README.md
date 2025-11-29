# AstrBot 以太坊代币钱包插件

一个基于以太坊智能合约的QQ代币钱包插件，为AstrBot提供完整的链上钱包功能。

## ✨ 功能特性

### 用户功能
- **钱包注册**: 自动创建以太坊钱包地址并绑定QQ号
- **余额查询**: 实时查询代币和ETH余额
- **转账功能**: 支持QQ用户之间的代币转账
- **提现功能**: 可将代币提现到外部以太坊地址
- **每日签到**: 支持带权重的随机签到奖励系统
- **排行榜**: 查看全服代币持有者排行

### 管理员功能
- **代币增发**: 向指定地址增发代币
- **新用户奖励**: 可配置为新注册用户赠送ETH作为Gas费

## 📋 安装要求

- AstrBot v4.5.0+
- Python 3.8+
- PostgreSQL 数据库
- 以太坊节点访问权限（主网/测试网）

## 🔧 安装步骤

1. 在AstrBot插件目录中克隆本仓库：
```bash
git clone https://github.com/GuJi08233/astrbot_plugin_token_wallet
```

2. 安装Python依赖：
```bash
pip install -r requirements.txt
```

3. 在AstrBot管理面板中配置插件参数（详见配置说明）

4. 重启AstrBot服务

## ⚙️ 配置说明

在AstrBot管理面板中配置以下参数：

| 配置项 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `rpc_node_url` | string | 是 | 以太坊RPC节点地址（如Infura、Alchemy或自建节点） |
| `contract_address` | string | 是 | 智能合约地址（需支持ERC20标准接口） |
| `owner_private_key` | string | 是 | 合约所有者私钥，用于Gas费转账和代币增发 |
| `database_url` | string | 是 | PostgreSQL连接地址，格式：`postgresql://user:password@host:port/dbname` |
| `registration_gas_fee_eth` | float | 否 | 新用户注册时赠送的ETH数量，默认0.1 ETH |
| `daily_check_in_reward` | string | 否 | 签到奖励配置（JSON格式），支持权重随机 |

### 签到奖励配置示例

```json
[
  {"amount": 1, "weight": 900},
  {"amount": 2, "weight": 99},
  {"amount": 3, "weight": 1}
]
```

**权重说明**：系统会根据权重随机选择奖励，例如900:99:1分别对应90%、9.9%、0.1%的概率。

## 📝 使用命令

### 基础命令
```
/帮助 - 显示帮助菜单
/注册 (或 /开户) - 创建你的链上钱包
/余额 - 查询代币和ETH余额
/我的账户 - 显示钱包地址
```

### 交易命令
```
/转账 <数量> @某人 - 给QQ好友转账代币
/提现 <数量> <外部地址> - 提现到外部钱包
```

### 互动命令
```
/签到 - 每日签到领取代币奖励
/排行榜 - 查看代币持有者排行
```

### 管理员命令
```
/增发 <数量> <地址> - 向指定地址增发代币
```

## 🔒 安全说明

⚠️ **重要安全提示**：

1. **私钥管理**: `owner_private_key`是最高权限密钥，请妥善保管，切勿泄露
2. **数据库安全**: 用户私钥以明文形式存储在数据库中，建议：
   - 使用独立的数据库实例
   - 限制数据库访问权限
   - 定期备份数据库
   - 生产环境建议实现私钥加密存储
3. **Gas费控制**: 合理设置`registration_gas_fee_eth`，避免资金耗尽
4. **合约权限**: 确保智能合约的`mint`函数已正确设置访问控制

## 🏗️ 技术架构

### 项目结构
```
astrbot_plugin_token_wallet/
├── main.py              # 插件主逻辑，处理用户命令
├── eth.py               # 以太坊服务层，封装链上交互
├── db.py                # 数据库管理，使用SQLAlchemy ORM
├── metadata.yaml        # 插件元数据
├── _conf_schema.json    # 配置项定义
├── requirements.txt     # Python依赖
└── README.md           # 本文档
```

### 依赖说明
- `web3==6.15.1`: 以太坊交互库
- `sqlalchemy`: 数据库ORM框架
- `psycopg2-binary`: PostgreSQL驱动

### 智能合约要求

本插件需要兼容以下接口的智能合约：

```solidity
// 只读函数
function name() public view returns (string)
function symbol() public view returns (string)
function decimals() public view returns (uint8)
function totalSupply() public view returns (uint256)
function balanceOf(address _owner) public view returns (uint256 balance)

// 交易函数
function transfer(address _to, uint256 _value) public returns (bool)
function mint(address to, uint256 amount) public
function burn(uint256 amount) public
```

## 🐛 故障排查

### 常见问题

**1. 插件加载失败**
- 检查RPC节点URL是否正确且可访问
- 确认合约地址格式正确（0x开头）
- 查看AstrBot日志获取详细错误信息

**2. 转账失败**
- 确认发送方余额充足
- 检查接收方地址是否有效
- 查看ETH余额是否足够支付Gas费

**3. 数据库连接失败**
- 确认PostgreSQL服务正在运行
- 检查连接字符串格式是否正确
- 验证数据库用户权限

**4. 签到奖励发放失败**
- 确认`owner_private_key`已配置
- 检查合约所有者是否有足够的代币余额
- 验证合约的`mint`函数权限设置

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🔗 相关链接

- [AstrBot 官方文档](https://astrbot.app/)
- [Web3.py 文档](https://web3py.readthedocs.io/)
- [SQLAlchemy 文档](https://www.sqlalchemy.org/)

## 👨‍💻 作者

**GuJi08233**

- GitHub: [@GuJi08233](https://github.com/GuJi08233)
- 项目地址: [https://github.com/GuJi08233/astrbot_plugin_token_wallet](https://github.com/GuJi08233/astrbot_plugin_token_wallet)

---

<div align="center">
如果这个项目对你有帮助，请给个 ⭐️ Star 支持一下！
</div>
