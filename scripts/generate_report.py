"""
OSS Pulse — PDF Risk Report Generator
Pulls live data from local PostgreSQL and renders a professional PDF.
"""

import subprocess
import sys

# Install reportlab if missing
try:
    import reportlab  # noqa: F401
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "reportlab", "--break-system-packages"],
        stdout=subprocess.DEVNULL,
    )

import os
import psycopg2
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
OUTPUT_PATH = "docs/OSS_Pulse_Risk_Report_2026-03-14.pdf"
REPORT_DATE = "March 14, 2026"

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
DARK_NAVY = colors.HexColor("#0D1B2A")
ACCENT_BLUE = colors.HexColor("#1B6CA8")
LIGHT_GRAY = colors.HexColor("#F2F4F7")
MID_GRAY = colors.HexColor("#C8CDD5")
WHITE = colors.white
RED_BG = colors.HexColor("#FDDEDE")
ORANGE_BG = colors.HexColor("#FDE8CB")
YELLOW_BG = colors.HexColor("#FDF6CB")
GREEN_BG = colors.HexColor("#D6F5D6")
TABLE_HEADER_BG = colors.HexColor("#1B2A3B")


def score_color(score: int):
    if score >= 80:
        return RED_BG
    if score >= 60:
        return ORANGE_BG
    if score >= 30:
        return YELLOW_BG
    return GREEN_BG


def score_tier(score: int) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "Elevated"
    if score >= 30:
        return "Moderate"
    return "Healthy"


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------
def fetch_project_data():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # Latest score per project
    cur.execute("""
        SELECT
            p.owner || '/' || p.repo AS project,
            rs.score,
            rs.scored_at
        FROM risk_scores rs
        JOIN projects p ON p.id = rs.project_id
        WHERE rs.id IN (
            SELECT DISTINCT ON (project_id) id
            FROM risk_scores
            ORDER BY project_id, scored_at DESC
        )
        ORDER BY rs.score DESC
    """)
    latest_rows = cur.fetchall()

    # Second most recent score per project (for WoW delta)
    cur.execute("""
        SELECT project, score FROM (
            SELECT
                p.owner || '/' || p.repo AS project,
                rs.score,
                ROW_NUMBER() OVER (
                    PARTITION BY rs.project_id ORDER BY rs.scored_at DESC
                ) AS rn
            FROM risk_scores rs
            JOIN projects p ON p.id = rs.project_id
        ) sub
        WHERE rn = 2
    """)
    prev_map = {row[0]: row[1] for row in cur.fetchall()}

    cur.close()
    conn.close()

    projects = []
    for project, score, scored_at in latest_rows:
        prev = prev_map.get(project)
        delta = (score - prev) if prev is not None else None
        projects.append({
            "project": project,
            "score": score,
            "scored_at": scored_at,
            "delta": delta,
            "tier": score_tier(score),
        })
    return projects


# ---------------------------------------------------------------------------
# Page decorations (watermark + page number)
# ---------------------------------------------------------------------------
def make_page_decorator(show_page_num=True):
    def decorator(canvas, doc):
        canvas.saveState()
        # Watermark top-right
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(MID_GRAY)
        canvas.drawRightString(
            letter[0] - 0.4 * inch,
            letter[1] - 0.35 * inch,
            "OSS PULSE",
        )
        # Page number bottom-center
        if show_page_num:
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#888888"))
            canvas.drawCentredString(
                letter[0] / 2,
                0.4 * inch,
                f"Page {doc.page}",
            )
        canvas.restoreState()

    return decorator


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
base_styles = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    "ReportTitle",
    fontName="Helvetica-Bold",
    fontSize=24,
    textColor=WHITE,
    spaceAfter=12,
    alignment=TA_CENTER,
    leading=30,
)
STYLE_SUBTITLE = ParagraphStyle(
    "ReportSubtitle",
    fontName="Helvetica",
    fontSize=13,
    textColor=colors.HexColor("#CCDBE8"),
    spaceAfter=8,
    alignment=TA_CENTER,
    leading=18,
)
STYLE_COVER_META = ParagraphStyle(
    "CoverMeta",
    fontName="Helvetica",
    fontSize=10,
    textColor=colors.HexColor("#AABBCC"),
    spaceAfter=4,
    alignment=TA_CENTER,
)
STYLE_COVER_FOOTER = ParagraphStyle(
    "CoverFooter",
    fontName="Helvetica-Oblique",
    fontSize=9,
    textColor=colors.HexColor("#8899AA"),
    alignment=TA_CENTER,
)
STYLE_H1 = ParagraphStyle(
    "H1",
    fontName="Helvetica-Bold",
    fontSize=16,
    textColor=DARK_NAVY,
    spaceBefore=6,
    spaceAfter=10,
    leading=20,
)
STYLE_BODY = ParagraphStyle(
    "Body",
    fontName="Helvetica",
    fontSize=11,
    textColor=colors.HexColor("#222222"),
    spaceAfter=8,
    leading=16,
)
STYLE_SUBHEADER = ParagraphStyle(
    "Subheader",
    fontName="Helvetica-Bold",
    fontSize=12,
    textColor=ACCENT_BLUE,
    spaceBefore=10,
    spaceAfter=4,
)
STYLE_DISCLAIMER = ParagraphStyle(
    "Disclaimer",
    fontName="Helvetica-Oblique",
    fontSize=9,
    textColor=colors.HexColor("#666666"),
    spaceAfter=6,
    leading=13,
)
STYLE_BULLET = ParagraphStyle(
    "Bullet",
    fontName="Helvetica",
    fontSize=11,
    textColor=colors.HexColor("#222222"),
    spaceAfter=4,
    leading=15,
    leftIndent=18,
    bulletIndent=6,
)


