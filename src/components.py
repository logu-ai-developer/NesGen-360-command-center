import html,streamlit as st
import logging
from datetime import datetime,timezone
ICONS={'Executive overview':'▦','Model lifecycle':'◈','Platform health':'⌁','User adoption':'♙','Chargeback':'⊕','AI assistant':'▣','Administration':'⚙','Solution design':'⌘','Requirements':'⬡','Demo & tests':'▤'}
def inject_css():
 st.markdown('''<style>
#MainMenu,footer,header{visibility:hidden}.stApp{background:#f5f7fb;color:#0b1f33}.block-container{padding:2.8rem 2.6rem 4rem;max-width:1450px}
[data-testid="stSidebar"]{background:#0b2136;border-right:0;min-width:285px;max-width:285px}[data-testid="stSidebar"] *{color:#e9f2ff}[data-testid="stSidebar"] .stRadio label{padding:.72rem .85rem;border-radius:12px;margin:.08rem 0;font-size:1rem}[data-testid="stSidebar"] .stRadio label:has(input:checked){background:#1768ff;color:#fff}[data-testid="stSidebar"] [data-testid="stWidgetLabel"]{display:none}[data-testid="stSidebar"] hr{border-color:#284059}
.brand{padding:.6rem .55rem 1.5rem}.brand-title{font-size:1.7rem;font-weight:800;color:#fff}.brand-sub{color:#b9cae0;font-size:.92rem;margin-top:.2rem}.topline{display:flex;justify-content:space-between;align-items:center;background:#fff;border-bottom:1px solid #dfe6ef;padding:.8rem 1rem;margin:-2.8rem -2.6rem 2.5rem}.top-title{font-weight:700}.top-meta{font-size:.83rem;color:#65758a}
.eyebrow{color:#1768ff;font-size:.82rem;font-weight:800;letter-spacing:.18em;margin-bottom:.55rem}.page-title{font-size:2.05rem;font-weight:800;letter-spacing:-.04em;margin:0}.page-sub{font-size:1.03rem;color:#516278;margin:.45rem 0 1.8rem}.kpi{background:#fff;border:1px solid #dfe6ef;border-radius:18px;padding:1.25rem 1.35rem;min-height:142px;box-shadow:0 2px 8px #0b213612}.kpi-label{color:#5e7390;font-size:.93rem}.kpi-value{font-size:2.35rem;font-weight:760;color:#07182b;margin:.35rem 0}.kpi-note{font-size:.82rem;color:#6b7e96}.panel{background:#fff;border:1px solid #dfe6ef;border-radius:18px;padding:1.3rem 1.45rem;box-shadow:0 2px 8px #0b213612;margin-top:1.25rem}.panel-title{font-weight:750;font-size:1.05rem;margin-bottom:.8rem}.pill{display:inline-block;padding:.22rem .55rem;border-radius:999px;font-size:.73rem;font-weight:750}.critical{background:#fde8ea;color:#ba1a1a}.high{background:#fff0de;color:#a84d00}.medium{background:#fff7d6;color:#7c6500}.low{background:#e4f8ef;color:#087a55}.callout{border:1px solid #f0c36a;background:#fff9e9;border-radius:14px;padding:.9rem 1rem;margin-bottom:1.25rem}.stDataFrame{border:1px solid #dfe6ef;border-radius:14px;overflow:hidden}[data-testid="stMetric"]{background:#fff;border:1px solid #dfe6ef;border-radius:18px;padding:1rem}
button[kind="primary"]{border-radius:10px}.small-muted{color:#6b7e96;font-size:.8rem}
</style>''',unsafe_allow_html=True)
def header(title,eyebrow,sub):
 st.markdown(f'<div class="topline"><div><div class="top-title">{html.escape(title)}</div><div class="top-meta">Decision scope · rendered {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div></div><div>⌕</div></div><div class="eyebrow">{html.escape(eyebrow.upper())}</div><div class="page-title">{html.escape(title)}</div><div class="page-sub">{html.escape(sub)}</div>',unsafe_allow_html=True)
def kpi(label,value,note=''):
 st.markdown(f'<div class="kpi"><div class="kpi-label">{html.escape(str(label))}</div><div class="kpi-value">{html.escape(str(value))}</div><div class="kpi-note">{html.escape(str(note))}</div></div>',unsafe_allow_html=True)
def panel_title(text):st.markdown(f'<div class="panel-title">{html.escape(text)}</div>',unsafe_allow_html=True)
def safe_page(fn):
 try:fn()
 except Exception as exc:
  logging.getLogger('nesgen.ui').error('Page render failed: %s',type(exc).__name__)
  st.error('This page could not render. Check local diagnostics; other pages remain available.')
