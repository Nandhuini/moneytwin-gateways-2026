"""Shared view helpers: design tokens, small HTML components, chart styling and banners.

Every HTML snippet is squashed onto one line before it is sent to st.markdown. A blank line or a
4-space indent inside raw HTML makes Markdown turn the rest of the snippet into a code block, and
**bold** is not converted inside HTML, which is why text goes through rich().
"""
from __future__ import annotations

import html
import re

import streamlit as st

from ..consent import describe_exclusions
from ..formatting import money

PRIMARY, ACCENT, NEUTRAL = "#1f6f8b", "#d1495b", "#9aa5b1"
GOOD, WARN, AMBER_SOFT = "#15803d", "#d97706", "#f2c572"
INK, MUTED, LINE = "#0f172a", "#64748b", "#e2e8f0"

THEME_CSS = """
<style>
:root{--mt-ink:#0f172a;--mt-muted:#64748b;--mt-line:#e2e8f0;--mt-primary:#1f6f8b;}

/* ---------- canvas and type ---------- */
.stApp{background:#f4f6fa;}
.stApp,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp label,.stApp li,.stApp button,
.stApp input,.stApp textarea,.stApp td,.stApp th,.mt-card,.mt-card div{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;}
.block-container,[data-testid="stMainBlockContainer"]{max-width:1280px;padding-top:2.2rem;padding-bottom:3rem;}
header[data-testid="stHeader"]{background:transparent;}
.stApp h1{font-size:2.1rem;font-weight:800;letter-spacing:-.03em;color:var(--mt-ink);padding:.15rem 0 .25rem;}
.stApp h2,.stApp h3{color:var(--mt-ink);font-weight:700;letter-spacing:-.01em;}
.stApp h3{font-size:1.15rem;}
.stApp [data-testid="stCaptionContainer"]{color:var(--mt-muted);}
.mt-eyebrow{font-size:13px;font-weight:600;color:var(--mt-primary);margin:0 0 -4px;}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b1220 0%,#111c33 100%);border-right:1px solid #1e293b;}
section[data-testid="stSidebar"] label,section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *{color:#cbd5e1;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] *{color:#94a3b8;}
section[data-testid="stSidebar"] div[data-baseweb="input"],section[data-testid="stSidebar"] div[data-baseweb="base-input"]{
  background:#1e293b;border-color:#334155;border-radius:10px;}
section[data-testid="stSidebar"] input{color:#f1f5f9 !important;-webkit-text-fill-color:#f1f5f9;}
section[data-testid="stSidebar"] [data-testid="stNumberInput"] button{background:#334155;color:#e2e8f0;border-color:#334155;}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{background:#1e293b;border:1px dashed #475569;border-radius:12px;}
section[data-testid="stSidebar"] [data-testid="stFileUploader"] *{color:#cbd5e1;}
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button{background:#334155;color:#f1f5f9;border:1px solid #475569;}
section[data-testid="stSidebar"] div[role="radiogroup"]{gap:4px;}
section[data-testid="stSidebar"] div[role="radiogroup"] label{width:100%;padding:9px 12px;border-radius:10px;cursor:pointer;}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{background:#1e293b;}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:#1f6f8b;}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) *{color:#ffffff !important;font-weight:600;}
.mt-brand{padding:4px 0 18px;border-bottom:1px solid #263246;margin-bottom:6px;}
.mt-brand-name{font-size:25px;font-weight:800;color:#ffffff;letter-spacing:-.03em;}
.mt-brand-tag{font-size:12px;color:#94a3b8;margin-top:3px;}
.mt-side-h{color:#94a3b8;font-size:12px;font-weight:600;letter-spacing:.06em;margin:22px 0 6px;}
.mt-side-note{margin-top:22px;padding:12px 14px;border-radius:12px;background:#16223a;border:1px solid #263246;color:#cbd5e1;font-size:13px;line-height:1.45;}
.mt-side-note b{color:#ffffff;}

/* ---------- widgets on the canvas ---------- */
.stApp .stButton > button{border-radius:10px;font-weight:600;border:1px solid #cbd5e1;padding:8px 18px;}
.stApp .stButton > button:hover{border-color:var(--mt-primary);color:var(--mt-primary);}
.stApp .stButton > button[kind="primary"]{background:var(--mt-primary);border-color:var(--mt-primary);color:#fff;}
.stApp .stButton > button[kind="primary"]:hover{background:#185a73;color:#fff;}
.stApp div[data-baseweb="input"],.stApp div[data-baseweb="select"] > div{border-radius:10px;}
.stApp [data-testid="stExpander"]{border-radius:14px;border:1px solid var(--mt-line);background:#fff;}
.stApp [data-testid="stDataFrame"]{border-radius:14px;overflow:hidden;border:1px solid var(--mt-line);}
.stApp [data-testid="stAlert"]{border-radius:12px;}
.stApp .stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--mt-line);}
.stApp .stTabs button[data-baseweb="tab"]{font-weight:600;padding:10px 14px;}
.stApp .stTabs button[data-baseweb="tab"][aria-selected="true"]{color:var(--mt-primary);}
.stApp .stTabs [data-baseweb="tab-highlight"]{background:var(--mt-primary);}

/* ---------- tones ---------- */
.mt-tone-neutral{--bg:#f1f5f9;--fg:#475569;--bar:#94a3b8;}
.mt-tone-info{--bg:#e3f0f5;--fg:#1f6f8b;--bar:#1f6f8b;}
.mt-tone-bad{--bg:#fde8ea;--fg:#b4233a;--bar:#d1495b;}
.mt-tone-warn{--bg:#fdf0d5;--fg:#a8600a;--bar:#d97706;}
.mt-tone-good{--bg:#dcf5e5;--fg:#15803d;--bar:#22a45d;}

/* ---------- components ---------- */
.mt-card{background:#fff;border:1px solid var(--mt-line);border-radius:16px;padding:16px 18px;box-shadow:0 1px 2px rgba(15,23,42,.04),0 4px 14px rgba(15,23,42,.04);}
.mt-kpi{position:relative;min-height:122px;border-left:4px solid var(--bar);}
.mt-kpi-icon{position:absolute;top:14px;right:14px;width:34px;height:34px;border-radius:10px;background:var(--bg);display:flex;align-items:center;justify-content:center;font-size:17px;}
.mt-kpi-label{font-size:13px;font-weight:600;color:var(--mt-muted);padding-right:44px;}
.mt-kpi-value{font-size:28px;font-weight:800;letter-spacing:-.03em;color:var(--mt-ink);margin-top:6px;line-height:1.15;}
.mt-kpi-note{font-size:13px;color:var(--mt-muted);margin-top:6px;line-height:1.4;}
.mt-pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;background:var(--bg);color:var(--fg);white-space:nowrap;}
.mt-callout{border-radius:14px;padding:14px 18px;background:var(--bg);border-left:4px solid var(--bar);margin:2px 0 14px;}
.mt-callout-title{font-size:14px;font-weight:700;color:var(--fg);}
.mt-callout-body{font-size:15px;color:#1e293b;line-height:1.55;margin-top:3px;}
.mt-hero{border-radius:20px;padding:30px 34px;margin-bottom:18px;color:#fff;background:linear-gradient(135deg,#0f172a 0%,#15385a 58%,#1f6f8b 100%);}
.mt-hero-title{font-size:42px;font-weight:800;letter-spacing:-.04em;line-height:1.05;}
.mt-hero-tag{font-size:16px;color:#cbd5e1;margin-top:8px;max-width:640px;line-height:1.5;}
.mt-chips{margin-top:16px;}
.mt-chip{display:inline-block;margin:0 8px 6px 0;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:600;background:rgba(255,255,255,.14);color:#e2e8f0;}
.mt-leak{background:#fff;border:1px solid var(--mt-line);border-left:4px solid #d1495b;border-radius:18px;padding:20px 24px;margin:6px 0 16px;box-shadow:0 1px 2px rgba(15,23,42,.04),0 4px 14px rgba(15,23,42,.04);}
.mt-leak-label{font-size:13px;font-weight:600;color:var(--mt-muted);}
.mt-leak-total{font-size:40px;font-weight:800;letter-spacing:-.04em;color:#b4233a;line-height:1.1;margin:4px 0 12px;}
.mt-leak-driver{font-size:14px;color:#334155;margin-top:10px;}
.mt-legend{display:inline-flex;align-items:center;gap:6px;margin:8px 18px 0 0;font-size:13px;color:#475569;}
.mt-legend i{width:10px;height:10px;border-radius:3px;display:inline-block;}
.mt-bar{position:relative;display:flex;overflow:hidden;border-radius:999px;background:#e2e8f0;}
.mt-bar-marker{position:absolute;top:0;bottom:0;width:3px;background:#0f172a;}
.mt-finding{display:flex;gap:11px;align-items:flex-start;background:#fff;border:1px solid var(--mt-line);border-radius:14px;padding:14px 16px;margin-bottom:10px;color:#334155;line-height:1.5;}
.mt-dot{flex:0 0 8px;height:8px;margin-top:7px;border-radius:50%;background:var(--mt-primary);}
.mt-cta{background:#0f172a;border-radius:16px;padding:18px 22px;margin-top:14px;}
.mt-cta-title{color:#fff;font-size:17px;font-weight:700;}
.mt-cta-body{color:#cbd5e1;font-size:14px;margin-top:4px;}
.mt-note{font-size:13px;color:var(--mt-muted);line-height:1.5;}
.mt-side{height:100%;}
.mt-side.is-plan{border:2px solid var(--mt-primary);}
.mt-side-head{font-size:13px;font-weight:700;color:var(--mt-muted);}
.mt-side.is-plan .mt-side-head{color:var(--mt-primary);}
.mt-side-name{font-size:15px;font-weight:600;color:var(--mt-ink);margin:2px 0 10px;}
.mt-side-big{font-size:34px;font-weight:800;letter-spacing:-.03em;color:var(--mt-ink);line-height:1.1;}
.mt-rows{margin-top:14px;border-top:1px solid var(--mt-line);}
.mt-rows div{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:14px;color:#475569;}
.mt-rows b{color:var(--mt-ink);}
.mt-saving{border-radius:20px;padding:26px 30px;margin:6px 0 16px;color:#fff;background:linear-gradient(135deg,#0c2f36 0%,#0f5f4a 60%,#15803d 100%);}
.mt-saving.is-flat{background:linear-gradient(135deg,#1e293b,#334155);}
.mt-saving-label{font-size:14px;color:#c7e9d6;font-weight:600;}
.mt-saving.is-flat .mt-saving-label{color:#cbd5e1;}
.mt-saving-big{font-size:52px;font-weight:800;letter-spacing:-.04em;line-height:1.05;margin:4px 0 6px;}
.mt-saving-sub{font-size:15px;color:#e2f5ea;line-height:1.5;}
.mt-saving.is-flat .mt-saving-sub{color:#e2e8f0;}
@media (max-width:640px){.mt-saving-big{font-size:38px;}.mt-hero{padding:22px;}.mt-hero-title{font-size:32px;}.mt-leak-total{font-size:32px;}}
</style>
"""


