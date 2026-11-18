"""Vector drawings of Fig. 1, Fig. 2 (two-stage procedure) and Fig. 3 (SVG, then PNG at 600 dpi with rsvg-convert if available).

The content follows the author's draw.io sources (eam.drawio, eam_reference_architecture_c4.drawio).
Both figures are drawn at the final text width (482 pt = 6.69 in), so every label is >= 8 pt in print.

    python3 diagrams.py
"""
import shutil
import subprocess
from html import escape

from paths import FIGURES

W = 482.0                      # text width of the IJITCS A4 template in points
FONT = "Arial, Helvetica, sans-serif"
INK, GREY = "#1a1a1a", "#666666"
FILL, FILL_EAM, FILL_KB, FILL_OP = "#f2f2f2", "#dae8fc", "#d5e8d4", "#fff2cc"


class SVG:
    def __init__(self, w, h):
        self.w, self.h, self.items = w, h, []

    def rect(self, x, y, w, h, fill=FILL, stroke=GREY, dash=None, rx=4, sw=0.8):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.items.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, lines, size=8.5, bold=False, anchor="middle", rotate=False, italic=False, color=INK):
        if isinstance(lines, str):
            lines = [lines]
        lh = size * 1.15
        y0 = y - lh * (len(lines) - 1) / 2 + size * 0.35
        attrs = f'font-family="{FONT}" font-size="{size}" fill="{color}" text-anchor="{anchor}"'
        if bold:
            attrs += ' font-weight="bold"'
        if italic:
            attrs += ' font-style="italic"'
        if rotate:
            attrs += f' transform="rotate(-90 {x:.1f} {y:.1f})"'
        def rich(t):            # "Δ_{run}" -> subscript tspan
            out, i = [], 0
            while True:
                j = t.find("_{", i)
                if j < 0:
                    out.append(escape(t[i:])); break
                k = t.index("}", j)
                out.append(escape(t[i:j]))
                out.append(f'<tspan baseline-shift="sub" font-size="{max(8.0, size * 0.85):.1f}">{escape(t[j + 2:k])}</tspan>')
                i = k + 1
            return "".join(out)
        spans = "".join(f'<tspan x="{x:.1f}" y="{y0 + i * lh:.1f}">{rich(t)}</tspan>' for i, t in enumerate(lines))
        self.items.append(f"<text {attrs}>{spans}</text>")

    def line(self, pts, arrow=True, color=GREY, sw=0.8):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        m = ' marker-end="url(#a)"' if arrow else ""
        self.items.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{m}/>')

    def save(self, path):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}pt" height="{self.h}pt" '
                f'viewBox="0 0 {self.w} {self.h}"><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{GREY}"/></marker></defs>'
                f'<rect width="100%" height="100%" fill="white"/>')
        path.write_text(head + "".join(self.items) + "</svg>", encoding="utf-8")


def box(s, x, y, w, h, label, fill=FILL, size=8.5, bold=True, stroke=GREY):
    s.rect(x, y, w, h, fill=fill, stroke=stroke)
    s.text(x + w / 2, y + h / 2, label, size=size, bold=bold)


