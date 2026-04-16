#!/usr/bin/env python3
"""
Generate OligoVoid stakeholder brief PDF -- slide-deck style.
Uses fpdf2 with dark-themed headers, clean layout, and minimal text per page.
All text uses only latin-1 compatible characters for Helvetica built-in font.
"""

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import os

OUTPUT_PATH = "/Users/kingmanas/Desktop/OligoVoid_Brief.pdf"

# -- Colour palette -----------------------------------------------------------
DARK_BG = (18, 18, 28)          # near-black with blue tint
HEADER_BG = (30, 30, 50)        # dark indigo header bar
ACCENT = (0, 200, 180)          # teal accent
ACCENT_DIM = (0, 150, 135)      # dimmer teal for secondary use
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 210)
MID_GRAY = (140, 140, 160)
HIGHLIGHT = (255, 200, 60)      # gold for key numbers
PAGE_BG = (245, 245, 250)       # very light grey page body
BODY_TEXT = (40, 40, 55)        # dark text on light background


class BriefPDF(FPDF):
    """Custom PDF with dark-header slide-deck styling."""

    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.slide_number = 0

    # -- helpers --------------------------------------------------------------
    def _draw_page_bg(self):
        self.set_fill_color(*PAGE_BG)
        self.rect(0, 0, self.w, self.h, "F")

    def _draw_header_bar(self, title, subtitle=""):
        bar_h = 38
        self.set_fill_color(*HEADER_BG)
        self.rect(0, 0, self.w, bar_h, "F")
        # accent line
        self.set_fill_color(*ACCENT)
        self.rect(0, bar_h, self.w, 1.2, "F")
        # title
        self.set_xy(14, 8)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*WHITE)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_xy(14, 22)
            self.set_font("Helvetica", "", 12)
            self.set_text_color(*LIGHT_GRAY)
            self.cell(0, 8, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def _draw_footer(self):
        self.set_xy(self.w - 60, self.h - 12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MID_GRAY)
        self.cell(50, 6, f"OligoVoid  |  Slide {self.slide_number}", align="R")

    def new_slide(self, title, subtitle=""):
        self.add_page()
        self.slide_number += 1
        self._draw_page_bg()
        self._draw_header_bar(title, subtitle)
        self._draw_footer()
        self.set_xy(14, 46)

    def _draw_bullet_dot(self, x, y, r=1.5):
        """Draw a small filled circle as bullet point."""
        self.set_fill_color(*ACCENT)
        self.ellipse(x - r, y - r, r * 2, r * 2, "F")

    def bullet(self, text, indent=0, bold_prefix="", size=12, spacing=9):
        """Render a teal-bullet line with optional bold prefix."""
        x_start = 18 + indent
        y_cur = self.get_y()
        self.set_xy(x_start, y_cur)

        # draw a small teal circle as bullet
        bullet_y = y_cur + spacing / 2
        self._draw_bullet_dot(x_start + 1.5, bullet_y, r=1.5)

        # move past bullet
        self.set_xy(x_start + 6, y_cur)

        if bold_prefix:
            self.set_font("Helvetica", "B", size)
            self.set_text_color(*BODY_TEXT)
            pw = self.get_string_width(bold_prefix) + 1
            self.cell(pw, spacing, bold_prefix, new_x=XPos.RIGHT, new_y=YPos.TOP)

        self.set_font("Helvetica", "", size)
        self.set_text_color(*BODY_TEXT)
        remaining_w = self.w - self.get_x() - 16
        self.multi_cell(remaining_w, spacing, text)
        self.set_x(x_start)

    def key_number(self, label, value, x, y, box_w=80, box_h=32):
        """Draw a highlighted stat box."""
        self.set_fill_color(*HEADER_BG)
        self.set_draw_color(*ACCENT)
        self.rect(x, y, box_w, box_h, "FD")
        self.set_xy(x, y + 4)
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*ACCENT)
        self.cell(box_w, 10, value, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_xy(x, y + 17)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*LIGHT_GRAY)
        self.cell(box_w, 8, label, align="C")

    def section_label(self, text, size=11):
        """Small caps-like label in accent colour."""
        self.set_font("Helvetica", "B", size)
        self.set_text_color(*ACCENT_DIM)
        self.cell(0, 8, text.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)