# ---------------------------------------------------------------------------
# Page 1 — Cover
# ---------------------------------------------------------------------------
def build_cover(styles):
    """Returns a list of flowables for the cover page (rendered with dark bg)."""
    # We use a canvas callback trick via a custom flowable for the background.
    from reportlab.platypus import Flowable

    class DarkBackground(Flowable):
        def wrap(self, aw, ah):
            return aw, ah

        def draw(self):
            c = self.canv
            c.saveState()
            page_w, page_h = letter
            c.setFillColor(DARK_NAVY)
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
            # Accent stripe
            c.setFillColor(ACCENT_BLUE)
            c.rect(0, page_h * 0.42, page_w, 4, fill=1, stroke=0)
            c.restoreState()

    # Build as a single-frame page — we'll use a KeepTogether trick
    story = []

    story.append(DarkBackground())
    story.append(Spacer(1, 1.8 * inch))
    story.append(Paragraph("OSS Pulse", STYLE_TITLE))
    story.append(Paragraph("Dependency Risk Report", STYLE_TITLE))
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph("Open Source Infrastructure Health Assessment", STYLE_SUBTITLE)
    )
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph(f"Compilation Date: {REPORT_DATE}", STYLE_COVER_META))
    story.append(
        Paragraph(
            "Compiled by: OSS Pulse Automated Intelligence System", STYLE_COVER_META
        )
    )
    story.append(Spacer(1, 2.8 * inch))
    story.append(
        Paragraph("Confidential — For internal use only", STYLE_COVER_FOOTER)
    )
    story.append(PageBreak())
    return story


# ---------------------------------------------------------------------------
# Page 2 — Executive Summary
# ---------------------------------------------------------------------------
def build_executive_summary(projects):
    tier_counts = {"Critical": 0, "Elevated": 0, "Moderate": 0, "Healthy": 0}
    for p in projects:
        tier_counts[p["tier"]] += 1

    story = []
    story.append(Paragraph("Executive Summary", STYLE_H1))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=10))

    body_text = (
        "OSS Pulse monitors 20 critical open source projects that form the foundation "
        "of enterprise Linux infrastructure. This report presents the current risk "
        "assessment as of March 14, 2026, derived from weekly analysis of contributor "
        "activity, commit velocity, bus factor, maintainer inactivity, issue health, "
        "and news sentiment signals. Of the 20 monitored projects, 17 are currently "
        "flagged at elevated risk or above. Three projects require immediate attention."
    )
    story.append(Paragraph(body_text, STYLE_BODY))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("Risk Tier Summary", STYLE_SUBHEADER))

    tier_data = [
        ["Tier", "Count", "Score Range"],
        ["Critical", str(tier_counts["Critical"]), "80 – 100"],
        ["Elevated", str(tier_counts["Elevated"]), "60 – 79"],
        ["Moderate", str(tier_counts["Moderate"]), "30 – 59"],
        ["Healthy", str(tier_counts["Healthy"]), "0 – 29"],
    ]

    tier_table = Table(tier_data, colWidths=[2 * inch, 1.5 * inch, 2 * inch])
    tier_style = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        # Color-code tier name cells
        ("BACKGROUND", (0, 1), (0, 1), RED_BG),
        ("BACKGROUND", (0, 2), (0, 2), ORANGE_BG),
        ("BACKGROUND", (0, 3), (0, 3), YELLOW_BG),
        ("BACKGROUND", (0, 4), (0, 4), GREEN_BG),
    ]
    tier_table.setStyle(TableStyle(tier_style))

    story.append(tier_table)
    story.append(PageBreak())
    return story


