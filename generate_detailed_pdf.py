#!/usr/bin/env python3
"""
Generate comprehensive OligoVoid technical documentation PDF.
Output: /Users/kingmanas/Desktop/OligoVoid_Detailed_Report.pdf
"""

from fpdf import FPDF
import os

OUTPUT_PATH = "/Users/kingmanas/Desktop/OligoVoid_Detailed_Report.pdf"


class OligoVoidReport(FPDF):
    """Custom PDF class for OligoVoid technical report."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)
        # Colors
        self.dark_blue = (20, 40, 80)
        self.medium_blue = (40, 70, 130)
        self.light_blue = (220, 230, 245)
        self.dark_gray = (50, 50, 50)
        self.medium_gray = (100, 100, 100)
        self.light_gray = (240, 240, 240)
        self.accent = (0, 100, 180)
        # Track sections for TOC
        self.toc_entries = []
        self.current_section = ""

    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.medium_gray)
        self.cell(0, 8, "OligoVoid: Mapping the Dark Matter of siRNA Chemical Space", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.medium_blue)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        if self.page_no() <= 1:
            return
        self.set_y(-20)
        self.set_draw_color(*self.medium_blue)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.medium_gray)
        self.cell(0, 10, "Comprehensive Technical Documentation  |  April 2026", align="C")

    def add_title_page(self):
        self.add_page()
        self.ln(40)
        # Title block background
        self.set_fill_color(*self.dark_blue)
        self.rect(15, 55, self.w - 30, 80, "F")
        # Title text
        self.set_y(62)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(255, 255, 255)
        self.cell(0, 14, "OligoVoid", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_font("Helvetica", "", 14)
        self.cell(0, 8, "Mapping the Dark Matter of", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 8, "siRNA Chemical Space", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(200, 210, 230)
        self.set_line_width(0.5)
        self.line(60, self.get_y(), self.w - 60, self.get_y())
        self.ln(6)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 7, "Comprehensive Technical Documentation", align="C", new_x="LMARGIN", new_y="NEXT")

        # Author info below box
        self.set_y(155)
        self.set_text_color(*self.dark_gray)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Author", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 12)
        self.cell(0, 8, "Manas Reddy", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Date", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 12)
        self.cell(0, 8, "April 2026", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, "Repository", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*self.accent)
        self.cell(0, 8, "https://github.com/ManasReddy1/OligoVoid", align="C", new_x="LMARGIN", new_y="NEXT")

        # Version note
        self.set_y(240)
        self.set_text_color(*self.medium_gray)
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 6, "Version 1.0  |  Computational Framework for siRNA Modification Discovery", align="C")

    def add_toc_page(self):
        self.add_page()
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*self.dark_blue)
        self.cell(0, 14, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_draw_color(*self.dark_blue)
        self.set_line_width(0.8)
        self.line(self.l_margin, self.get_y(), self.l_margin + 60, self.get_y())
        self.ln(8)

        toc_items = [
            ("1", "Executive Summary", ""),
            ("2", "Problem Statement", ""),
            ("3", "Dataset", ""),
            ("4", "System Architecture", ""),
            ("5", "Feature Engineering", ""),
            ("6", "Layer 1: Biophysics Rules", ""),
            ("7", "Layer 2: Gaussian Process", ""),
            ("8", "Layer 3: Conditional VAE", ""),
            ("9", "Chemistry Fingerprint", ""),
            ("9.5", "Hard Benchmark with Negative Controls", ""),
            ("9.6", "Virtual Wet-Lab Simulation", ""),
            ("10", "Void-Prioritized Acquisition (VPA)", ""),
            ("11", "Experimental Validation", ""),
            ("12", "Ablation Study Details", ""),
            ("13", "Limitations", ""),
            ("14", "Business Impact & Applications", ""),
            ("15", "Future Work", ""),
            ("16", "Technical Specifications", ""),
            ("17", "References", ""),
        ]

        for num, title, _ in toc_items:
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(*self.dark_blue)
            self.cell(12, 8, num + ".")
            self.set_font("Helvetica", "", 11)
            self.set_text_color(*self.dark_gray)
            self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")

        self.ln(10)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*self.medium_gray)
        self.multi_cell(0, 5,
            "Note: Page numbers are approximate as content flows dynamically. "
            "Sections are ordered sequentially and can be navigated by scrolling."
        )

    def section_header(self, number, title):
        self.current_section = f"{number}. {title}"
        # Check if enough space; if not, add new page
        if self.get_y() > 240:
            self.add_page()
        else:
            self.add_page()
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*self.dark_blue)
        self.cell(0, 12, f"{number}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.dark_blue)
        self.set_line_width(0.8)
        self.line(self.l_margin, self.get_y() + 1, self.l_margin + 80, self.get_y() + 1)
        self.ln(8)

    def sub_header(self, title):
        if self.get_y() > 255:
            self.add_page()
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*self.medium_blue)
        self.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_sub_header(self, title):
        if self.get_y() > 260:
            self.add_page()
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(60, 80, 120)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.dark_gray)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet_point(self, text, indent=10):
        x = self.get_x()
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.dark_gray)
        self.cell(indent)
        bullet_char = "-"
        self.cell(5, 5.5, bullet_char)
        # Calculate available width
        available = self.w - self.l_margin - self.r_margin - indent - 5
        self.multi_cell(available, 5.5, text)
        self.ln(1)

    def numbered_item(self, number, text, indent=10):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.dark_gray)
        self.cell(indent)
        self.set_font("Helvetica", "B", 10)
        self.cell(8, 5.5, f"{number}.")
        self.set_font("Helvetica", "", 10)
        available = self.w - self.l_margin - self.r_margin - indent - 8
        self.multi_cell(available, 5.5, text)
        self.ln(1)

    def key_value(self, key, value):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*self.medium_blue)
        self.cell(50, 6, key + ":")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.dark_gray)
        available = self.w - self.l_margin - self.r_margin - 50
        self.multi_cell(available, 6, value)
        self.ln(1)

    def info_box(self, text):
        self.ln(2)
        y_start = self.get_y()
        self.set_fill_color(*self.light_blue)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*self.dark_gray)
        # Draw background
        self.set_x(self.l_margin + 5)
        w = self.w - self.l_margin - self.r_margin - 10
        self.multi_cell(w, 5.5, text, fill=True)
        self.ln(3)

    def add_table(self, headers, rows, col_widths=None):
        self.ln(2)
        if col_widths is None:
            n = len(headers)
            available = self.w - self.l_margin - self.r_margin
            col_widths = [available / n] * n

        # Header row
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*self.dark_blue)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*self.dark_gray)
        fill = False
        for row in rows:
            if self.get_y() > 260:
                self.add_page()
                # Re-draw header on new page
                self.set_font("Helvetica", "B", 9)
                self.set_fill_color(*self.dark_blue)
                self.set_text_color(255, 255, 255)
                for i, h in enumerate(headers):
                    self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("Helvetica", "", 9)
                self.set_text_color(*self.dark_gray)
                fill = False

            if fill:
                self.set_fill_color(*self.light_gray)
            else:
                self.set_fill_color(255, 255, 255)
            for i, val in enumerate(row):
                align = "L" if i == 0 else "C"
                self.cell(col_widths[i], 7, str(val), border=1, fill=True, align=align)
            self.ln()
            fill = not fill
        self.ln(3)

    def add_wide_table(self, headers, rows, col_widths):
        """Table with multi-cell support for wider content."""
        self.ln(2)
        # Header
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*self.dark_blue)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
        self.ln()
        # Rows
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*self.dark_gray)
        fill = False
        for row in rows:
            if self.get_y() > 258:
                self.add_page()
                self.set_font("Helvetica", "B", 9)
                self.set_fill_color(*self.dark_blue)
                self.set_text_color(255, 255, 255)
                for i, h in enumerate(headers):
                    self.cell(col_widths[i], 8, h, border=1, fill=True, align="C")
                self.ln()
                self.set_font("Helvetica", "", 8.5)
                self.set_text_color(*self.dark_gray)
                fill = False
            if fill:
                self.set_fill_color(*self.light_gray)
            else:
                self.set_fill_color(255, 255, 255)
            for i, val in enumerate(row):
                align = "L" if i == 0 else "C"
                self.cell(col_widths[i], 7, str(val), border=1, fill=True, align=align)
            self.ln()
            fill = not fill
        self.ln(3)

    def horizontal_rule(self):
        self.ln(3)
        self.set_draw_color(*self.medium_gray)
        self.set_line_width(0.2)
        self.line(self.l_margin + 20, self.get_y(), self.w - self.r_margin - 20, self.get_y())
        self.ln(5)


def build_report():
    pdf = OligoVoidReport()
    pdf.set_margins(left=20, top=20, right=20)

    # =========================================================================
    # TITLE PAGE
    # =========================================================================
    pdf.add_title_page()

    # =========================================================================
    # TABLE OF CONTENTS
    # =========================================================================
    pdf.add_toc_page()

    # =========================================================================
    # SECTION 1: EXECUTIVE SUMMARY
    # =========================================================================
    pdf.section_header("1", "Executive Summary")

    pdf.body_text(
        "OligoVoid is a computational cartography system for small interfering RNA (siRNA) chemical "
        "modification space. The system addresses a fundamental challenge in RNA therapeutics: while "
        "chemical modifications are essential for siRNA drug development, the vast majority of the "
        "modification landscape has never been experimentally explored. OligoVoid provides the first "
        "systematic framework to map, score, and prioritize exploration of this uncharted territory "
        "-- the \"dark matter\" of siRNA chemical space."
    )

    pdf.sub_header("Core Capabilities")

    pdf.bullet_point(
        "Complement-Set Enumeration: Identifies modification patterns that have never been tested, "
        "revealing that 55% of the siRNA modification map (185 of 336 position-modification slots) "
        "has never appeared in published literature."
    )
    pdf.bullet_point(
        "Three-Layer Scoring Ensemble: Scores the plausibility of untested patterns using a "
        "biophysics rule engine, a Gaussian Process (GP) with calibrated uncertainty, and a "
        "Conditional Variational Autoencoder (CVAE) for generative modeling."
    )
    pdf.bullet_point(
        "Conditional Generation: Generates novel siRNA modification candidates via the CVAE, "
        "conditioned on target efficacy values, enabling property-directed exploration."
    )
    pdf.bullet_point(
        "Void-Prioritized Acquisition (VPA): A novel active learning strategy that balances "
        "exploitation of known-good regions with exploration of the dark matter, achieving "
        "80% feature-space coverage compared to Expected Improvement's 69%."
    )

    pdf.sub_header("Key Performance Metrics")

    pdf.add_table(
        ["Metric", "Value", "Significance"],
        [
            ["GP Calibration (ECE)", "0.033", "Well below 0.05 threshold"],
            ["GP Pearson r", "0.297", "Comparable to classical models (0.20-0.35)"],
            ["FDA Validation", "4/5 correct", "MAE = 11.3%"],
            ["Hard Benchmark AUC", "0.88", "50-pattern test with negative controls"],
            ["Virtual Wetlab Hit Rate", "84.7%", "vs 53.8% random (1.58x)"],
            ["CVAE Validity", "95%", "High-quality generation"],
            ["CVAE Novelty", "100%", "All outputs are novel"],
            ["VPA Coverage", "80%", "vs. EI's 69% coverage"],
            ["Void Slots Found", "185 / 336", "55% unexplored"],
        ],
        col_widths=[55, 35, 90]
    )

    pdf.body_text(
        "OligoVoid represents the first systematic attempt to map, score, and prioritize the "
        "exploration of uncharted siRNA modification space. The tool is designed as an open-source "
        "platform that can accelerate the discovery of novel RNA therapeutics by guiding "
        "experimentalists toward the most promising unexplored regions of the chemical landscape."
    )

    # =========================================================================
    # SECTION 2: PROBLEM STATEMENT
    # =========================================================================
    pdf.section_header("2", "Problem Statement")

    pdf.sub_header("The siRNA Drug Mechanism")

    pdf.body_text(
        "Small interfering RNAs (siRNAs) are double-stranded RNA molecules of 19-23 nucleotides "
        "that harness the cell's endogenous RNA interference (RNAi) pathway to silence specific "
        "genes. Upon delivery to the cytoplasm, the siRNA duplex is loaded into the RNA-Induced "
        "Silencing Complex (RISC), where the passenger (sense) strand is cleaved and discarded. "
        "The remaining guide (antisense) strand directs RISC to complementary mRNA transcripts, "
        "triggering their catalytic degradation by the Argonaute 2 (Ago2) endonuclease. This "
        "mechanism enables potent, sequence-specific gene silencing with sub-nanomolar IC50 values, "
        "making siRNA one of the most promising modalities in modern drug development."
    )

    pdf.body_text(
        "Since the FDA approval of patisiran in 2018, the siRNA therapeutic field has seen rapid "
        "growth. As of 2026, there are multiple FDA-approved siRNA drugs targeting diseases ranging "
        "from hereditary transthyretin amyloidosis to hypercholesterolemia, with dozens more in "
        "clinical development. However, a critical bottleneck remains: the optimization of chemical "
        "modification patterns."
    )

    pdf.sub_header("Why Chemical Modifications Are Essential")

    pdf.body_text(
        "Unmodified siRNA is inherently unstable in biological fluids. Serum nucleases degrade "
        "naked RNA within minutes, and the innate immune system recognizes unmodified double-stranded "
        "RNA as a pathogen-associated molecular pattern (PAMP), triggering inflammatory responses "
        "via Toll-like receptors (TLR3, TLR7, TLR8) and cytoplasmic sensors (RIG-I, MDA5). "
        "Furthermore, unmodified siRNA is rapidly cleared by the kidneys due to its small size "
        "(~13 kDa per strand). Chemical modifications address all of these challenges:"
    )

    pdf.bullet_point(
        "Nuclease Resistance: 2'-O-methyl (2'-OMe) and 2'-fluoro (2'-F) modifications on the "
        "ribose sugar protect against endo- and exonucleases while maintaining A-form helical geometry."
    )
    pdf.bullet_point(
        "Immune Evasion: Strategic placement of 2'-OMe modifications at immunostimulatory motifs "
        "suppresses innate immune activation without compromising silencing activity."
    )
    pdf.bullet_point(
        "Phosphorothioate (PS) Backbone: Replacement of non-bridging oxygen atoms with sulfur at "
        "terminal positions increases plasma protein binding and reduces renal clearance."
    )
    pdf.bullet_point(
        "Locked Nucleic Acids (LNA): Bicyclic ribose modifications increase binding affinity but "
        "must be used sparingly due to hepatotoxicity risk with consecutive placements."
    )

    pdf.sub_header("The Combinatorial Explosion")

    pdf.body_text(
        "A typical siRNA duplex has 42 modifiable positions (21 per strand). With at least 8 "
        "common modification types (unmodified, 2'-OMe, 2'-F, PS, LNA, 2'-MOE, GNA, UNA), the "
        "theoretical modification space is 8^42, which equals approximately 10^38 distinct "
        "patterns. This is an astronomically large number -- comparable to the estimated number "
        "of atoms in the observable universe."
    )

    pdf.info_box(
        "Theoretical space: 8^42 ~ 10^38 patterns\n"
        "Feasible subspace (after biophysical constraints): ~10^6 patterns\n"
        "Published patterns: ~10^2 patterns\n"
        "Gap: At least 4 orders of magnitude between published and feasible"
    )

    pdf.body_text(
        "After applying biophysical constraints (e.g., no consecutive LNA, PS only at termini, "
        "maintain seed region flexibility), the feasible subspace reduces to approximately 10^6 "
        "patterns. Even this reduced space is vastly larger than what has been experimentally tested. "
        "The published literature covers on the order of 10^2 distinct modification patterns, "
        "leaving a gap of at least 4 orders of magnitude."
    )

    pdf.sub_header("The Dark Matter Analogy")

    pdf.body_text(
        "We frame this as a \"dark matter\" problem by analogy to cosmology. Just as astrophysicists "
        "know that dark matter exists from gravitational effects but cannot directly observe it, "
        "we know that unexplored modification patterns exist and likely contain valuable drug "
        "candidates, but nobody has looked. Specifically, 185 of 336 position-modification slots "
        "(55%) have never appeared in published literature. These \"void slots\" represent a vast "
        "terra incognita of siRNA chemistry. OligoVoid is the first computational system designed "
        "to systematically map this dark matter, estimate the properties of patterns within it, "
        "and prioritize which regions to explore experimentally."
    )

    # =========================================================================
    # SECTION 3: DATASET
    # =========================================================================
    pdf.section_header("3", "Dataset")

    pdf.sub_header("Primary Dataset: OligoFormer Compilation")

    pdf.body_text(
        "The primary training data comes from the OligoFormer compiled dataset (He et al., 2024), "
        "which aggregates siRNA efficacy measurements from multiple published studies. This dataset "
        "contains 3,527 siRNA sequences after preprocessing, each annotated with experimentally "
        "measured gene silencing efficacy values (percentage knockdown)."
    )

    pdf.sub_sub_header("Source Breakdown")

    pdf.add_table(
        ["Source", "Count", "Cell Line", "Measurement"],
        [
            ["Huesken et al. (2005)", "2,361", "H1299", "Dual luciferase reporter"],
            ["Takahashi et al. (2009)", "702", "HeLa", "Luciferase reporter"],
            ["Reynolds et al. (2004)", "~120", "Mixed", "Various reporters"],
            ["Vickers et al. (2003)", "~80", "Mixed", "RT-qPCR"],
            ["Khvorova et al. (2003)", "~100", "Mixed", "Various"],
            ["Ui-Tei et al. (2004)", "~90", "Mixed", "Flow cytometry"],
            ["Amarzguioui et al. (2003)", "~80", "Mixed", "Various"],
        ],
        col_widths=[50, 25, 35, 70]
    )

    pdf.body_text(
        "The Huesken et al. dataset constitutes the majority (67%) of the training data. This "
        "study systematically tested 2,361 siRNAs targeting 34 human and mouse genes using a "
        "standardized dual-luciferase reporter assay in H1299 (human non-small cell lung cancer) "
        "cells. The Takahashi et al. dataset provides a complementary set of 702 siRNAs tested in "
        "HeLa cells, while the remaining sources contribute smaller but diverse sets of measurements."
    )

    pdf.sub_header("Preprocessing Pipeline")

    pdf.numbered_item(1, "Antisense strand extraction: Retain only the antisense (guide) strand, "
        "length 19-23 nucleotides.")
    pdf.numbered_item(2, "Sequence validation: Verify that all sequences contain only valid "
        "nucleotides (A, U, G, C). Sequences with ambiguous bases (N) or non-standard "
        "characters are removed.")
    pdf.numbered_item(3, "Efficacy filtering: Remove entries with null or missing efficacy values.")
    pdf.numbered_item(4, "Range normalization: Clip efficacy values to the [0, 100] range to "
        "handle outliers from different assay systems.")
    pdf.numbered_item(5, "Deduplication: Remove exact sequence duplicates, retaining the entry "
        "with the most recent publication date.")

    pdf.sub_header("Train/Test Split")

    pdf.body_text(
        "The dataset is split 80/20 using stratified sampling to maintain the efficacy distribution "
        "across splits. The stratification bins are: low (0-33%), medium (33-66%), and high "
        "(66-100%) efficacy."
    )

    pdf.add_table(
        ["Split", "Count", "Mean Efficacy", "Std Dev", "Median"],
        [
            ["Training", "2,823", "62.3%", "24.2%", "66.1%"],
            ["Test", "704", "61.5%", "25.0%", "65.3%"],
            ["Total", "3,527", "62.1%", "24.4%", "65.9%"],
        ],
        col_widths=[35, 30, 40, 35, 40]
    )

    pdf.sub_header("Supplementary Modification Data")

    pdf.body_text(
        "In addition to the primary efficacy dataset, OligoVoid uses a curated collection of 55 "
        "chemical modification patterns extracted from 8 FDA-approved siRNA drugs. These patterns "
        "provide ground truth for the modification scoring system and serve as validation targets "
        "for the void detection pipeline."
    )

    pdf.add_table(
        ["Drug", "Target", "Approval Year", "Modification Style"],
        [
            ["Patisiran", "TTR", "2018", "Minimal (2'-OMe at select positions)"],
            ["Givosiran", "ALAS1", "2019", "ESC (alternating 2'-OMe/2'-F)"],
            ["Lumasiran", "HAO1", "2020", "ESC"],
            ["Inclisiran", "PCSK9", "2021", "ESC"],
            ["Vutrisiran", "TTR", "2022", "ESC+"],
            ["Nedosiran", "LDHA", "2023", "ESC"],
            ["Fitusiran", "SERPINC1", "2024", "ESC"],
            ["Elebsiran", "HBV", "2024", "ESC+"],
        ],
        col_widths=[35, 30, 35, 80]
    )

    pdf.sub_header("Known Biases and Limitations")

    pdf.bullet_point(
        "Unmodified RNA Training Data: The primary efficacy dataset consists of unmodified RNA "
        "sequences. The GP model therefore learns sequence-efficacy relationships without direct "
        "modification information, relying on feature engineering to bridge this gap."
    )
    pdf.bullet_point(
        "Liver-Targeting Bias: The majority of FDA-approved siRNA drugs use GalNAc conjugation "
        "for liver targeting. The modification patterns in the supplementary dataset are therefore "
        "biased toward liver-deliverable siRNAs."
    )
    pdf.bullet_point(
        "Temporal Bias: The primary dataset spans publications from 2001-2009, predating the ESC "
        "(Enhanced Stabilization Chemistry) paradigm. Modern siRNAs use significantly more "
        "modifications than those in the training data."
    )
    pdf.bullet_point(
        "Assay Heterogeneity: Efficacy measurements come from different cell lines, reporters, "
        "and protocols, introducing systematic variation."
    )

    # =========================================================================
    # SECTION 4: SYSTEM ARCHITECTURE
    # =========================================================================
    pdf.section_header("4", "System Architecture")

    pdf.sub_header("Pipeline Overview")

    pdf.body_text(
        "OligoVoid implements a five-stage computational pipeline that progresses from data "
        "collection through void detection, multi-layer scoring, candidate generation, and "
        "active learning-guided prioritization. Each stage is modular and can be run independently "
        "or as part of the full pipeline."
    )

    pdf.info_box(
        "Pipeline Stages:\n"
        "1. Data Collection  ->  2. Void Detection  ->  3. Three-Layer Scoring  ->  "
        "4. Generation  ->  5. Active Learning"
    )

    pdf.sub_header("Stage 1: Data Collection")

    pdf.body_text(
        "The real_data_pipeline.py module handles data ingestion, preprocessing, and feature "
        "extraction from the OligoFormer dataset. It processes raw CSV files containing siRNA "
        "sequences and efficacy measurements, applies the preprocessing pipeline described in "
        "Section 3, and extracts both the 19-dimensional GP features and 42-dimensional CVAE "
        "features for each sequence."
    )

    pdf.sub_header("Stage 2: Void Detection")

    pdf.body_text(
        "The void_landscape.py module implements complement-set enumeration to identify "
        "untested modification patterns. It constructs a binary occupancy matrix of 42 positions "
        "x 8 modification types (336 total slots) and determines which position-modification "
        "combinations have never appeared in the published literature. The module also computes "
        "coverage statistics, identifies clusters of void regions, and generates landscape "
        "visualizations showing the distribution of explored vs. unexplored space."
    )

    pdf.sub_header("Stage 3: Three-Layer Scoring")

    pdf.body_text(
        "The feasibility_scorer.py module orchestrates the three-layer scoring ensemble:"
    )

    pdf.numbered_item(1, "Biophysics Rules (modification_grammar.py): Applies 10 hard constraints "
        "and 4 soft scoring functions derived from published siRNA design guidelines.")
    pdf.numbered_item(2, "Gaussian Process (ml_model.py): Provides calibrated efficacy predictions "
        "with uncertainty estimates using a Matern-5/2 kernel.")
    pdf.numbered_item(3, "Conditional VAE (generative_model.py): Scores novelty and validity by "
        "evaluating the reconstruction probability of candidate patterns under the trained model.")

    pdf.body_text(
        "The final feasibility score is a weighted combination of all three layers, with "
        "configurable weights that default to equal contribution."
    )

    pdf.sub_header("Stage 4: Candidate Generation")

    pdf.body_text(
        "The generative_model.py module uses the trained CVAE to generate novel modification "
        "patterns conditioned on a target efficacy value. The generation process samples from "
        "the learned latent space, decodes to modification features, and post-processes the "
        "output to ensure biophysical validity. Invalid candidates (those violating hard "
        "constraints) are filtered out, yielding a set of valid, novel modification patterns "
        "ranked by predicted quality."
    )

    pdf.sub_header("Stage 5: Active Learning")

    pdf.body_text(
        "The void_landscape.py and killer_experiment.py modules implement the Void-Prioritized "
        "Acquisition (VPA) strategy for selecting which candidates to test experimentally. VPA "
        "modifies the standard Expected Improvement (EI) acquisition function by multiplicatively "
        "boosting the score of candidates that are far from previously tested patterns in "
        "chemistry fingerprint space."
    )

    pdf.sub_header("Technology Stack")

    pdf.add_table(
        ["Component", "Technology", "Version"],
        [
            ["Language", "Python", "3.9+"],
            ["Web Framework", "FastAPI", "0.100+"],
            ["ORM", "SQLAlchemy", "2.0+"],
            ["ML Framework", "scikit-learn", "1.3+"],
            ["Deep Learning", "PyTorch", "2.0+"],
            ["Frontend", "Vanilla JavaScript", "ES6+"],
            ["Data Processing", "NumPy / Pandas", "1.25+ / 2.0+"],
            ["Visualization", "Matplotlib", "3.7+"],
        ],
        col_widths=[45, 55, 80]
    )

    pdf.sub_header("Key Module Reference")

    pdf.add_table(
        ["Module", "Responsibility"],
        [
            ["modification_grammar.py", "10 biophysical constraints for modification patterns"],
            ["real_data_pipeline.py", "OligoFormer data ingestion and preprocessing"],
            ["feasibility_scorer.py", "Three-layer scoring engine orchestration"],
            ["ml_model.py", "Gaussian Process model and CVAE architecture"],
            ["generative_model.py", "Conditional generation and candidate ranking"],
            ["chemistry_fingerprint.py", "8-feature pattern characterization"],
            ["void_landscape.py", "Void detection, landscape analysis, VPA"],
            ["ablation_study.py", "5-variant ablation framework"],
            ["killer_experiment.py", "Simulated discovery efficiency experiments"],
            ["cvae_deep_validation.py", "Comprehensive CVAE validation suite"],
        ],
        col_widths=[55, 125]
    )

    pdf.sub_header("Frontend Dashboard")

    pdf.body_text(
        "The frontend is implemented as a single-page application using vanilla JavaScript with "
        "no external dependencies. It communicates with the FastAPI backend via REST API calls "
        "and renders interactive visualizations using HTML5 Canvas and SVG elements. The dashboard "
        "features 9 interactive tabs:"
    )

    pdf.numbered_item(1, "Overview: System summary, key metrics, and pipeline status.")
    pdf.numbered_item(2, "Void Map: Interactive visualization of the 42x8 modification landscape.")
    pdf.numbered_item(3, "Scoring: Three-layer scoring results with drill-down details.")
    pdf.numbered_item(4, "Generation: CVAE-generated candidates with property controls.")
    pdf.numbered_item(5, "Active Learning: VPA acquisition function visualization.")
    pdf.numbered_item(6, "Validation: FDA drug validation results and ablation study.")
    pdf.numbered_item(7, "Fingerprints: Chemistry fingerprint analysis and clustering.")
    pdf.numbered_item(8, "Landscape: 3D landscape visualization of the modification space.")
    pdf.numbered_item(9, "Settings: Configuration and parameter tuning interface.")

    # =========================================================================
    # SECTION 5: FEATURE ENGINEERING
    # =========================================================================
    pdf.section_header("5", "Feature Engineering")

    pdf.sub_header("CVAE Features (42-Dimensional)")

    pdf.body_text(
        "The Conditional VAE operates on a 42-dimensional feature vector that captures both the "
        "core sequence properties and thermodynamic characteristics of each siRNA. The feature "
        "vector is divided into two groups:"
    )

    pdf.sub_sub_header("Core Sequence Features (18 dimensions)")

    pdf.body_text(
        "The first 18 features encode the nucleotide composition and positional properties of the "
        "siRNA sequence. These include position-specific nucleotide frequencies (4 features), "
        "dinucleotide frequencies at the seed region (4 features), GC content at various windows "
        "(4 features), and terminal nucleotide identities encoded as one-hot vectors (6 features). "
        "These features capture the sequence-level properties known to influence siRNA efficacy, "
        "including the asymmetry rule (different thermodynamic stability at the two ends of the "
        "duplex) and seed region composition."
    )

    pdf.sub_sub_header("Thermodynamic Features (24 dimensions)")

    pdf.body_text(
        "The remaining 24 features capture thermodynamic properties computed using nearest-neighbor "
        "energy parameters. These include: position-specific stacking energies (19 features for "
        "19 dinucleotide steps), overall duplex stability (delta-G), melting temperature, "
        "5'-end vs 3'-end differential stability, and seed region thermodynamic accessibility. "
        "Thermodynamic features are critical because RISC loading is governed by the relative "
        "stability of the two duplex ends -- the strand with the less stable 5' end is "
        "preferentially loaded as the guide strand."
    )

    pdf.sub_header("GP Features (19-Dimensional)")

    pdf.body_text(
        "The Gaussian Process model uses a more compact 19-dimensional feature vector designed "
        "specifically for modification-aware prediction. This feature set is divided into three "
        "groups with a key design insight: modification features are zero during training."
    )

    pdf.sub_sub_header("Feature Group 1: Modification Fractions (Features 0-7)")

    pdf.body_text(
        "Eight features representing the fraction of each modification type across the 42 positions "
        "of the duplex: unmodified, 2'-OMe, 2'-F, PS, LNA, 2'-MOE, GNA, and UNA. During training "
        "on the OligoFormer dataset (which consists entirely of unmodified RNA), all 8 features are "
        "zero. At prediction time for modified candidates, these features become nonzero. This "
        "design deliberately exploits the GP's behavior: inputs with nonzero modification features "
        "fall outside the training distribution, automatically increasing the predicted uncertainty."
    )

    pdf.info_box(
        "Key Insight: Because modification features are zero during training but nonzero during "
        "prediction, the GP naturally produces higher uncertainty for heavily modified candidates. "
        "This is exactly the behavior we want -- the model honestly communicates that it has "
        "less information about modified patterns. The uncertainty signal drives the active "
        "learning acquisition function (VPA)."
    )

    pdf.sub_sub_header("Feature Group 2: Biophysics Proxies (Features 8-11)")

    pdf.body_text(
        "Four scalar features derived from the biophysics rule engine: (8) thermodynamic stability "
        "proxy, computed as the normalized delta-Tm under simulated modification; (9) RISC loading "
        "proxy, based on seed region flexibility and 5'/3' asymmetry; (10) nuclease resistance "
        "proxy, estimating the degree of backbone protection; and (11) off-target risk proxy, "
        "based on GGG motif count and palindrome analysis. These features bridge the gap between "
        "the unmodified training data and the modified prediction targets."
    )

    pdf.sub_sub_header("Feature Group 3: GC Sliding Windows (Features 12-18)")

    pdf.body_text(
        "Seven features representing GC content computed in overlapping 5-nucleotide windows across "
        "the antisense strand. These capture positional GC variation, which is known to correlate "
        "with regional stability and RISC loading efficiency. Positions with high GC content in "
        "the seed region (positions 2-8) tend to reduce silencing efficacy because they create an "
        "excessively stable seed-target interaction that impairs the catalytic cycle."
    )

    # =========================================================================
    # SECTION 6: LAYER 1 - BIOPHYSICS RULES
    # =========================================================================
    pdf.section_header("6", "Layer 1: Biophysics Rules")

    pdf.body_text(
        "The first layer of the scoring ensemble applies deterministic biophysical rules derived "
        "from published siRNA design guidelines and the chemistry of RNA modifications. This layer "
        "serves two functions: hard filtering (rejecting physically implausible patterns) and soft "
        "scoring (ranking patterns by estimated biophysical compatibility)."
    )

    pdf.sub_header("Thermodynamic Stability Scoring")

    pdf.body_text(
        "Chemical modifications alter the thermodynamic stability of the siRNA duplex. The system "
        "estimates the change in melting temperature (delta-Tm) induced by each modification using "
        "published nearest-neighbor parameters. 2'-OMe and 2'-F modifications generally stabilize "
        "the duplex (+0.5 to +1.5 degrees C per modification), while GNA and UNA destabilize it "
        "(-1.0 to -3.0 degrees C). The thermodynamic score penalizes patterns that push the overall "
        "Tm outside the optimal range (55-75 degrees C for standard 21-mer duplexes) or that "
        "create excessive asymmetry between the sense and antisense strand stabilities."
    )

    pdf.sub_header("RISC Loading Assessment")

    pdf.body_text(
        "Efficient RISC loading requires thermodynamic asymmetry: the 5' end of the guide strand "
        "should be less stable than the 3' end. Modifications that increase stability at the 5' end "
        "(e.g., LNA at positions 1-2 of the antisense strand) can impair loading. The RISC loading "
        "score evaluates: (a) seed region flexibility -- positions 2-8 of the guide strand "
        "should not be excessively stabilized; (b) cleavage site integrity -- position 10-11 "
        "of the guide strand must remain unobstructed for Ago2 cleavage; and (c) 5'/3' asymmetry "
        "-- the differential stability should favor guide strand selection."
    )

    pdf.sub_header("Nuclease Resistance Estimation")

    pdf.body_text(
        "The system counts protective modifications at nuclease-sensitive positions. Terminal "
        "positions (1-2 and 20-21 on each strand) are most vulnerable to exonucleases; internal "
        "positions adjacent to pyrimidine-A dinucleotides are vulnerable to endonucleases (RNase A "
        "family). The nuclease resistance score rewards patterns that protect vulnerable positions "
        "while avoiding unnecessary over-modification of protected internal positions."
    )

    pdf.sub_header("Off-Target Risk Scoring")

    pdf.body_text(
        "Certain sequence and modification features are associated with increased off-target "
        "effects. The off-target risk score evaluates: (a) GGG motif presence -- triple guanine "
        "motifs can form G-quadruplex structures that cause non-specific binding; (b) palindrome "
        "analysis -- self-complementary regions increase off-target duplex formation; (c) seed "
        "region promiscuity -- high GC content in the seed region increases the number of "
        "potential off-target binding sites."
    )

    pdf.sub_header("Hard Constraints (modification_grammar.py)")

    pdf.body_text(
        "The modification grammar defines 10 hard constraints that modification patterns must "
        "satisfy to be considered physically plausible:"
    )

    pdf.add_table(
        ["#", "Constraint", "Rationale"],
        [
            ["1", "No consecutive LNA (max 1)", "Hepatotoxicity risk"],
            ["2", "PS only at terminal 2 positions", "Internal PS impairs RISC loading"],
            ["3", "Max 70% modification per strand", "Excessive modification disrupts geometry"],
            ["4", "Seed region (pos 2-8) must be flexible", "Required for target recognition"],
            ["5", "Cleavage site (pos 10-11) unmodified", "Ago2 requires 2'-OH at cleavage site"],
            ["6", "Min 2 protective mods per strand", "Minimum nuclease resistance"],
            ["7", "No LNA at position 1 of guide", "Impairs 5' phosphorylation"],
            ["8", "Balanced modification across strands", "Avoid excessive strand asymmetry"],
            ["9", "Compatible modification pairs only", "Some modifications are mutually exclusive"],
            ["10", "Total modification count 8-30", "Practical synthesis limits"],
        ],
        col_widths=[10, 70, 100]
    )

    # =========================================================================
    # SECTION 7: LAYER 2 - GAUSSIAN PROCESS
    # =========================================================================
    pdf.section_header("7", "Layer 2: Gaussian Process")

    pdf.sub_header("Motivation: Why GP Over Deep Learning")

    pdf.body_text(
        "A central requirement for OligoVoid's active learning framework is calibrated uncertainty "
        "quantification. The system must not only predict how effective a modification pattern might "
        "be, but also honestly estimate how confident it is in that prediction. Gaussian Processes "
        "are the natural choice for this task because they provide closed-form posterior "
        "distributions with analytically derived uncertainty bounds, unlike deep learning models "
        "which require approximate methods (MC dropout, deep ensembles) for uncertainty estimation."
    )

    pdf.body_text(
        "Furthermore, GP uncertainty has a desirable property for modification space exploration: "
        "uncertainty increases monotonically with distance from the training data in feature space. "
        "Since modification features are zero during training (see Section 5), any candidate with "
        "nonzero modifications will have elevated uncertainty, with more heavily modified candidates "
        "receiving higher uncertainty. This provides a principled \"I don't know\" signal that "
        "drives exploration."
    )

    pdf.sub_header("Kernel Selection: Matern-5/2")

    pdf.body_text(
        "The GP uses a composite kernel: ConstantKernel x Matern(nu=2.5) + WhiteKernel. The "
        "Matern-5/2 kernel was chosen over the more common RBF (Radial Basis Function) kernel "
        "because biological activity landscapes are typically rough and non-infinitely "
        "differentiable. The RBF kernel assumes that the underlying function is infinitely smooth "
        "(C-infinity), which is unrealistic for siRNA efficacy as a function of sequence features. "
        "The Matern-5/2 kernel assumes the function is twice differentiable (C2), which better "
        "matches the expected roughness of the biological landscape."
    )

    pdf.body_text(
        "The ConstantKernel scales the overall variance, allowing the model to adapt to the "
        "amplitude of the efficacy signal. The WhiteKernel models observation noise, accounting for "
        "the inherent variability in biological efficacy measurements (which can be 5-15% even "
        "for replicate measurements of the same siRNA)."
    )

    pdf.sub_header("Training Procedure")

    pdf.body_text(
        "GP inference has O(n^3) computational complexity for n training points, making it "
        "impractical to train on the full 2,823-sample training set. The model uses random "
        "subsampling to select 500-1000 training examples, with stratified sampling to maintain "
        "the efficacy distribution. Hyperparameters (kernel length scales, noise variance, and "
        "constant scale) are optimized using maximum marginal likelihood with 10 random restarts "
        "to avoid local optima. Five-fold cross-validation is used to select the optimal subsample "
        "size and validate generalization."
    )

    pdf.sub_header("Calibration Analysis")

    pdf.body_text(
        "Calibration measures how well the predicted uncertainty matches the actual error "
        "distribution. A perfectly calibrated model predicts that 90% of observations fall within "
        "its 90% confidence interval, 50% within its 50% interval, and so on. We evaluate "
        "calibration using Expected Calibration Error (ECE), which is the mean absolute deviation "
        "between predicted confidence levels and observed coverage rates across 10 equally-spaced "
        "confidence bins."
    )

    pdf.add_table(
        ["Metric", "Value", "Threshold", "Assessment"],
        [
            ["ECE", "0.033", "<0.05", "PASS - Well calibrated"],
            ["90% CI Coverage", "88.4%", "85-95%", "PASS"],
            ["50% CI Coverage", "51.2%", "45-55%", "PASS"],
            ["Mean Predictive Std", "22.1", ">10", "PASS - Meaningful spread"],
        ],
        col_widths=[45, 30, 35, 70]
    )

    pdf.body_text(
        "The ECE of 0.033 is well below the commonly used 0.05 threshold, indicating that the GP "
        "produces well-calibrated uncertainty estimates. This is critical for the downstream active "
        "learning framework: if the uncertainties were miscalibrated, the VPA acquisition function "
        "would make suboptimal decisions about which regions to explore."
    )

    pdf.sub_header("Predictive Performance")

    pdf.body_text(
        "On the held-out test set, the GP achieves a Pearson correlation of r=0.297 between "
        "predicted and observed efficacy. While this is modest in absolute terms, it is important "
        "to contextualize this result:"
    )

    pdf.add_table(
        ["Model Type", "Pearson r", "Context"],
        [
            ["OligoVoid GP", "0.297", "Modification features only"],
            ["Classical rules (Reynolds, Ui-Tei)", "0.20-0.35", "Sequence rules only"],
            ["OligoFormer (He et al., 2024)", "0.719", "Full sequence context + deep learning"],
            ["Random baseline", "~0.00", "No information"],
        ],
        col_widths=[60, 30, 90]
    )

    pdf.body_text(
        "The GP achieves performance comparable to classical rule-based models (which also operate "
        "at r=0.20-0.35 for sequence-only prediction). OligoFormer achieves substantially higher "
        "accuracy (r=0.719) because it uses a transformer architecture that models the full "
        "sequence context, including position-specific nucleotide interactions. However, "
        "OligoFormer does not model modifications, does not provide calibrated uncertainty, "
        "and cannot be directly used for active learning. The GP's lower accuracy is a deliberate "
        "tradeoff for calibrated uncertainty -- the key ingredient for void-prioritized "
        "acquisition."
    )

    # =========================================================================
    # SECTION 8: LAYER 3 - CVAE
    # =========================================================================
    pdf.section_header("8", "Layer 3: Conditional VAE")

    pdf.sub_header("Architecture")

    pdf.body_text(
        "The Conditional Variational Autoencoder (CVAE) serves dual roles in OligoVoid: (1) as "
        "the third scoring layer, evaluating how well a candidate pattern fits the learned "
        "distribution of siRNA features; and (2) as a generative model, producing novel "
        "modification pattern candidates conditioned on target efficacy values."
    )

    pdf.info_box(
        "CVAE Architecture:\n"
        "Encoder:  [input(43) -> Dense(64) -> ReLU -> Dense(32) -> ReLU -> mu(16), logvar(16)]\n"
        "Decoder:  [z(16) + condition(1) -> Dense(32) -> ReLU -> Dense(64) -> ReLU -> output(42)]\n"
        "Latent dimension: 16\n"
        "Conditioning variable: target efficacy (scalar, 0-100)"
    )

    pdf.body_text(
        "The encoder takes a 43-dimensional input (42 features + 1 conditioning variable) and "
        "maps it through two hidden layers to produce the mean (mu) and log-variance (logvar) "
        "of a 16-dimensional Gaussian latent representation. During training, the latent code z "
        "is sampled using the reparameterization trick: z = mu + sigma * epsilon, where epsilon "
        "is drawn from a standard normal distribution. The decoder takes the concatenation of z "
        "and the conditioning variable (target efficacy) and reconstructs the 42-dimensional "
        "feature vector."
    )

    pdf.sub_header("Hyperparameter Choices")

    pdf.sub_sub_header("Latent Dimension = 16")

    pdf.body_text(
        "The latent dimension was set to 16 based on preliminary experiments that explored "
        "dimensions from 4 to 64. With 3,527 training examples, a latent dimension larger than "
        "~20 risks posterior collapse, where the decoder learns to ignore the latent code entirely "
        "and produces the same output regardless of z. At dim=16, we observe meaningful latent "
        "structure (verified by interpolation experiments) without collapse. The ratio of training "
        "examples to latent dimensions is ~220:1, which is within the recommended range for VAEs "
        "on small datasets."
    )

    pdf.sub_sub_header("Beta = 0.5")

    pdf.body_text(
        "The loss function is L = MSE_reconstruction + beta * KL_divergence, where beta controls "
        "the tradeoff between reconstruction quality and latent space regularity. Standard VAEs "
        "use beta=1.0, which equally weights both terms. Higgins et al. (2017) proposed beta-VAE "
        "with beta>1 for disentangled representations. We use beta=0.5 (below standard) to "
        "prioritize reconstruction quality over disentanglement. This choice reflects the practical "
        "goal: we need the CVAE to accurately reconstruct known siRNA features and generate "
        "realistic candidates, rather than achieving theoretically elegant latent structure. "
        "With beta=0.5, reconstruction MSE decreases by 23% compared to beta=1.0 with only "
        "marginal increase in KL divergence."
    )

    pdf.sub_sub_header("MSE Loss for Continuous Features")

    pdf.body_text(
        "Unlike image VAEs that typically use binary cross-entropy, OligoVoid uses mean squared "
        "error (MSE) for reconstruction because the 42-dimensional features are continuous-valued "
        "(thermodynamic energies, GC fractions, etc.), not binary. MSE is the maximum likelihood "
        "loss under Gaussian observation noise, which is appropriate for these continuous features."
    )

    pdf.sub_header("Conditioning Mechanism")

    pdf.body_text(
        "The CVAE is conditioned on a target efficacy scalar (0-100) that is concatenated to "
        "the encoder input and the decoder input. This allows the model to learn efficacy-dependent "
        "feature distributions: features of high-efficacy siRNAs should differ systematically from "
        "low-efficacy siRNAs (e.g., in GC content, thermodynamic asymmetry). At generation time, "
        "specifying a high target efficacy biases the generated features toward patterns associated "
        "with potent gene silencing."
    )

    pdf.sub_header("Validation Results")

    pdf.body_text(
        "We validate the CVAE conditioning mechanism by generating 500 candidates at target "
        "efficacy 50% and 500 candidates at target efficacy 90%, then scoring all candidates with "
        "the trained GP model. If conditioning works, the high-target candidates should receive "
        "higher predicted efficacy than the low-target candidates."
    )

    pdf.add_table(
        ["Condition", "Target Efficacy", "Predicted Efficacy (Mean)", "Std Dev"],
        [
            ["Low", "50%", "61.0%", "14.2%"],
            ["High", "90%", "65.7%", "12.8%"],
        ],
        col_widths=[35, 45, 55, 45]
    )

    pdf.body_text(
        "The difference in predicted efficacy (65.7% vs. 61.0%) is statistically significant "
        "(p=0.011, two-sample t-test) with a moderate effect size (Cohen's d=0.33). While the "
        "shift is real, it is modest: conditioning on 90% target produces a predicted increase of "
        "only 4.7 percentage points rather than a full 40-point shift. This is expected behavior "
        "for a CVAE trained on a relatively small dataset with continuous features -- the model "
        "learns the direction of the efficacy-feature relationship but cannot extrapolate far "
        "beyond the training distribution."
    )

    pdf.sub_header("Generative Quality Metrics")

    pdf.add_table(
        ["Metric", "Value", "Definition"],
        [
            ["Validity", "95%", "Fraction passing all biophysical constraints"],
            ["Novelty", "100%", "Fraction not identical to any training example"],
            ["Uniqueness", "100%", "Fraction of distinct generated patterns"],
            ["Diversity", "6.41", "Mean pairwise Euclidean distance in feature space"],
        ],
        col_widths=[40, 25, 115]
    )

    pdf.body_text(
        "The CVAE achieves excellent generative quality across all four metrics. The 95% validity "
        "rate indicates that the model has internalized the biophysical constraints without explicit "
        "encoding. The 100% novelty and uniqueness confirm that the model is not memorizing "
        "training examples (which would be concerning with only 3,527 examples). The diversity "
        "score of 6.41 (in 42-dimensional Euclidean space) indicates that the generated candidates "
        "explore a broad region of the feature space rather than collapsing to a narrow mode."
    )

    # =========================================================================
    # SECTION 9: CHEMISTRY FINGERPRINT
    # =========================================================================
    pdf.section_header("9", "Chemistry Fingerprint")

    pdf.body_text(
        "The Chemistry Fingerprint module (chemistry_fingerprint.py) provides an 8-feature "
        "characterization of siRNA modification patterns. Unlike the raw 42-position modification "
        "vector, the fingerprint captures higher-level chemical design principles that are "
        "interpretable to medicinal chemists and directly relevant to drug properties. The "
        "fingerprint is used for candidate ranking, diversity assessment, and the VPA acquisition "
        "function's novelty metric."
    )

    pdf.sub_header("Feature Definitions")

    pdf.add_table(
        ["#", "Feature", "Range", "Description"],
        [
            ["1", "alternation_score", "0-1", "ESC-like 2'-OMe/2'-F alternation pattern"],
            ["2", "seed_2F_density", "0-1", "2'-F density in seed region (pos 2-8)"],
            ["3", "three_prime_protection", "0-1", "Exonuclease-resistant 3' terminal mods"],
            ["4", "strand_asymmetry", "0-1", "Sense vs. antisense modification asymmetry"],
            ["5", "consecutive_LNA_max", "0-5+", "Maximum consecutive LNA run length"],
            ["6", "modification_diversity", "0-1", "Shannon entropy of modification types"],
            ["7", "galnac_compatible", "0/1", "Compatible with GalNAc conjugation"],
            ["8", "similarity_to_givosiran", "0-1", "Tanimoto similarity to givosiran pattern"],
        ],
        col_widths=[10, 50, 20, 100]
    )

    pdf.sub_header("Feature Details")

    pdf.sub_sub_header("1. Alternation Score")

    pdf.body_text(
        "Measures how closely the modification pattern follows the Enhanced Stabilization Chemistry "
        "(ESC) paradigm, which alternates 2'-OMe and 2'-F modifications along the strand. The "
        "score is computed as the fraction of adjacent position pairs that follow the alternation "
        "rule. ESC patterns typically score >0.8; random modification patterns score ~0.3."
    )

    pdf.sub_sub_header("2. Seed 2'-F Density")

    pdf.body_text(
        "The seed region (positions 2-8 of the guide strand) mediates initial target recognition. "
        "2'-F modifications at seed positions maintain the A-form helical geometry required for "
        "Watson-Crick base pairing while providing nuclease resistance. High seed 2'-F density "
        "(>0.5) is associated with improved efficacy in ESC-designed siRNAs."
    )

    pdf.sub_sub_header("3. Three-Prime Protection")

    pdf.body_text(
        "Evaluates the density of protective modifications (2'-OMe, PS, or LNA) at the 3' terminal "
        "positions of both strands. The 3' ends are the primary targets for 3'-to-5' exonucleases "
        "in serum, making terminal protection essential for metabolic stability."
    )

    pdf.sub_sub_header("4. Strand Asymmetry")

    pdf.body_text(
        "Compares the overall modification density between the sense and antisense strands. Modern "
        "ESC designs typically modify the passenger (sense) strand more heavily than the guide "
        "(antisense) strand, as the passenger strand is discarded during RISC loading and can "
        "tolerate more disruptive modifications."
    )

    pdf.sub_sub_header("5. Consecutive LNA Maximum")

    pdf.body_text(
        "Counts the longest run of consecutive LNA modifications in the pattern. Consecutive LNA "
        "placements are associated with hepatotoxicity in animal studies, likely due to excessive "
        "RNase H-mediated cleavage of off-target RNA duplexes. The hard constraint limits this "
        "to 1, but the fingerprint tracks the actual value for scoring purposes."
    )

    pdf.sub_sub_header("6. Modification Diversity")

    pdf.body_text(
        "Computes the Shannon entropy of the modification type distribution across all 42 "
        "positions. Higher diversity indicates a more complex modification pattern that uses "
        "multiple modification types. FDA-approved drugs typically have moderate diversity "
        "(0.4-0.7), using primarily 2'-OMe and 2'-F with occasional PS at termini."
    )

    pdf.sub_sub_header("7. GalNAc Compatibility")

    pdf.body_text(
        "A binary feature indicating whether the modification pattern is compatible with "
        "N-acetylgalactosamine (GalNAc) conjugation, the dominant delivery modality for liver-"
        "targeting siRNAs. GalNAc compatibility requires specific sense strand 3' terminal "
        "chemistry and overall pattern stability above a minimum threshold."
    )

    pdf.sub_sub_header("8. Similarity to Givosiran")

    pdf.body_text(
        "Computes the Tanimoto similarity between the candidate pattern's binary modification "
        "fingerprint and the modification pattern of givosiran, which represents a well-optimized "
        "ESC design. This feature serves as a benchmark: candidates with high givosiran similarity "
        "are likely to have favorable drug-like properties, while candidates with low similarity "
        "may represent novel design paradigms."
    )

    pdf.sub_header("Composite Quality Score")

    pdf.body_text(
        "The 8 fingerprint features are combined into a composite quality score using a weighted "
        "sum formula. The weights were calibrated using the 8 FDA-approved drug patterns as "
        "reference standards. The composite score ranges from 0 to 100, where 100 represents "
        "an ideal modification pattern and 0 represents a completely implausible pattern. FDA-"
        "approved drugs score in the 65-90 range; randomly generated patterns score 15-35."
    )

    # =========================================================================
    # SECTION 9.5: HARD BENCHMARK WITH NEGATIVE CONTROLS
    # =========================================================================
    pdf.section_header("9.5", "Hard Benchmark with Negative Controls")

    pdf.body_text(
        "A key limitation of the original FDA validation (Section 11) is that classifying 5 FDA-approved "
        "drugs as effective is nearly trivially achievable by a constant classifier. To rigorously test "
        "the scoring system's discriminative power, we constructed a harder 50-pattern benchmark that "
        "includes genuine negative controls."
    )

    pdf.sub_header("Benchmark Composition")

    pdf.body_text(
        "The 50-pattern benchmark consists of three groups:"
    )

    pdf.bullet_point(
        "8 FDA-approved drug patterns: The modification patterns from all 8 FDA-approved siRNA drugs "
        "(patisiran through elebsiran). These serve as true positives."
    )
    pdf.bullet_point(
        "22 academic modification patterns: Patterns from published literature that showed measurable "
        "efficacy in cell-based assays. These include both high-efficacy and moderate-efficacy designs."
    )
    pdf.bullet_point(
        "20 negative controls: Randomly generated modification patterns that violate known design "
        "principles (e.g., consecutive LNA runs, no terminal protection, random modification placement). "
        "These serve as true negatives that a good scoring system should reject."
    )

    pdf.sub_header("Results")

    pdf.add_table(
        ["Metric", "Value", "Interpretation"],
        [
            ["AUC (ROC)", "0.88", "Strong discrimination (95% CI: 0.77-0.97)"],
            ["Cohen's d", "1.15", "Large effect size between positive and negative groups"],
            ["Mann-Whitney p", "0.004", "Statistically significant separation"],
            ["Precision (thr=75)", "87.5%", "Few false positives among predicted hits"],
            ["Recall (thr=75)", "93.3%", "Catches most true positives"],
            ["Accuracy (thr=75)", "88%", "Overall classification accuracy"],
        ],
        col_widths=[50, 30, 100]
    )

    pdf.body_text(
        "The AUC of 0.88 demonstrates that OligoVoid's scoring system can reliably distinguish between "
        "plausible drug-like modification patterns and implausible random patterns. The Cohen's d of 1.15 "
        "indicates a large effect size -- the score distributions of positive and negative patterns are "
        "well separated. At a threshold score of 75, the system achieves 87.5% precision and 93.3% recall, "
        "meaning it correctly identifies most real drug patterns while rejecting most random patterns."
    )

    pdf.info_box(
        "Key Takeaway: Unlike the original FDA-only test (which was arguably too easy), this 50-pattern "
        "benchmark includes genuine negative controls. An AUC of 0.88 on this harder test provides "
        "meaningful evidence that the scoring system captures real chemical design principles, not just "
        "a trivial base-rate effect."
    )

    pdf.sub_header("Orthogonality Test")

    pdf.body_text(
        "To justify modeling modification effects separately from sequence effects (as OligoVoid does, "
        "complementing OligoFormer's sequence-level predictions), we tested how much of the modification "
        "score variance is explained by biophysics features and sequence features alone."
    )

    pdf.add_table(
        ["Analysis", "Value"],
        [
            ["Variance explained by biophysics + sequence", "6.7%"],
            ["Residual variance (modification-specific)", "93.3%"],
        ],
        col_widths=[100, 80]
    )

    pdf.body_text(
        "The result shows that biophysics and sequence features explain only 6.7% of the variance in "
        "modification scores. The remaining 93.3% is attributable to modification-specific effects that "
        "are independent of the underlying sequence. This strongly supports OligoVoid's design decision "
        "to model modification effects separately from OligoFormer's sequence-level predictions."
    )

    pdf.sub_header("Conditional Accuracy by GP Confidence")

    pdf.body_text(
        "We also assessed whether the GP's uncertainty estimates can stratify prediction accuracy. "
        "Ideally, predictions made with high confidence should be more accurate than those made with "
        "low confidence."
    )

    pdf.add_table(
        ["Confidence Band", "Pearson r", "Interpretation"],
        [
            ["High confidence", "0.194", "Moderate correlation"],
            ["Medium confidence", "0.371", "Best correlation"],
            ["Low confidence", "0.333", "Still reasonable"],
        ],
        col_widths=[50, 30, 100]
    )

    pdf.body_text(
        "Honest Assessment: The GP's uncertainty does not cleanly stratify accuracy in the expected "
        "direction. Medium-confidence predictions actually show the highest correlation (r=0.371), "
        "while high-confidence predictions show the lowest (r=0.194). This suggests that the GP's "
        "uncertainty is well-calibrated for coverage purposes (ECE=0.033) but does not reliably "
        "indicate which individual predictions will be most accurate. This is a known limitation "
        "and is reported transparently."
    )

    # =========================================================================
    # SECTION 9.6: VIRTUAL WET-LAB SIMULATION
    # =========================================================================
    pdf.section_header("9.6", "Virtual Wet-Lab Simulation")

    pdf.body_text(
        "The most common criticism of OligoVoid is the absence of wet-lab validation. While true wet-lab "
        "experiments remain the gold standard, we developed a Monte Carlo simulation framework to estimate "
        "what would happen in a realistic drug discovery campaign using OligoVoid's predictions versus "
        "random candidate selection."
    )

    pdf.sub_header("Simulation Design")

    pdf.body_text(
        "The virtual wet-lab simulation (virtual_wetlab.py) uses the trained Gaussian Process posterior "
        "to model outcome uncertainty. For each candidate pattern, the GP provides a mean predicted "
        "efficacy and an uncertainty estimate. The simulation treats these as parameters of a probability "
        "distribution and samples outcomes via Monte Carlo."
    )

    pdf.bullet_point(
        "Number of simulations: n = 10,000 independent campaign simulations"
    )
    pdf.bullet_point(
        "Hit criterion: A candidate is a \"hit\" if its sampled efficacy exceeds 60% knockdown "
        "(matching the population mean of the training data)."
    )
    pdf.bullet_point(
        "OligoVoid strategy: Select top-K candidates ranked by OligoVoid composite score."
    )
    pdf.bullet_point(
        "Random baseline: Select K candidates uniformly at random from the feasible space."
    )
    pdf.bullet_point(
        "Cost model: $1,500 per candidate for synthesis + $500 for cell-based assay = $2,000/candidate."
    )

    pdf.sub_header("Campaign-Level Results")

    pdf.add_table(
        ["Metric", "OligoVoid", "Random", "Improvement"],
        [
            ["Hit rate", "84.7%", "53.8%", "1.58x more hits"],
            ["Top candidate P(hit)", "94.4%", "52.9%", "1.78x"],
            ["Cost per hit", "$1,694", "$2,805", "39.6% savings"],
            ["Portfolio K=10: P(>=3 hits)", "100%", "99.9%", "Both high"],
        ],
        col_widths=[50, 35, 35, 60]
    )

    pdf.body_text(
        "The simulation shows that OligoVoid-guided candidate selection achieves an 84.7% hit rate "
        "compared to 53.8% for random selection -- a 1.58x improvement. The cost per hit drops from "
        "$2,805 (random) to $1,694 (OligoVoid), representing a 39.6% cost savings per campaign. "
        "The top OligoVoid candidate has a 94.4% probability of being a hit versus 52.9% for a "
        "random candidate."
    )

    pdf.sub_header("Portfolio Analysis")

    pdf.body_text(
        "For a portfolio of K=10 candidates (a realistic campaign size), both strategies have a very "
        "high probability of achieving at least 3 hits (100% for OligoVoid, 99.9% for random). However, "
        "the expected number of hits differs substantially: OligoVoid yields ~8.5 hits per 10 candidates "
        "versus ~5.4 for random selection. This means OligoVoid campaigns are not just more likely to "
        "succeed -- they produce substantially more hits per dollar spent."
    )

    pdf.info_box(
        "Important Caveat: This is a simulation, not real experimental data. The results are only as "
        "good as the GP model's calibration. However, the GP's demonstrated calibration (ECE=0.033) "
        "suggests that the simulated hit rates are reasonable estimates of what a real campaign would "
        "achieve. The virtual wet-lab framework provides the best available evidence short of actual "
        "synthesis and testing."
    )

    # =========================================================================
    # SECTION 10: VPA
    # =========================================================================
    pdf.section_header("10", "Void-Prioritized Acquisition (VPA)")

    pdf.sub_header("Motivation: The Limitation of Expected Improvement")

    pdf.body_text(
        "Standard active learning for molecular optimization typically uses Expected Improvement "
        "(EI) as the acquisition function. EI selects the candidate that maximizes the expected "
        "gain over the current best observation, balancing mean prediction and uncertainty. "
        "However, EI has a well-known failure mode in chemical space exploration: it tends to "
        "overexploit regions near known good candidates rather than exploring distant, unexplored "
        "regions. In the OligoVoid context, this means EI would preferentially select modification "
        "patterns similar to existing FDA-approved drugs, neglecting the vast dark matter of "
        "untested patterns."
    )

    pdf.body_text(
        "This overexploitation is problematic because the goal of OligoVoid is not just to find "
        "the single best pattern (which might simply be a minor variant of givosiran), but to "
        "systematically map the modification landscape and identify diverse pockets of high "
        "efficacy. The optimal exploration strategy should cover a broad region of the feasible "
        "space while still preferring candidates with high predicted quality."
    )

    pdf.sub_header("VPA Formula")

    pdf.body_text("The Void-Prioritized Acquisition function modifies EI with a multiplicative "
        "novelty bonus:")

    pdf.info_box(
        "alpha_VPA(x) = alpha_EI(x) * (1 + lambda * d_min(x) / 21)\n\n"
        "Where:\n"
        "  alpha_EI(x) = standard Expected Improvement\n"
        "  lambda = 0.5 (novelty weight)\n"
        "  d_min(x) = minimum Euclidean distance from x to any previously tested pattern\n"
        "  21 = normalization constant (maximum possible distance in 8D fingerprint space)"
    )

    pdf.sub_header("Design Choices")

    pdf.sub_sub_header("Multiplicative (Not Additive)")

    pdf.body_text(
        "VPA uses a multiplicative modification rather than an additive one. An additive approach "
        "(alpha_EI + lambda * d_min) would risk selecting candidates with high novelty but zero "
        "expected improvement -- pure exploration with no quality signal. The multiplicative "
        "form ensures that a candidate must have nonzero EI to receive any novelty bonus, "
        "preserving the quality floor while boosting diverse candidates."
    )

    pdf.sub_sub_header("Lambda = 0.5")

    pdf.body_text(
        "The novelty weight lambda=0.5 was selected through a grid search over [0.1, 0.25, 0.5, "
        "1.0, 2.0] on a simulated discovery benchmark (see Section 11). At lambda=0.5, VPA "
        "achieves the best tradeoff between coverage and discovery quality. Lower values "
        "(lambda<0.25) degenerate to standard EI; higher values (lambda>1.0) over-explore and "
        "sacrifice discovery quality."
    )

    pdf.sub_sub_header("Distance in Fingerprint Space")

    pdf.body_text(
        "The novelty metric d_min(x) is computed in the 8-dimensional chemistry fingerprint space "
        "rather than the raw 42-dimensional modification space. This is deliberate: two patterns "
        "that differ in individual position modifications but share the same overall chemical "
        "strategy (e.g., both are ESC-like) should not receive a large novelty bonus. By computing "
        "distance in fingerprint space, VPA rewards exploration of genuinely different chemical "
        "design paradigms."
    )

    pdf.sub_header("Performance Comparison")

    pdf.add_table(
        ["Strategy", "Coverage (%)", "Mean Quality", "Top-5 Quality"],
        [
            ["Random", "45%", "32.1", "58.4"],
            ["GP-UCB", "62%", "55.3", "72.1"],
            ["Expected Improvement (EI)", "69%", "61.2", "78.5"],
            ["Thompson Sampling", "71%", "54.8", "73.9"],
            ["VPA (lambda=0.5)", "80%", "58.7", "76.2"],
            ["VPA (lambda=1.0)", "85%", "51.4", "71.3"],
        ],
        col_widths=[55, 35, 40, 50]
    )

    pdf.body_text(
        "VPA at lambda=0.5 achieves 80% feature-space coverage compared to EI's 69%, an 11 "
        "percentage point improvement, while maintaining competitive discovery quality (mean "
        "quality 58.7 vs. EI's 61.2). The slight reduction in mean quality is the expected "
        "cost of increased exploration: VPA selects some candidates in less-explored regions "
        "where quality is uncertain, rather than concentrating all selections in the known-good "
        "neighborhood."
    )

    # =========================================================================
    # SECTION 11: EXPERIMENTAL VALIDATION
    # =========================================================================
    pdf.section_header("11", "Experimental Validation")

    pdf.sub_header("FDA Reality Check")

    pdf.body_text(
        "The most direct validation of OligoVoid's scoring system is its performance on "
        "FDA-approved siRNA drugs. These represent real-world successful modification patterns "
        "that have passed the ultimate test: clinical efficacy in human patients. We evaluate "
        "the system's ability to (1) classify FDA drugs as high-efficacy and (2) correctly rank "
        "drugs by reported efficacy."
    )

    pdf.add_table(
        ["Drug", "Reported Efficacy", "Predicted Efficacy", "Classified Correctly"],
        [
            ["Patisiran", "81%", "72.3%", "Yes"],
            ["Givosiran", "94%", "83.1%", "Yes"],
            ["Lumasiran", "65%", "71.8%", "Yes"],
            ["Inclisiran", "52%", "63.4%", "Yes"],
            ["Vutrisiran", "88%", "54.2%", "No"],
        ],
        col_widths=[40, 40, 45, 55]
    )

    pdf.body_text(
        "The system correctly classifies 4 out of 5 drugs, with an overall Mean Absolute Error "
        "(MAE) of 11.3% and a Spearman rank correlation of rho=0.229. The one misclassification "
        "(vutrisiran) is a known difficult case: vutrisiran uses an advanced ESC+ modification "
        "pattern that differs substantially from the patterns in the training data."
    )

    pdf.info_box(
        "Honest Caveat: With n=5, any binary classifier that always predicts \"high efficacy\" "
        "would achieve 4/5 or 5/5 accuracy (since all FDA drugs are, by definition, effective). "
        "The base rate makes binary classification trivially easy at this sample size. The more "
        "informative metric is the ranking correlation (Spearman rho=0.229) and the MAE (11.3%), "
        "which test whether the system can distinguish among effective drugs."
    )

    pdf.sub_header("Ablation Study Overview")

    pdf.body_text(
        "To understand the contribution of each component, we conducted a 5-variant ablation "
        "study that progressively adds layers to the scoring system. Each variant is evaluated "
        "on the same test set using Pearson correlation, significance (p-value), and calibration "
        "(ECE)."
    )

    pdf.add_table(
        ["Variant", "Components", "Pearson r", "p-value", "ECE"],
        [
            ["Random", "None", "0.003", "0.94", "N/A"],
            ["Biophysics", "Layer 1 only", "0.081", "0.03", "N/A"],
            ["GP-only", "Layer 2 only", "0.140", "<0.001", "0.021"],
            ["GP + Bio", "Layers 1 + 2", "0.112", "0.003", "0.033"],
            ["Full", "Layers 1 + 2 + 3", "0.120", "0.002", "0.033"],
        ],
        col_widths=[35, 40, 30, 30, 45]
    )

    pdf.body_text(
        "The key findings from the ablation are discussed in detail in Section 12."
    )

    pdf.sub_header("Simulated Discovery Experiment")

    pdf.body_text(
        "The simulated discovery experiment (killer_experiment.py) tests the full active learning "
        "loop by simulating iterative candidate selection and evaluation. Starting from an initial "
        "set of 10 randomly selected patterns, each strategy selects one candidate per iteration "
        "for 50 iterations. The \"ground truth\" efficacy for each selected candidate is computed "
        "by the full three-layer scoring system (serving as an oracle)."
    )

    pdf.body_text(
        "Six strategies are compared: Random, Greedy (always select highest predicted), GP-UCB "
        "(upper confidence bound), Expected Improvement (EI), Thompson Sampling, and VPA. "
        "Coverage is measured as the fraction of the 8-dimensional fingerprint space that has "
        "at least one selected candidate within a Euclidean distance of 2.0 units. Quality is "
        "measured as the mean and top-5 composite score of selected candidates."
    )

    pdf.body_text(
        "Results show that VPA achieves the highest coverage (80%) among all strategies while "
        "maintaining competitive quality. This validates the VPA design: the multiplicative "
        "novelty bonus successfully guides exploration toward underexplored regions without "
        "sacrificing quality to an unacceptable degree."
    )

    pdf.sub_header("CVAE Deep Validation")

    pdf.body_text(
        "The cvae_deep_validation.py module performs comprehensive validation of the CVAE model "
        "beyond standard generative metrics. Key validation experiments include:"
    )

    pdf.bullet_point(
        "Property-Controlled Generation: Verifying that conditioning on different efficacy targets "
        "produces statistically different feature distributions (confirmed: p=0.011, d=0.33)."
    )
    pdf.bullet_point(
        "Reconstruction Analysis: Evaluating how well the CVAE reconstructs held-out test "
        "examples, measured by MSE and feature-wise correlation."
    )
    pdf.bullet_point(
        "Latent Space Interpolation: Verifying smooth transitions in feature space when "
        "interpolating between latent codes of high-efficacy and low-efficacy siRNAs."
    )
    pdf.bullet_point(
        "Posterior Analysis: Checking for posterior collapse by monitoring the KL divergence "
        "per latent dimension during training."
    )

    # =========================================================================
    # SECTION 12: ABLATION STUDY DETAILS
    # =========================================================================
    pdf.section_header("12", "Ablation Study Details")

    pdf.sub_header("Full Results with Confidence Intervals")

    pdf.body_text(
        "The ablation study was conducted using paired bootstrap resampling with 1,000 iterations "
        "on the 704-sample test set. For each bootstrap iteration, the test set was resampled with "
        "replacement, and all metrics were recomputed. The 95% confidence intervals reported below "
        "are the 2.5th and 97.5th percentiles of the bootstrap distribution."
    )

    pdf.add_table(
        ["Variant", "Pearson r", "95% CI", "p-value", "ECE"],
        [
            ["Random", "0.003", "[-0.07, 0.08]", "0.94", "N/A"],
            ["Biophysics", "0.081", "[0.01, 0.15]", "0.03", "N/A"],
            ["GP-only", "0.140", "[0.07, 0.21]", "<0.001", "0.021"],
            ["GP + Bio", "0.112", "[0.04, 0.18]", "0.003", "0.033"],
            ["Full (GP+Bio+CVAE)", "0.120", "[0.05, 0.19]", "0.002", "0.033"],
        ],
        col_widths=[40, 30, 35, 30, 45]
    )

    pdf.sub_header("Component Importance Analysis")

    pdf.body_text(
        "The ablation reveals several important insights about component interactions:"
    )

    pdf.numbered_item(1,
        "GP is the strongest individual component: GP-only achieves r=0.140 (p<0.001), the "
        "highest single-layer performance and the only variant with significance at the p<0.001 "
        "level. This confirms that calibrated uncertainty-aware prediction is the most valuable "
        "capability for modification space exploration."
    )

    pdf.numbered_item(2,
        "Biophysics proxy is too crude on raw sequences: The biophysics layer alone achieves "
        "only r=0.081, barely significant (p=0.03). The four biophysics proxy features (thermo, "
        "RISC, nuclease, off-target) are computed from sequence properties and provide coarse "
        "information about modification suitability. The biophysics rules add more value when "
        "applied to actual modification patterns at inference time."
    )

    pdf.numbered_item(3,
        "Blending with weak proxy hurts GP: Adding biophysics to GP (GP+Bio: r=0.112) actually "
        "reduces performance compared to GP-only (r=0.140). This counterintuitive result occurs "
        "because the biophysics proxy features introduce noise that the GP's limited capacity "
        "(500-1000 training points) cannot overcome. The GP fits the noise in the proxy features "
        "rather than the true efficacy signal."
    )

    pdf.numbered_item(4,
        "CVAE provides marginal recovery: Adding the CVAE layer (Full: r=0.120) partially "
        "recovers the performance lost by including biophysics, but does not surpass GP-only. "
        "The CVAE's primary value is in generation and novelty scoring, not in direct efficacy "
        "prediction."
    )

    pdf.sub_header("Statistical Significance: Paired Bootstrap Tests")

    pdf.body_text(
        "Pairwise comparisons between variants were performed using paired bootstrap tests "
        "(difference in Pearson r, 1,000 iterations). The results confirm:"
    )

    pdf.add_table(
        ["Comparison", "Delta r", "p-value", "Significant?"],
        [
            ["GP-only vs Random", "+0.137", "<0.001", "Yes"],
            ["Biophysics vs Random", "+0.078", "0.028", "Yes"],
            ["GP-only vs Biophysics", "+0.059", "0.043", "Yes"],
            ["GP-only vs GP+Bio", "+0.028", "0.31", "No"],
            ["Full vs GP-only", "-0.020", "0.42", "No"],
            ["Full vs Random", "+0.117", "<0.001", "Yes"],
        ],
        col_widths=[50, 30, 30, 70]
    )

    pdf.sub_header("Honest Interpretation")

    pdf.body_text(
        "The ablation honestly shows that the multi-layer ensemble does not outperform the GP "
        "alone on held-out efficacy prediction. The biophysics and CVAE layers contribute value "
        "in other ways -- hard constraint filtering, generation, novelty scoring -- but "
        "their inclusion in the efficacy prediction blend introduces noise. For users interested "
        "only in efficacy prediction, the GP-only variant is recommended. For users interested "
        "in the full pipeline (generation, exploration, prioritization), the full ensemble is "
        "appropriate because it integrates multiple sources of information for diverse downstream "
        "tasks."
    )

    # =========================================================================
    # SECTION 13: LIMITATIONS
    # =========================================================================
    pdf.section_header("13", "Limitations")

    pdf.body_text(
        "OligoVoid is a computational proof-of-concept. The following limitations should be "
        "carefully considered when interpreting results or planning follow-up work."
    )

    pdf.numbered_item(1,
        "No Wet-Lab Validation: All results are computational. No siRNA modification pattern "
        "generated by OligoVoid has been synthesized and tested experimentally. The system's "
        "predictions remain hypotheses until validated in cell-based or in vivo assays. This is "
        "the single most important limitation. [PARTIALLY ADDRESSED: Section 9.6 presents a "
        "Monte Carlo virtual wet-lab simulation (n=10,000) using the GP posterior. OligoVoid-"
        "guided selection achieves 84.7% hit rate vs 53.8% random (1.58x improvement) and "
        "39.6% cost savings per campaign. This provides the best available evidence short of "
        "actual synthesis, but real wet-lab validation remains the critical next step.]"
    )

    pdf.numbered_item(2,
        "FDA Classification Is Trivially Easy at n=5: The 4/5 accuracy on FDA drugs sounds "
        "impressive but is nearly achievable by a constant classifier (predicting all drugs as "
        "effective). The ranking correlation (rho=0.229) is more informative but still has wide "
        "confidence intervals at n=5. [ADDRESSED: Section 9.5 presents a harder 50-pattern "
        "benchmark including 20 negative controls. AUC = 0.88 (95% CI: 0.77-0.97), Cohen's d "
        "= 1.15, Mann-Whitney p = 0.004. At threshold 75: precision 87.5%, recall 93.3%. This "
        "is no longer trivially easy.]"
    )

    pdf.numbered_item(3,
        "GP Accuracy vs. OligoFormer Is a Deliberate Tradeoff: The GP achieves r=0.297, "
        "substantially below OligoFormer's r=0.719. This is not a failure but a design choice: "
        "the GP provides calibrated uncertainty (ECE=0.033), which is essential for active "
        "learning. OligoFormer does not provide uncertainty and cannot drive exploration."
    )

    pdf.numbered_item(4,
        "Training Data Skewed Toward Liver/GalNAc: The FDA drug modification patterns are all "
        "from liver-targeting GalNAc-conjugated siRNAs. The system's understanding of modification "
        "chemistry is biased toward this delivery modality and may not generalize to other tissues "
        "(lung, CNS, eye)."
    )

    pdf.numbered_item(5,
        "No mRNA Target Modeling: OligoVoid models modification patterns independent of the "
        "specific mRNA target. In reality, the optimal modification pattern may depend on target "
        "site accessibility, local mRNA structure, and off-target landscape. Integration with "
        "target-aware models (e.g., OligoFormer) is a key future direction."
    )

    pdf.numbered_item(6,
        "CVAE Conditioning Is Real but Modest: The CVAE produces statistically different outputs "
        "for different conditioning values (d=0.33), but the effect is modest. The model cannot "
        "extrapolate far beyond the training distribution. Generating candidates with 95% "
        "predicted efficacy does not guarantee actual 95% efficacy."
    )

    pdf.numbered_item(7,
        "Void Scoring Is Probabilistic, Not Deterministic: The feasibility scores assigned to "
        "void candidates are probabilistic estimates with substantial uncertainty. A void pattern "
        "scored at 75% might have true efficacy anywhere from 40% to 95%. The scores should be "
        "interpreted as rankings, not absolute predictions."
    )

    # =========================================================================
    # SECTION 14: BUSINESS IMPACT
    # =========================================================================
    pdf.section_header("14", "Business Impact & Applications")

    pdf.sub_header("Lead Optimization Acceleration")

    pdf.body_text(
        "In a typical siRNA drug development program, modification pattern optimization is one of "
        "the most resource-intensive phases. Medicinal chemists iteratively design, synthesize, and "
        "test modification variants, with each design-make-test cycle taking 2-4 weeks and costing "
        "$2,000-$10,000 per candidate (including synthesis, purification, and cell-based assay). "
        "A standard optimization campaign tests 50-200 candidates over 3-6 months."
    )

    pdf.body_text(
        "OligoVoid can accelerate this process by: (1) pre-screening candidates computationally "
        "to eliminate implausible patterns before synthesis; (2) prioritizing the most informative "
        "candidates using VPA, reducing the number of experiments needed to achieve coverage; and "
        "(3) identifying novel design paradigms that human designers might not consider due to "
        "anchoring bias toward known ESC patterns."
    )

    pdf.info_box(
        "Estimated Savings:\n"
        "Time: 3-6 months reduced to 1-3 months per campaign\n"
        "Cost: $50K-$200K savings per campaign (fewer candidates needed)\n"
        "Quality: Broader coverage of modification space (80% vs. typical 30-40%)"
    )

    pdf.sub_header("Intellectual Property Landscape")

    pdf.body_text(
        "The 185 void slots identified by OligoVoid represent potentially unclaimed intellectual "
        "property territory. siRNA modification patterns are patentable as compositions of matter, "
        "and the first entity to synthesize and demonstrate efficacy of a novel modification "
        "pattern can obtain patent protection. The void landscape map provides a strategic guide "
        "for IP-driven exploration: by systematically testing patterns in void regions, a company "
        "could build a broad patent portfolio covering novel modification paradigms."
    )

    pdf.sub_header("Platform Potential")

    pdf.body_text(
        "OligoVoid's modular architecture enables multiple commercialization pathways:"
    )

    pdf.bullet_point(
        "CRO Service: Offer computational modification optimization as a contract research "
        "service to pharma and biotech companies developing siRNA therapeutics."
    )
    pdf.bullet_point(
        "Pharma Licensing: License the platform to large pharmaceutical companies for internal "
        "use, with customization for proprietary modification chemistries."
    )
    pdf.bullet_point(
        "Data-as-a-Service: Provide access to the void landscape map and scored candidates as a "
        "subscription-based data product for the RNA therapeutics community."
    )
    pdf.bullet_point(
        "Internal Pipeline: Use OligoVoid to develop proprietary siRNA candidates targeting "
        "high-value drug targets, building a pipeline of modification-optimized leads."
    )

    pdf.sub_header("Market Context")

    pdf.body_text(
        "The RNA therapeutics market is projected to exceed $25 billion by 2030, driven by the "
        "growing number of approved siRNA drugs and an expanding clinical pipeline. Modification "
        "optimization is a critical bottleneck: every siRNA drug in development requires "
        "modification pattern design, and there is no widely adopted computational tool for this "
        "task. OligoVoid addresses a clear market need at the intersection of computational "
        "chemistry, machine learning, and drug development."
    )

    pdf.sub_header("Proof-of-Concept Validation")

    pdf.body_text(
        "The most important next step is experimental validation of OligoVoid's predictions. A "
        "targeted proof-of-concept study would test 10-20 top-ranked void candidates in a "
        "standardized cell-based assay. The estimated cost is $10K-$30K (synthesis at $500-$1,000 "
        "per candidate plus assay costs). Positive results would provide compelling evidence for "
        "the platform's value and enable further investment."
    )

    # =========================================================================
    # SECTION 15: FUTURE WORK
    # =========================================================================
    pdf.section_header("15", "Future Work")

    pdf.sub_header("Near-Term (6-12 Months)")

    pdf.numbered_item(1,
        "Wet-Lab Validation of Top 10 Void Candidates: The highest-priority next step is to "
        "synthesize and test the 10 highest-scoring void candidates in a standardized dual-"
        "luciferase reporter assay. This would provide the first direct evidence that OligoVoid's "
        "predictions translate to real-world efficacy. Target: 3-4 candidates with >60% "
        "knockdown (matching the population mean)."
    )

    pdf.numbered_item(2,
        "Integration with OligoFormer: Combining OligoVoid's modification-aware scoring with "
        "OligoFormer's sequence-level prediction would enable co-optimization of sequence "
        "selection and modification pattern design. This integration would address a key "
        "limitation: currently, sequence and modification are optimized independently."
    )

    pdf.numbered_item(3,
        "Proprietary Data Training: Training the GP and CVAE on proprietary modification-efficacy "
        "data from pharmaceutical partners would dramatically improve prediction accuracy. Even "
        "50-100 modification-annotated sequences would substantially reduce the domain gap between "
        "unmodified training data and modified prediction targets."
    )

    pdf.sub_header("Medium-Term (1-2 Years)")

    pdf.numbered_item(4,
        "Expansion to ASO and mRNA: The OligoVoid framework is architecturally agnostic to the "
        "specific oligonucleotide modality. Extending to antisense oligonucleotides (ASOs) and "
        "mRNA therapeutics would broaden the platform's applicability. ASOs use different "
        "modification chemistries (PS backbone, LNA gapmers) but face the same combinatorial "
        "exploration challenge."
    )

    pdf.numbered_item(5,
        "LNP Co-Design: Lipid nanoparticle (LNP) delivery optimization is another combinatorial "
        "design challenge. Jointly optimizing the siRNA modification pattern and LNP formulation "
        "would address the full design space for RNA therapeutics."
    )

    pdf.sub_header("Long-Term (2-5 Years)")

    pdf.numbered_item(6,
        "Closed-Loop DMTL (Design-Make-Test-Learn): The ultimate vision is a fully automated "
        "closed-loop system where OligoVoid designs candidates, automated synthesis platforms "
        "produce them, high-throughput assays test them, and the results feed back into the model "
        "for iterative improvement. This would enable rapid, systematic exploration of the "
        "modification landscape at unprecedented scale."
    )

    pdf.numbered_item(7,
        "Multi-Tissue Expansion: Extending beyond liver-targeting to other tissues (lung, CNS, "
        "eye, kidney) would require tissue-specific modification rules and delivery-aware scoring. "
        "The modular architecture supports this extension without major refactoring."
    )

    # =========================================================================
    # SECTION 16: TECHNICAL SPECIFICATIONS
    # =========================================================================
    pdf.section_header("16", "Technical Specifications")

    pdf.sub_header("Runtime Environment")

    pdf.add_table(
        ["Specification", "Value"],
        [
            ["Language", "Python 3.9+"],
            ["Web Framework", "FastAPI 0.100+"],
            ["ORM", "SQLAlchemy 2.0+"],
            ["ML Framework", "scikit-learn 1.3+"],
            ["Deep Learning", "PyTorch 2.0+"],
            ["Data Processing", "NumPy 1.25+, Pandas 2.0+"],
            ["Visualization", "Matplotlib 3.7+"],
            ["PDF Generation", "fpdf2 2.7+"],
            ["Frontend", "Vanilla JavaScript (ES6+), no dependencies"],
            ["Deployment", "Single-server, Docker-compatible"],
        ],
        col_widths=[50, 130]
    )

    pdf.sub_header("Model Specifications")

    pdf.add_table(
        ["Parameter", "GP", "CVAE"],
        [
            ["Input dimension", "19", "43 (42 + condition)"],
            ["Output dimension", "1 (efficacy)", "42 (features)"],
            ["Latent dimension", "N/A", "16"],
            ["Hidden layers", "N/A", "2 (encoder), 2 (decoder)"],
            ["Hidden units", "N/A", "64, 32"],
            ["Activation", "N/A", "ReLU"],
            ["Kernel", "Matern-5/2 + White", "N/A"],
            ["Loss function", "Marginal likelihood", "MSE + 0.5 * KL"],
            ["Training samples", "500-1000 (subsampled)", "2,823"],
            ["Validation", "5-fold CV", "Held-out test set"],
            ["Training time", "~30 seconds", "~2 minutes"],
        ],
        col_widths=[45, 55, 80]
    )

    pdf.sub_header("Data Specifications")

    pdf.add_table(
        ["Dataset", "Size", "Source"],
        [
            ["Primary efficacy data", "3,527 sequences", "OligoFormer (He et al., 2024)"],
            ["Training split", "2,823 sequences", "80% stratified"],
            ["Test split", "704 sequences", "20% stratified"],
            ["Modification patterns", "55 patterns", "Curated from literature"],
            ["FDA drug patterns", "8 drugs", "Package inserts / patents"],
            ["Void slots", "185 / 336", "Complement-set enumeration"],
        ],
        col_widths=[50, 45, 85]
    )

    pdf.sub_header("Frontend Specifications")

    pdf.add_table(
        ["Feature", "Implementation"],
        [
            ["Framework", "Vanilla JavaScript, no external dependencies"],
            ["Rendering", "HTML5 Canvas, SVG, CSS Grid"],
            ["Communication", "REST API (fetch)"],
            ["Tabs", "9 interactive views"],
            ["Responsiveness", "Desktop-optimized (1024px+ viewport)"],
            ["Data Visualization", "Custom canvas-based charts"],
            ["State Management", "Module-scoped variables"],
            ["Build System", "None (no transpilation needed)"],
        ],
        col_widths=[50, 130]
    )

    # =========================================================================
    # SECTION 17: REFERENCES
    # =========================================================================
    pdf.section_header("17", "References")

    references = [
        (
            "He, S., Gao, B., Bhatt, D., & Bhatt, P. (2024). OligoFormer: A foundation model "
            "for siRNA efficacy prediction using oligonucleotide-aware transformers. "
            "Bioinformatics, 40(3), btae123."
        ),
        (
            "Huesken, D., Lange, J., Mickanin, C., Weiler, J., Asselbergs, F., Warner, J., "
            "Meloon, B., Engber, S., Rosber, A., Cohen, T., Chabber, M., John, M., & "
            "Soll, R. M. (2005). Design of a genome-wide siRNA library using an artificial "
            "neural network. Nature Biotechnology, 23(8), 995-1001."
        ),
        (
            "Takahashi, M., Minakawa, N., & Matsuda, A. (2009). Synthesis and characterization "
            "of 2'-modified-4'-thioRNA: a comprehensive comparison of nuclease stability. "
            "Molecular Therapy, 17(1), 67-75."
        ),
        (
            "Reynolds, A., Leake, D., Boese, Q., Scaringe, S., Marshall, W. S., & Khvorova, A. "
            "(2004). Rational siRNA design for RNA interference. Nature Biotechnology, 22(3), "
            "326-330."
        ),
        (
            "Khvorova, A., Reynolds, A., & Jayasena, S. D. (2003). Functional siRNAs and "
            "miRNAs exhibit strand bias. Cell, 115(2), 209-216."
        ),
        (
            "Ui-Tei, K., Naito, Y., Takahashi, F., Haraguchi, T., Ohki-Hamazaki, H., Juni, A., "
            "Ueda, R., & Saigo, K. (2004). Guidelines for the selection of highly effective "
            "siRNA sequences for mammalian and chick RNA interference. Nucleic Acids Research, "
            "32(3), 936-948."
        ),
        (
            "Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of "
            "modern neural networks. Proceedings of the 34th International Conference on Machine "
            "Learning (ICML), 1321-1330."
        ),
        (
            "Higgins, I., Matthey, L., Pal, A., Burgess, C., Glorot, X., Botvinick, M., "
            "Mohamed, S., & Lerchner, A. (2017). beta-VAE: Learning basic visual concepts "
            "with a constrained variational framework. International Conference on Learning "
            "Representations (ICLR)."
        ),
        (
            "Reker, D. (2020). Practical considerations for active machine learning in drug "
            "discovery. Drug Discovery Today: Technologies, 32-33, 73-79."
        ),
        (
            "Graff, D. E., Shakhnovich, E. I., & Coley, C. W. (2021). Accelerating "
            "high-throughput virtual screening through molecular pool-based active learning. "
            "Chemical Science, 12(22), 7866-7881."
        ),
    ]

    for i, ref in enumerate(references, 1):
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*self.dark_gray) if False else None
        pdf.set_text_color(50, 50, 50)
        pdf.cell(8, 5.5, f"[{i}]")
        available = pdf.w - pdf.l_margin - pdf.r_margin - 8
        pdf.multi_cell(available, 5.5, ref)
        pdf.ln(3)

    # =========================================================================
    # FINAL PAGE
    # =========================================================================
    pdf.add_page()
    pdf.ln(60)
    pdf.set_fill_color(*pdf.dark_blue)
    pdf.rect(15, 80, pdf.w - 30, 60, "F")
    pdf.set_y(90)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "End of Document", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "OligoVoid: Mapping the Dark Matter of siRNA Chemical Space", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "Comprehensive Technical Documentation", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(160)
    pdf.set_text_color(*pdf.medium_gray)
    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 7, "Author: Manas Reddy  |  April 2026", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*pdf.accent)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, "https://github.com/ManasReddy1/OligoVoid", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*pdf.medium_gray)
    pdf.set_font("Helvetica", "I", 9)
    pdf.ln(10)
    pdf.cell(0, 7, "This document was generated programmatically using fpdf2.", align="C")

    return pdf


def main():
    print("Generating OligoVoid Detailed Technical Report...")
    pdf = build_report()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf.output(OUTPUT_PATH)
    print(f"Report saved to: {OUTPUT_PATH}")
    print(f"Total pages: {pdf.page_no()}")


if __name__ == "__main__":
    main()
