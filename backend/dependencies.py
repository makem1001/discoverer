"""
发现者（Discoverer）— 共享依赖注入

提供全局单例的 DataService、TemplateMatcher、RuleEngine 访问，
供 main.py 和所有 routers 使用，避免循环引用。

P0-4 新增：
  - get_template_matcher() 暴露 TemplateMatcher 单例
  - get_rule_engine() 暴露 RuleEngine 单例
"""

from config import TDX_DEFAULT_DIR

_data_service = None
_template_matcher = None
_rule_engine = None


def get_data_service(tdx_dir: str = ""):
    """获取全局 DataService 实例（延迟初始化）。

    自动使用 TDX_DATA_DIR 环境变量作为默认 tdx_dir。

    Args:
        tdx_dir: 可选的通达信数据目录路径，为空时使用 TDX_DATA_DIR 环境变量。

    Returns:
        DataService 全局单例。
    """
    global _data_service
    if _data_service is None:
        from services.data_service import DataService
        _data_service = DataService(tdx_dir=tdx_dir or TDX_DEFAULT_DIR)
    return _data_service


def get_template_matcher():
    """获取全局 TemplateMatcher 实例（延迟初始化）。

    TemplateMatcher 是 LLM 降级链 Level 1：基于 jieba 分词 + Jaccard
    相似度匹配 15+ 预置策略模板。

    Returns:
        TemplateMatcher 全局单例。
    """
    global _template_matcher
    if _template_matcher is None:
        from services.strategy_templates import TemplateMatcher
        _template_matcher = TemplateMatcher()
    return _template_matcher


def get_rule_engine():
    """获取全局 RuleEngine 实例（延迟初始化）。

    RuleEngine 是 LLM 降级链 Level 3：基于关键词→信号映射的兜底规则引擎。

    Returns:
        RuleEngine 全局单例。
    """
    global _rule_engine
    if _rule_engine is None:
        from services.rule_engine import RuleEngine
        _rule_engine = RuleEngine()
    return _rule_engine


# ── P1-3: 模拟交易引擎单例 ─────────────────────────────

_paper_engine = None


def get_paper_engine():
    """获取全局 PaperEngine 实例（延迟初始化）。

    PaperEngine 负责模拟账户的日K前向仿真，接收 DataService 和
    SignalService 作为依赖。

    Returns:
        PaperEngine 全局单例。
    """
    global _paper_engine
    if _paper_engine is None:
        from services.data_service import DataService
        from services.signal_service import SignalService
        from services.paper_engine import PaperEngine
        _paper_engine = PaperEngine(
            data_service=DataService(),
            signal_service=SignalService(),
        )
    return _paper_engine
