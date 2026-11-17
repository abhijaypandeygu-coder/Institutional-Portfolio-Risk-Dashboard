import csv
import io
from typing import List, Dict, Any, Optional

class CsvGenerator:
    """Generates clean, deterministic, UTF-8 CSV exports with formula-injection neutralization."""

    @staticmethod
    def sanitize_field(value: Any) -> Any:
        """Neutralize potential spreadsheet formula injection for text starting with =, +, -, @

        Preserves numerical negative numbers as numbers, neutralizing only text strings.
        """
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            return value

        str_val = str(value)
        # If text begins with dangerous formula trigger characters
        if str_val and str_val[0] in ("=", "+", "-", "@", "\t", "\r"):
            # If string is purely a valid number (e.g. "-125.40"), keep it numeric
            try:
                float(str_val)
                return str_val
            except ValueError:
                # Prepend single apostrophe to neutralize formula execution in Excel/Calc
                return f"'{str_val}"
        return str_val

    @classmethod
    def generate(
        cls,
        columns: List[str],
        data_rows: List[Dict[str, Any]],
        include_manifest_comments: bool = False,
        manifest_meta: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Generate UTF-8 encoded CSV string with optional manifest comments at top."""
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)

        if include_manifest_comments and manifest_meta:
            for k, v in manifest_meta.items():
                output.write(f"# {k}: {v}\n")

        # Write header
        writer.writerow(columns)

        # Write data rows in deterministic order
        for row in data_rows:
            formatted_row = [cls.sanitize_field(row.get(col)) for col in columns]
            writer.writerow(formatted_row)

        return output.getvalue().encode("utf-8")