def build_pdf():
    pdf = BriefPDF()

    # == Slide 1: Title =======================================================
    pdf.add_page()
    pdf.slide_number = 1
    pdf.set_fill_color(*DARK_BG)
    pdf.rect(0, 0, pdf.w, pdf.h, "F")

    # accent bar top
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, pdf.w, 3, "F")

    # main title
    pdf.set_xy(0, 52)
    pdf.set_font("Helvetica", "B", 44)
    pdf.set_text_color(*ACCENT)
    pdf.cell(pdf.w, 18, "OligoVoid", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # tagline
    pdf.set_xy(0, 78)
    pdf.set_font("Helvetica", "", 18)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(pdf.w, 10, "Mapping the Dark Matter of siRNA Drug Design",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # separator
    pdf.set_fill_color(*ACCENT_DIM)
    pdf.rect(pdf.w / 2 - 40, 96, 80, 0.8, "F")

    # author + date
    pdf.set_xy(0, 104)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*MID_GRAY)
    pdf.cell(pdf.w, 8, "Manas Reddy  |  April 2026", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # GitHub
    pdf.set_xy(0, 116)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*ACCENT_DIM)
    pdf.cell(pdf.w, 8, "github.com/ManasReddy1/OligoVoid", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # footer bar
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, pdf.h - 3, pdf.w, 3, "F")

    # slide number
    pdf.set_xy(pdf.w - 60, pdf.h - 12)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MID_GRAY)
    pdf.cell(50, 6, "OligoVoid  |  Slide 1", align="R")

    # == Slide 2: The Problem =================================================
    pdf.new_slide("The Problem", "Why siRNA drug design is stuck")

    pdf.bullet("siRNA drugs silence disease-causing genes", size=12)
    pdf.bullet("8 FDA-approved siRNA drugs on the market today", size=12)
    pdf.ln(3)
    pdf.bullet("Raw RNA dies in ~15 seconds in the bloodstream", size=12)
    pdf.bullet("Chemical modifications = protective armor for survival", size=12)
    pdf.ln(3)
    pdf.section_label("The combinatorial explosion")
    pdf.bullet("42 positions x 8 modification types per siRNA duplex", size=12)
    pdf.ln(1)

    # stat boxes
    y_box = pdf.get_y() + 2
    pdf.key_number("Possible Combinations", "10^38", 18, y_box, 85, 30)
    pdf.key_number("Patterns Ever Tested", "~3,500", 115, y_box, 85, 30)
    pdf.key_number("Map NEVER Explored", "55%", 212, y_box, 85, 30)

    # == Slide 3: The Gap =====================================================
    pdf.new_slide("The Gap", "What nobody had quantified before")

    pdf.section_label("Position-Modification Landscape")
    pdf.bullet("336 possible position-modification combinations", size=13)
    pdf.ln(4)

    y_box = pdf.get_y() + 2
    pdf.key_number("Tested (45%)", "151", 40, y_box, 100, 34)
    pdf.key_number("Untested (55%)", "185", 160, y_box, 100, 34)

    pdf.set_xy(18, y_box + 44)
    pdf.ln(4)
    pdf.bullet("Nobody had built a systematic map of what's been tried vs. what hasn't",
               size=12)
    pdf.ln(2)
    pdf.bullet("", bold_prefix="That's what OligoVoid does.", size=13)

    # == Slide 4: What OligoVoid Does =========================================
    pdf.new_slide("What OligoVoid Does", "Three capabilities in one platform")

    cards = [
        ("MAPS", "Identifies every untested modification\npattern in the siRNA design space"),
        ("SCORES", "3-layer scoring engine\n(Biophysics + GP + CVAE)"),
        ("PRIORITISES", "VPA active learning tells you\nexactly what to test next"),
    ]

    card_w = 85
    gap = 12
    total = card_w * 3 + gap * 2
    x_start = (pdf.w - total) / 2
    y_card = 56

    for i, (label, desc) in enumerate(cards):
        x = x_start + i * (card_w + gap)
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_draw_color(*ACCENT)
        pdf.rect(x, y_card, card_w, 65, "FD")

        pdf.set_xy(x, y_card + 8)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*ACCENT)
        pdf.cell(card_w, 12, label, align="C",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(x + 6, y_card + 28)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.multi_cell(card_w - 12, 7, desc, align="C")

    # == Slide 5: The 3-Layer Scoring Engine ==================================
    pdf.new_slide("The 3-Layer Scoring Engine", "Each layer adds a different lens")

    layers = [
        ("Layer 1: Biophysics Rules",
         ["Thermodynamic stability",
          "RISC loading compatibility",
          "Nuclease resistance profiling",
          "Off-target risk assessment"]),
        ("Layer 2: Gaussian Process",
         ["Trained on 3,527 real experiments",
          "Pearson r = 0.297",
          "ECE = 0.033 (well-calibrated)"]),
        ("Layer 3: CVAE Novelty",
         ["Generative AI checks if a pattern is truly novel",
          "Reconstruction quality validates chemical plausibility"]),
    ]

    col_w = 88
    col_gap = 8
    total_w = col_w * 3 + col_gap * 2
    x_base = (pdf.w - total_w) / 2

    for i, (heading, items) in enumerate(layers):
        x = x_base + i * (col_w + col_gap)
        y_top = 48

        # column header
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_draw_color(*ACCENT)
        pdf.rect(x, y_top, col_w, 18, "FD")
        pdf.set_xy(x, y_top + 4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*ACCENT)
        pdf.cell(col_w, 10, heading, align="C")

        # items
        y_item = y_top + 24
        for item_text in items:
            pdf.set_xy(x + 4, y_item)
            # small bullet dot
            pdf._draw_bullet_dot(x + 6, y_item + 3, r=1.2)
            pdf.set_xy(x + 10, y_item)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*BODY_TEXT)
            pdf.multi_cell(col_w - 14, 6, item_text)
            y_item = pdf.get_y() + 2

    # == Slide 6: Key Results =================================================
    pdf.new_slide("Key Results", "Quantitative performance across all components")

    results = [
        ("GP Calibration", "ECE = 0.033", "Excellent calibration"),
        ("FDA Validation", "4/5 correct", "MAE = 11.3%"),
        ("CVAE Quality", "95% valid", "100% novel, 100% unique"),
        ("VPA Coverage", "80%", "vs EI's 69% in simulated discovery"),
    ]

    box_w = 60
    box_gap = 10
    total_w = box_w * 4 + box_gap * 3
    x_s = (pdf.w - total_w) / 2
    y_s = 52

    for i, (label, big, sub) in enumerate(results):
        x = x_s + i * (box_w + box_gap)
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_draw_color(*ACCENT)
        pdf.rect(x, y_s, box_w, 58, "FD")

        pdf.set_xy(x, y_s + 4)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ACCENT)
        pdf.cell(box_w, 7, label, align="C",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(x, y_s + 16)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(*WHITE)
        pdf.cell(box_w, 12, big, align="C",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(x + 3, y_s + 34)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.multi_cell(box_w - 6, 6, sub, align="C")

    # == Slide 7: FDA Reality Check ===========================================
    pdf.new_slide("FDA Reality Check",
                  "Validating against approved drugs not in training data")

    pdf.bullet("Scored 5 FDA-approved drugs NOT in training data", size=12)
    pdf.ln(1)
    pdf.bullet("4 of 5 correctly classified as high-efficacy", size=12)
    pdf.ln(4)

    y_box = pdf.get_y()
    pdf.key_number("Spearman rho", "0.229", 30, y_box, 85, 30)
    pdf.key_number("Mean Abs. Error", "11.3%", 130, y_box, 85, 30)

    pdf.set_xy(18, y_box + 40)
    pdf.ln(2)
    pdf.section_label("Honest Caveat")
    pdf.bullet("Base rate makes this relatively easy to pass", size=11)
    pdf.bullet("This is a sanity check, not proof of predictive power", size=11)
    pdf.bullet("Real validation requires prospective wet-lab experiments", size=11)

    # == Slide 8: Beyond FDA: Harder Tests ====================================
    pdf.new_slide("Beyond FDA: Harder Tests",
                  "Addressing the 'too easy' critique with negative controls")

    pdf.section_label("50-Pattern Hard Benchmark")
    pdf.bullet("8 FDA drugs + 22 academic patterns + 20 negative controls", size=12)
    pdf.ln(2)

    y_box = pdf.get_y()
    pdf.key_number("AUC", "0.88", 18, y_box, 70, 30)
    pdf.key_number("Cohen's d", "1.15", 100, y_box, 70, 30)
    pdf.key_number("Mann-Whitney p", "0.004", 182, y_box, 70, 30)

    pdf.set_xy(18, y_box + 38)
    pdf.ln(2)
    pdf.section_label("At Threshold 75")
    pdf.bullet("", bold_prefix="Precision 87.5%", size=12)
    pdf.bullet("", bold_prefix="Recall 93.3%", size=12)
    pdf.bullet("", bold_prefix="Accuracy 88%", size=12)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*ACCENT_DIM)
    pdf.cell(0, 8, "This is NOT trivially easy.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # == Slide 9: AI-Generated Candidates =====================================
    pdf.new_slide("AI-Generated Candidates",
                  "CVAE generates novel modification patterns")

    pdf.bullet("Conditional generation works as expected:", size=12)
    pdf.ln(2)

    y_box = pdf.get_y()
    pdf.key_number("50% Target", "61 predicted", 30, y_box, 90, 30)
    pdf.key_number("90% Target", "65.7 predicted", 135, y_box, 90, 30)

    # p-value box
    pdf.set_fill_color(*HEADER_BG)
    pdf.set_draw_color(*ACCENT)
    pdf.rect(240, y_box, 50, 30, "FD")
    pdf.set_xy(240, y_box + 5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*HIGHLIGHT)
    pdf.cell(50, 8, "p = 0.011", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_xy(240, y_box + 16)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(50, 6, "significant", align="C")

    pdf.set_xy(18, y_box + 40)
    pdf.ln(2)
    pdf.bullet("95% of generated patterns pass biophysics validation", size=12)
    pdf.ln(1)
    pdf.bullet("100% are genuinely novel (not found in training data)", size=12)

    # == Slide 10: Business Impact ============================================
    pdf.new_slide("Business Impact", "Where the value lies -- now with simulated evidence")

    pdf.section_label("Virtual Wet-Lab Simulation (Monte Carlo, n=10,000)")
    pdf.ln(1)

    y_box = pdf.get_y()
    pdf.key_number("Hit Rate Boost", "1.58x", 18, y_box, 65, 30)
    pdf.key_number("Cost / Hit", "$1,694", 93, y_box, 65, 30)
    pdf.key_number("vs Random", "$2,805", 168, y_box, 65, 30)
    pdf.key_number("Cost Savings", "39.6%", 243, y_box, 65, 30)

    pdf.set_xy(18, y_box + 38)
    pdf.ln(1)
    pdf.bullet("OligoVoid hit rate 84.7% vs random 53.8%", size=12)
    pdf.bullet("Top candidate P(hit) = 94.4% vs 52.9% random", size=12)
    pdf.ln(2)

    pdf.section_label("Market Opportunity")
    pdf.bullet("185 void slots = unclaimed intellectual property territory", size=12)
    pdf.ln(1)
    pdf.bullet("", bold_prefix="RNA therapeutics market: $25B+ by 2030", size=13)

    # == Slide 11: What Needs to Happen Next ==================================
    pdf.new_slide("What Needs to Happen Next", "A clear path to validation")

    steps = [
        ("1", "Proof-of-Concept\nExperiment", "~$10K-$30K",
         "Synthesize + test 10-20\ntop void candidates"),
        ("2", "Validate\nPredictions", "3-5 show >50% knockdown",
         "If hit, value\nproposition is proven"),
        ("3", "Scale", "Platform licensing\nCRO partnerships",
         "Pharma collaborations for\npipeline integration"),
    ]

    card_w = 85
    gap = 10
    total_w = card_w * 3 + gap * 2
    x_start = (pdf.w - total_w) / 2
    y_card = 52

    for i, (num, title, metric, desc) in enumerate(steps):
        x = x_start + i * (card_w + gap)
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_draw_color(*ACCENT)
        pdf.rect(x, y_card, card_w, 75, "FD")

        # step number circle
        pdf.set_fill_color(*ACCENT)
        cx = x + 10
        cy = y_card + 10
        pdf.ellipse(cx - 6, cy - 6, 12, 12, "F")
        pdf.set_xy(cx - 6, cy - 5)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*DARK_BG)
        pdf.cell(12, 10, num, align="C")

        # title
        pdf.set_xy(x + 4, y_card + 22)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*ACCENT)
        pdf.multi_cell(card_w - 8, 7, title, align="C")

        # metric
        pdf.set_xy(x + 4, y_card + 42)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*HIGHLIGHT)
        pdf.multi_cell(card_w - 8, 6, metric, align="C")

        # description
        pdf.set_xy(x + 4, y_card + 57)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.multi_cell(card_w - 8, 6, desc, align="C")

    # == Slide 12: Technical Architecture =====================================
    pdf.new_slide("Technical Architecture", "Open-source, end-to-end platform")

    components = [
        ("Backend", "Python / FastAPI"),
        ("ML Models", "scikit-learn GP (Matern-5/2), PyTorch CVAE"),
        ("Data", "3,527 OligoFormer sequences + 55 curated modification patterns"),
        ("Frontend", "Vanilla JS, 9-tab interactive dashboard"),
        ("License", "MIT License - fully open source"),
    ]

    y_start = 50
    label_w = 50
    val_w = 220

    for i, (label, value) in enumerate(components):
        y = y_start + i * 20

        # label box
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_draw_color(*ACCENT)
        pdf.rect(22, y, label_w, 14, "FD")
        pdf.set_xy(22, y + 2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*ACCENT)
        pdf.cell(label_w, 10, label, align="C")

        # value
        pdf.set_xy(22 + label_w + 8, y + 2)
        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(*BODY_TEXT)
        pdf.cell(val_w, 10, value)

    # == Slide 13: Who This Is For ============================================
    pdf.new_slide("Who This Is For", "Target stakeholders and use cases")

    audiences = [
        ("Pharma / Biotech", "Lead optimization teams\ndesigning siRNA drugs"),
        ("CROs", "Offering modification\nscreening as a service"),
        ("Academics", "Prioritizing grant-funded\nexperiments"),
        ("Investors", "RNA therapeutics is a $25B\nmarket with clear unmet need"),
    ]

    card_w = 62
    gap = 8
    total_w = card_w * 4 + gap * 3
    x_start = (pdf.w - total_w) / 2
    y_card = 54

    for i, (who, what) in enumerate(audiences):
        x = x_start + i * (card_w + gap)
        pdf.set_fill_color(*HEADER_BG)
        pdf.set_draw_color(*ACCENT)
        pdf.rect(x, y_card, card_w, 62, "FD")

        pdf.set_xy(x, y_card + 8)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*ACCENT)
        pdf.cell(card_w, 10, who, align="C",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_xy(x + 4, y_card + 26)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*LIGHT_GRAY)
        pdf.multi_cell(card_w - 8, 6, what, align="C")

    # == Slide 14: Contact ====================================================
    pdf.add_page()
    pdf.slide_number += 1
    pdf.set_fill_color(*DARK_BG)
    pdf.rect(0, 0, pdf.w, pdf.h, "F")

    # accent bar top
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, pdf.w, 3, "F")

    # name
    pdf.set_xy(0, 42)
    pdf.set_font("Helvetica", "B", 32)
    pdf.set_text_color(*ACCENT)
    pdf.cell(pdf.w, 14, "Manas Reddy", align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # separator
    pdf.set_fill_color(*ACCENT_DIM)
    pdf.rect(pdf.w / 2 - 30, 64, 60, 0.8, "F")

    # github
    pdf.set_xy(0, 74)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(*LIGHT_GRAY)
    pdf.cell(pdf.w, 10, "GitHub: github.com/ManasReddy1/OligoVoid",
             align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # quote
    pdf.set_xy(30, 100)
    pdf.set_font("Helvetica", "I", 14)
    pdf.set_text_color(*MID_GRAY)
    quote = ('"The dark matter is real. The map is drawn. '
             'Now someone needs to go explore it."')
    pdf.multi_cell(pdf.w - 60, 9, quote, align="C")

    # footer bar
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, pdf.h - 3, pdf.w, 3, "F")

    # slide number
    pdf.set_xy(pdf.w - 60, pdf.h - 12)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MID_GRAY)
    pdf.cell(50, 6, f"OligoVoid  |  Slide {pdf.slide_number}", align="R")

    # -- Write to disk --------------------------------------------------------
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf.output(OUTPUT_PATH)
    print(f"PDF generated: {OUTPUT_PATH}")
    print(f"Total slides : {pdf.slide_number}")


if __name__ == "__main__":
    build_pdf()