# ---------- text and html helpers ----------

def esc(text) -> str:
    """HTML-escape any value."""
    return html.escape(str(text), quote=True)


def rich(text) -> str:
    """Escape text, then turn **bold** into <strong> (Markdown is not parsed inside HTML)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


def html_block(markup: str) -> None:
    """Render one HTML snippet. Whitespace is squashed so no blank line can split the block."""
    st.markdown(" ".join(markup.split()), unsafe_allow_html=True)


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


# ---------- streamlit version compatibility ----------

def stretch(fn) -> dict:
    """Full-width argument for a Streamlit element function.

    Newer Streamlit takes width='stretch' and deprecates use_container_width. Older versions only know
    use_container_width, so we check the function's own documentation instead of guessing a version number.
    """
    try:
        if "stretch" in (fn.__doc__ or ""):
            return {"width": "stretch"}
    except Exception:
        pass
    return {"use_container_width": True}


def show_chart(fig) -> None:
    st.plotly_chart(fig, **stretch(st.plotly_chart))


def show_table(data, **kwargs) -> None:
    st.dataframe(data, hide_index=True, **stretch(st.dataframe), **kwargs)


def card():
    """A bordered panel that groups related widgets or a chart."""
    return st.container(border=True)


# ---------- components ----------

def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    html_block(f'<div class="mt-eyebrow">{esc(eyebrow)}</div>')
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def section(title: str, caption: str = "") -> None:
    st.subheader(title)
    if caption:
        st.caption(caption)


def hero(title: str, tagline: str, chips=()) -> None:
    chip_html = "".join(f'<span class="mt-chip">{esc(c)}</span>' for c in chips)
    html_block(f'<div class="mt-hero"><div class="mt-hero-title">{esc(title)}</div>'
               f'<div class="mt-hero-tag">{esc(tagline)}</div><div class="mt-chips">{chip_html}</div></div>')


def pill(text: str, tone: str = "neutral") -> str:
    """Returns HTML for a small status pill (embed it inside other html_block content)."""
    return f'<span class="mt-pill mt-tone-{tone}">{esc(text)}</span>'


def kpi_card(label: str, value: str, note: str = "", tone: str = "neutral", icon: str = "", help: str = "") -> None:
    tip = f' title="{esc(help)}"' if help else ""
    icon_html = f'<div class="mt-kpi-icon">{icon}</div>' if icon else ""
    note_html = f'<div class="mt-kpi-note">{rich(note)}</div>' if note else ""
    html_block(f'<div class="mt-card mt-kpi mt-tone-{tone}"{tip}>{icon_html}<div class="mt-kpi-label">{esc(label)}</div>'
               f'<div class="mt-kpi-value">{esc(value)}</div>{note_html}</div>')


def kpi_row(items: list[dict]) -> None:
    """Lay out kpi_card(**item) for each item in equal columns."""
    for col, item in zip(st.columns(len(items)), items):
        with col:
            kpi_card(**item)


def callout(title: str, body: str, tone: str = "info", icon: str = "") -> None:
    heading = f"{icon} {esc(title)}".strip()
    html_block(f'<div class="mt-callout mt-tone-{tone}"><div class="mt-callout-title">{heading}</div>'
               f'<div class="mt-callout-body">{rich(body)}</div></div>')


def bar(segments, marker=None, height: int = 10) -> str:
    """Returns HTML for a horizontal bar. segments: [(share 0-1, colour)]; marker: optional 0-1 position."""
    parts = "".join(f'<div style="width:{max(0.0, min(float(s), 1.0)) * 100:.1f}%;background:{c}"></div>' for s, c in segments)
    mark = "" if marker is None else f'<div class="mt-bar-marker" style="left:{max(0.0, min(float(marker), 1.0)) * 100:.1f}%"></div>'
    return f'<div class="mt-bar" style="height:{height}px">{parts}{mark}</div>'


def finding_card(text: str) -> None:
    html_block(f'<div class="mt-finding"><span class="mt-dot"></span><div>{rich(text)}</div></div>')


def cta_card(title: str, body: str) -> None:
    html_block(f'<div class="mt-cta"><div class="mt-cta-title">{esc(title)}</div><div class="mt-cta-body">{esc(body)}</div></div>')


def leak_total(lk: dict) -> float:
    return lk["total_fees"] + lk["return_loss_confirmed"] + lk["return_loss_expected"]


def leak_banner(lk: dict) -> None:
    """Total leakage (fees + return losses) with a proportion bar; same sum the page used before."""
    parts = [("Hidden fees", float(lk["total_fees"]), ACCENT),
             ("Confirmed return losses", float(lk["return_loss_confirmed"]), WARN),
             ("Expected return losses", float(lk["return_loss_expected"]), AMBER_SOFT)]
    total = sum(v for _, v, _ in parts)
    shares = bar([(v / total if total else 0.0, c) for _, v, c in parts], height=12)
    legend = "".join(f'<span class="mt-legend"><i style="background:{c}"></i>{esc(n)} <b>{esc(money(v))}</b></span>' for n, v, c in parts)
    if total > 0:
        top = max(parts, key=lambda p: p[1])
        driver = f"Biggest driver: {top[0].lower()}, {top[1] / total * 100:.0f}% of the total."
    else:
        driver = "No fees or return losses were found in the data you shared."
    html_block(f'<div class="mt-leak"><div class="mt-leak-label">Total money leaks (fees + return losses)</div>'
               f'<div class="mt-leak-total">{esc(money(leak_total(lk)))}</div>{shares}<div>{legend}</div>'
               f'<div class="mt-leak-driver">{esc(driver)}</div></div>')


# ---------- charts ----------

def style_fig(fig, height: int = 360, legend: bool = False, axes: bool = True):
    """Consistent Plotly look: transparent background, one font, light grid, unified hover."""
    fig.update_layout(height=height, margin=dict(t=16, b=8, l=8, r=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="-apple-system, Segoe UI, Inter, Roboto, Arial, sans-serif", size=13, color=INK),
                      showlegend=legend, hoverlabel=dict(bgcolor="white", font_size=13))
    if legend:
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
    if axes:
        fig.update_xaxes(showgrid=False, title=None, linecolor=LINE)
        fig.update_yaxes(gridcolor=LINE, zeroline=False)
    return fig


# ---------- notices shown on every page ----------

def banners(twin) -> None:
    """Notices that apply to every page: cold start and switched-off data."""
    if twin.confidence == "low":
        st.warning(f"Low confidence: only {twin.history_days} days of history, so predictions are shown as wide ranges "
                   "and will improve as more data arrives.")
    note = describe_exclusions(twin.excluded)
    if note:
        st.info(note)
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)