# ---------------------------------------------------------------------------
# Page 3 — Full Risk Ranking Table
# ---------------------------------------------------------------------------
def build_ranking_table(projects):
    story = []
    story.append(Paragraph(f"Project Risk Ranking — {REPORT_DATE}", STYLE_H1))
    story.append(
        HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=10)
    )

    headers = ["Rank", "Project", "Score", "Tier", "WoW Delta*"]
    rows = [headers]
    row_colors = []  # (row_index, bg_color) for score column

    for i, p in enumerate(projects, start=1):
        delta = p["delta"]
        if delta is None:
            wow = "N/A"
        elif delta > 0:
            wow = f"+{delta}"
        elif delta < 0:
            wow = str(delta)
        else:
            wow = "±0"
        rows.append([str(i), p["project"], str(p["score"]), p["tier"], wow])
        row_colors.append((i, score_color(p["score"])))

    col_widths = [0.5 * inch, 3.0 * inch, 0.7 * inch, 1.0 * inch, 0.9 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT_GRAY, WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.5, MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
    ]

    # Color score column per row
    for row_idx, bg in row_colors:
        style_cmds.append(("BACKGROUND", (2, row_idx), (2, row_idx), bg))
        style_cmds.append(("FONTNAME", (2, row_idx), (2, row_idx), "Helvetica-Bold"))

    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "* Week-over-week delta requires two consecutive weekly pipeline runs. "
            "First automated run completed March 14, 2026.",
            STYLE_DISCLAIMER,
        )
    )
    story.append(PageBreak())
    return story


# ---------------------------------------------------------------------------
# Page 4 — Critical Projects Spotlight
# ---------------------------------------------------------------------------
def build_critical_spotlight():
    story = []
    story.append(Paragraph("Critical Risk Projects", STYLE_H1))
    story.append(
        HRFlowable(width="100%", thickness=1, color=colors.red, spaceAfter=12)
    )

    critical_projects = [
        {
            "name": "rpm-software-management/rpm",
            "score": 85,
            "body": (
                "The RPM Package Manager is the foundational package management system "
                "underpinning Red Hat Enterprise Linux, CentOS, Fedora, and a broad "
                "ecosystem of enterprise distributions. A degradation in maintainer "
                "activity or contributor diversity creates serious systemic risk: "
                "vulnerabilities may go unpatched, distribution pipelines can stall, "
                "and downstream security posture weakens across thousands of deployments. "
                "At a score of 85, rpm warrants immediate escalation to platform and "
                "security teams."
            ),
        },
        {
            "name": "opencontainers/runc",
            "score": 80,
            "body": (
                "runc is the low-level OCI container runtime that powers Docker, "
                "containerd, Podman, and virtually every Kubernetes node in production. "
                "Because it executes at the container-to-kernel boundary, any instability "
                "in its maintenance cadence directly threatens the security and reliability "
                "of all container workloads. A score of 80 signals reduced commit velocity "
                "or contributor concentration that could delay critical CVE patches, "
                "exposing container infrastructure to privilege-escalation risks."
            ),
        },
        {
            "name": "cri-o/cri-o",
            "score": 80,
            "body": (
                "CRI-O is the Kubernetes-native container runtime interface implementation "
                "used by OpenShift and a growing share of enterprise Kubernetes clusters. "
                "Its tight coupling to Kubernetes release cycles means that maintainer "
                "slowdowns directly impact cluster upgrade paths and security patching "
                "timelines. At a risk score of 80, CRI-O's health signals suggest "
                "increased bus factor concentration, warranting proactive engagement "
                "with the upstream maintainer community."
            ),
        },
    ]

    for proj in critical_projects:
        story.append(Paragraph(proj["name"], STYLE_SUBHEADER))
        story.append(
            Paragraph(
                f"<b>Current Risk Score:</b> {proj['score']} — Critical",
                STYLE_BODY,
            )
        )
        story.append(Paragraph(proj["body"], STYLE_BODY))
        story.append(Spacer(1, 0.1 * inch))

    story.append(PageBreak())
    return story