# ---------------------------------------------------------------- Fig. 1
def fig1():
    groups = [("Classical", ["Descriptive", "Diagnostic", "Predictive", "Prescriptive"], FILL),
              ("Execution modes", ["Continuous", "Periodic", "Event-driven", "On-demand"], FILL),
              ("Methodological", ["Rule-based", "Model-based", "Data-driven", "Knowledge-driven", "Hybrid"], FILL),
              ("Adaptive and intelligent", ["Adaptive", "Self-learning", "Observability-driven", "Autonomic",
                                            "Context-aware", "Semantic-aware", "Goal-aware"], FILL),
              ("Evolution-aware (proposed)", ["Configuration drift", "Topology drift", "Role drift", "Policy drift",
                                              "Architectural drift", "Contextual drift", "Semantic drift",
                                              "Goal drift", "Security drift"], FILL_EAM)]
    n = sum(len(g[1]) for g in groups)
    gap_leaf, gap_group = 2.0, 6.0
    leaf_w = (W - gap_leaf * (n - len(groups)) - gap_group * (len(groups) - 1)) / n
    H = 198.0
    s = SVG(W, H)
    root_y, grp_y, grp_h, leaf_y, leaf_h = 4, 52, 26, 100, 96
    box(s, W / 2 - 95, root_y, 190, 20, "Intelligent monitoring taxonomy", size=9)
    x = 0.0
    for name, leaves, fill in groups:
        gw = len(leaves) * leaf_w + (len(leaves) - 1) * gap_leaf
        stroke = "#6c8ebf" if fill == FILL_EAM else GREY
        s.line([(W / 2, root_y + 20), (x + gw / 2, grp_y)])
        label = name.split(" ", 1) if len(name) > 14 else [name]
        box(s, x, grp_y, gw, grp_h, label, fill=fill, size=8.5, stroke=stroke)
        for i, leaf in enumerate(leaves):
            lx = x + i * (leaf_w + gap_leaf)
            s.line([(x + gw / 2, grp_y + grp_h), (lx + leaf_w / 2, leaf_y)])
            s.rect(lx, leaf_y, leaf_w, leaf_h, fill=fill, stroke=stroke, rx=2)
            s.text(lx + leaf_w / 2, leaf_y + leaf_h / 2, leaf, size=8, rotate=True)
        x += gw + gap_group
    return s


# ---------------------------------------------------------------- Fig. 2
def fig2():
    H = 262.0
    s = SVG(W, H)
    # platform boundary
    s.rect(100, 2, 286, 244, fill="none", stroke="#6c8ebf", dash="4,3", rx=8)
    s.text(243, 254, "Evolution-aware monitoring platform", size=8.5, italic=True, color="#2f4f7f")
    bw, bh = 96, 34
    # external sources (left)
    box(s, 0, 8, 88, bh, ["Observability and", "runtime sources"], bold=False)
    box(s, 0, 56, 88, bh, ["Operational", "environment"], bold=False)
    box(s, 0, 104, 88, bh, ["Monitored IS /", "dynamic MAS"], bold=False)
    box(s, 0, 190, 88, bh, ["Runtime state", "store"], fill=FILL_KB, bold=False, stroke="#82b366")
    # platform layers
    L = {"L1": (112, 8, ["L1 Evidence", "acquisition"]), "L2": (112, 104, ["L2 Normalization", "and correlation"]),
         "L3": (220, 8, ["L3 Runtime model", "reconstruction"]), "L4": (282, 62, ["L4 Drift vector", "and EDI"]),
         "L5": (282, 128, ["L5 Interpretation", "and assessment"]), "L6": (282, 196, ["L6 Response and", "re-check zone A(t)"])}
    for k, (x, y, lab) in L.items():
        box(s, x, y, bw, bh, lab, fill=FILL_EAM, stroke="#6c8ebf")
    # right-hand actors
    box(s, 396, 62, 86, bh, ["Knowledge base", "(K, Φ_{D})"], fill=FILL_KB, bold=False, stroke="#82b366", size=9.5)
    box(s, 396, 196, 86, bh, ["Operator /", "governance"], fill=FILL_OP, bold=False, stroke="#d6b656")
    # data flow
    for y in (25, 73, 121):
        s.line([(88, y), (112, 25 if y == 25 else (30 if y == 73 else 36))])
    s.line([(160, 42), (160, 104)]); s.text(164, 73, ["raw", "evidence"], size=8, anchor="start")
    s.line([(208, 121), (240, 121), (240, 42)]); s.text(244, 98, ["normalized", "evidence"], size=8, anchor="start")
    s.line([(316, 25), (330, 25), (330, 62)])
    s.line([(396, 79), (378, 79)]); s.text(437, 54, "reference model", size=8)
    s.line([(330, 96), (330, 128)]); s.text(334, 112, "Δ_{run}, Δ_{rel}", size=9.5, anchor="start")
    s.line([(439, 96), (439, 145), (378, 145)]); s.text(443, 118, ["rules,", "ontologies"], size=8, anchor="start")
    s.line([(330, 162), (330, 196)]); s.text(334, 179, "state, trend", size=8, anchor="start")
    s.line([(378, 160), (420, 160), (420, 196)]); s.text(392, 174, "alerts", size=8, anchor="start")
    s.line([(439, 230), (439, 240), (330, 240), (330, 230)]); s.text(392, 247, "reviews / approves", size=8)
    s.line([(468, 196), (468, 96)]); s.text(476, 150, "maintains", size=8, rotate=True)
    s.line([(282, 228), (44, 228), (44, 138)]); s.text(165, 235, "probe updates, corrections, escalation", size=8)
    # state store links
    s.line([(112, 132), (88, 200)]); s.text(120, 160, ["store evidence,", "models, drift", "and actions"], size=8, anchor="start")
    return s


