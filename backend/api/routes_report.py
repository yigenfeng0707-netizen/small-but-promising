"""报告查询相关路由：内存+文件轻量存储、查询、PDF 导出、删除。

对应 Task 6 SubTask 6.4：
    - GET    /api/report/{request_id}      读取评测报告 JSON
    - GET    /api/report/{request_id}/pdf  导出 PDF（含化学品名/风险等级/5维评分/
                                           家庭建议/应急指导/绿色替代品等）
    - DELETE /api/report/{request_id}      删除报告

存储策略：保持轻量、不引入数据库。POST /api/evaluate 时由
routes_evaluate.save_report 把完整结果写到 backend/storage/reports/{request_id}.json，
本模块只负责读/删/PDF 渲染。

PDF 中文字体：优先加载 Windows 自带 simhei.ttf；失败则降级为英文 PDF。
"""
from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from fpdf import FPDF

from config import REPORT_DIR

router = APIRouter(prefix="/api", tags=["report"])

# REPORT_DIR 由 config.py 集中解析（魔搭创空间自动走 /mnt/workspace 持久化）

# Windows 自带的中文字体路径（simhei.ttf 是单文件 TTF，fpdf2 加载最稳）
_CJK_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux 兜底
    "/System/Library/Fonts/PingFang.ttc",             # macOS 兜底
]


