"""
发现者（Discoverer）— PDF 报告导出路由 (P1-1)

POST /api/report/export  — 导出回测结果为 PDF 报告

使用 ReportLab 将回测结果渲染为 A4 PDF 文件，支持内嵌图表和 AI 解读。
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import BacktestRecord, User
from models.schemas import ReportExportRequest
from routers.auth import get_current_user

# ReportLab imports
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

logger = logging.getLogger("discoverer.report")
router = APIRouter()

# ── 中文字体检测与注册 ──────────────────────────────────────────

_CHINESE_FONT_NAME: str | None = None


def _register_chinese_font() -> str:
    """注册中文字体，返回注册的字体名。

    按优先级搜索系统已有字体，macOS 优先 PingFang，Linux 优先 Noto/WenQuanYi。
    """
    global _CHINESE_FONT_NAME
    if _CHINESE_FONT_NAME:
        return _CHINESE_FONT_NAME

    font_paths = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        # Linux (Docker)
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        # 项目本地字体
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
                logger.info("已注册中文字体: %s", font_path)
                return _CHINESE_FONT_NAME
            except Exception as exc:
                logger.debug("字体 %s 注册失败: %s", font_path, exc)
                continue

    raise RuntimeError(
        "未找到可用的中文字体。请在 Docker 中安装: "
        "apt-get install fonts-noto-cjk 或 fonts-wqy-zenhei"
    )


def _get_styles() -> dict:
    """构建 ReportLab 段落样式表。"""
    font = _register_chinese_font()

    return {
        "title": ParagraphStyle(
            "Title",
            fontName=font, fontSize=18, leading=24,
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            fontName=font, fontSize=9, leading=12,
            alignment=TA_CENTER, textColor=HexColor("#6b7280"), spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "H2",
            fontName=font, fontSize=14, leading=18,
            spaceBefore=16, spaceAfter=8,
        ),
        "cell": ParagraphStyle(
            "Cell",
            fontName=font, fontSize=9, leading=13,
            alignment=TA_CENTER,
        ),
        "cell_left": ParagraphStyle(
            "CellLeft",
            fontName=font, fontSize=9, leading=13,
            alignment=TA_LEFT,
        ),
        "cell_header": ParagraphStyle(
            "CellHeader",
            fontName=font, fontSize=9, leading=13,
            alignment=TA_CENTER,
        ),
        "metric_value": ParagraphStyle(
            "MetricValue",
            fontName=font, fontSize=16, leading=20,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            fontName=font, fontSize=8, leading=11,
            alignment=TA_CENTER, textColor=HexColor("#6b7280"),
        ),
        "ai_body": ParagraphStyle(
            "AI",
            fontName=font, fontSize=10, leading=16,
            textColor=HexColor("#374151"),
        ),
        "footer": ParagraphStyle(
            "Footer",
            fontName=font, fontSize=8, leading=11,
            alignment=TA_CENTER, textColor=HexColor("#9ca3af"),
        ),
    }


# ── 辅助函数 ─────────────────────────────────────────────────

def _p(text: str, style: ParagraphStyle) -> Paragraph:
    """快捷创建 Paragraph。"""
    return Paragraph(text, style)


def _table_style(header_rows: int = 1) -> TableStyle:
    """通用表格样式。"""
    return TableStyle([
        # 表头背景
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), HexColor("#f3f4f6")),
        # 网格线
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d1d5db")),
        # 对齐
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # 内边距
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ])


# ── PDF 生成 ─────────────────────────────────────────────────

def _generate_pdf(
    backtest_result: dict,
    chart_images: dict[str, str] | None = None,
    include_ai: bool = True,
    include_chart: bool = True,
) -> bytes:
    """使用 ReportLab 生成 PDF 报告。

    Args:
        backtest_result: 回测结果字典
        chart_images: 图表 base64 图片映射
        include_ai: 是否包含 AI 解读
        include_chart: 是否包含权益曲线图

    Returns:
        PDF 文件的字节数据
    """
    chart_images = chart_images or {}
    styles = _get_styles()
    font = _register_chinese_font()

    # 提取数据
    metrics = backtest_result.get("metrics", {})
    trades = backtest_result.get("trades", [])
    stock_code = backtest_result.get("stock_code", "")
    stock_name = backtest_result.get("stock_name", "")
    strategy = backtest_result.get("strategy", {})
    strategy_name = strategy.get("name", "—") if strategy else "—"
    ai_text = backtest_result.get("ai_interpretation", "")

    # 格式化指标
    total_return = metrics.get("total_return", 0) * 100
    annual_return = metrics.get("annual_return", 0) * 100
    max_drawdown = metrics.get("max_drawdown", 0) * 100
    win_rate = metrics.get("win_rate", 0) * 100
    sharpe = metrics.get("sharpe_ratio", 0)
    pl_ratio = metrics.get("profit_loss_ratio", 0)
    total_trades = metrics.get("total_trades", 0)
    win_trades = metrics.get("win_trades", 0)
    lose_trades = metrics.get("lose_trades", 0)

    # 颜色
    POS = HexColor("#059669")
    NEG = HexColor("#dc2626")

    # 构建 Story
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"回测报告 — {stock_code} {stock_name}",
    )

    story = []

    # ── 标题 ──
    story.append(Paragraph("策略回测报告", styles["title"]))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(f"生成时间: {timestamp}", styles["subtitle"]))
    story.append(Spacer(1, 6 * mm))

    # ── 基本信息 ──
    story.append(Paragraph("基本信息", styles["h2"]))
    info_data = [
        [
            _p("股票代码", styles["cell_header"]),
            _p(stock_code, styles["cell"]),
            _p("股票名称", styles["cell_header"]),
            _p(stock_name, styles["cell"]),
        ],
        [
            _p("策略名称", styles["cell_header"]),
            _p(strategy_name, styles["cell"]),
            _p("数据来源", styles["cell_header"]),
            _p(backtest_result.get("data_source", "—"), styles["cell"]),
        ],
    ]
    info_table = Table(info_data, colWidths=[80 * mm, 60 * mm, 80 * mm, 60 * mm])
    info_table.setStyle(_table_style(header_rows=0))
    # 首列染色模拟标签列
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#f3f4f6")),
        ("BACKGROUND", (2, 0), (2, -1), HexColor("#f3f4f6")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 6 * mm))

    # ── 核心指标 ──
    story.append(Paragraph("核心指标", styles["h2"]))

    # 构建 2 行 x 3 列的指标卡片
    metric_items = [
        ("总收益率", f"{total_return:+.2f}%", POS if total_return >= 0 else NEG),
        ("年化收益率", f"{annual_return:+.2f}%", POS if annual_return >= 0 else NEG),
        ("最大回撤", f"{max_drawdown:.2f}%", NEG),
        ("胜率", f"{win_rate:.1f}%", None),
        ("夏普比率", f"{sharpe:.2f}", None),
        ("盈亏比", f"{pl_ratio:.2f}", None),
    ]

    # 每行 3 个指标，排列为 2 行
    col_w = (doc.width - 4) / 3  # 减去 grid 间距
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

    metric_table_data = []
    for row in metric_rows:
        metric_table_data.append([row[0], row[1], row[2]])

    metric_table = Table(
        metric_table_data,
        colWidths=[col_w] * 3,
        rowHeights=[36] * len(metric_rows),
    )
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

    # ── 交易统计 ──
    story.append(Paragraph("交易统计", styles["h2"]))
    stats_data = [[
        _p("总交易数", styles["cell_header"]), _p(str(total_trades), styles["cell"]),
        _p("盈利次数", styles["cell_header"]), _p(str(win_trades), styles["cell"]),
        _p("亏损次数", styles["cell_header"]), _p(str(lose_trades), styles["cell"]),
    ]]
    stats_table = Table(stats_data, colWidths=[50 * mm, 40 * mm, 50 * mm, 40 * mm, 50 * mm, 40 * mm])
    stats_table.setStyle(_table_style(header_rows=0))
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), HexColor("#f3f4f6")),
        ("BACKGROUND", (2, 0), (2, 0), HexColor("#f3f4f6")),
        ("BACKGROUND", (4, 0), (4, 0), HexColor("#f3f4f6")),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 6 * mm))

    # ── 图表（可选） ──
    if include_chart and chart_images:
        try:
            from reportlab.platypus import Image

            for name, img_data in chart_images.items():
                try:
                    if img_data.startswith("data:"):
                        _, encoded = img_data.split(",", 1)
                        img_bytes = base64.b64decode(encoded)
                        img = Image(
                            io.BytesIO(img_bytes),
                            width=doc.width * 0.9,
                            height=140,
                        )
                        img.hAlign = "CENTER"
                        story.append(img)
                        story.append(Spacer(1, 4 * mm))
                except Exception as exc:
                    logger.warning("图表 %s 嵌入失败: %s", name, exc)
        except ImportError:
            logger.warning("ReportLab Image 模块不可用，跳过图表")

    # ── 交易明细 ──
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
                _p(
                    f'<font color="{ret_color.hexval()}">{ret:+.2f}%</font>',
                    styles["cell"],
                ),
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

    # ── AI 解读（可选） ──
    if include_ai and ai_text:
        story.append(Paragraph("AI 策略解读", styles["h2"]))
        story.append(Paragraph(ai_text, styles["ai_body"]))
        story.append(Spacer(1, 6 * mm))

    # ── 页脚 ──
    story.append(HRFlowable(
        width="100%", thickness=0.5,
        color=HexColor("#e5e7eb"), spaceBefore=16, spaceAfter=8,
    ))
    story.append(Paragraph(
        "本报告由「发现者」A股量化回测平台自动生成 · 仅供研究参考，不构成投资建议",
        styles["footer"],
    ))

    # 构建 PDF
    doc.build(story)
    return buf.getvalue()


def _build_html_report(
    backtest_result: dict,
    chart_images: dict[str, str],
    include_ai: bool,
    include_chart: bool,
) -> str:
    """根据回测结果构建 HTML 报告模板。

    Args:
        backtest_result: 回测结果字典
        chart_images: 图表 base64 图片映射
        include_ai: 是否包含 AI 解读
        include_chart: 是否包含权益曲线图

    Returns:
        完整 HTML 字符串
    """
    metrics = backtest_result.get("metrics", {})
    trades = backtest_result.get("trades", [])
    stock_code = backtest_result.get("stock_code", "")
    stock_name = backtest_result.get("stock_name", "")
    strategy = backtest_result.get("strategy", {})
    strategy_name = strategy.get("name", "—") if strategy else "—"
    ai_text = backtest_result.get("ai_interpretation", "")

    # 格式化指标
    total_return = metrics.get("total_return", 0) * 100
    annual_return = metrics.get("annual_return", 0) * 100
    max_drawdown = metrics.get("max_drawdown", 0) * 100
    win_rate = metrics.get("win_rate", 0) * 100
    sharpe = metrics.get("sharpe_ratio", 0)
    pl_ratio = metrics.get("profit_loss_ratio", 0)
    total_trades = metrics.get("total_trades", 0)
    win_trades = metrics.get("win_trades", 0)
    lose_trades = metrics.get("lose_trades", 0)

    # 构建交易表格行
    trade_rows = ""
    for i, t in enumerate(trades[:50]):
        ret = t.get("return_pct", 0) * 100
        color = "#059669" if ret >= 0 else "#dc2626"
        trade_rows += f"""
        <tr>
            <td>{i + 1}</td>
            <td>{t.get("entry_date", "")}</td>
            <td>{t.get("entry_price", 0):.2f}</td>
            <td>{t.get("exit_date", "")}</td>
            <td>{t.get("exit_price", 0):.2f}</td>
            <td style="color:{color};font-weight:500">{ret:+.2f}%</td>
            <td>{t.get("exit_reason", "")[:20]}</td>
        </tr>"""

    # 图表图片
    chart_html = ""
    if include_chart and chart_images:
        for name, img_data in chart_images.items():
            chart_html += f'<img src="{img_data}" style="width:100%;max-width:700px;margin:8px 0;border:1px solid #e5e7eb;" />'

    # AI 解读
    ai_html = ""
    if include_ai and ai_text:
        ai_html = f"""
        <div style="margin-top:24px;padding:16px;background:#f0fdf4;border-radius:8px;border-left:4px solid #059669;">
            <h3 style="color:#065f46;margin:0 0 8px 0;">AI 策略解读</h3>
            <p style="color:#374151;line-height:1.7;white-space:pre-wrap;">{ai_text}</p>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>回测报告 — {stock_code} {stock_name}</title>
