import io
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Custom canvas that tracks total pages for running header/footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header
        self.drawString(54, 570, "INSTITUTIONAL PORTFOLIO RISK DASHBOARD — EXPORT REPORT")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 564, 738, 564)

        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(738, 36, page_str)
        self.drawString(54, 36, "STRICTLY CONFIDENTIAL — FOR INTERNAL RISK MANAGEMENT USE ONLY")
        self.line(54, 46, 738, 46)
        self.restoreState()


class PdfGenerator:
    """Generates paginated institutional financial reports in landscape PDF format."""

    @classmethod
    def generate(
        cls,
        report_title: str,
        columns: List[str],
        data_rows: List[Dict[str, Any]],
        column_display_names: Optional[Dict[str, str]] = None,
        summary_metadata: Optional[Dict[str, Any]] = None,
        methodology_notes: Optional[List[str]] = None,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            leftMargin=54,
            rightMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=12,
        )
        h2_style = ParagraphStyle(
            "SectionHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=14,
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
        meta_key_style = ParagraphStyle(
            "MetaKey",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
        )
        cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
        )
        header_cell_style = ParagraphStyle(
            "HeaderCell",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=1,
        )

        story = []

        # Title
        story.append(Paragraph(report_title, title_style))
        story.append(Spacer(1, 6))

        # Metadata table
        if summary_metadata:
            meta_data = []
            keys = list(summary_metadata.keys())
            for i in range(0, len(keys), 2):
                k1 = keys[i]
                v1 = str(summary_metadata[k1])
                k2 = keys[i+1] if i+1 < len(keys) else ""
                v2 = str(summary_metadata[k2]) if k2 else ""
                meta_data.append([
                    Paragraph(str(k1).replace("_", " ").title(), meta_key_style),
                    Paragraph(v1, body_style),
                    Paragraph(str(k2).replace("_", " ").title() if k2 else "", meta_key_style),
                    Paragraph(v2, body_style),
                ])
            
            meta_table = Table(meta_data, colWidths=[130, 210, 130, 214])
            meta_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("PADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(meta_table)
            story.append(Spacer(1, 14))

        # Main Data Table
        story.append(Paragraph("Analytical Dataset Records", h2_style))
        
        display_headers = [
            (column_display_names.get(col) if column_display_names else col.replace("_", " ").title())
            for col in columns
        ]
        
        table_rows = [[Paragraph(dh, header_cell_style) for dh in display_headers]]
        for r in data_rows[:1000]: # Safety boundary on PDF table records
            row_cells = [Paragraph(str(r.get(c, "")), cell_style) for c in columns]
            table_rows.append(row_cells)

        num_cols = len(columns)
        available_width = 684.0 # 792 - 108 margins
        col_w = available_width / max(num_cols, 1)

        data_table = Table(table_rows, colWidths=[col_w] * num_cols, repeatRows=1)
        data_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ]))
        story.append(data_table)

        # Methodology section
        if methodology_notes:
            story.append(Spacer(1, 14))
            story.append(Paragraph("Methodology & Governance Notes", h2_style))
            for note in methodology_notes:
                story.append(Paragraph(f"• {note}", body_style))
                story.append(Spacer(1, 3))

        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()
