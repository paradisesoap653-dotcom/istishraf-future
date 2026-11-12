"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401

from .guards import install_api_guards  # noqa: E402

# تُثبَّت الحراسة مرة واحدة عند الاستيراد: تعديل الأزرقية بعد تسجيلها ممنوع في Flask.
install_api_guards(graph_bp, simulation_bp, report_bp)

