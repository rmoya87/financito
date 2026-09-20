from decimal import Decimal
from financito.services.imports import parse_decimal, parse_date

def test_spanish_decimal(): assert parse_decimal("1.234,56 €")==Decimal("1234.56")
def test_spanish_date(): assert parse_date("20/09/2026").isoformat()=="2026-09-20"