def fig_two_stage():
    """Two-stage procedure: Stage 1 identifies evolution, Stage 2 keeps, modifies or synthesizes monitoring."""
    H = 128.0
    s = SVG(W, H)
    # stage frames
    s.rect(0, 2, 214, 112, fill="none", stroke="#6c8ebf", dash="4,3", rx=6)
    s.text(107, 122, "Stage 1: monitoring the evolution of the IS", size=8.5, italic=True, color="#2f4f7f")
    s.rect(228, 2, 254, 112, fill="none", stroke="#82b366", dash="4,3", rx=6)
    s.text(355, 122, "Stage 2: adapting the monitoring system", size=8.5, italic=True, color="#3d6b35")
    # stage 1
    box(s, 6, 10, 104, 30, ["Evidence E(t): telemetry,", "code, advisories"], bold=False, size=8)
    box(s, 6, 50, 104, 30, ["Active release model", "M_{ref}(v), approved changes"], bold=False, size=8)
    box(s, 120, 22, 88, 46, ["Nine drift operators", "Δ_{run}, Δ_{rel}, EDI,", "CriticalCheck"], fill=FILL_EAM, stroke="#6c8ebf", size=8)
    box(s, 120, 78, 88, 28, ["Evolution event", "or no change"], fill=FILL_EAM, stroke="#6c8ebf", size=8)
    s.line([(110, 25), (120, 38)]); s.line([(110, 65), (120, 52)]); s.line([(164, 68), (164, 78)])
    # stage 2
    box(s, 236, 34, 84, 40, ["Dependency map Φ_{D}", "→ probe-update", "zone A(t)"], fill=FILL_KB, stroke="#82b366", size=8)
    s.line([(208, 92), (222, 92), (222, 54), (236, 54)])
    box(s, 340, 8, 136, 26, ["Keep: zone empty,", "probes still valid"], bold=False, size=8)
    box(s, 340, 41, 136, 26, ["Modify the probes in A(t)", "(selective, S3)"], fill=FILL_EAM, stroke="#6c8ebf", size=8)
    box(s, 340, 74, 136, 32, ["Synthesize a new monitoring", "system (full regeneration, S2)"], fill=FILL_OP, stroke="#d6b656", size=8)
    for y in (21, 54, 90):
        s.line([(320, 54), (330, 54), (330, y), (340, y)])
    return s


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    out = {"fig1_monitoring_taxonomy": fig1(), "fig2_two_stage_procedure": fig_two_stage(), "fig3_reference_architecture": fig2()}
    for name, svg in out.items():
        p = FIGURES / f"{name}.svg"
        svg.save(p)
        if shutil.which("rsvg-convert"):
            subprocess.run(["rsvg-convert", "-d", "600", "-p", "600", "-f", "png", "-o", str(p.with_suffix(".png")), str(p)], check=True)
        print(p.name, "->", p.with_suffix(".png").name if shutil.which("rsvg-convert") else "(SVG only)")


if __name__ == "__main__":
    main()
