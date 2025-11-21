# app/web/pages/home.py
"""
Home/Dashboard Page - Main report generation interface
"""

import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
from pathlib import Path
import base64
import io

dash.register_page(__name__, path="/", title="Dashboard - Compliance Analytics")

# Page layout
layout = dbc.Container([
    dbc.Row([
        # Left column - Upload and Config
        dbc.Col([
            # Upload Section
            dbc.Card([
                dbc.CardHeader(html.H4("Upload File", className="mb-0")),
                dbc.CardBody([
                    dcc.Upload(
                        id='upload-data',
                        children=html.Div([
                            html.Div(style={"height": "30px"}),
                            html.I(className="bi bi-cloud-upload", style={"fontSize": "48px", "color": "#0d6efd"}),
                            html.Div(style={"height": "10px"}),
                            html.Span("Drag and Drop or "),
                            html.A("Select CSV/Excel File", className="upload-link")
                        ]),
                        style={
                            'width': '100%',
                            'height': '170px',
                            'lineHeight': '60px',
                            'borderWidth': '2px',
                            'borderStyle': 'dashed',
                            'borderRadius': '10px',
                            'textAlign': 'center',
                            'cursor': 'pointer',
                            'borderColor': '#dee2e6'
                        },
                        multiple=False
                    ),
                    html.Div(id='upload-status', className="mt-2"),
                    dcc.Store(id='stored-filename')
                ])
            ], className="mb-4"),

            # Config Section
            dbc.Card([
                dbc.CardHeader(html.H4("Configuration", className="mb-0")),
                dbc.CardBody([
                    html.Label("Tenant Organization", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id='tenant-dropdown',
                        options=[
                            {'label': 'ACME Health Center', 'value': 'acme_health'},
                            {'label': 'Metro Clinic', 'value': 'metro_clinic'},
                        ],
                        value='acme_health',
                        clearable=False,
                        className="mb-3"
                    ),

                    html.Label("Target State", className="fw-bold mb-2"),
                    dcc.Dropdown(
                        id='state-dropdown',
                        options=[
                            {'label': 'New Jersey (NJ)', 'value': 'NJ'},
                            {'label': 'New York (NY)', 'value': 'NY'},
                        ],
                        value='NJ',
                        clearable=False,
                        className="mb-3"
                    ),

                    html.Hr(),

                    dbc.Button(
                        [html.I(className="bi bi-play-fill me-2"), "Generate Report"],
                        id='generate-btn',
                        color="primary",
                        size="lg",
                        className="w-100",
                        disabled=True
                    )
                ])
            ])
        ], width=4),

        # Right column - Results
        dbc.Col([
            dbc.Card([
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
        ], width=8)
    ])
], fluid=True, className="mt-4")


@callback(
    Output('upload-status', 'children'),
    Output('generate-btn', 'disabled'),
    Output('stored-filename', 'data'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
)
def handle_upload(contents, filename):
    """Handle file upload"""
    if contents is None:
        return None, True, None

    # Show upload success
    status = dbc.Alert([
        html.I(className="bi bi-check-circle me-2"),
        f"Uploaded: {filename}"
    ], color="success", className="mb-0 mt-2")

    return status, False, filename


@callback(
    Output('results-area', 'children'),
    Input('generate-btn', 'n_clicks'),
    State('upload-data', 'contents'),
    State('stored-filename', 'data'),
    State('tenant-dropdown', 'value'),
    State('state-dropdown', 'value'),
    prevent_initial_call=True
)
def generate_report(n_clicks, contents, filename, tenant, state):
    """Generate compliance report"""
    if not contents:
        return dbc.Alert("Please upload a file first", color="warning")

    try:
        # Decode file
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        # Save temp file
        temp_path = Path("temp") / filename
        temp_path.parent.mkdir(exist_ok=True)
        with open(temp_path, 'wb') as f:
            f.write(decoded)

        # Run pipeline
        from app.adapters.report_adapter import ReportAdapter

        adapter = ReportAdapter(
            config_dir="config",
            output_dir="output"
        )

        artifact = adapter.generate(
            tenant_id=tenant,
            state_code=state,
            source_file=str(temp_path)
        )

        # Clean up temp file
        temp_path.unlink()

        # Display results
        if artifact.status == "ready":
            return dbc.Alert([
                html.H4("✓ Report Generated Successfully", className="alert-heading"),
                html.Hr(),
                html.P(f"Records: {artifact.control_totals.row_count if artifact.control_totals else 0}"),
                html.P(f"Status: {artifact.status}"),
                html.P(f"Run ID: {artifact.run_id}"),
            ], color="success")
        else:
            return dbc.Alert([
                html.H4("✗ Validation Failed", className="alert-heading"),
                html.Hr(),
                html.P(f"Errors: {artifact.validation.error_count if artifact.validation else 0}"),
                html.P(f"Warnings: {artifact.validation.warning_count if artifact.validation else 0}"),
            ], color="danger")

    except Exception as e:
        return dbc.Alert([
            html.H4("Error", className="alert-heading"),
            html.P(str(e))
        ], color="danger")
