import io
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class ExcelGenerator:
    """Generates structured, styled multi-worksheet Excel workbooks with frozen headers and financial formatting."""

    HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    HEADER_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    TITLE_FONT = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
    META_KEY_FONT = Font(name="Segoe UI", size=10, bold=True, color="475569")
    DATA_FONT = Font(name="Segoe UI", size=10, color="0F172A")
    THIN_BORDER = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    @staticmethod
    def sanitize_field(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, (int, float, bool)):
            return value
        str_val = str(value)
        if str_val and str_val[0] in ("=", "+", "-", "@"):
            try:
                float(str_val)
                return str_val
            except ValueError:
                return f"'{str_val}"
        return str_val

    @classmethod
    def generate(
        cls,
        dataset_name: str,
        columns: List[str],
        data_rows: List[Dict[str, Any]],
        column_display_names: Optional[Dict[str, str]] = None,
        summary_metadata: Optional[Dict[str, Any]] = None,
        methodology_notes: Optional[List[str]] = None,
    ) -> bytes:
        wb = openpyxl.Workbook()
        # Default active sheet
        ws_summary = wb.active
        ws_summary.title = "Executive Summary"

        # 1. Executive Summary Sheet
        ws_summary.append([f"Institutional Risk & Analytical Export — {dataset_name}"])
        ws_summary.cell(row=1, column=1).font = cls.TITLE_FONT
        ws_summary.append([])

        if summary_metadata:
            ws_summary.append(["Metadata Parameter", "Configuration Value"])
            ws_summary.cell(row=3, column=1).font = cls.HEADER_FONT
            ws_summary.cell(row=3, column=1).fill = cls.HEADER_FILL
            ws_summary.cell(row=3, column=2).font = cls.HEADER_FONT
            ws_summary.cell(row=3, column=2).fill = cls.HEADER_FILL
            
            row_idx = 4
            for k, v in summary_metadata.items():
                ws_summary.append([str(k).replace("_", " ").title(), str(v)])
                ws_summary.cell(row=row_idx, column=1).font = cls.META_KEY_FONT
                ws_summary.cell(row=row_idx, column=2).font = cls.DATA_FONT
                row_idx += 1

        ws_summary.column_dimensions["A"].width = 30
        ws_summary.column_dimensions["B"].width = 45

        # 2. Main Data Sheet
        ws_data = wb.create_sheet(title="Analytical Data")
        display_headers = [
            (column_display_names.get(col) if column_display_names else col.replace("_", " ").title())
            for col in columns
        ]
        ws_data.append(display_headers)

        for col_num in range(1, len(display_headers) + 1):
            cell = ws_data.cell(row=1, column=col_num)
            cell.font = cls.HEADER_FONT
            cell.fill = cls.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cls.THIN_BORDER

        # Data rows
        for row in data_rows:
            formatted_row = [cls.sanitize_field(row.get(col)) for col in columns]
            ws_data.append(formatted_row)

        # Style data rows and adjust width
        for row_idx in range(2, len(data_rows) + 2):
            for col_idx in range(1, len(columns) + 1):
                cell = ws_data.cell(row=row_idx, column=col_idx)
                cell.font = cls.DATA_FONT
                cell.border = cls.THIN_BORDER
                # Alignment
                if isinstance(cell.value, (int, float)):
                    cell.alignment = Alignment(horizontal="right")
                else:
                    cell.alignment = Alignment(horizontal="left")

        # Auto column width
        for col in ws_data.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_data.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # Freeze header row
        ws_data.freeze_panes = "A2"

        # 3. Methodology Sheet
        if methodology_notes:
            ws_meth = wb.create_sheet(title="Methodology & Governance")
            ws_meth.append(["Methodology Disclosures & Analytical Notes"])
            ws_meth.cell(row=1, column=1).font = cls.TITLE_FONT
            ws_meth.append([])
            for note in methodology_notes:
                ws_meth.append([f"• {note}"])
                ws_meth.cell(row=ws_meth.max_row, column=1).font = cls.DATA_FONT
            ws_meth.column_dimensions["A"].width = 80

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
