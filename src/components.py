import html,streamlit as st
import logging
from src.metrics import SOURCE_BADGE_NOTE
from datetime import datetime,timezone
ICONS={'Executive overview':'▦','Model lifecycle':'◈','Platform health':'⌁','User adoption':'♙','Chargeback':'⊕','AI assistant':'▣','Administration':'⚙','Solution design':'⌘','Requirements':'⬡','Demo & tests':'▤'}
def inject_css():
 st.markdown('''<style>
#MainMenu,footer,{visibility:hidden}.stApp{background:#f5f7fb;color:#0b1f33}.block-container{padding:2.8rem 2.6rem 4rem;max-width:1450px}
[data-testid="stSidebar"]{background:#0b2136;border-right:0;}[data-testid="stSidebar"] *{color:#e9f2ff}[data-testid="stSidebar"] .stRadio label{padding:.72rem .85rem;border-radius:12px;margin:.08rem 0;font-size:1rem}[data-testid="stSidebar"] .stRadio label:has(input:checked){background:#1768ff;color:#fff}[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{font-size:.8rem;color:#b9cae0}[data-testid="stSidebar"] hr{border-color:#284059}
.brand{padding:.6rem .55rem 1.5rem}.brand-title{font-size:1.7rem;font-weight:800;color:#fff}.brand-sub{color:#b9cae0;font-size:.92rem;margin-top:.2rem}.topline{display:flex;justify-content:space-between;align-items:center;background:#fff;border-bottom:1px solid #dfe6ef;padding:.8rem 1rem;margin:-2.8rem -2.6rem 2.5rem}.top-title{font-weight:700}.top-meta{font-size:.83rem;color:#65758a}
.eyebrow{color:#1768ff;font-size:.82rem;font-weight:800;letter-spacing:.18em;margin-bottom:.55rem}.page-title{font-size:2.05rem;font-weight:800;letter-spacing:-.04em;margin:0}.page-sub{font-size:1.03rem;color:#516278;margin:.45rem 0 1.8rem}.kpi{background:#fff;border:1px solid #dfe6ef;border-radius:18px;padding:1.25rem 1.35rem;min-height:142px;box-shadow:0 2px 8px #0b213612}.kpi-label{color:#1f3347;font-size:1.06rem;font-weight:700;line-height:1.3}.kpi-value{font-size:2.0rem;font-weight:740;color:#07182b;margin:.25rem 0}.kpi-note{font-size:.82rem;color:#6b7e96}.panel{background:#fff;border:1px solid #dfe6ef;border-radius:18px;padding:1.3rem 1.45rem;box-shadow:0 2px 8px #0b213612;margin-top:1.25rem}.panel-title{font-weight:750;font-size:1.05rem;margin-bottom:.8rem}.pill{display:inline-block;padding:.22rem .55rem;border-radius:999px;font-size:.73rem;font-weight:750}.critical{background:#fde8ea;color:#ba1a1a}.high{background:#fff0de;color:#a84d00}.medium{background:#fff7d6;color:#7c6500}.low{background:#e4f8ef;color:#087a55}.callout{border:1px solid #f0c36a;background:#fff9e9;border-radius:14px;padding:.9rem 1rem;margin-bottom:1.25rem}.stDataFrame{border:1px solid #dfe6ef;border-radius:14px;overflow:hidden}[data-testid="stMetric"]{background:#fff;border:1px solid #dfe6ef;border-radius:18px;padding:1rem}
button[kind="primary"]{border-radius:10px}.small-muted{color:#6b7e96;font-size:.8rem}
/* V1.1: KPI card is position:relative so the in-card info drawer never moves the layout */
.kpi{position:relative}.kpi-label{padding-right:1.6rem}
.kpi-ok{border-left:6px solid #39b98a;background:#f1fbf6}.kpi-bad{border-left:6px solid #df4b55;background:#fff2f3}.kpi-warn{border-left:6px solid #f2a93b;background:#fffaf0}
.kpi-info{position:absolute;top:.7rem;right:.9rem;text-align:left}.kpi-info summary{list-style:none;cursor:pointer;color:#1768ff;font-size:1.05rem;user-select:none}.kpi-info summary::-webkit-details-marker{display:none}
.kpi-info-body{position:absolute;right:0;top:1.6rem;z-index:50;width:300px;max-width:80vw;background:#fff;border:1px solid #dfe6ef;border-radius:12px;box-shadow:0 8px 24px #0b213626;padding:.8rem .9rem;font-size:.8rem;line-height:1.45;color:#1f3347}
.kpi-info-body b{color:#0b1f33}.lineage{margin-top:.4rem;padding:.35rem .5rem;background:#f1f5fb;border-radius:8px;font-size:.74rem}
.kpi-row{margin-top:.45rem}.kpi-info .kpi-more{margin-top:.5rem}.kpi-info .kpi-more summary{font-size:.76rem;color:#1768ff;cursor:pointer}.kpi-info .kpi-more>div{margin-top:.35rem}
.group-title{font-weight:750;font-size:.98rem;color:#0b1f33;border-left:4px solid #1768ff;padding-left:.6rem;margin:1.4rem 0 .7rem}.group-sub{font-weight:400;color:#65758a;font-size:.8rem;margin-left:.4rem}
.badge{display:inline-block;padding:.05rem .55rem;border-radius:999px;font-size:.68rem;font-weight:700;color:#fff;vertical-align:middle}
.finding{border:1px solid #dfe6ef;border-left-width:5px;border-radius:10px;padding:.6rem .85rem;margin-bottom:.6rem;background:#fff}.finding-title{font-weight:700;font-size:.92rem}.finding-meta{font-size:.78rem;color:#65758a;margin-top:.15rem}.finding-line{font-size:.84rem;margin-top:.2rem}.finding-module{display:inline-block;font-size:1rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;color:#1768ff;margin-bottom:.35rem;padding-bottom:.18rem;border-bottom:2px solid #1768ff33}
.exec-summary{background:#eef3fb;border:1px solid #d4e0f2;border-left:4px solid #1768ff;border-radius:12px;padding:.8rem 1rem;margin:.2rem 0 1.3rem;font-size:1rem;line-height:1.5;color:#1f3347}
</style>''',unsafe_allow_html=True)
def header(title,eyebrow,sub,source=None):
 st.markdown(f'<div class="topline"><div><div class="top-title">{html.escape(title)}</div><div class="top-meta">Rendered {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}'+(f' · Source: {source_badge(source)}' if source else '')+f'</div></div><div>⌕</div></div><div class="eyebrow">{html.escape(eyebrow.upper())}</div><div class="page-title">{html.escape(title)}</div><div class="page-sub">{html.escape(sub)}</div>',unsafe_allow_html=True)

