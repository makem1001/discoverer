"""
发现者（Discoverer）— 69个信号 + 8个持有规则 + 13个经典策略定义

信号分类：
  均线类(MA) — 12个
  MACD类 — 6个
  KDJ类 — 6个
  RSI类 — 6个
  布林带(BOLL) — 5个
  成交量(Volume) — 8个
  形态类(Pattern) — 10个
  趋势类(Trend) — 6个
  动量类(Momentum) — 6个
  波动率(Volatility) — 4个
"""

from models.schemas import Signal, HoldingRule, SignalCondition, Strategy

# ══════════════════════════════════════════════════════════════════
# 69个信号定义
# ══════════════════════════════════════════════════════════════════

ALL_SIGNALS: list[Signal] = [
    # ── 均线类 (MA) ── 12个 ──
    Signal(id="ma_golden_cross", name="均线金叉(5/20)", category="均线",
           description="5日均线上穿20日均线，短期趋势转多", params={"fast": 5, "slow": 20}),
    Signal(id="ma_death_cross", name="均线死叉(5/20)", category="均线",
           description="5日均线下穿20日均线，短期趋势转空", params={"fast": 5, "slow": 20}),
    Signal(id="ma_golden_cross_10_30", name="均线金叉(10/30)", category="均线",
           description="10日均线上穿30日均线，中期趋势转多", params={"fast": 10, "slow": 30}),
    Signal(id="ma_death_cross_10_30", name="均线死叉(10/30)", category="均线",
           description="10日均线下穿30日均线，中期趋势转空", params={"fast": 10, "slow": 30}),
    Signal(id="ma_golden_cross_20_60", name="均线金叉(20/60)", category="均线",
           description="20日均线上穿60日均线，长期趋势转多", params={"fast": 20, "slow": 60}),
    Signal(id="ma_death_cross_20_60", name="均线死叉(20/60)", category="均线",
           description="20日均线下穿60日均线，长期趋势转空", params={"fast": 20, "slow": 60}),
    Signal(id="price_above_ma5", name="收盘价站上MA5", category="均线",
           description="收盘价从下方上穿5日均线", params={"ma": 5}),
    Signal(id="price_below_ma5", name="收盘价跌破MA5", category="均线",
           description="收盘价从上方下穿5日均线", params={"ma": 5}),
    Signal(id="price_above_ma20", name="收盘价站上MA20", category="均线",
           description="收盘价从下方上穿20日均线", params={"ma": 20}),
    Signal(id="price_below_ma20", name="收盘价跌破MA20", category="均线",
           description="收盘价从上方下穿20日均线", params={"ma": 20}),
    Signal(id="ma_bullish_alignment", name="均线多头排列", category="均线",
           description="MA5 > MA10 > MA20 > MA60 同时满足", params={"mas": [5, 10, 20, 60]}),
    Signal(id="ma_bearish_alignment", name="均线空头排列", category="均线",
           description="MA5 < MA10 < MA20 < MA60 同时满足", params={"mas": [5, 10, 20, 60]}),

    # ── MACD类 ── 6个 ──
    Signal(id="macd_golden_cross", name="MACD金叉", category="MACD",
           description="DIF线上穿DEA线，经典买入信号", params={"fast": 12, "slow": 26, "signal": 9}),
    Signal(id="macd_death_cross", name="MACD死叉", category="MACD",
           description="DIF线下穿DEA线，经典卖出信号", params={"fast": 12, "slow": 26, "signal": 9}),
    Signal(id="macd_above_zero", name="MACD零轴上方", category="MACD",
           description="DIF和DEA均在零轴上方，多头市场", params={}),
    Signal(id="macd_below_zero", name="MACD零轴下方", category="MACD",
           description="DIF和DEA均在零轴下方，空头市场", params={}),
    Signal(id="macd_divergence_bullish", name="MACD底背离", category="MACD",
           description="股价新低但MACD未新低，看涨背离", params={}),
    Signal(id="macd_divergence_bearish", name="MACD顶背离", category="MACD",
           description="股价新高但MACD未新高，看跌背离", params={}),

    # ── KDJ类 ── 6个 ──
    Signal(id="kdj_golden_cross", name="KDJ金叉", category="KDJ",
           description="K线上穿D线，短线买入信号", params={"n": 9}),
    Signal(id="kdj_death_cross", name="KDJ死叉", category="KDJ",
           description="K线下穿D线，短线卖出信号", params={"n": 9}),
    Signal(id="kdj_oversold", name="KDJ超卖区", category="KDJ",
           description="K值和D值均低于20，处于超卖区", params={"threshold": 20}),
    Signal(id="kdj_overbought", name="KDJ超买区", category="KDJ",
           description="K值和D值均高于80，处于超买区", params={"threshold": 80}),
    Signal(id="kdj_j_oversold", name="KDJ的J值超卖", category="KDJ",
           description="J值低于0，极端超卖", params={}),
    Signal(id="kdj_j_overbought", name="KDJ的J值超买", category="KDJ",
           description="J值高于100，极端超买", params={}),

    # ── RSI类 ── 6个 ──
    Signal(id="rsi_oversold_6", name="RSI(6)超卖", category="RSI",
           description="6日RSI低于30，超卖反弹概率大", params={"period": 6, "threshold": 30}),
    Signal(id="rsi_overbought_6", name="RSI(6)超买", category="RSI",
           description="6日RSI高于70，超买回调概率大", params={"period": 6, "threshold": 70}),
    Signal(id="rsi_oversold_14", name="RSI(14)超卖", category="RSI",
           description="14日RSI低于30，中期超卖", params={"period": 14, "threshold": 30}),
    Signal(id="rsi_overbought_14", name="RSI(14)超买", category="RSI",
           description="14日RSI高于70，中期超买", params={"period": 14, "threshold": 70}),
    Signal(id="rsi_golden_cross", name="RSI金叉", category="RSI",
           description="短期RSI上穿长期RSI", params={"fast": 6, "slow": 14}),
    Signal(id="rsi_death_cross", name="RSI死叉", category="RSI",
           description="短期RSI下穿长期RSI", params={"fast": 6, "slow": 14}),

    # ── 布林带(BOLL) ── 5个 ──
    Signal(id="boll_lower_touch", name="触及布林下轨", category="布林带",
           description="收盘价触及或跌破布林带下轨，超卖反弹", params={"period": 20, "std": 2}),
    Signal(id="boll_upper_touch", name="触及布林上轨", category="布林带",
           description="收盘价触及或突破布林带上轨，超买回调", params={"period": 20, "std": 2}),
    Signal(id="boll_mid_break_up", name="突破布林中轨", category="布林带",
           description="收盘价从下方突破布林带中轨（20日线）", params={"period": 20}),
    Signal(id="boll_mid_break_down", name="跌破布林中轨", category="布林带",
           description="收盘价从上方跌破布林带中轨", params={"period": 20}),
    Signal(id="boll_squeeze", name="布林收窄", category="布林带",
           description="布林带宽度缩小到近期最低水平，预示变盘", params={"period": 20}),

    # ── 成交量(Volume) ── 8个 ──
    Signal(id="vol_breakout_1_5", name="放量1.5倍", category="成交量",
           description="当日成交量超过20日均量的1.5倍", params={"multiplier": 1.5, "ma_period": 20}),
    Signal(id="vol_breakout_2", name="放量2倍", category="成交量",
           description="当日成交量超过20日均量的2倍", params={"multiplier": 2.0, "ma_period": 20}),
    Signal(id="vol_breakout_3", name="放量3倍", category="成交量",
           description="当日成交量超过20日均量的3倍，天量", params={"multiplier": 3.0, "ma_period": 20}),
    Signal(id="vol_shrink_half", name="缩量一半", category="成交量",
           description="当日成交量低于20日均量的一半，地量", params={"multiplier": 0.5, "ma_period": 20}),
    Signal(id="vol_price_rise", name="价涨量增", category="成交量",
           description="收盘价上涨且成交量放大（>20日均量1.2倍）", params={}),
    Signal(id="vol_price_fall", name="价跌量增", category="成交量",
           description="收盘价下跌且成交量放大，恐慌出逃", params={}),
    Signal(id="vol_3day_increasing", name="连续3日放量", category="成交量",
           description="连续3天成交量逐日增加", params={"days": 3}),
    Signal(id="vol_5day_shrinking", name="连续5日缩量", category="成交量",
           description="连续5天成交量低于20日均量", params={"days": 5}),

    # ── 形态类(Pattern) ── 10个 ──
    Signal(id="hammer", name="锤子线", category="形态",
           description="下影线长度超过实体2倍且实体较小，看涨反转", params={}),
    Signal(id="shooting_star", name="射击之星", category="形态",
           description="上影线长度超过实体2倍且实体较小，看跌反转", params={}),
    Signal(id="engulfing_bullish", name="看涨吞没", category="形态",
           description="阳线实体完全包裹前一日阴线实体", params={}),
    Signal(id="engulfing_bearish", name="看跌吞没", category="形态",
           description="阴线实体完全包裹前一日阳线实体", params={}),
    Signal(id="three_white_soldiers", name="三白兵", category="形态",
           description="连续三根实体递增的阳线，强势上涨", params={}),
    Signal(id="three_black_crows", name="三乌鸦", category="形态",
           description="连续三根实体递增的阴线，强势下跌", params={}),
    Signal(id="doji", name="十字星", category="形态",
           description="开盘价≈收盘价，实体极小，变盘信号", params={}),
    Signal(id="breakout_20day_high", name="突破20日高点", category="形态",
           description="收盘价突破过去20个交易日的最高价", params={"period": 20}),
    Signal(id="breakdown_20day_low", name="跌破20日低点", category="形态",
           description="收盘价跌破过去20个交易日的最低价", params={"period": 20}),
    Signal(id="gap_up", name="向上跳空", category="形态",
           description="当日最低价高于前一日最高价，强势信号", params={}),

    # ── 趋势类(Trend) ── 6个 ──
    Signal(id="new_high_20", name="创20日新高", category="趋势",
           description="收盘价创过去20个交易日新高", params={"period": 20}),
    Signal(id="new_low_20", name="创20日新低", category="趋势",
           description="收盘价创过去20个交易日新低", params={"period": 20}),
    Signal(id="new_high_60", name="创60日新高", category="趋势",
           description="收盘价创过去60个交易日新高", params={"period": 60}),
    Signal(id="new_low_60", name="创60日新低", category="趋势",
           description="收盘价创过去60个交易日新低", params={"period": 60}),
    Signal(id="consecutive_up_3", name="连涨3天", category="趋势",
           description="连续3个交易日收盘价上涨", params={"days": 3}),
    Signal(id="consecutive_down_3", name="连跌3天", category="趋势",
           description="连续3个交易日收盘价下跌", params={"days": 3}),

    # ── 动量类(Momentum) ── 6个 ──
    Signal(id="momentum_5d_strong", name="5日动量强势", category="动量",
           description="5日涨跌幅超过5%", params={"period": 5, "threshold": 0.05}),
    Signal(id="momentum_5d_weak", name="5日动量弱势", category="动量",
           description="5日涨跌幅低于-5%", params={"period": 5, "threshold": -0.05}),
    Signal(id="momentum_20d_strong", name="20日动量强势", category="动量",
           description="20日涨跌幅超过10%", params={"period": 20, "threshold": 0.10}),
    Signal(id="momentum_20d_weak", name="20日动量弱势", category="动量",
           description="20日涨跌幅低于-10%", params={"period": 20, "threshold": -0.10}),
    Signal(id="volume_price_ratio", name="量比放大", category="动量",
           description="当日量比（成交量/5日均量）大于1.5", params={"threshold": 1.5}),
    Signal(id="turnover_rate_high", name="高换手率", category="动量",
           description="当日换手率超过10%（需换手率数据）", params={"threshold": 0.10}),

    # ── 波动率(Volatility) ── 4个 ──
    Signal(id="atr_high", name="ATR放大", category="波动率",
           description="14日ATR超过20日均值的1.5倍，波动加剧", params={"period": 14}),
    Signal(id="atr_low", name="ATR缩小", category="波动率",
           description="14日ATR低于20日均值的0.5倍，波动收窄", params={"period": 14}),
    Signal(id="volatility_breakout", name="波动率突破", category="波动率",
           description="20日历史波动率突破布林带上轨", params={"period": 20}),
    Signal(id="low_volatility", name="低波动率", category="波动率",
           description="20日历史波动率处于近一年最低25%分位", params={"period": 20}),
]

