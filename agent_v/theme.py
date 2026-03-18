"""
OAE Dashboard Design System — colours, typography, layout helpers.

All dashboard and editor components import style tokens from here
to ensure a consistent, professional scientific appearance.
"""

from typing import Any

try:
    from dash import html  # type: ignore[import-untyped]
    _DASH = True
except ImportError:
    _DASH = False

try:
    import plotly.graph_objects as go  # type: ignore[import-untyped]
    _PLOTLY = True
except ImportError:
    _PLOTLY = False

# ── Colour Palette ──────────────────────────────────────────────────────────

NAVY_900 = "#0B1528"
NAVY_800 = "#111D35"
NAVY_700 = "#1A2744"
NAVY_600 = "#243352"
TEAL_500 = "#2A9D8F"
TEAL_400 = "#3DB8A9"
TEAL_300 = "#58D4C6"
GOLD_400 = "#E9C46A"
RED_500 = "#E63946"
BLUE_500 = "#457B9D"
DARK_TEXT = "#1A2744"
TEXT_PRIMARY = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F6F8FA"
BORDER = "#E5E7EB"
BORDER_DARK = "#D0D7DE"

# ── Typography ──────────────────────────────────────────────────────────────

FONT_STACK = "'Inter', 'Source Sans Pro', 'Segoe UI', system-ui, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Fira Code', 'Consolas', monospace"
FONT_CDN = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"

# ── Style Factories ─────────────────────────────────────────────────────────


def card_style(flex: str = "1", min_height: str | None = None) -> dict[str, Any]:
    """Return a card container style dict."""
    s: dict[str, Any] = {
        "flex": flex,
        "backgroundColor": SURFACE,
        "borderRadius": "10px",
        "padding": "16px",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
        "border": f"1px solid {BORDER}",
    }
    if min_height:
        s["minHeight"] = min_height
    return s


def card_title_style() -> dict[str, Any]:
    """Return style for a card's H4 title."""
    return {
        "marginTop": "0",
        "color": DARK_TEXT,
        "fontSize": "13px",
        "fontWeight": "600",
        "textTransform": "uppercase",
        "letterSpacing": "0.5px",
        "borderBottom": f"2px solid {TEAL_500}",
        "paddingBottom": "8px",
        "marginBottom": "12px",
    }


def tab_style() -> dict[str, Any]:
    """Unselected tab style."""
    return {
        "borderRadius": "8px 8px 0 0",
        "padding": "10px 24px",
        "fontWeight": "500",
        "fontSize": "13px",
        "backgroundColor": SURFACE_ALT,
        "border": f"1px solid {BORDER}",
        "borderBottom": "none",
        "color": "#6B7280",
    }


def tab_selected_style() -> dict[str, Any]:
    """Selected tab style."""
    base = tab_style()
    base.update({
        "backgroundColor": SURFACE,
        "borderBottom": f"2px solid {TEAL_500}",
        "color": TEAL_500,
        "fontWeight": "600",
    })
    return base


def badge_style(state: str) -> dict[str, Any]:
    """Pill-shaped status badge."""
    base = {
        "padding": "3px 10px",
        "borderRadius": "12px",
        "fontSize": "11px",
        "fontWeight": "600",
        "display": "inline-block",
    }
    variants = {
        "active": {
            "backgroundColor": "#ECFDF5", "color": "#065F46",
            "border": "1px solid #A7F3D0",
        },
        "idle": {
            "backgroundColor": "#FFFBEB", "color": "#92400E",
            "border": "1px solid #FDE68A",
        },
        "no data": {
            "backgroundColor": "#FEF2F2", "color": "#991B1B",
            "border": "1px solid #FECACA",
        },
    }
    base.update(variants.get(state, variants["no data"]))
    return base


def button_style(color: str = TEAL_500) -> dict[str, Any]:
    """Consistent button style."""
    return {
        "backgroundColor": color,
        "color": "white",
        "border": "none",
        "borderRadius": "6px",
        "padding": "8px 16px",
        "fontWeight": "600",
        "fontSize": "13px",
        "cursor": "pointer",
        "fontFamily": FONT_STACK,
    }


def table_header_style() -> dict[str, Any]:
    """DataTable header cell style."""
    return {
        "backgroundColor": NAVY_700,
        "color": "white",
        "fontWeight": "600",
        "fontSize": "12px",
        "padding": "8px",
        "borderBottom": f"2px solid {TEAL_500}",
    }


def table_cell_style() -> dict[str, Any]:
    """DataTable body cell style."""
    return {
        "textAlign": "left",
        "fontSize": "12px",
        "padding": "6px 8px",
        "whiteSpace": "nowrap",
        "fontFamily": FONT_STACK,
    }


# ── Plotly Template ─────────────────────────────────────────────────────────


def plotly_template() -> Any:
    """Return a custom Plotly layout template for OAE charts."""
    if not _PLOTLY:
        return None
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_STACK, color=DARK_TEXT, size=12),
            paper_bgcolor=SURFACE,
            plot_bgcolor="#FAFBFC",
            xaxis=dict(
                gridcolor="#E5E7EB", zerolinecolor=BORDER_DARK,
                title_font=dict(size=12),
            ),
            yaxis=dict(
                gridcolor="#E5E7EB", zerolinecolor=BORDER_DARK,
                title_font=dict(size=12),
            ),
            colorway=[
                TEAL_500, RED_500, BLUE_500, GOLD_400,
                "#F4A261", "#264653", "#A8DADC", "#7209B7",
            ],
            title=dict(font=dict(size=14, color=DARK_TEXT)),
            margin=dict(l=50, r=30, t=50, b=40),
        ),
    )


# ── Layout Components ───────────────────────────────────────────────────────


def header_bar() -> Any:
    """Return the top branding bar as a Dash layout component."""
    if not _DASH:
        return None
    return html.Div(
        style={
            "background": f"linear-gradient(135deg, {NAVY_900} 0%, {NAVY_700} 100%)",
            "padding": "14px 24px",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "space-between",
            "borderRadius": "12px",
            "marginBottom": "16px",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
        },
        children=[
            html.Div(
                style={"display": "flex", "alignItems": "baseline", "gap": "12px"},
                children=[
                    html.Span("OAE", style={
                        "color": TEAL_400, "fontSize": "26px", "fontWeight": "700",
                        "letterSpacing": "3px",
                    }),
                    html.Span("|", style={
                        "color": "#4A5568", "fontSize": "22px", "fontWeight": "300",
                    }),
                    html.Span("Crystal Structure Explorer", style={
                        "color": TEXT_PRIMARY, "fontSize": "14px", "fontWeight": "400",
                        "letterSpacing": "0.5px",
                    }),
                ],
            ),
            html.Div(
                id="clock",
                style={
                    "color": TEXT_SECONDARY, "fontSize": "12px",
                    "fontFamily": FONT_MONO,
                },
            ),
        ],
    )