# ----------------------------------------------------------------------
# 存储辅助函数
# ----------------------------------------------------------------------
def save_report(result: dict) -> None:
    """把评测结果写到 backend/storage/reports/{request_id}.json。

    评测路由在每次 /api/evaluate 系列接口成功后调用一次。
    """
    request_id = result.get("request_id")
    if not request_id:
        return
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"{request_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def _load_report(request_id: str) -> Optional[dict]:
    """读取报告 JSON；不存在返回 None。"""
    path = os.path.join(REPORT_DIR, f"{request_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------
# PDF 字体加载（一次性，模块级缓存）
# ----------------------------------------------------------------------
_CJK_FONT_PATH: Optional[str] = None
_CJK_FONT_TRIED = False


def _resolve_cjk_font_path() -> Optional[str]:
    """探测一个可用的中文字体文件路径；找不到返回 None。

    模块级缓存：整个进程只探测一次。返回路径后由 _build_pdf 在实际 PDF
    实例上调用 add_font 注册字体（add_font 只对调用它的 FPDF 实例生效）。
    """
    global _CJK_FONT_PATH, _CJK_FONT_TRIED
    if _CJK_FONT_TRIED:
        return _CJK_FONT_PATH
    _CJK_FONT_TRIED = True

    for path in _CJK_FONT_CANDIDATES:
        if not os.path.isfile(path):
            continue
        # 用一个临时 FPDF 实例试加载，避免污染真正生成 PDF 的实例
        probe = FPDF()
        try:
            probe.add_font("CJK", "", path)
            _CJK_FONT_PATH = path
            return _CJK_FONT_PATH
        except Exception:
            # 该字体加载失败（如 .ttc 多集合索引问题），换下一个
            continue
    return None


# ----------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------
@router.get("/report/{request_id}")
async def get_report(request_id: str) -> dict:
    """读取评测报告 JSON。"""
    report = _load_report(request_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在: {request_id}")
    return report


@router.get("/report/{request_id}/pdf")
async def get_report_pdf(request_id: str):
    """导出评测报告 PDF。

    PDF 内容关键字段：化学品名 / 风险等级 / 5 维评分 / 家庭建议 / 应急指导 /
    绿色替代品。优先用中文字体渲染；字体不可用时降级为英文字段名 PDF。
    """
    report = _load_report(request_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在: {request_id}")

    pdf_bytes = _build_pdf(report)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="report_{request_id}.pdf"'},
    )


@router.delete("/report/{request_id}")
async def delete_report(request_id: str) -> dict:
    """删除评测报告。"""
    path = os.path.join(REPORT_DIR, f"{request_id}.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"报告不存在: {request_id}")
    os.remove(path)
    return {"deleted": True, "request_id": request_id}


# ----------------------------------------------------------------------
# PDF 构建
# ----------------------------------------------------------------------
def _build_pdf(report: dict) -> bytes:
    """根据报告 dict 构建 PDF 字节流。

    字段布局：
        - 标题：安居智评报告 + request_id
        - 识别：化学品名/品牌/类别
        - 风险：overall_level / adjusted_level + 5 维评分
        - 家庭建议：调整原因 + 针对性警告
        - 应急指导：立即行动 / 禁止事项 / 热线
        - 绿色替代品：原物 → 替代列表
        - 总结：summary
    """
    cjk_path = _resolve_cjk_font_path()
    cjk = cjk_path is not None  # 供后续中英文标签三元判断使用
    pdf = FPDF()
    if cjk_path:
        # 在实际 PDF 实例上注册中文字体（add_font 只对调用方生效）
        pdf.add_font("CJK", "", cjk_path)
    pdf.add_page()

    def set_font(size: int = 12, bold: bool = False) -> None:
        if cjk_path:
            pdf.set_font("CJK", size=size)
        else:
            # 没有中文字体时退回 Helvetica（仅 ASCII）
            style = "B" if bold else ""
            pdf.set_font("Helvetica", style=style, size=size)

    def emit(label: str, value) -> None:
        """输出一行 label: value。无 CJK 字体时跳过纯中文 value。"""
        if value is None:
            value = ""
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        else:
            value = str(value)
        # 无中文字体时，丢弃非 ASCII 内容（避免 fpdf2 报错或乱码）
        if not cjk_path:
            label = _ascii_only(label)
            value = _ascii_only(value)
        pdf.cell(0, 8, f"{label}: {value}", ln=True)

    # 标题
    set_font(size=16, bold=True)
    title = "安居智评 评测报告" if cjk else "Home Chem Safety Report"
    pdf.cell(0, 12, title, ln=True, align="C")
    pdf.ln(4)
    set_font(size=10)
    pdf.cell(0, 6, f"request_id: {report.get('request_id', '')}", ln=True)
    pdf.cell(0, 6, f"mode: {report.get('mode', '')}", ln=True)
    if report.get("partial"):
        warn = "注：本次评测有步骤降级" if cjk else "Note: partial degradation"
        pdf.cell(0, 6, warn, ln=True)
    pdf.ln(4)

    # 识别
    set_font(size=13, bold=True)
    pdf.cell(0, 8, "识别结果" if cjk else "Recognition", ln=True)
    set_font(size=11)
    rec = report.get("recognition") or {}
    emit("化学品名" if cjk else "Chemical", rec.get("chemical_name"))
    emit("品牌" if cjk else "Brand", rec.get("brand"))
    emit("类别" if cjk else "Category", rec.get("category"))
    pdf.ln(3)

    # 风险评测
    set_font(size=13, bold=True)
    pdf.cell(0, 8, "风险评测" if cjk else "Risk Evaluation", ln=True)
    set_font(size=11)
    risk = report.get("risk") or {}
    emit("原始风险等级" if cjk else "Overall Level", risk.get("overall_level"))
    fam = report.get("family_adjustment") or {}
    emit("家庭调整后等级" if cjk else "Adjusted Level", fam.get("adjusted_level"))
    # 5 维评分
    scores = risk.get("scores") or {}
    score_labels = {
        "toxicity": "毒性" if cjk else "Toxicity",
        "flammability": "易燃性" if cjk else "Flammability",
        "corrosivity": "腐蚀性" if cjk else "Corrosivity",
        "allergy": "致敏性" if cjk else "Allergy",
        "environment": "环境影响" if cjk else "Environment",
    }
    for k, lbl in score_labels.items():
        emit(lbl, scores.get(k))
    emit("主要风险" if cjk else "Key Risks", risk.get("key_risks"))
    emit("相互作用" if cjk else "Interactions", risk.get("interactions"))
    pdf.ln(3)

    # 家庭建议
    set_font(size=13, bold=True)
    pdf.cell(0, 8, "家庭画像建议" if cjk else "Family Advice", ln=True)
    set_font(size=11)
    emit("调整原因" if cjk else "Reasons", fam.get("adjustment_reasons"))
    emit("针对性警告" if cjk else "Warnings", fam.get("specific_warnings"))
    pdf.ln(3)

    # 应急指导
    set_font(size=13, bold=True)
    pdf.cell(0, 8, "应急指导" if cjk else "Emergency Guide", ln=True)
    set_font(size=11)
    em = report.get("emergency_guide") or {}
    emit("立即行动" if cjk else "Immediate Actions", em.get("immediate_actions"))
    emit("禁止事项" if cjk else "Do NOT", em.get("do_not"))
    emit("是否需就医" if cjk else "Seek Medical", em.get("seek_medical_help"))
    emit("急救热线" if cjk else "Hotlines", em.get("hotlines"))
    pdf.ln(3)

    # 绿色替代品
    set_font(size=13, bold=True)
    pdf.cell(0, 8, "绿色替代品" if cjk else "Green Alternatives", ln=True)
    set_font(size=11)
    sce = report.get("scenario_advice") or {}
    greens = sce.get("green_alternatives") or []
    if greens:
        for g in greens:
            if isinstance(g, dict):
                alts = g.get("alternatives") or []
                line = f"{g.get('original', '')} -> {', '.join(str(a) for a in alts)}"
            else:
                line = str(g)
            if not cjk:
                line = _ascii_only(line)
            pdf.cell(0, 8, line, ln=True)
    else:
        none_txt = "无" if cjk else "None"
        pdf.cell(0, 8, none_txt, ln=True)
    pdf.ln(3)

    # 总结
    set_font(size=13, bold=True)
    pdf.cell(0, 8, "总结" if cjk else "Summary", ln=True)
    set_font(size=11)
    summary = report.get("summary") or ""
    if not cjk:
        summary = _ascii_only(summary)
    pdf.multi_cell(0, 8, summary)

    return bytes(pdf.output())


def _ascii_only(text: str) -> str:
    """丢弃非 ASCII 字符（用于无中文字体时的兜底 PDF 渲染）。"""
    return "".join(ch for ch in text if ord(ch) < 128)
