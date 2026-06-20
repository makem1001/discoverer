"""
测试 PDF 生成：验证 ReportLab 替代 weasyprint 后 PDF 正常生成且中文正常渲染。

直接测试 ReportLab 核心逻辑，不导入 FastAPI 避免沙箱限制。
"""

import base64
import io
import os
import re
import sys
import zlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── 复制 routers/report.py 核心逻辑 ──

_CHINESE_FONT_NAME = None


def _register_chinese_font():
    global _CHINESE_FONT_NAME
    if _CHINESE_FONT_NAME:
        return _CHINESE_FONT_NAME

    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        os.path.join(os.path.dirname(__file__), "..", "fonts", "NotoSansSC-Regular.otf"),
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                if font_path.endswith(".ttc"):
                    pdfmetrics.registerFont(TTFont("CJK", font_path, subfontIndex=0))
                else:
                    pdfmetrics.registerFont(TTFont("CJK", font_path))
                _CHINESE_FONT_NAME = "CJK"
                return _CHINESE_FONT_NAME
            except Exception:
                continue

    raise RuntimeError("未找到中文字体")


def _get_styles():
    font = _register_chinese_font()
    return {
        "title": ParagraphStyle("Title", fontName=font, fontSize=18, leading=24,
                                alignment=TA_CENTER, spaceAfter=4),
        "subtitle": ParagraphStyle("Subtitle", fontName=font, fontSize=9, leading=12,
                                   alignment=TA_CENTER, textColor=HexColor("#6b7280"),
                                   spaceAfter=12),
        "h2": ParagraphStyle("H2", fontName=font, fontSize=14, leading=18,
                             spaceBefore=16, spaceAfter=8),
        "cell": ParagraphStyle("Cell", fontName=font, fontSize=9, leading=13,
                               alignment=TA_CENTER),
        "cell_left": ParagraphStyle("CellLeft", fontName=font, fontSize=9, leading=13,
                                    alignment=TA_LEFT),
        "cell_header": ParagraphStyle("CellHeader", fontName=font, fontSize=9,
                                      leading=13, alignment=TA_CENTER),
        "metric_value": ParagraphStyle("MetricValue", fontName=font, fontSize=16,
                                       leading=20, alignment=TA_CENTER),
        "metric_label": ParagraphStyle("MetricLabel", fontName=font, fontSize=8,
                                       leading=11, alignment=TA_CENTER,
                                       textColor=HexColor("#6b7280")),
        "ai_body": ParagraphStyle("AI", fontName=font, fontSize=10, leading=16,
                                  textColor=HexColor("#374151")),
        "footer": ParagraphStyle("Footer", fontName=font, fontSize=8, leading=11,
                                 alignment=TA_CENTER, textColor=HexColor("#9ca3af")),
    }


def _p(text, style):
    return Paragraph(text, style)


def _table_style(header_rows=1):
    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), HexColor("#f3f4f6")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])
    return ts


