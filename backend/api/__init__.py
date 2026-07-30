"""API 路由包：评测路由 + 报告路由。

Task 6 把 main.py 中的业务路由按职责拆分到本包下：
    - routes_evaluate.py：评测相关（评测/上传/语音/批量评测）
    - routes_report.py：报告查询、PDF 导出、删除

main.py 通过 include_router 挂载这两个 APIRouter。
"""
from .routes_evaluate import router as evaluate_router
from .routes_report import router as report_router

__all__ = ["evaluate_router", "report_router"]
