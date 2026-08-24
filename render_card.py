#!/usr/bin/env python3
"""
Triangulation ring card renderer.

Turns the one-off HTML mockup built 23 Aug 2026 into a repeatable, data-driven
function. Input: one vendor's Movement/Visibility/Proof scores, tier, and
(optionally) an Impact Threat Level + Decision Lever pulled from PRLog.
Output: a single branded SVG card, ready to drop into the LinkedIn teaser,
the gated monthly leaderboard, or a Confirmed Card share-out.

Locked design inputs (see /areas/triangulation.md, /areas/swnw-brand.md):
- Rings: Movement (outer) / Visibility (middle) / Proof (inner), Apple
  Activity-ring style. Full ring = relative to that month's top vendor on
  each metric (rank-based, not fixed 0-100). A tracker with no data yet
  passes None, not 0 - renders as an empty track (no arc) and "-" in the
  score column, muted grey. RESOLVED 24 Aug 2026: a real 0 and "not
  measured yet" were rendering identically, which reads as a bad score
  rather than a missing one - caught on the real NiCE/RingCentral card,
  where Movement/Visibility are genuinely pending, not zero.
- Tier read off a coloured top border + text label - NOT baked into ring
  geometry (locked 1 Aug 2026, reaffirmed 23 Aug 2026: ring size/geometry
  must not carry a second meaning).
- Score line "Movement X . Visibility Y . Proof Z" printed under the rings.
- Decision Lever line: REMOVED 24 Aug 2026, was briefly built 23-24 Aug.
  Reasoning: a five-word category (Pricing/Roadmap/GTM messaging/M&A/
  Monitor) with no supporting reasoning reads as a label, not a judgment -
  same "one element doing a job it can't compress" problem already caught
  with ring-size-as-impact. Also works against the locked funnel design:
  the free LinkedIn teaser is deliberately capped at a single ring cluster,
  not the full analysis - a real Decision Lever with reasoning belongs in
  the gated write-up, reachable via the signal link below, not given away
  on the card. The impactThreatLevel/decisionLever PRLog fields still
  exist and are still useful as a longitudinal record; they're just not
  rendered on the card.
- Signal link (built 24 Aug 2026): a "Read the Signal ->" line at the
  card's foot, pulling PRLog's existing swnwPieceUrl/swnwPieceTitle fields
  - populated already at publish time by signal-wix, no new data needed.
  Kept deliberately separate from the rings/score legend: this is a
  navigation element (where to read more), not evidence of how much the
  move landed - that distinction is the reason it lives at the card's
  foot, not folded into the Proof ring or score columns.
- PR summary line (built 24 Aug 2026): a one-sentence factual synopsis of
  the press release itself, sitting between the pillar tag and the rings.
  Closes a real gap - before this, the card showed Vendor/Pillar/Tier/
  scores but never WHAT the vendor actually did, forcing a click-through
  just to find out what's being tracked. Sourced from PRLog's
  `prSummaryShort` field (signal-brief/pattern-brief/teardown-brief's
  Step 3.5/1.5/1.5, ~90-char fill-in-the-blank template: "[Vendor]
  [past-tense verb] [concrete change], for [buyer/use case]."). Evidence
  only, same discipline as everything else on this card - never the
  deeper "so what," which stays in the gated write-up reachable via the
  signal link below. Optional: cards for vendors/pillars logged before
  this field existed render exactly as before, just without this line -
  the layout only reserves the extra vertical space when the field is
  present, so older cards don't gain empty whitespace.
- Brand palette: Core #0d0a1f, Insight #3b408c, Trust #8c2ead, Edge #40e0d1,
  Base #f5f2f0. Inter font family.

Open design question NOT resolved by this script (flag to Tim before using
on an Early/Static-tier vendor): the signal link is omitted entirely when
no piece has been written yet, rather than shown as a blank/pending state.
Revisit once that's a real decision rather than a default.

NOT part of this card, flagged as a separate backlog item: third-party
pickup outlets (CX Today, Renascence, etc.) that fed the Proof score.
SHIPPED 24 Aug 2026 into PRLog's own `pickups` field (see resonance-tracker
Steps 8/9) - captured for the published write-up and the longitudinal
record, deliberately still not rendered on this card; the card's job is
the quick-read overview, not the full pickup list.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Optional

BRAND = {
    "core": "#0d0a1f",
    "insight": "#3b408c",   # Movement
    "trust": "#8c2ead",     # Visibility (also used for tier border by default)
    "edge": "#40e0d1",      # Proof
    "base": "#f5f2f0",
}

TIER_COLOUR = {
    "Confirmed": BRAND["edge"],
    "Early": BRAND["insight"],
    "Static": "#6b6478",  # muted grey - matches the mockup's inactive tone
}

# One-line gloss under the tier label - added 24 Aug 2026. "CONFIRMED" alone
# is SWNW's internal tier name; it carries no inherent meaning to a reader
# who hasn't separately read the legend. Same flaw already caught and fixed
# once on this card - Decision Lever was cut because a label with no
# reasoning attached reads as jargon, not information (see module
# docstring). Fixed here the same way Movement/Visibility/Proof already
# solve it: a short source line under the value (Heat Index/SOV/Resonance),
# not a separate lookup. Wording matches render_legend_svg's TIER rows
# verbatim so the card and the legend never drift apart.
TIER_GLOSS = {
    "Confirmed": "All three signals agree",
    "Early": "Two of three signals present",
    "Static": "Not enough signal yet",
}

RING_RADII = {"movement": 92, "visibility": 72, "proof": 52}
RING_STROKE = 14

# Rough chars-per-line at 12px Inter within the card's ~300px text width -
# used only to decide wrap points, not rendered directly.
SUMMARY_CHARS_PER_LINE = 46
SUMMARY_LINE_HEIGHT = 15


@dataclass
class CardInput:
    vendor: str
    movement: Optional[float]  # 0-100 relative-to-top-vendor score; None = pending, renders "-"
    visibility: Optional[float]
    proof: Optional[float]
    tier: str                 # "Confirmed" | "Early" | "Static"
    pillar: Optional[str] = None
    confidence: Optional[str] = None       # "High" | "Moderate" | "Low"
    confidence_reason: Optional[str] = None
    signal_url: Optional[str] = None       # PRLog's swnwPieceUrl - None => line omitted
    signal_title: Optional[str] = None     # PRLog's swnwPieceTitle, optional label text
    pr_summary_short: Optional[str] = None # PRLog's prSummaryShort - None => line omitted, layout unchanged


def _ring_arc(cx: float, cy: float, r: float, pct: float, colour: str, stroke: float) -> str:
    """One Activity-ring style arc, pct in [0,100]. Full ring at pct>=100."""
    pct = max(0.0, min(100.0, pct))
    if pct <= 0:
        return ""
    circumference = 2 * 3.14159265 * r
    dash = circumference * (pct / 100.0)
    gap = circumference - dash
    # start at 12 o'clock, clockwise
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colour}" '
        f'stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-dasharray="{dash:.2f} {gap:.2f}" '
        f'transform="rotate(-90 {cx} {cy})" opacity="0.95"/>'
    )


def _ring_track(cx: float, cy: float, r: float, stroke: float) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="{BRAND["base"]}" stroke-width="{stroke}" opacity="0.25"/>'
    )


def _wrap_summary(text: str, chars_per_line: int = SUMMARY_CHARS_PER_LINE, max_lines: int = 3) -> list:
    """Greedy word-wrap into at most max_lines lines. prSummaryShort is
    supposed to already respect the ~90 char cap set at drafting time, so
    at ~44-46 usable chars/line this should always fit within 2 lines in
    practice - max_lines=3 is a safety margin, not the expected case. If
    words are still left over after max_lines, the last line is truncated
    with an ellipsis rather than silently dropping the remainder."""
    words = text.split()
    lines = []
    idx = 0
    while idx < len(words) and len(lines) < max_lines:
        current = words[idx]
        idx += 1
        while idx < len(words):
            candidate = f"{current} {words[idx]}"
            if len(candidate) <= chars_per_line:
                current = candidate
                idx += 1
            else:
                break
        lines.append(current)

    if idx < len(words):
        # Leftover words after filling every line - fold as many as still
        # fit into the last line, then mark the truncation with an
        # ellipsis so it's visibly cut rather than silently incomplete.
        combined = lines[-1]
        for word in words[idx:]:
            candidate = f"{combined} {word}"
            if len(candidate) + 1 <= chars_per_line:  # +1 reserves room for the ellipsis
                combined = candidate
            else:
                break
        lines[-1] = f"{combined}\u2026"

    return lines


def render_card_svg(data: CardInput, show_tier_label: bool = True) -> str:
    """show_tier_label controls whether the "CONFIRMED"/"EARLY"/etc. text
    and its one-line gloss render under the rings - added 24 Aug 2026.
    Defaults True (unchanged behaviour for a standalone card, e.g. the
    LinkedIn teaser or leaderboard, which has no legend attached and needs
    the tier spelled out). render_combined_svg passes False: once the
    legend sits right beside the card in the same file, its own TIER
    section already names and explains every tier - repeating the label on
    the card too is pure duplication, not a second useful signal. The
    coloured top border still marks the tier visually either way."""
    tier_colour = TIER_COLOUR.get(data.tier, "#6b6478")

    # Reserve vertical space for the PR summary line only when it's
    # present, so cards logged before this field existed (or vendors
    # where the brief genuinely didn't produce one) keep the original
    # layout exactly, rather than gaining dead whitespace.
    summary_lines = _wrap_summary(data.pr_summary_short) if data.pr_summary_short else []
    offset = (len(summary_lines) * SUMMARY_LINE_HEIGHT) + 10 if summary_lines else 0

    # How much vertical space to close up when the tier label+gloss is
    # hidden (40px = the block they occupy: label at +290, gloss at +306,
    # 24px clearance before the next element at +330). Applied to every
    # coordinate below that point so nothing leaves a gap or collides.
    tier_gap = 0 if show_tier_label else 40

    cx, cy = 170, 170 + offset

    rings = []
    tracks = []
    for key, colour, val in [
        ("movement", BRAND["insight"], data.movement),
        ("visibility", BRAND["trust"], data.visibility),
        ("proof", BRAND["edge"], data.proof),
    ]:
        r = RING_RADII[key]
        tracks.append(_ring_track(cx, cy, r, RING_STROKE))
        if val is not None:
            rings.append(_ring_arc(cx, cy, r, val, colour, RING_STROKE))

    # Three-column score legend, colour-matched to each ring. Stacked
    # label/value/source per column (not inline "Label NN") - the earlier
    # inline version collided ("Movement 88" ran into "Visibility 64")
    # because three columns in a 340px card don't leave room for two-word
    # inline text. Stacking removes the horizontal collision regardless of
    # label length, since each column is bounded to a fixed width.
    columns = [
        ("Movement", data.movement, "Heat Index", BRAND["insight"]),
        ("Visibility", data.visibility, "SOV", BRAND["trust"]),
        ("Proof", data.proof, "Resonance", BRAND["edge"]),
    ]
    col_x = [65, 170, 275]  # thirds of the 340-wide card
    score_columns_svg = ""
    for (label, raw_val, source, colour), x in zip(columns, col_x):
        pending = raw_val is None
        value = "\u2014" if pending else f"{raw_val:.0f}"
        # Pending columns render muted grey, not the tracker's real colour -
        # an em dash in Insight indigo would still read as "this is a
        # Movement reading" when there isn't one yet.
        label_colour = "#8b8494" if pending else colour
        value_colour = "#8b8494" if pending else colour
        score_columns_svg += f"""
    <text x="{x}" y="{330 + offset - tier_gap}" text-anchor="middle" font-family="Inter, sans-serif"
          font-weight="700" font-size="10" fill="{label_colour}" letter-spacing="0.03em"
          text-transform="uppercase">{label}</text>
    <text x="{x}" y="{352 + offset - tier_gap}" text-anchor="middle" font-family="Inter, sans-serif"
          font-weight="800" font-size="20" fill="{value_colour}">{value}</text>
    <text x="{x}" y="{366 + offset - tier_gap}" text-anchor="middle" font-family="Inter, sans-serif"
          font-weight="500" font-size="9" fill="#8b8494" letter-spacing="0.03em"
          text-transform="uppercase">{source}{' . pending' if pending else ''}</text>"""

    tier_label_svg = ""
    if show_tier_label:
        tier_label_svg = f"""
  <text x="170" y="{290 + offset}" text-anchor="middle" font-weight="700" font-size="12"
        fill="{tier_colour}" letter-spacing="0.08em">{data.tier.upper()}</text>
  <text x="170" y="{306 + offset}" text-anchor="middle" font-family="Inter, sans-serif"
        font-weight="500" font-size="10" fill="#8b8494">{TIER_GLOSS.get(data.tier, "")}</text>"""

    confidence_svg = ""
    if data.confidence:
        conf_text = data.confidence
        if data.confidence_reason:
            conf_text += f" - {data.confidence_reason}"
        confidence_svg = f"""
    <text x="170" y="{396 + offset - tier_gap}" text-anchor="middle" font-family="Inter, sans-serif"
          font-weight="500" font-size="11" fill="#6b6478">{conf_text}</text>"""

    pillar_svg = ""
    if data.pillar:
        pillar_svg = f"""
    <text x="170" y="46" text-anchor="middle" font-family="Inter, sans-serif"
          font-weight="600" font-size="11" fill="#6b6478"
          text-transform="uppercase" letter-spacing="0.08em">{data.pillar.upper()}</text>"""

    summary_svg = ""
    if summary_lines:
        summary_start_y = 62
        summary_text_nodes = "".join(
            f'<tspan x="170" dy="{0 if i == 0 else SUMMARY_LINE_HEIGHT}">{line}</tspan>'
            for i, line in enumerate(summary_lines)
        )
        summary_svg = f"""
    <text x="170" y="{summary_start_y}" text-anchor="middle" font-family="Inter, sans-serif"
          font-weight="500" font-size="12" fill="{BRAND['core']}" opacity="0.85">{summary_text_nodes}</text>"""

    signal_link_svg = ""
    if data.signal_url:
        def _truncate_on_word(text: str, limit: int) -> str:
            if len(text) <= limit:
                return text
            trimmed = text[:limit].rsplit(" ", 1)[0]
            return f"{trimmed}\u2026"

        link_text = (
            "Read the Signal \u2192" if not data.signal_title
            else f"Read: {_truncate_on_word(data.signal_title, 34)} \u2192"
        )
        signal_link_svg = f"""
    <line x1="40" y1="{412 + offset - tier_gap}" x2="300" y2="{412 + offset - tier_gap}" stroke="#e3ded9" stroke-width="1"/>
    <a href="{data.signal_url}" target="_blank">
      <text x="170" y="{428 + offset - tier_gap}" text-anchor="middle" font-family="Inter, sans-serif"
            font-weight="600" font-size="11" fill="{BRAND['trust']}"
            text-decoration="underline">{link_text}</text>
    </a>"""

    canvas_height = 446 + offset - tier_gap

    svg = f"""<svg viewBox="0 0 340 {canvas_height}" xmlns="http://www.w3.org/2000/svg" font-family="Inter, sans-serif">
  <rect x="0" y="0" width="340" height="{canvas_height}" rx="16" fill="{BRAND['base']}"/>
  <rect x="0" y="0" width="340" height="6" rx="3" fill="{tier_colour}"/>

  <text x="170" y="26" text-anchor="middle" font-weight="800" font-size="19"
        fill="{BRAND['core']}">{data.vendor}</text>
  {pillar_svg}
  {summary_svg}

  <g>
    {''.join(tracks)}
    {''.join(rings)}
  </g>

  {tier_label_svg}

  {score_columns_svg}
  {confidence_svg}
  {signal_link_svg}