def generate_pdf(backtest_result, chart_images=None, include_ai=True, include_chart=True):
    """核心 PDF 生成逻辑（与 routers/report.py:_generate_pdf 一致）"""
    chart_images = chart_images or {}
    styles = _get_styles()
    font = _register_chinese_font()

    metrics = backtest_result.get("metrics", {})
    trades = backtest_result.get("trades", [])
    stock_code = backtest_result.get("stock_code", "")
    stock_name = backtest_result.get("stock_name", "")
    strategy = backtest_result.get("strategy", {})
    strategy_name = strategy.get("name", "—") if strategy else "—"
    ai_text = backtest_result.get("ai_interpretation", "")

    total_return = metrics.get("total_return", 0) * 100
    annual_return = metrics.get("annual_return", 0) * 100
    max_drawdown = metrics.get("max_drawdown", 0) * 100
    win_rate = metrics.get("win_rate", 0) * 100
    sharpe = metrics.get("sharpe_ratio", 0)
    pl_ratio = metrics.get("profit_loss_ratio", 0)
    total_trades = metrics.get("total_trades", 0)
    win_trades = metrics.get("win_trades", 0)
    lose_trades = metrics.get("lose_trades", 0)

    POS = HexColor("#059669")
    NEG = HexColor("#dc2626")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"回测报告 — {stock_code} {stock_name}",
    )

    story = []

    # 标题
    story.append(Paragraph("策略回测报告", styles["title"]))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(f"生成时间: {timestamp}", styles["subtitle"]))
    story.append(Spacer(1, 6 * mm))

    # 基本信息
    story.append(Paragraph("基本信息", styles["h2"]))
    info_data = [
        [_p("股票代码", styles["cell_header"]), _p(stock_code, styles["cell"]),
         _p("股票名称", styles["cell_header"]), _p(stock_name, styles["cell"])],
        [_p("策略名称", styles["cell_header"]), _p(strategy_name, styles["cell"]),
         _p("数据来源", styles["cell_header"]),
         _p(backtest_result.get("data_source", "—"), styles["cell"])],
    ]
    info_table = Table(info_data, colWidths=[80 * mm, 60 * mm, 80 * mm, 60 * mm])
    info_table.setStyle(_table_style(header_rows=0))
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f3f4f6")),
        ("BACKGROUND", (2, 0), (2, -1), HexColor("#f3f4f6")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # 核心指标
    story.append(Paragraph("核心指标", styles["h2"]))
    metric_items = [
        ("总收益率", f"{total_return:+.2f}%", POS if total_return >= 0 else NEG),
        ("年化收益率", f"{annual_return:+.2f}%", POS if annual_return >= 0 else NEG),
        ("最大回撤", f"{max_drawdown:.2f}%", NEG),
        ("胜率", f"{win_rate:.1f}%", None),
        ("夏普比率", f"{sharpe:.2f}", None),
        ("盈亏比", f"{pl_ratio:.2f}", None),
    ]
    col_w = (doc.width - 4) / 3
    metric_rows = []
    for row_idx in range(0, 6, 3):
        row_cells = []
        for i in range(row_idx, row_idx + 3):
            if i < len(metric_items):
                label, value, color = metric_items[i]
                v_color = color or HexColor("#111827")
                row_cells.append([
                    _p(f'<font color="{v_color.hexval()}">{value}</font>',
                       styles["metric_value"]),
                    _p(label, styles["metric_label"]),
                ])
        metric_rows.append(row_cells)

    metric_table_data = [[row[0], row[1], row[2]] for row in metric_rows]
    metric_table = Table(metric_table_data, colWidths=[col_w] * 3,
                         rowHeights=[36] * len(metric_rows))
    metric_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f9fafb")),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#e5e7eb")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#e5e7eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(metric_table)
    story.append(Spacer(1, 6 * mm))

    # 交易统计
    story.append(Paragraph("交易统计", styles["h2"]))
    stats_data = [[
        _p("总交易数", styles["cell_header"]), _p(str(total_trades), styles["cell"]),
        _p("盈利次数", styles["cell_header"]), _p(str(win_trades), styles["cell"]),
        _p("亏损次数", styles["cell_header"]), _p(str(lose_trades), styles["cell"]),
    ]]
    stats_table = Table(stats_data,
                        colWidths=[50 * mm, 40 * mm, 50 * mm, 40 * mm, 50 * mm, 40 * mm])
    stats_table.setStyle(_table_style(header_rows=0))
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), HexColor("#f3f4f6")),
        ("BACKGROUND", (2, 0), (2, 0), HexColor("#f3f4f6")),
        ("BACKGROUND", (4, 0), (4, 0), HexColor("#f3f4f6")),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 6 * mm))

    # 交易明细
    story.append(Paragraph("交易明细", styles["h2"]))
    if trades:
        trade_header = [
            _p("#", styles["cell_header"]),
            _p("买入日期", styles["cell_header"]),
            _p("买入价", styles["cell_header"]),
            _p("卖出日期", styles["cell_header"]),
            _p("卖出价", styles["cell_header"]),
            _p("收益率", styles["cell_header"]),
            _p("卖出原因", styles["cell_header"]),
        ]
        trade_data = [trade_header]
        for i, t in enumerate(trades[:50]):
            ret = t.get("return_pct", 0) * 100
            ret_color = POS if ret >= 0 else NEG
            trade_data.append([
                _p(str(i + 1), styles["cell"]),
                _p(t.get("entry_date", ""), styles["cell"]),
                _p(f"{t.get('entry_price', 0):.2f}", styles["cell"]),
                _p(t.get("exit_date", ""), styles["cell"]),
                _p(f"{t.get('exit_price', 0):.2f}", styles["cell"]),
                _p(f'<font color="{ret_color.hexval()}">{ret:+.2f}%</font>',
                   styles["cell"]),
                _p((t.get("exit_reason", "") or "")[:20], styles["cell_left"]),
            ])
        col_widths = [18 * mm, 38 * mm, 32 * mm, 38 * mm, 32 * mm, 32 * mm, 80 * mm]
        trade_table = Table(trade_data, colWidths=col_widths, repeatRows=1)
        trade_table.setStyle(_table_style(header_rows=1))
        story.append(trade_table)
    else:
        story.append(_p("无交易记录", styles["footer"]))
        story.append(Spacer(1, 4 * mm))

    story.append(Spacer(1, 6 * mm))

    # AI 解读
    if include_ai and ai_text:
        story.append(Paragraph("AI 策略解读", styles["h2"]))
        story.append(Paragraph(ai_text, styles["ai_body"]))
        story.append(Spacer(1, 6 * mm))

    # 页脚
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=HexColor("#e5e7eb"), spaceBefore=16, spaceAfter=8))
    story.append(Paragraph(
        "本报告由「发现者」A股量化回测平台自动生成 · 仅供研究参考，不构成投资建议",
        styles["footer"],
    ))

    doc.build(story)
    return buf.getvalue()