<style>
    body {{ font-family: "PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif; font-size: 10px; color: #1f2937; margin: 20px; }}
    h1 {{ font-size: 18px; color: #111827; margin: 0 0 4px 0; }}
    h2 {{ font-size: 14px; color: #374151; border-bottom: 2px solid #1a73e8; padding-bottom: 4px; margin: 20px 0 12px 0; }}
    h3 {{ font-size: 12px; color: #374151; margin: 12px 0 8px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 9px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 4px 6px; text-align: left; }}
    th {{ background: #f3f4f6; font-weight: 600; }}
    .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }}
    .meta {{ color: #6b7280; font-size: 9px; }}
    .metric-card {{ display: inline-block; width: 30%; padding: 8px; margin: 4px 1%; background: #f9fafb; border-radius: 6px; text-align: center; }}
    .metric-value {{ font-size: 16px; font-weight: 700; }}
    .metric-label {{ font-size: 8px; color: #6b7280; }}
    .positive {{ color: #059669; }}
    .negative {{ color: #dc2626; }}
    @page {{ size: A4; margin: 15mm; }}
</style>
</head>
<body>
    <div class="header">
        <div>
            <h1>策略回测报告</h1>
            <div class="meta">生成时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
        </div>
        <div style="text-align:right;color:#6b7280;font-size:9px;">
            发现者 · A股量化回测平台
        </div>
    </div>

    <h2>基本信息</h2>
    <table>
        <tr><th>股票代码</th><td>{stock_code}</td><th>股票名称</th><td>{stock_name}</td></tr>
        <tr><th>策略名称</th><td>{strategy_name}</td><th>数据来源</th><td>{backtest_result.get("data_source", "—")}</td></tr>
    </table>

    <h2>核心指标</h2>
    <div>
        <div class="metric-card">
            <div class="metric-value {'positive' if total_return >= 0 else 'negative'}">{total_return:+.2f}%</div>
            <div class="metric-label">总收益率</div>
        </div>
        <div class="metric-card">
            <div class="metric-value {'positive' if annual_return >= 0 else 'negative'}">{annual_return:+.2f}%</div>
            <div class="metric-label">年化收益率</div>
        </div>
        <div class="metric-card">
            <div class="metric-value negative">{max_drawdown:.2f}%</div>
            <div class="metric-label">最大回撤</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{win_rate:.1f}%</div>
            <div class="metric-label">胜率</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{sharpe:.2f}</div>
            <div class="metric-label">夏普比率</div>
        </div>
        <div class="metric-card">
            <div class="metric-value">{pl_ratio:.2f}</div>
            <div class="metric-label">盈亏比</div>
        </div>
    </div>

    <h2>交易统计</h2>
    <table>
        <tr><th>总交易数</th><td>{total_trades}</td><th>盈利次数</th><td>{win_trades}</td><th>亏损次数</th><td>{lose_trades}</td></tr>
    </table>

    {chart_html}

    <h2>交易明细</h2>
    <table>
        <tr><th>#</th><th>买入日期</th><th>买入价</th><th>卖出日期</th><th>卖出价</th><th>收益率</th><th>卖出原因</th></tr>
        {trade_rows if trade_rows else '<tr><td colspan="7" style="text-align:center;color:#9ca3af;">无交易记录</td></tr>'}
    </table>

    {ai_html}

    <div style="margin-top:32px;padding-top:12px;border-top:1px solid #e5e7eb;text-align:center;color:#9ca3af;font-size:8px;">
        本报告由「发现者」A股量化回测平台自动生成 · 仅供研究参考，不构成投资建议
    </div>
</body>
</html>"""
    return html


# ══════════════════════════════════════════════════════════
# POST /api/report/export — 导出 PDF 报告
# ══════════════════════════════════════════════════════════

@router.post("/report/export")
async def export_pdf_report(
    req: ReportExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """将回测结果导出为 PDF 报告。

    接收完整的回测结果数据和可选的图表 base64 图片，
    使用 ReportLab 渲染为 A4 PDF 文件，返回 base64 编码。

    Args:
        req: 报告导出请求体

    Returns:
        {code: 0, data: ReportExportResponse, message: "success"}
    """
    try:
        result = req.backtest_result
        stock_code = result.get("stock_code", "report")
        stock_name = result.get("stock_name", "")

        # 生成 PDF（ReportLab 直接从数据生成，无需 HTML 中间层）
        pdf_bytes = _generate_pdf(
            backtest_result=result,
            chart_images=req.chart_images,
            include_ai=req.include_ai,
            include_chart=req.include_chart,
        )

        # Base64 编码
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        # 生成文件名
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"回测报告_{stock_code}_{stock_name}_{timestamp}.pdf"

        logger.info(
            "PDF 报告生成成功: stock=%s, size=%d bytes, user=%d",
            stock_code, len(pdf_bytes), current_user.id,
        )

        return {
            "code": 0,
            "data": {
                "pdf_base64": pdf_base64,
                "filename": filename,
            },
            "message": "success",
        }

    except RuntimeError as e:
        logger.error("PDF 导出失败（依赖缺失）: %s", e)
        return {"code": -1, "data": None, "message": str(e)}
    except Exception as e:
        logger.error("PDF 导出失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"PDF 导出失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# GET /api/report/export/{backtest_id} — 按历史记录 ID 导出
# ══════════════════════════════════════════════════════════

@router.get("/report/export/{backtest_id}")
async def export_pdf_by_id(
    backtest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """根据回测历史记录 ID 导出 PDF 报告。

    从 backtest_history 表加载回测结果，生成 PDF 报告。

    Args:
        backtest_id: 回测历史记录 ID

    Returns:
        {code: 0, data: ReportExportResponse, message: "success"}
    """
    try:
        record = (
            db.query(BacktestRecord)
            .filter(BacktestRecord.id == backtest_id)
            .first()
        )

        if record is None:
            return {"code": -1, "data": None, "message": "回测记录不存在"}

        if record.user_id != current_user.id:
            return {"code": -1, "data": None, "message": "无权限访问该回测记录"}

        # 构建回测结果字典
        result_data = {}
        if record.result_data:
            try:
                result_data = (
                    json.loads(record.result_data)
                    if isinstance(record.result_data, str)
                    else record.result_data
                )
            except (json.JSONDecodeError, TypeError):
                result_data = {}

        backtest_result = {
            "stock_code": record.stock_code,
            "stock_name": record.stock_name or "",
            "strategy": {"name": ""},
            "metrics": {
                "total_return": record.total_return,
                "annual_return": record.annual_return,
                "max_drawdown": record.max_drawdown,
                "win_rate": record.win_rate,
                "sharpe_ratio": record.sharpe_ratio,
                "profit_loss_ratio": record.profit_loss_ratio,
                "total_trades": record.total_trades,
                "win_trades": 0,
                "lose_trades": 0,
            },
            "trades": result_data.get("trades", []),
            "equity_curve": result_data.get("equity_curve", []),
        }

        # 生成 PDF
        pdf_bytes = _generate_pdf(
            backtest_result=backtest_result,
            include_ai=False,
            include_chart=False,
        )
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"回测报告_{record.stock_code}_{timestamp}.pdf"

        logger.info(
            "历史回测 PDF 导出: history_id=%d, user=%d",
            backtest_id, current_user.id,
        )

        return {
            "code": 0,
            "data": {
                "pdf_base64": pdf_base64,
                "filename": filename,
            },
            "message": "success",
        }

    except RuntimeError as e:
        logger.error("PDF 导出失败（依赖缺失）: %s", e)
        return {"code": -1, "data": None, "message": str(e)}
    except Exception as e:
        logger.error("PDF 导出失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"PDF 导出失败: {str(e)}"}