</svg>"""
    return svg


def render_legend_svg(highlight_tier: Optional[str] = None) -> str:
    """A single, reusable "how to read this" explainer for the Triangulation
    ring cards - built 24 Aug 2026, in response to a real reader-facing gap:
    the cards themselves are deliberately terse (see the module docstring -
    evidence only, five-second scan, no baked-in judgment), which is correct
    for the card itself but leaves a first-time reader with no way to know
    what the three ring colours or the tier label actually mean.

    Deliberately NOT rendered per-vendor or baked into render_card_svg's
    output - that would reintroduce the clutter the terse design was built
    to avoid, and most of a card's content (vendor, PR summary, scores) is
    unique per run while this explainer is identical every time. Generate
    this once, pair it alongside the FIRST ring card that appears in any
    given context (a post, a page, a teaser), not repeated on every card.
    Same static-asset pattern as a chart's axis legend: drawn once, reused
    wherever the chart type recurs.

    highlight_tier - added 24 Aug 2026, replacing the card's own tier label
    (see render_card_svg's show_tier_label) as the answer to "which tier
    does THIS vendor sit at": rather than repeat the tier name a second
    time on the card, the matching TIER row here stays in full colour and
    the other two grey out, so the one that applies is obvious by contrast
    without duplicating text. None (default) keeps the legend fully
    vendor-independent - all three tiers shown at equal weight - for any
    context where it's reused without a specific card (a standalone "how
    this works" reference), which is why this stays optional rather than
    required.
    """
    swatch_r = 7
    rows = [
        (BRAND["insight"], "Movement", "Search interest for the vendor, ranked against the pillar's top mover that month (Heat Index)."),
        (BRAND["trust"], "Visibility", "Share of voice in search/AI results for the same tracked terms (SOV)."),
        (BRAND["edge"], "Proof", "Whether the vendor's own announcements actually landed with buyers afterwards (Resonance)."),
    ]

    def _wrap(text: str, chars_per_line: int = 34) -> list:
        return _wrap_summary(text, chars_per_line=chars_per_line, max_lines=3)

    row_blocks = []
    y = 108
    for colour, label, desc in rows:
        desc_lines = _wrap(desc)
        row_blocks.append(f"""
<circle cx="34" cy="{y}" r="{swatch_r}" fill="{colour}"/>
<text x="52" y="{y + 4}" font-family="Inter, sans-serif" font-weight="700"
    font-size="13" fill="{BRAND['core']}">{label}</text>""")
        desc_y = y + 20
        for i, line in enumerate(desc_lines):
            row_blocks.append(f"""
<text x="52" y="{desc_y + i * 14}" font-family="Inter, sans-serif"
    font-weight="500" font-size="11" fill="#6b6478">{line}</text>""")
        y = desc_y + len(desc_lines) * 14 + 22

    tier_y = y + 4
    tier_rows = [
        ("Confirmed", TIER_COLOUR["Confirmed"], "Confirmed", "All three legs agree - the strongest read available."),
        ("Early", TIER_COLOUR["Early"], "Early", "Two of three legs present, not yet all agreeing."),
        ("Static", TIER_COLOUR["Static"], "Static / pending", "Fewer than two legs have real data yet - shown as a dash, not a zero."),
    ]
    tier_blocks = [f"""
<text x="34" y="{tier_y}" font-family="Inter, sans-serif" font-weight="800"
    font-size="13" fill="{BRAND['core']}" letter-spacing="0.04em">TIER</text>"""]
    ty = tier_y + 22
    # Muted grey for whichever tiers don't apply to this card - matches the
    # rest of the file's existing "pending" grey (#8b8494/#6b6478 family)
    # rather than inventing a new tone.
    inactive_swatch = "#c7c2c9"
    inactive_label = "#8b8494"
    inactive_desc = "#a8a3ab"
    for tier_name, colour, label, desc in tier_rows:
        active = highlight_tier is None or tier_name == highlight_tier
        swatch_colour = colour if active else inactive_swatch
        label_colour = BRAND['core'] if active else inactive_label
        desc_colour = "#6b6478" if active else inactive_desc
        tier_blocks.append(f"""
<rect x="27" y="{ty - 10}" width="14" height="14" rx="3" fill="{swatch_colour}"/>
<text x="52" y="{ty + 1}" font-family="Inter, sans-serif" font-weight="700"
    font-size="12" fill="{label_colour}">{label}</text>""")
        desc_lines = _wrap(desc, chars_per_line=36)
        for i, line in enumerate(desc_lines):
            ty += 15
            tier_blocks.append(f"""
<text x="52" y="{ty + 1}" font-family="Inter, sans-serif" font-weight="500"
    font-size="10.5" fill="{desc_colour}">{line}</text>""")
        ty += 24

    canvas_height = int(ty + 16)

    svg = f"""<svg viewBox="0 0 340 {canvas_height}" xmlns="http://www.w3.org/2000/svg" font-family="Inter, sans-serif">
<rect x="0" y="0" width="340" height="{canvas_height}" rx="16" fill="{BRAND['base']}"/>
<rect x="0" y="0" width="340" height="6" rx="3" fill="{BRAND['trust']}"/>

<text x="170" y="30" text-anchor="middle" font-weight="800" font-size="15"
    fill="{BRAND['core']}">How to read a Triangulation card</text>
<text x="170" y="48" text-anchor="middle" font-family="Inter, sans-serif"
    font-weight="500" font-size="10" fill="#6b6478" letter-spacing="0.03em"
    text-transform="uppercase">Three independent trackers, one vendor</text>

<line x1="24" y1="64" x2="316" y2="64" stroke="#e3ded9" stroke-width="1"/>

{''.join(row_blocks)}
<line x1="24" y1="{tier_y - 22}" x2="316" y2="{tier_y - 22}" stroke="#e3ded9" stroke-width="1"/>
{''.join(tier_blocks)}
</svg>"""
    return svg


def render_combined_svg(data: CardInput) -> str:
    """Card (left) + legend (right), in one file - added 24 Aug 2026 as the
    standing hero-image format. Every future vendor card is generated this
    way by default: one upload instead of two, legend always travels with
    its card rather than depending on someone remembering to pair them.

    Implementation: strips each existing, unmodified render function's
    outer <svg> wrapper and re-parents its inner markup under a translate
    group on one shared canvas - NOT a nested <svg viewBox="..."> per
    panel. Nested <svg> looked like the natural approach but doesn't
    reliably establish its own clipped coordinate system across renderers
    (confirmed broken in cairosvg specifically: the right-hand panel's text
    overflowed straight past the canvas edge instead of clipping to its own
    340-unit box). A translate-only <g> avoids the ambiguity entirely - the
    same absolute coordinates render exactly as they did standalone, just
    offset, so font sizes stay byte-for-byte what render_card_svg/
    render_legend_svg already output. The legend is naturally taller than
    the card (more rows of prose); rather than shrink the legend's type to
    force a matching height, the shorter card is vertically centred against
    the legend's full height, and the combined canvas is simply as tall as
    the legend needs.
    """
    card_svg = render_card_svg(data, show_tier_label=False)
    legend_svg = render_legend_svg(highlight_tier=data.tier)

    def _extract_height(svg: str) -> int:
        match = re.search(r'viewBox="0 0 340 (\d+)"', svg)
        if not match:
            raise ValueError("Could not read panel height from generated SVG viewBox.")
        return int(match.group(1))

    def _inner_content(svg: str) -> str:
        """Strip the outer <svg ...> ... </svg> wrapper, keeping only what's
        inside it, so it can be re-parented under a <g> on the shared canvas
        instead of establishing its own (unreliable, see docstring above)
        nested coordinate system."""
        opening_tag_end = svg.index(">") + 1
        closing_tag_start = svg.rindex("</svg>")
        return svg[opening_tag_end:closing_tag_start]

    card_height = _extract_height(card_svg)
    legend_height = _extract_height(legend_svg)
    card_inner = _inner_content(card_svg)
    legend_inner = _inner_content(legend_svg)

    panel_width = 340
    gap = 24
    combined_width = panel_width * 2 + gap
    combined_height = max(card_height, legend_height)

    card_y = (combined_height - card_height) // 2
    legend_y = (combined_height - legend_height) // 2

    combined = f"""<svg viewBox="0 0 {combined_width} {combined_height}" xmlns="http://www.w3.org/2000/svg" font-family="Inter, sans-serif">
<rect x="0" y="0" width="{combined_width}" height="{combined_height}" fill="{BRAND['base']}"/>
<g transform="translate(0, {card_y})">
{card_inner}
</g>
<g transform="translate({panel_width + gap}, {legend_y})">
{legend_inner}
</g>
</svg>"""
    return combined


def main():
    ap = argparse.ArgumentParser(description="Render a Triangulation ring card as SVG.")
    ap.add_argument("--json", help="Path to a JSON file with the card's input fields.")
    ap.add_argument("--out", default="triangulation-card.svg", help="Output SVG path.")
    ap.add_argument("--legend", action="store_true",
                     help="Render the static, vendor-independent legend instead of a card. "
                          "Ignores --json; --out still applies.")
    ap.add_argument("--combined", action="store_true",
                     help="Render the card and legend side by side as one file - the "
                          "standing hero-image format (added 24 Aug 2026). Requires --json "
                          "(or uses the demo payload). Do NOT use this for the LinkedIn "
                          "teaser or leaderboard - those stay card-only per the locked "
                          "funnel design; --combined is for blog-post hero images only.")
    args = ap.parse_args()

    if args.legend:
        svg = render_legend_svg()
        with open(args.out, "w") as f:
            f.write(svg)
        print(f"Wrote {args.out}", file=sys.stderr)
        return

    if args.json:
        with open(args.json) as f:
            payload = json.load(f)
    else:
        # Demo payload - real, worked example from the resonance-tracker
        # backlog entry (NiCE/RingCentral, still Early tier, Proof lit only,
        # no Decision Lever yet since no piece has been written on it).
        payload = {
            "vendor": "NiCE / RingCentral",
            "movement": None,
            "visibility": None,
            "proof": 78,
            "tier": "Early",
            "pillar": "UC / CCaaS",
            "confidence": "Low",
            "confidence_reason": "fewer than 6-8 weeks of Movement/Visibility history",
            "pr_summary_short": "NiCE and RingCentral integrated their platforms for unified CX and UC administration.",
        }

    card = CardInput(**payload)
    svg = render_combined_svg(card) if args.combined else render_card_svg(card)
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"Wrote {args.out}", file=sys.stderr)




if __name__ == "__main__":
    main()
