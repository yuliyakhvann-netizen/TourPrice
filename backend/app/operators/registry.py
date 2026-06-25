"""
Maps operator codes to their connector instances. Used by anything that
needs to search "every connected operator" without hardcoding which
ones exist - currently FunSun, Kompas, and Pegas; Anex joins here once
its connector is written.
"""

from app.operators.funsun.connector import FunSunOperator
from app.operators.kompas.connector import KompasOperator
from app.operators.pegas.connector import PegasOperator
from app.operators.selfie.connector import SelfieOperator
from app.operators.kazunion.connector import KazunionOperator

OPERATOR_CONNECTORS = {
    "funsun": FunSunOperator(),
    "kompas": KompasOperator(),
    "pegas": PegasOperator(),
    "selfie": SelfieOperator(),
    "kazunion": KazunionOperator(),
}