# ══════════════════════════════════════════════════════════════════
# 8个持有规则定义
# ══════════════════════════════════════════════════════════════════

ALL_HOLDING_RULES: list[HoldingRule] = [
    HoldingRule(id="hold_n_days", name="持有N天",
                description="买入后固定持有N个交易日，到期自动卖出",
                params={"days": 5}),
    HoldingRule(id="stop_loss", name="固定止损",
                description="亏损达到设定比例时立即止损卖出",
                params={"loss_pct": -0.05}),
    HoldingRule(id="stop_profit", name="固定止盈",
                description="盈利达到设定比例时立即止盈卖出",
                params={"profit_pct": 0.10}),
    HoldingRule(id="trailing_stop", name="移动止损",
                description="从最高点回撤超过设定比例时卖出",
                params={"trailing_pct": 0.05}),
    HoldingRule(id="next_signal_reverse", name="反向信号出场",
                description="出现与入场信号相反的交易信号时卖出",
                params={}),
    HoldingRule(id="ma_cross_exit", name="均线死叉出场",
                description="出现MA5/MA20死叉时卖出",
                params={"fast": 5, "slow": 20}),
    HoldingRule(id="hold_until_end", name="持有到期末",
                description="买入后一直持有到回测结束日期",
                params={}),
    HoldingRule(id="atr_trailing_stop", name="ATR移动止损",
                description="以N倍ATR作为移动止损距离",
                params={"atr_multiplier": 2.0, "atr_period": 14}),
]

