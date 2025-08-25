"""
分析类提示词模板

包含技术分析、基本面分析、情绪分析等专业提示词
"""


class AnalysisPrompts:
    """分析类提示词"""
    
    # 技术分析系统提示词
    TECHNICAL_ANALYSIS_SYSTEM = """你是一个资深的技术分析师，专精于加密货币市场的技术指标分析和图表解读。

技术分析方法：
1. 趋势分析：识别主要趋势方向和强度
2. 支撑阻力：确定关键价格位
3. 指标分析：RSI、MACD、布林带等指标解读
4. 形态识别：头肩顶、双底、三角形等经典形态
5. 成交量分析：量价关系和成交量指标

分析原则：
- 多时间框架分析
- 多指标相互验证
- 结合成交量确认
- 考虑市场结构和流动性
- 提供概率性判断

输出要求：
- 明确的趋势判断
- 具体的价格目标
- 详细的风险控制建议
- 时间周期预测"""
    
    # 基本面分析系统提示词
    FUNDAMENTAL_ANALYSIS_SYSTEM = """你是一个专业的加密货币基本面分析师，关注项目价值和市场驱动因素。

分析维度：
1. 项目基本面：技术创新、团队背景、发展路线图
2. 市场数据：市值、流通量、持币分布
3. 生态发展：DApp数量、活跃用户、交易量
4. 宏观因素：监管政策、机构采用、市场情绪
5. 竞争分析：同类项目对比、优势劣势

评估标准：
- 技术先进性和实用性
- 团队执行能力
- 社区活跃度
- 合作伙伴质量
- 长期发展潜力

输出格式：
- 项目评级（A+到D-）
- 价值分析报告
- 投资风险评估
- 长期价格预期"""
    
    # 市场情绪分析
    SENTIMENT_ANALYSIS_PROMPT = """分析当前加密货币市场情绪：

数据来源：
- 社交媒体热度
- 新闻舆情分析
- 大户资金流向
- 期权PCR比率
- 恐慌贪婪指数

情绪指标：
{sentiment_data}

请分析：
1. 当前市场整体情绪
2. 主要驱动因素
3. 情绪转换信号
4. 交易建议

输出情绪评级：极度恐慌 | 恐慌 | 中性 | 贪婪 | 极度贪婪"""
    
    # 链上数据分析
    ONCHAIN_ANALYSIS_PROMPT = """分析以下链上数据：

网络活动：
- 活跃地址数量：{active_addresses}
- 交易数量：{transaction_count}
- 网络费用：{network_fees}

资金流动：
- 交易所流入/流出：{exchange_flows}
- 大户转账：{whale_transactions}
- 新地址增长：{new_addresses}

持币分布：
- 长期持有者比例：{long_term_holders}
- 交易所余额：{exchange_balance}
- 巨鲸持币量：{whale_holdings}

请基于链上数据分析：
1. 网络健康状况
2. 投资者行为模式
3. 价格影响因素
4. 未来走势预测"""
    
    # DeFi协议分析
    DEFI_ANALYSIS_PROMPT = """分析DeFi协议表现：

协议名称：{protocol_name}
协议类型：{protocol_type}

关键指标：
- TVL（总锁仓价值）：${tvl:,.2f}
- 24h交易量：${volume_24h:,.2f}
- 用户数量：{user_count:,}
- 代币价格：${token_price:.4f}

收益数据：
- APY：{apy:.2f}%
- 手续费收入：${fee_revenue:,.2f}
- 代币奖励：{token_rewards}

风险评估：
- 智能合约风险：{contract_risk}
- 流动性风险：{liquidity_risk}
- 治理风险：{governance_risk}

请提供：
1. 协议价值评估
2. 收益风险分析
3. 参与建议
4. 风险控制措施"""
    
    # NFT市场分析
    NFT_ANALYSIS_PROMPT = """分析NFT项目：

项目信息：
- 项目名称：{project_name}
- 发行数量：{total_supply}
- 地板价：{floor_price} ETH
- 市值：{market_cap} ETH

交易数据：
- 24h交易量：{volume_24h} ETH
- 持有者数量：{holder_count}
- 交易次数：{trade_count}
- 平均价格：{average_price} ETH

稀有度分析：
- 稀有特征：{rare_traits}
- 稀有度分布：{rarity_distribution}

社区数据：
- Discord成员：{discord_members}
- Twitter粉丝：{twitter_followers}
- 社区活跃度：{community_engagement}

请分析：
1. 项目价值和潜力
2. 市场表现评估
3. 投资风险等级
4. 交易策略建议"""
    
    @classmethod
    def format_sentiment_analysis(cls, sentiment_data: dict) -> str:
        """格式化情绪分析提示词"""
        return cls.SENTIMENT_ANALYSIS_PROMPT.format(
            sentiment_data=str(sentiment_data)
        )
    
    @classmethod
    def format_onchain_analysis(
        cls,
        active_addresses: int,
        transaction_count: int,
        network_fees: float,
        exchange_flows: dict,
        whale_transactions: int,
        new_addresses: int,
        long_term_holders: float,
        exchange_balance: float,
        whale_holdings: float
    ) -> str:
        """格式化链上数据分析提示词"""
        return cls.ONCHAIN_ANALYSIS_PROMPT.format(
            active_addresses=active_addresses,
            transaction_count=transaction_count,
            network_fees=network_fees,
            exchange_flows=exchange_flows,
            whale_transactions=whale_transactions,
            new_addresses=new_addresses,
            long_term_holders=long_term_holders,
            exchange_balance=exchange_balance,
            whale_holdings=whale_holdings
        )