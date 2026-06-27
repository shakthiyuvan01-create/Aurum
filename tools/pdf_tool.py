"""PDF tool — generate PDFs and extract/analyse existing PDFs."""
import os, uuid

NAME        = "pdf_tool"
DESCRIPTION = "Generate a PDF document from text/content, OR extract and analyse text from an existing PDF file"
CATEGORY    = "builtin"
ICON        = "📄"
INPUTS = [
    {"name": "action",   "label": "Action",   "type": "select",   "required": True,
     "options": [{"value": "generate", "label": "Generate PDF"},
                 {"value": "analyze",  "label": "Analyze PDF (extract text)"}]},
    {"name": "content",  "label": "Content (text to put in PDF) or File Path (to analyze)",
     "type": "textarea", "placeholder": "Enter content or path to PDF...", "required": True},
    {"name": "title",    "label": "Document Title",   "type": "text",   "placeholder": "My Document"},
    {"name": "filename", "label": "Output Filename",  "type": "text",   "placeholder": "output.pdf"},
]

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_docs")


def _ensure_dir():
    os.makedirs(DOCS_DIR, exist_ok=True)


def _generate(content: str, title: str, filename: str) -> dict:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_LEFT

        _ensure_dir()
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        path = os.path.join(DOCS_DIR, filename)

        doc    = SimpleDocTemplate(path, pagesize=A4,
                                   leftMargin=20*mm, rightMargin=20*mm,
                                   topMargin=20*mm,  bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        story  = []

        # Title
        if title:
            title_style = ParagraphStyle("Title2", parent=styles["Title"], spaceAfter=12)
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 6*mm))

        # Body — split by newlines, handle blank lines as spacers
        body_style = ParagraphStyle("Body2", parent=styles["Normal"],
                                    fontSize=11, leading=16, spaceAfter=6)
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped:
                # Escape XML special chars
                safe = stripped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, body_style))
            else:
                story.append(Spacer(1, 4*mm))

        doc.build(story)
        return {"message": f"✅ PDF generated!\n[📥 Download {filename}](/docs/{filename})",
                "file": f"/docs/{filename}"}

    except ImportError:
        return {"error": "reportlab not installed. Run: pip install reportlab"}
    except Exception as e:
        return {"error": f"PDF generation failed: {e}"}


def _analyze(file_path: str) -> dict:
    try:
        import pdfplumber
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                t = page.extract_text() or ""
                if t.strip():
                    text_parts.append(f"--- Page {i} ---\n{t.strip()}")
        if not text_parts:
            return {"message": "No text found in PDF (may be scanned image)."}
        text = "\n\n".join(text_parts)
        if len(text) > 4000:
            text = text[:4000] + "\n\n[...truncated]"
        return {"message": f"**Extracted text from PDF:**\n\n{text}"}
    except ImportError:
        # Fallback: PyPDF2
        try:
            import PyPDF2
            text_parts = []
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages, 1):
                    t = page.extract_text() or ""
                    if t.strip():
                        text_parts.append(f"--- Page {i} ---\n{t.strip()}")
            text = "\n\n".join(text_parts)[:4000]
            return {"message": f"**Extracted text:**\n\n{text}"}
        except ImportError:
            return {"error": "pdfplumber or PyPDF2 not installed. Run: pip install pdfplumber"}
    except Exception as e:
        return {"error": f"PDF analysis failed: {e}"}


def run(action: str, content: str, title: str = "", filename: str = "") -> dict:
    if not filename:
        filename = f"doc_{uuid.uuid4().hex[:8]}.pdf"
    if action == "generate":
        return _generate(content, title or "Document", filename)
    elif action == "analyze":
        return _analyze(content)
    else:
        return {"error": f"Unknown action: {action}. Use 'generate' or 'analyze'."}