# ══════════════════════════════════════════════════════════════════
# 13个经典策略定义
# ══════════════════════════════════════════════════════════════════

CLASSIC_STRATEGIES = [
    {
        "id": "macd_golden_death",
        "name": "MACD金叉死叉",
        "description": "DIF上穿DEA买入，DIF下穿DEA卖出",
        "entry_signal": "macd_golden_cross",
        "exit_signal": "macd_death_cross",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "ma_golden_death",
        "name": "均线金叉死叉(5/20)",
        "description": "MA5上穿MA20买入，MA5下穿MA20卖出",
        "entry_signal": "ma_golden_cross",
        "exit_signal": "ma_death_cross",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "ma_golden_death_10_30",
        "name": "均线金叉死叉(10/30)",
        "description": "MA10上穿MA30买入，MA10下穿MA30卖出",
        "entry_signal": "ma_golden_cross_10_30",
        "exit_signal": "ma_death_cross_10_30",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "ma_golden_death_20_60",
        "name": "均线金叉死叉(20/60)",
        "description": "MA20上穿MA60买入，MA20下穿MA60卖出",
        "entry_signal": "ma_golden_cross_20_60",
        "exit_signal": "ma_death_cross_20_60",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "rsi_oversold_overbought",
        "name": "RSI超卖超买(14)",
        "description": "RSI(14)低于30买入，高于70卖出",
        "entry_signal": "rsi_oversold_14",
        "exit_signal": "rsi_overbought_14",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "kdj_golden_death",
        "name": "KDJ金叉死叉",
        "description": "K线上穿D线买入，K线下穿D线卖出",
        "entry_signal": "kdj_golden_cross",
        "exit_signal": "kdj_death_cross",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "boll_lower_buy_upper_sell",
        "name": "布林带下轨买上轨卖",
        "description": "触及布林下轨买入，触及布林上轨卖出",
        "entry_signal": "boll_lower_touch",
        "exit_signal": "boll_upper_touch",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "vol_breakout_with_ma_golden",
        "name": "放量+均线金叉",
        "description": "成交量放大1.5倍且MA5/20金叉买入，均线死叉卖出",
        "entry_signal": "vol_breakout_1_5",
        "exit_signal": "ma_death_cross",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "ma_golden_hold_10d",
        "name": "均线金叉+持有10天",
        "description": "MA5/20金叉买入，持有10个交易日后卖出",
        "entry_signal": "ma_golden_cross",
        "exit_signal": None,
        "holding_rule": "hold_n_days",
    },
    {
        "id": "breakout_20d_high",
        "name": "突破20日高点+移动止损",
        "description": "收盘价突破20日高点买入，5%移动止损",
        "entry_signal": "breakout_20day_high",
        "exit_signal": None,
        "holding_rule": "trailing_stop",
    },
    {
        "id": "bullish_alignment_hold",
        "name": "多头排列买入持有",
        "description": "均线多头排列时买入，持有到期末",
        "entry_signal": "ma_bullish_alignment",
        "exit_signal": None,
        "holding_rule": "hold_until_end",
    },
    {
        "id": "macd_golden_vol_breakout",
        "name": "MACD金叉+放量确认",
        "description": "MACD金叉且成交量放大1.5倍买入，MACD死叉卖出",
        "entry_signal": "macd_golden_cross",
        "exit_signal": "macd_death_cross",
        "holding_rule": "next_signal_reverse",
    },
    {
        "id": "kdj_oversold_buy_overbought_sell",
        "name": "KDJ超卖买超买卖",
        "description": "KDJ超卖区(K<20,D<20)买入，超买区(K>80,D>80)卖出",
        "entry_signal": "kdj_oversold",
        "exit_signal": "kdj_overbought",
        "holding_rule": "next_signal_reverse",
    },
]