# V1.1: source badge (workbook / parquet / synthetic)
SOURCE_COLORS={'workbook':'#1768ff','parquet':'#39b98a','synthetic':'#f2a93b','derived':'#7a5af8','locally':'#0e9aa7','unclassified':'#df4b55'}
def source_badge(mode):
    mode=str(mode).lower();key=next((k for k in SOURCE_COLORS if mode.startswith(k)),None)
    return f'<span class="badge" style="background:{SOURCE_COLORS.get(key,"#65758a")}">{html.escape(mode)}</span>'

# V1.1: explanation lives INSIDE the card (info dict -> details drawer with lineage); tone = ok/bad/warn colours the card
def _info_html(info,mode=None):
    e=lambda k:html.escape(str(info.get(k,'')))
    source=e("source")+(f' · {html.escape(str(mode))}' if mode else '')
    rows=[f'<div><b>What it means</b><br>{e("definition")}</div>']
    if info.get('why'):rows.append(f'<div class="kpi-row"><b>Why it matters</b><br>{e("why")}</div>')
    rows.append(f'<div class="kpi-row"><b>Source</b><br>{source}</div>')
    # Technical mechanics stay available for auditors, but are collapsed by default.
    more=[f'<div><b>How it is derived:</b> {e("formula")}</div>']
    if info.get('caveat'):more.append(f'<div><b>Caveat:</b> {e("caveat")}</div>')
    more.append(f'<div class="lineage"><b>Lineage:</b> {e("source")} → {e("dataset")} → {e("metric")}'+(f' · {source_badge(mode)}<br>{html.escape(SOURCE_BADGE_NOTE)}' if mode else '')+'</div>')
    rows.append('<details class="kpi-more"><summary>▸ Advanced metric details</summary>'+''.join(more)+'</details>')
    return '<details class="kpi-info"><summary title="What does this mean?">ⓘ</summary><div class="kpi-info-body">'+''.join(rows)+'</div></details>'

def kpi(label,value,note='',info=None,source_mode=None,tone=None):
 extra=_info_html(info,source_mode) if info else ''
 cls='kpi'+(f' kpi-{tone}' if tone else '')
 st.markdown(f'<div class="{cls}"><div class="kpi-label">{html.escape(str(label))}</div><div class="kpi-value">{html.escape(str(value))}</div><div class="kpi-note">{html.escape(str(note)).replace(chr(10),'<br>')}</div>{extra}</div>',unsafe_allow_html=True)

SEVERITY_COLORS={'Critical':'#df4b55','High':'#f2a93b','Medium':'#1768ff','Low':'#39b98a'}

def kpi_help(
    title,
    definition,
    source,
    formula,
    limitation,
    insight
):
    with st.popover("ⓘ"):
        st.markdown(f"### {title}")

        st.markdown("**Definition**")
        st.write(definition)

        st.markdown("**Source**")
        st.write(source)

        st.markdown("**Formula**")
        st.code(formula)

        st.markdown("**Limitation**")
        st.write(limitation)

        st.markdown("**AI Insight**")
        st.write(insight)

def group_title(text,sub=''):st.markdown(f'<div class="group-title">{html.escape(text)}'+(f'<span class="group-sub">{html.escape(sub)}</span>' if sub else '')+'</div>',unsafe_allow_html=True)

def panel_title(text):st.markdown(f'<div class="panel-title">{html.escape(text)}</div>',unsafe_allow_html=True)

def safe_page(fn):
 try:fn()
 except Exception as exc:
  # V1.1: full traceback goes to the server terminal (never the browser) so render failures can be diagnosed
  logging.getLogger('nesgen.ui').exception('Page render failed: %s',type(exc).__name__)
  st.error('This page could not render. Check local diagnostics; other pages remain available.')
