# dashboard/layouts.py
"""
UI layouts and components for the Dash application.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd


def create_header():
    """Create the application header."""
    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H3("State Charity Care Reporting", className="header-title mb-0"),
                    ])
                ]),
                dbc.Col([
                    html.Div([
                        html.Div([
                            html.I(className="bi bi-sun-fill header-icon me-2"),
                            html.Div(id="theme-toggle", className="theme-toggle-switch"),
                            html.I(className="bi bi-moon-fill header-icon ms-2"),
                        ], className="d-flex align-items-center me-4"),
                    ], className="d-flex align-items-center justify-content-end")
                ], width="auto"),
                dbc.Col([
                    html.Div([
                        html.Span("User: ", className="header-user-label"),
                        html.Span(id="current-user", className="header-user-name")
                    ], className="text-end")
                ], width="auto")
            ], align="center", className="w-100")
        ], fluid=True),
        className="modern-navbar mb-4"
    )


def create_upload_section():
    """Create the file upload section."""
    return dbc.Card([
        dbc.CardHeader(html.H4("Upload File", className="mb-0")),
        dbc.CardBody([
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    html.Div(style={"height": "30px"}),
                    html.I(className="bi bi-cloud-upload upload-icon-primary", style={"fontSize": "48px"}),
                    html.Div(style={"height": "10px"}),
                    html.Span("Drag and Drop or "),
                    html.A("Select CSV/Excel File", className="upload-link")
                ]),
                className="upload-box",
                style={
                    'width': '100%',
                    'height': '170px',
                    'lineHeight': '60px',
                    'borderWidth': '2px',
                    'borderStyle': 'dashed',
                    'borderRadius': '10px',
                    'textAlign': 'center',
                    'cursor': 'pointer'
                },
                multiple=False
            ),
            html.Br(),
            # Hidden div to store filename
            dcc.Store(id='stored-filename')
        ])
    ], className="mb-4")


def create_config_section():
    """Create the configuration section."""
    return dbc.Card([
        dbc.CardHeader(html.H4("Configuration", className="mb-0")),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Label("Tenant Organization", className="fw-bold"),
                    dcc.Dropdown(
                        id='tenant-dropdown',
                        options=[
                            {'label': 'ACME Health Center', 'value': 'acme_health'},
                            {'label': 'Metro Clinic', 'value': 'metro_clinic'},
                        ],
                        value='acme_health',
                        clearable=False,
                        style={'fontWeight': 'normal'}
                    )
                ], width=6),
                dbc.Col([
                    html.Label("Target State", className="fw-bold"),
                    dcc.Dropdown(
                        id='state-dropdown',
                        options=[
                            {'label': 'New Jersey (NJ)', 'value': 'NJ'},
                            {'label': 'New York (NY)', 'value': 'NY'},
                        ],
                        value='NJ',
                        clearable=False,
                        style={'fontWeight': 'normal'}
                    )
                ], width=6),
            ], className="mb-3"),
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        [html.I(className="bi bi-play-fill me-2"), "Generate Report"],
                        id='generate-btn',
                        color="primary",
                        size="lg",
                        className="w-100"
                    )
                ])
            ])
        ])
    ], className="mb-4")


def create_results_section():
    """Create the results display section."""
    return dbc.Card([
        dbc.CardHeader(html.H4("Results", className="mb-0")),
        dbc.CardBody([
            dcc.Loading(
                id="loading",
                type="default",
                children=html.Div(id='results-area', children=[
                    html.Div([
                        html.I(className="bi bi-info-circle", style={"fontSize": "48px", "color": "#6c757d"}),
                        html.Br(),
                        html.Br(),
                        html.P("Upload a file and click 'Generate Report' to begin", className="text-muted")
                    ], className="text-center py-5")
                ])
            )
        ])
    ])


def create_success_results(artifact):
    """Display successful report generation results."""
    return dbc.Container([
        # Summary Stats
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-file-text", style={"fontSize": "24px", "color": "#0d6efd"}),
                            html.H5("Records", className="mt-2 mb-0 text-muted"),
                            html.H2(f"{artifact.control_totals.row_count:,}" if artifact.control_totals else "0", className="mb-0")
                        ], className="text-center")
                    ])
                ], className="shadow-sm")
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-cash-stack", style={"fontSize": "24px", "color": "#198754"}),
                            html.H5("Total Charges", className="mt-2 mb-0 text-muted"),
                            html.H2(f"${artifact.control_totals.sum_total_charges:,.2f}" if artifact.control_totals else "$0",
                                   className="mb-0", style={"fontSize": "1.5rem"})
                        ], className="text-center")
                    ])
                ], className="shadow-sm")
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-wallet2", style={"fontSize": "24px", "color": "#ffc107"}),
                            html.H5("Total Payments", className="mt-2 mb-0 text-muted"),
                            html.H2(f"${artifact.control_totals.sum_total_payment_received:,.2f}" if artifact.control_totals else "$0",
                                   className="mb-0", style={"fontSize": "1.5rem"})
                        ], className="text-center")
                    ])
                ], className="shadow-sm")
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="bi bi-speedometer2", style={"fontSize": "24px", "color": "#dc3545"}),
                            html.H5("Gen Time", className="mt-2 mb-0 text-muted"),
                            html.H2(f"{artifact.generation_time_seconds:.2f}s", className="mb-0")
                        ], className="text-center")
                    ])
                ], className="shadow-sm")
            ], width=3),
        ], className="mb-4"),

        # Control Totals Breakdown
        html.H5("Control Totals", className="mt-4 mb-3"),
        dbc.Row([
            dbc.Col([
                html.H6("By Payor Source", className="text-muted"),
                dbc.Table.from_dataframe(
                    pd.DataFrame([
                        {"Payor": k, "Count": v}
                        for k, v in artifact.control_totals.by_payor_source.items()
                    ]) if artifact.control_totals and artifact.control_totals.by_payor_source else pd.DataFrame(),
                    striped=True,
                    bordered=True,
                    hover=True,
                    size="sm"
                )
            ], width=6),
            dbc.Col([
                html.H6("By Claim Type", className="text-muted"),
                dbc.Table.from_dataframe(
                    pd.DataFrame([
                        {"Claim Type": k, "Count": v}
                        for k, v in artifact.control_totals.by_claim_type.items()
                    ]) if artifact.control_totals and artifact.control_totals.by_claim_type else pd.DataFrame(),
                    striped=True,
                    bordered=True,
                    hover=True,
                    size="sm"
                )
            ], width=6),
        ], className="mb-4"),

        # Show warnings if any exist
        html.Div([
            dbc.Alert([
                html.I(className="bi bi-exclamation-triangle-fill me-2"),
                f"{len(artifact.validation.warnings)} Warning(s) Found - Review recommended but submission allowed"
            ], color="warning", className="mb-3"),

            html.H5("Warnings", className="text-warning mb-3"),
            dbc.Table.from_dataframe(
                pd.DataFrame(artifact.validation.warnings) if artifact.validation.warnings else pd.DataFrame(),
                striped=True,
                bordered=True,
                hover=True,
                size="sm"
            ),
        ], className="mb-4") if artifact.validation and artifact.validation.warnings else html.Div(),

        # Download Section
        html.H5("Downloads", className="mt-4 mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Button([
                    html.I(className="bi bi-download me-2"),
                    "Download"
                ], id="download-all-btn", color="primary", size="lg", className="w-100")
            ], width=12)
        ]),

        # Hidden download component
        dcc.Download(id="download-all"),

        # Store run_id for downloads
        dcc.Store(id='current-run-id', data=artifact.run_id)
    ], fluid=True)


def create_error_results(artifact):
    """Display validation errors."""
    return dbc.Container([
        dbc.Alert([
            html.I(className="bi bi-exclamation-triangle-fill me-2"),
            f"Validation Failed - {len(artifact.validation.errors)} Errors Found"
        ], color="danger", className="mb-4"),

        # Errors Table
        html.H5("Errors", className="text-danger mb-3"),
        dbc.Table.from_dataframe(
            pd.DataFrame(artifact.validation.errors) if artifact.validation.errors else pd.DataFrame({"message": ["No errors"]}),
            striped=True,
            bordered=True,
            hover=True,
            size="sm"
        ) if artifact.validation.errors else html.P("No errors", className="text-muted"),

        html.Hr(),

        # Warnings Table
        html.H5("Warnings", className="text-warning mb-3"),
        dbc.Table.from_dataframe(
            pd.DataFrame(artifact.validation.warnings) if artifact.validation.warnings else pd.DataFrame({"message": ["No warnings"]}),
            striped=True,
            bordered=True,
            hover=True,
            size="sm"
        ) if artifact.validation.warnings else html.P("No warnings", className="text-muted"),

        html.Hr(),

        # Still show validation report download
        html.H5("Downloads", className="mb-3"),
        dbc.Button([
            html.I(className="bi bi-clipboard-check me-2"),
            "Download Validation Report"
        ], id="download-validation-btn", color="danger", outline=True),

        dcc.Download(id="download-validation"),
        dcc.Store(id='current-run-id', data=artifact.run_id)
    ], fluid=True)


def create_main_layout():
    """Create the main application layout."""
    return html.Div([
        dcc.Store(id='theme-store', data='light', storage_type='local'),
        html.Div(id='toast-notification', className='toast-notification'),
        dbc.Container([
            create_header(),
            dbc.Row([
                dbc.Col([
                    create_upload_section(),
                    create_config_section(),
                ], width=4),
                dbc.Col([
                    create_results_section()
                ], width=8)
            ])
        ], fluid=True, className="px-4")
    ])
    