# ══════════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════════

def get_signal_by_id(signal_id: str) -> Signal | None:
    """根据ID查找信号定义"""
    for s in ALL_SIGNALS:
        if s.id == signal_id:
            return s
    return None


def get_holding_rule_by_id(rule_id: str) -> HoldingRule | None:
    """根据ID查找持有规则"""
    for r in ALL_HOLDING_RULES:
        if r.id == rule_id:
            return r
    return None


def get_classic_strategy(strategy_id: str) -> dict | None:
    """根据ID查找经典策略"""
    for s in CLASSIC_STRATEGIES:
        if s["id"] == strategy_id:
            return s
    return None


def build_strategy_from_classic(strategy_id: str) -> Strategy | None:
    """从经典策略构建完整的Strategy对象"""
    cs = get_classic_strategy(strategy_id)
    if cs is None:
        return None

    entry_signal = get_signal_by_id(cs["entry_signal"])
    exit_signal = get_signal_by_id(cs.get("exit_signal", ""))
    holding_rule = get_holding_rule_by_id(cs["holding_rule"])

    entry_conditions = []
    if entry_signal:
        entry_conditions.append(SignalCondition(
            signal_id=entry_signal.id,
            operator="cross_above" if "cross" in entry_signal.id or "golden" in entry_signal.id else "trigger",
            threshold=0.0,
        ))

    exit_conditions = []
    if exit_signal:
        exit_conditions.append(SignalCondition(
            signal_id=exit_signal.id,
            operator="cross_below" if "cross" in exit_signal.id or "death" in exit_signal.id else "trigger",
            threshold=0.0,
        ))

    return Strategy(
        id=cs["id"],
        name=cs["name"],
        raw_text=cs["description"],
        entry_conditions=entry_conditions,
        exit_conditions=exit_conditions,
        holding_rule=holding_rule,
    )
