from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_pdf(text: str) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    margin = 20 * mm
    y = height - margin
    line_height = 18

    c.setFont("Times-Roman", 14)

    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue

        words = paragraph.split()
        current = ""

        for word in words:
            test = current + (" " if current else "") + word
            if c.stringWidth(test, "Times-Roman", 14) < (width - 2 * margin):
                current = test
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)

    for line in lines:
        if y < margin:
            c.showPage()
            c.setFont("Times-Roman", 14)
            y = height - margin

        c.drawString(margin, y, line)
        y -= line_height

    c.save()
    buffer.seek(0)
    return buffer