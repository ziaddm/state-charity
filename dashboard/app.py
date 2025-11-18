# dashboard/app.py
"""
Main Dash application initialization with multi-page support.
"""
import dash
import dash_bootstrap_components as dbc
from dash import html, dcc
import sys
from pathlib import Path

# Add parent directory to path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize the Dash app with Bootstrap theme and multi-page support
app = dash.Dash(
    __name__,
    use_pages=True,  # Enable multi-page apps
    pages_folder="../app/web/pages",  # Point to pages directory
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        dbc.icons.BOOTSTRAP,  # Bootstrap Icons
    ],
    title="Compliance Analytics",
    suppress_callback_exceptions=True
)

# Main layout with navigation
app.layout = html.Div([
    dcc.Store(id='theme-store', data='light', storage_type='local'),

    # Navigation bar
    dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H3("State Charity Care Submission", className="header-title mb-0"),
                ], width="auto"),
                dbc.Col([
                    dbc.Nav([
                        dbc.NavItem(dbc.NavLink("Dashboard", href="/", active="exact", className="nav-link-custom")),
                        dbc.NavItem(dbc.NavLink("Admin", href="/admin", active="exact", className="nav-link-custom")),
                    ], navbar=True),
                ], width="auto"),
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-sun-fill header-icon me-2"),
                            html.Div(id="theme-toggle", className="theme-toggle-switch"),
                            html.I(className="bi bi-moon-fill header-icon ms-2"),
                        ], className="d-flex align-items-center"),
                    ], className="ms-auto")
                ], width="auto"),
            ], align="center", className="w-100")
        ], fluid=True),
        className="modern-navbar"
    ),

    # Page content
    dbc.Container([
        dash.page_container
    ], fluid=True, className="px-4")
])

# Register shared callbacks (theme toggle, etc.)
from app.web.shared_callbacks import register_shared_callbacks
register_shared_callbacks(app)

# Expose server for deployment
server = app.server
