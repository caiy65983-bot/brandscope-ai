"""Shared visual tokens for the workspace, dashboards and exported reports."""

APP_CSS = """
<style>
html { font-size:14px; }
.stApp {
    background:#f5f7fb; color:#15243a;
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
    font-size:14px; line-height:1.5;
}
.stApp input, .stApp textarea, .stApp button, [data-baseweb="select"] {
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif !important;
    font-size:14px; line-height:1.5;
}
.stApp :is(p,li,h1,h2,h3,h4,label,small),
.stApp [data-testid="stMarkdownContainer"] {
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif !important;
}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p,
[data-testid="stCaptionContainer"] p {
    font-size:14px; line-height:1.5;
}
[data-testid="stMarkdownContainer"] p { text-align:justify; text-justify:inter-character; }
[data-testid="stSidebar"] { background:#10223f; }
[data-testid="stSidebar"] * { color:#edf4ff !important; }
[data-testid="stSidebarNav"] { display:none; }
[data-testid="stSidebar"] code { background:rgba(255,255,255,.14); border-radius:0; }
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"],
[data-testid="stSidebar"] input { background:#1c314f; border-color:#38506c; }
.hero, .dash-hero {
    box-sizing:border-box; width:100%; min-height:190px;
    display:flex; flex-direction:column; justify-content:center;
    padding:38px 40px; margin-bottom:24px;
    background:#10223f; color:#fff; border-radius:0;
}
.hero h1, .dash-hero h1 {
    color:#fff; font-size:32px; line-height:1.5;
    font-weight:650; letter-spacing:-.025em; margin:0;
}
.hero p, .dash-hero p {
    font-size:14px; line-height:1.5; color:#d3e6f8;
    margin:8px 0 0; text-align:justify;
}
[data-testid="stMain"] h3 { font-size:23px; font-weight:650; line-height:1.5; }
[data-testid="stMain"] h4 { font-size:18px; line-height:1.5; }
.st-key-workspace_source, .st-key-workspace_mapping,
.st-key-workspace_quality, .st-key-workspace_scope,
.st-key-workspace_annotation { padding:18px 0 24px; }
.source-tag {
    color:#8a4b00; background:#fff3dc; padding:7px 11px;
    font-size:13px; line-height:1.5; font-weight:600; display:inline-block;
}
[data-testid="stMetric"] { background:white; padding:16px 18px; border:0; }
[data-testid="stVerticalBlock"], [data-testid="stExpander"],
[data-testid="stMetric"], [data-testid="stButton"] button,
[data-testid="stDownloadButton"] button, [data-testid="stFileUploader"] section,
[data-baseweb="select"] > div, [data-baseweb="tag"],
[data-testid="stTextInput"] input, [data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea, [data-testid="stDataFrame"] { border-radius:0 !important; }
[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child,
[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child > div { border-radius:0 !important; }
@media (max-width:640px) {
    .hero, .dash-hero { min-height:170px; padding:28px 22px; }
    .hero h1, .dash-hero h1 { font-size:27px; }
}
</style>
"""

REPORT_CSS = """
* { box-sizing:border-box; }
body { font-family:system-ui,-apple-system,"Segoe UI",sans-serif; font-size:14px;
    line-height:1.5; background:#f5f7fb; color:#15243a; margin:0; }
main { max-width:1180px; margin:0 auto; padding:28px; }
header { background:#10223f; color:white; padding:36px; min-height:180px; }
header p { color:#d3e6f8; }
section { background:white; padding:24px; margin:24px 0; }
article { padding:18px 0; margin:16px 0; }
h1,h2,h3 { margin:0 0 14px; line-height:1.5; font-weight:650; }
h1 { font-size:28px; } h2 { font-size:22px; } h3 { font-size:18px; }
p { text-align:justify; margin:10px 0; }
.table-scroll { width:100%; overflow-x:auto; margin:14px 0; }
table { width:100%; border-collapse:collapse; }
th,td { padding:10px 9px; border-bottom:1px solid #e1e8f0; text-align:left; vertical-align:top; }
th { font-size:12px; line-height:1.5; white-space:nowrap; font-weight:650;
    background:#edf2f8; color:#314965; }
td { font-size:14px; line-height:1.5; }
.opportunity-table { min-width:760px; }
.opportunity-table td:last-child { min-width:180px; }
blockquote { margin:12px 0; padding:14px 16px; background:#f5f7fb; border-left:3px solid #147fa3; }
.tag { font-weight:600; color:#ffe0a6; }
small { font-size:12px; line-height:1.5; color:#667085; }
@media (max-width:640px) {
    main { padding:14px; } header { padding:24px; }
    section { padding:18px; } h1 { font-size:24px; }
}
@media print { main { padding:0; max-width:none; } .table-scroll { overflow:visible; }
    .opportunity-table { min-width:0; } th { font-size:11px; } td { font-size:12px; } }
"""