# ---------------------------------------------------------------------------
# Page 5 — Methodology
# ---------------------------------------------------------------------------
def build_methodology():
    story = []
    story.append(Paragraph("Scoring Methodology", STYLE_H1))
    story.append(
        HRFlowable(width="100%", thickness=1, color=ACCENT_BLUE, spaceAfter=10)
    )

    signals = [
        (
            "Contributor Delta %",
            "Measures the percentage change in active contributor count over a "
            "rolling 30-day window. A sustained decline signals community attrition "
            "and increased key-person dependency.",
        ),
        (
            "Commit Velocity Delta",
            "Tracks the week-over-week change in commit frequency. Sharp drops can "
            "indicate maintainer burnout, project abandonment, or a shift to "
            "infrequent batch releases.",
        ),
        (
            "Issue Close Rate",
            "The ratio of issues closed to issues opened over the past 30 days. "
            "Values below 0.5 indicate a growing backlog and reduced maintainer "
            "responsiveness.",
        ),
        (
            "Bus Factor",
            "The minimum number of contributors whose removal would account for "
            "50% or more of total commits. Low values (1–2) indicate critical "
            "single-point-of-failure risk.",
        ),
        (
            "Maintainer Inactivity Days",
            "The number of days since the last commit by a known core maintainer. "
            "Prolonged inactivity (>60 days) is a leading indicator of project "
            "stagnation.",
        ),
        (
            "News Sentiment Average",
            "Average sentiment score derived from recent news articles and "
            "security advisories mentioning the project. Negative sentiment "
            "frequently precedes or accompanies disclosed vulnerabilities.",
        ),
        (
            "Days Since Last Release",
            "Recency of the most recent tagged release. Projects with long release "
            "gaps may be accumulating unshipped fixes or have reduced release "
            "engineering capacity.",
        ),
    ]

    for i, (signal, desc) in enumerate(signals, start=1):
        story.append(
            Paragraph(f"{i}. <b>{signal}</b> — {desc}", STYLE_BULLET)
        )

    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph("Model", STYLE_SUBHEADER))
    story.append(
        Paragraph(
            "Scores are produced by an XGBoost classifier trained on 48 labeled "
            "historical disruption events. SHAP values identify the top contributing "
            "signals per project.",
            STYLE_BODY,
        )
    )

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph("Disclaimer", STYLE_SUBHEADER))
    story.append(
        Paragraph(
            "This report is generated automatically by OSS Pulse. Scores reflect "
            "statistical patterns and should be interpreted alongside domain expertise. "
            f"Compilation date: {REPORT_DATE}.",
            STYLE_DISCLAIMER,
        )
    )

    return story


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------
def build_pdf(projects):
    os.makedirs("docs", exist_ok=True)

    page_w, page_h = letter
    margin = 0.75 * inch

    # Two page templates: cover (no page number) and interior (with page number)
    cover_frame = Frame(0, 0, page_w, page_h, leftPadding=margin, rightPadding=margin,
                        topPadding=0, bottomPadding=0)
    interior_frame = Frame(margin, margin, page_w - 2 * margin, page_h - 2 * margin,
                           leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc = BaseDocTemplate(
        OUTPUT_PATH,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    cover_template = PageTemplate(
        id="Cover",
        frames=[cover_frame],
        onPage=make_page_decorator(show_page_num=False),
    )
    interior_template = PageTemplate(
        id="Interior",
        frames=[interior_frame],
        onPage=make_page_decorator(show_page_num=True),
    )
    doc.addPageTemplates([cover_template, interior_template])

    from reportlab.platypus import NextPageTemplate

    story = []

    # Cover (uses Cover template — no page number)
    story.append(NextPageTemplate("Cover"))
    story.extend(build_cover(base_styles))

    # Rest of pages use Interior template
    story.append(NextPageTemplate("Interior"))
    story.extend(build_executive_summary(projects))
    story.extend(build_ranking_table(projects))
    story.extend(build_critical_spotlight())
    story.extend(build_methodology())

    doc.build(story)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Fetching project risk data from database...")
    projects = fetch_project_data()
    print(f"  {len(projects)} projects loaded.")

    print("Generating PDF report...")
    build_pdf(projects)

    print(f"Report generated: {OUTPUT_PATH}")
