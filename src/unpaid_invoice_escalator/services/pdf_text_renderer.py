from __future__ import annotations

from collections.abc import Sequence


class TextPdfRenderer:
    def __init__(
        self,
        *,
        page_width: int = 595,
        page_height: int = 842,
        margin_left: int = 72,
        margin_top: int = 780,
        margin_bottom: int = 60,
        font_size: int = 11,
        line_height: int = 14,
    ) -> None:
        self._page_width = page_width
        self._page_height = page_height
        self._margin_left = margin_left
        self._margin_top = margin_top
        self._margin_bottom = margin_bottom
        self._font_size = font_size
        self._line_height = line_height

    def render(self, lines: Sequence[str]) -> bytes:
        page_lines = self._paginate(lines)
        page_object_numbers = [4 + index * 2 for index in range(len(page_lines))]
        page_refs = " ".join(f"{object_number} 0 R" for object_number in page_object_numbers)

        objects: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{page_refs}] /Count {len(page_lines)} >>".encode("latin-1"),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        for index, lines_for_page in enumerate(page_lines):
            page_object_number = 4 + index * 2
            content_object_number = page_object_number + 1
            stream = self._page_stream(lines_for_page)
            objects.append(
                (
                    "<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {self._page_width} {self._page_height}] "
                    "/Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {content_object_number} 0 R >>"
                ).encode("latin-1")
            )
            objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode("latin-1"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")

        xref_start = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("latin-1")
        )
        return bytes(pdf)

    def _paginate(self, lines: Sequence[str]) -> tuple[tuple[str, ...], ...]:
        lines_per_page = max(1, ((self._margin_top - self._margin_bottom) // self._line_height) + 1)
        normalized_lines = tuple(lines) if lines else ("",)
        return tuple(
            tuple(normalized_lines[index : index + lines_per_page])
            for index in range(0, len(normalized_lines), lines_per_page)
        )

    def _page_stream(self, lines: Sequence[str]) -> bytes:
        safe_lines = [self._escape_pdf_text(line) for line in lines]
        commands = ["BT", f"/F1 {self._font_size} Tf", f"{self._margin_left} {self._margin_top} Td"]
        for index, line in enumerate(safe_lines):
            if index > 0:
                commands.append(f"0 -{self._line_height} Td")
            commands.append(f"({line}) Tj")
        commands.append("ET")
        return "\n".join(commands).encode("latin-1", errors="replace")

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
