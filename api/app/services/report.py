"""PDF report (SPEC.md section 4/6). English, core fonts only (no external font files)."""

from datetime import datetime

from fpdf import FPDF

from app.schemas.api import DISCLAIMER
from app.services.questionnaires import get_questionnaire

SAGE = (74, 117, 97)
TEXT = (31, 42, 46)
MUTED = (90, 113, 132)
BAND_COLOURS = {0: (127, 181, 154), 1: (201, 180, 88), 2: (217, 144, 91), 3: (181, 97, 90)}


def _latin1(s: str) -> str:
    return (
        s.replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _max_score(qid: str) -> int:
    q = get_questionnaire(qid)
    if q.scoring.method == "subscales":
        return 0
    mult = 2 if q.scoring.method == "sum_x2" else 1
    return mult * sum(max(o.value for o in q.options_for(i)) for i in q.items)


def build_pdf(
    scores: dict, ml: dict | None, flagged: bool, helplines: dict | None, created_at: datetime
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    def h(text: str, size: int = 14) -> None:
        pdf.set_font("Helvetica", "B", size)
        pdf.set_text_color(*TEXT)
        pdf.cell(0, 9, _latin1(text), new_x="LMARGIN", new_y="NEXT")

    def p(text: str, colour=TEXT, size: int = 10, style: str = "") -> None:
        pdf.set_font("Helvetica", style, size)
        pdf.set_text_color(*colour)
        pdf.multi_cell(0, 5.5, _latin1(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*SAGE)
    pdf.cell(0, 12, "Calma", new_x="LMARGIN", new_y="NEXT")
    p(f"Screening report - {created_at:%d %B %Y}", MUTED)
    pdf.ln(2)
    p(DISCLAIMER, MUTED, 9, "I")
    pdf.ln(4)

    if flagged and helplines:
        h("Support is available now", 13)
        p("You don't have to go through this alone. You can talk to someone today:")
        for hl in helplines["helplines"]:
            line = hl["name"] + ": " + (hl.get("number") or hl.get("url") or "")
            if hl.get("alt_number"):
                line += f" (also {hl['alt_number']})"
            p("- " + line, style="B")
        pdf.ln(3)

    h("Validated questionnaire scores")
    for qid, s in scores.items():
        q = get_questionnaire(qid)
        if s.get("subscales"):
            p(f"{q.name}", style="B")
            for key, sub in s["subscales"].items():
                _band_row(pdf, f"  {key.title()}", f"{sub['score']}", sub["band"], sub["level"])
        else:
            _band_row(pdf, q.name, f"{s['total']} / {_max_score(qid)}", s["band"], s["level"])
    pdf.ln(3)

    if ml:
        h("AI-assisted estimate (secondary)")
        p(
            f"Composite estimate: {ml['composite_label']} "
            f"(confidence {ml['confidence']:.0%}, model {ml['model_version']}). "
            "When this differs from the validated scores above, the validated scores take priority."
        )
        if ml.get("top_factors"):
            p("What drove this estimate most:", MUTED)
            for f in ml["top_factors"]:
                direction = "raised" if f["impact"] > 0 else "lowered"
                p(f"- {f['label']} ({direction} the estimate)")
        pdf.ln(3)

    h("Next steps")
    for step in (
        "Share this report with a doctor, counsellor or other qualified professional.",
        "If your scores are moderate or higher, consider booking an appointment soon.",
        "Re-checking in 2-4 weeks can help you see how things are changing.",
    ):
        p("- " + step)
    return bytes(pdf.output())


def _band_row(pdf: FPDF, name: str, score: str, band: str, level: int) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*TEXT)
    pdf.cell(60, 7, _latin1(name))
    pdf.cell(30, 7, score)
    pdf.set_fill_color(*BAND_COLOURS.get(min(level, 3), MUTED))
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(50, 7, _latin1(band), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