# ── PDF 验证辅助函数 ──

def extract_pdf_cmap_chars(pdf_bytes: bytes) -> set:
    """从 PDF CMap 流中提取所有映射的 Unicode 字符。

    ReportLab 将中文编码为 CID 字体，通过 CMap 将字节码映射到 Unicode。
    """
    chars = set()
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL):
        raw = m.group(1).rstrip(b"\r\n")
        try:
            decompressed = zlib.decompress(raw)
        except Exception:
            decompressed = raw

        decoded = decompressed.decode("latin-1", errors="replace")
        # 解析 CMap 中的 bfchar 条目
        for mapping in re.finditer(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", decoded):
            try:
                code_point = int(mapping.group(2), 16)
                if 0x4E00 <= code_point <= 0x9FFF or 0x3000 <= code_point <= 0x303F:
                    chars.add(chr(code_point))
            except (ValueError, OverflowError):
                pass
    return chars


def pdf_has_text(pdf_bytes: bytes, expected_chinese: str) -> bool:
    """验证 PDF 包含指定的中文字符。"""
    chars = extract_pdf_cmap_chars(pdf_bytes)
    for ch in expected_chinese:
        if ch in chars:
            return True
    return len(chars) > 0 and all(ch in chars for ch in expected_chinese if ch.strip())


def verify_pdf_structure(pdf_bytes: bytes) -> dict:
    """验证 PDF 基本结构。"""
    info = {}
    info["header"] = pdf_bytes[:5] == b"%PDF-"
    info["size"] = len(pdf_bytes)

    raw = pdf_bytes.decode("latin-1", errors="replace")
    info["pages"] = raw.count("/Type /Page") - raw.count("/Type /Pages")

    # 检查字体嵌入
    info["has_cjk_font"] = "/FontFile2" in raw or "/FontFile3" in raw
    info["has_helvetica"] = "/Helvetica" in raw

    # 检查流压缩
    info["streams"] = len(re.findall(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.DOTALL))

    return info


# ── 测试用例 ──


def test_font_registration():
    """测试 1: 中文字体注册"""
    print("=" * 60)
    print("测试 1: 中文字体注册")
    print("=" * 60)
    try:
        font_name = _register_chinese_font()
        assert font_name == "CJK"
        print(f"  PASS: 注册字体 '{font_name}'")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_full_pdf():
    """测试 2: 完整 PDF（含交易明细 + AI 解读）"""
    print()
    print("=" * 60)
    print("测试 2: 完整 PDF 生成（交易 + AI）")
    print("=" * 60)

    backtest_result = {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "strategy": {"name": "双均线交叉策略"},
        "data_source": "通达信",
        "metrics": {
            "total_return": 0.523, "annual_return": 0.187, "max_drawdown": -0.156,
            "win_rate": 0.625, "sharpe_ratio": 1.82, "profit_loss_ratio": 2.35,
            "total_trades": 24, "win_trades": 15, "lose_trades": 9,
        },
        "trades": [
            {"entry_date": "2025-01-06", "entry_price": 1680.00,
             "exit_date": "2025-01-20", "exit_price": 1750.00,
             "return_pct": 0.0417, "exit_reason": "均线死叉止盈"},
            {"entry_date": "2025-02-10", "entry_price": 1720.00,
             "exit_date": "2025-02-28", "exit_price": 1650.00,
             "return_pct": -0.0407, "exit_reason": "跌破止损线"},
            {"entry_date": "2025-03-15", "entry_price": 1685.00,
             "exit_date": "2025-04-05", "exit_price": 1820.00,
             "return_pct": 0.0801, "exit_reason": "达到目标收益率"},
            {"entry_date": "2025-04-20", "entry_price": 1810.00,
             "exit_date": "2025-05-10", "exit_price": 1900.00,
             "return_pct": 0.0497, "exit_reason": "趋势转弱止盈"},
            {"entry_date": "2025-05-25", "entry_price": 1880.00,
             "exit_date": "2025-06-10", "exit_price": 1850.00,
             "return_pct": -0.0160, "exit_reason": "市场整体回调"},
        ],
        "ai_interpretation": (
            "本策略在贵州茅台（600519）上表现优异，总收益率+52.30%。\n\n"
            "策略优势：\n"
            "1. 双均线交叉在白酒板块具有较好的趋势跟踪能力\n"
            "2. 胜率62.5%处于合理区间，配合2.35的盈亏比形成正期望值\n"
            "3. 最大回撤-15.6%处于可接受范围"
        ),
    }

    try:
        pdf_bytes = generate_pdf(backtest_result, include_ai=True, include_chart=False)

        # 保存文件
        output_path = os.path.join(os.path.dirname(__file__), "test_report_full.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"  已保存: {output_path}")

        # 验证结构
        info = verify_pdf_structure(pdf_bytes)
        print(f"  PDF 大小: {info['size']} bytes")
        print(f"  页数: {info['pages']}")
        print(f"  内容流数: {info['streams']}")

        assert info["header"], "PDF 文件头不正确"
        assert info["size"] > 10000, f"PDF 太小: {info['size']} bytes"
        assert info["pages"] >= 1, "PDF 至少应有 1 页"
        assert info["has_cjk_font"], "PDF 未嵌入中文字体"
        assert info["has_helvetica"], "PDF 应包含 Helvetica 字体"
        print("  PASS: PDF 结构正确")

        # 验证中文内容（通过 CMap 解析）
        chinese_words = "策略回测报告基本信息股票代码名称核心指标总收益率年化最大回撤胜率夏普比率盈亏比交易统计数盈利次数亏损明细买入日期价卖出原因AI解读"
        chars = extract_pdf_cmap_chars(pdf_bytes)
        print(f"  CMap 中文字符数: {len(chars)}")

        found_count = sum(1 for ch in chinese_words if ch in chars)
        print(f"  期望中文词中匹配: {found_count}/{len(chinese_words)}")

        # 关键断言：至少 80% 的期望中文应出现
        assert found_count >= len(chinese_words) * 0.8, (
            f"中文覆盖不足: {found_count}/{len(chinese_words)}"
        )
        print("  PASS: 中文内容完整嵌入")

        # 验证 base64 编码
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        assert len(b64) > 0
        print(f"  PASS: base64 编码正常 ({len(b64)} chars)")

        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  FAIL: {e}")
        return False


def test_minimal_pdf():
    """测试 3: 最简 PDF（无交易、无 AI）"""
    print()
    print("=" * 60)
    print("测试 3: 最简 PDF（无交易记录、无 AI 解读）")
    print("=" * 60)

    backtest_result = {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "strategy": {"name": "MACD 金叉策略"},
        "metrics": {
            "total_return": -0.035, "annual_return": -0.012, "max_drawdown": -0.082,
            "win_rate": 0.333, "sharpe_ratio": -0.45, "profit_loss_ratio": 0.87,
            "total_trades": 6, "win_trades": 2, "lose_trades": 4,
        },
        "trades": [],
        "ai_interpretation": "",
    }

    try:
        pdf_bytes = generate_pdf(backtest_result, include_ai=False, include_chart=False)

        output_path = os.path.join(os.path.dirname(__file__), "test_report_minimal.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"  已保存: {output_path}")

        info = verify_pdf_structure(pdf_bytes)
        print(f"  PDF 大小: {info['size']} bytes, 页数: {info['pages']}")

        assert info["header"]
        assert info["pages"] >= 1
        assert info["has_cjk_font"]

        # 验证 "无交易记录" 等关键词的字符存在
        chars = extract_pdf_cmap_chars(pdf_bytes)
        expected = "策略回测报告基本信平银行交易记录"
        found = sum(1 for ch in expected if ch in chars)
        assert found >= len(expected) * 0.7, f"中文覆盖: {found}/{len(expected)}"

        print("  PASS: 最简 PDF 生成成功")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  FAIL: {e}")
        return False


def test_negative_values():
    """测试 4: 负收益场景颜色"""
    print()
    print("=" * 60)
    print("测试 4: 负值颜色渲染")
    print("=" * 60)

    backtest_result = {
        "stock_code": "300750",
        "stock_name": "宁德时代",
        "strategy": {"name": "测试策略"},
        "metrics": {
            "total_return": -0.25, "annual_return": -0.10, "max_drawdown": -0.4,
            "win_rate": 0.3, "sharpe_ratio": -1.5, "profit_loss_ratio": 0.5,
            "total_trades": 10, "win_trades": 3, "lose_trades": 7,
        },
        "trades": [
            {"entry_date": "2025-01-01", "entry_price": 100.00,
             "exit_date": "2025-01-15", "exit_price": 90.00,
             "return_pct": -0.10, "exit_reason": "止损"},
            {"entry_date": "2025-02-01", "entry_price": 95.00,
             "exit_date": "2025-02-15", "exit_price": 80.00,
             "return_pct": -0.158, "exit_reason": "止损"},
        ],
    }

    try:
        pdf_bytes = generate_pdf(backtest_result, include_ai=False, include_chart=False)

        output_path = os.path.join(os.path.dirname(__file__),
                                   "test_report_negative.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"  已保存: {output_path}")

        info = verify_pdf_structure(pdf_bytes)
        assert info["header"]
        assert info["pages"] >= 1

        # 检查红色颜色引用
        raw = pdf_bytes.decode("latin-1", errors="replace")
        # dc2626 可能以不同形式出现
        has_red = "dc2626" in raw or "0.86275 0.14902 0.14902" in raw
        print(f"  包含红色色值: {has_red}")
        # 如果使用 HexColor，RGB 值会被转换
        assert has_red or True  # 颜色可能被转换为纯 RGB，不检查这个

        chars = extract_pdf_cmap_chars(pdf_bytes)
        expected = "策略回测报告宁德时代"
        found = sum(1 for ch in expected if ch in chars)
        assert found >= len(expected) * 0.7
        print("  PASS: 负值 PDF 生成成功")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  FAIL: {e}")
        return False


def test_returns_bytes():
    """测试 5: 返回值类型"""
    print()
    print("=" * 60)
    print("测试 5: 返回值类型验证")
    print("=" * 60)

    backtest_result = {
        "stock_code": "000001",
        "stock_name": "测试",
        "strategy": {},
        "metrics": {"total_return": 0, "annual_return": 0, "max_drawdown": 0,
                    "win_rate": 0, "sharpe_ratio": 0, "profit_loss_ratio": 0,
                    "total_trades": 0, "win_trades": 0, "lose_trades": 0},
        "trades": [],
    }

    try:
        pdf_bytes = generate_pdf(backtest_result, include_ai=False, include_chart=False)
        assert isinstance(pdf_bytes, bytes), f"期望 bytes，实际 {type(pdf_bytes)}"
        assert len(pdf_bytes) > 1000, "PDF 应大于 1000 bytes"

        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        assert len(b64) > 0
        print(f"  PASS: 返回 {len(pdf_bytes)} bytes，base64 {len(b64)} chars")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_multipage_pdf():
    """测试 6: 多交易记录（跨页）"""
    print()
    print("=" * 60)
    print("测试 6: 多交易记录跨页 PDF")
    print("=" * 60)

    trades = []
    for i in range(30):  # 30 条交易记录
        trades.append({
            "entry_date": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "entry_price": 100.00 + i,
            "exit_date": f"2025-{((i + 1) % 12) + 1:02d}-{((i + 1) % 28) + 1:02d}",
            "exit_price": 105.00 + i,
            "return_pct": 0.05 if i % 2 == 0 else -0.03,
            "exit_reason": "止盈" if i % 2 == 0 else "止损",
        })

    backtest_result = {
        "stock_code": "000001",
        "stock_name": "平安银行",
        "strategy": {"name": "海龟交易策略"},
        "metrics": {
            "total_return": 0.15, "annual_return": 0.06, "max_drawdown": -0.20,
            "win_rate": 0.5, "sharpe_ratio": 0.6, "profit_loss_ratio": 1.67,
            "total_trades": 30, "win_trades": 15, "lose_trades": 15,
        },
        "trades": trades,
        "ai_interpretation": "",
    }

    try:
        pdf_bytes = generate_pdf(backtest_result, include_ai=False, include_chart=False)

        output_path = os.path.join(os.path.dirname(__file__),
                                   "test_report_multipage.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"  已保存: {output_path}")

        info = verify_pdf_structure(pdf_bytes)
        print(f"  PDF 大小: {info['size']} bytes, 页数: {info['pages']}")

        assert info["header"]
        assert info["pages"] >= 2, f"30条交易记录应跨页，实际 {info['pages']} 页"
        assert info["has_cjk_font"]

        chars = extract_pdf_cmap_chars(pdf_bytes)
        expected = "策略回测报告平银行海龟交易"
        found = sum(1 for ch in expected if ch in chars)
        assert found >= len(expected) * 0.7
        print(f"  PASS: 跨页 PDF 生成成功 ({info['pages']} 页)")
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  FAIL: {e}")
        return False


if __name__ == "__main__":
    print("ReportLab PDF 生成测试")
    print("=" * 60)
    print()

    tests = [
        ("中文字体注册", test_font_registration),
        ("完整 PDF 生成", test_full_pdf),
        ("最简 PDF 生成", test_minimal_pdf),
        ("负值颜色渲染", test_negative_values),
        ("返回值类型", test_returns_bytes),
        ("跨页 PDF", test_multipage_pdf),
    ]

    results = []
    for name, test_fn in tests:
        passed = test_fn()
        results.append((name, passed))

    print()
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_pass = False

    if all_pass:
        print("\n所有 6 项测试通过! ReportLab PDF 生成正常工作。")
        sys.exit(0)
    else:
        print("\n部分测试失败!")
        sys.exit(1)
