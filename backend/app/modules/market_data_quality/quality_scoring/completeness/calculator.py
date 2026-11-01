"""
M03.07.02 - Completeness Scoring Calculator.
Measures proportion of expected market data records and fields received and validated.
Completeness = (Valid Unique Observed Records / Eligible Expected Records) * 100
Field Completeness = (Valid Required Fields / Expected Fields)
"""

from decimal import Decimal
from typing import Tuple, Dict, Any
from backend.app.modules.market_data_quality.quality_scoring.schemas import CompletenessEvaluationInput


class CompletenessCalculator:
    """
    Computes dataset and field-level completeness scores.
    """

    @classmethod
    def calculate_completeness(
        cls, inp: CompletenessEvaluationInput
    ) -> Tuple[Decimal, Decimal, str, Dict[str, Any]]:
        """
        Calculates (completeness_score, field_ratio, classification, metadata).
        """
        # 1. Record-level completeness
        if inp.expected_records > 0:
            # Only count valid unique records (duplicates and invalid records do not count)
            valid_unique = min(inp.expected_records, inp.valid_records)
            comp_score = (Decimal(str(valid_unique)) / Decimal(str(inp.expected_records))) * Decimal("100.0")
        else:
            comp_score = Decimal("100.0")
        comp_score = round(min(Decimal("100.0"), max(Decimal("0.0"), comp_score)), 2)

        # 2. Field-level completeness ratio
        if inp.expected_fields_count > 0:
            field_ratio = Decimal(str(inp.valid_fields_count)) / Decimal(str(inp.expected_fields_count))
            field_ratio = min(Decimal("1.0"), max(Decimal("0.0"), field_ratio))
        else:
            field_ratio = Decimal("1.0")
        field_ratio = round(field_ratio, 4)

        # 3. Classification
        if comp_score >= Decimal("100.00"):
            classification = "COMPLETE"
        elif comp_score >= Decimal("98.00"):
            classification = "MOSTLY_COMPLETE"
        elif comp_score >= Decimal("90.00"):
            classification = "PARTIALLY_COMPLETE"
        else:
            classification = "INCOMPLETE"

        metadata = {
            "expected_records": inp.expected_records,
            "valid_records": inp.valid_records,
            "missing_records": inp.missing_records,
            "invalid_records": inp.invalid_records,
            "duplicate_receipts_excluded": inp.duplicate_receipts,
            "field_completeness_ratio": str(field_ratio),
        }
        return comp_score, field_ratio, classification, metadata
