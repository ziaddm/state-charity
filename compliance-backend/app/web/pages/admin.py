# app/web/pages/admin.py
"""
Admin Dashboard Page - Testing and Debugging Tools

Features:
- Run unit tests from UI
- Run golden file tests
- View test results in real-time
- See test coverage
- Debug failed runs
- View system logs
"""

import dash
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import subprocess
import json
from pathlib import Path

dash.register_page(__name__, path="/admin", title="Admin - Compliance Analytics")

# Page layout
layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H2("Admin Dashboard", className="mb-4"),
        ])
    ]),

    dbc.Row([
        # Left column - Test Controls
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H4("Test Runner")),
                dbc.CardBody([
                    html.H5("Unit Tests"),
                    dbc.ButtonGroup([
                        dbc.Button("Run All Tests", id="btn-run-all-tests", color="primary", className="me-2"),
                        dbc.Button("Field Validator", id="btn-test-field", color="secondary", size="sm"),
                        dbc.Button("Pre Validator", id="btn-test-pre", color="secondary", size="sm"),
                        dbc.Button("Control Totals", id="btn-test-control", color="secondary", size="sm"),
                    ], className="mb-3 d-block"),

                    html.Hr(),

                    html.H5("Golden File Tests"),
                    dbc.Button("Run Golden Tests", id="btn-golden-tests", color="primary", className="mb-3 w-100"),

                    html.Hr(),

                    html.H5("Test Options"),
                    dbc.Checklist(
                        id="test-options",
                        options=[
                            {"label": "Verbose output", "value": "verbose"},
                            {"label": "Show coverage", "value": "coverage"},
                            {"label": "Stop on first failure", "value": "stop-first"},
                        ],
                        value=["verbose"],
                        className="mb-3"
                    ),

                    # Test status
                    html.Div(id="test-status", className="mt-3"),
                ])
            ], className="mb-3"),

            # System Info Card
            dbc.Card([
                dbc.CardHeader(html.H4("System Info")),
                dbc.CardBody([
                    html.Div(id="system-info")
                ])
            ])
        ], width=4),

        # Right column - Test Results
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.Div([
                        html.H4("Test Results", className="d-inline"),
                        dbc.Button("Clear", id="btn-clear-results", color="link", size="sm", className="float-end"),
                    ])
                ]),
                dbc.CardBody([
                    dcc.Loading(
                        id="loading-test-results",
                        type="default",
                        children=html.Div(id="test-results-output",
                                         style={"height": "600px", "overflow-y": "scroll"})
                    )
                ])
            ])
        ], width=8)
    ]),

    # Hidden interval for refreshing running tests
    dcc.Interval(id="test-refresh-interval", interval=1000, disabled=True),
    dcc.Store(id="test-running-store", data=False),

], fluid=True, className="mt-4")


# Callback to run all tests
@callback(
    Output("test-results-output", "children"),
    Output("test-status", "children"),
    Output("test-running-store", "data"),
    Output("test-refresh-interval", "disabled"),
    Input("btn-run-all-tests", "n_clicks"),
    Input("btn-test-field", "n_clicks"),
    Input("btn-test-pre", "n_clicks"),
    Input("btn-test-control", "n_clicks"),
    Input("btn-golden-tests", "n_clicks"),
    State("test-options", "value"),
    prevent_initial_call=True
)
def run_tests(btn_all, btn_field, btn_pre, btn_control, btn_golden, options):
    """Run pytest tests based on button clicked"""
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Determine which tests to run
    test_files = {
        "btn-run-all-tests": ["tests/test_field_validator.py", "tests/test_pre_validator.py", "tests/test_control_totals_validator.py"],
        "btn-test-field": ["tests/test_field_validator.py"],
        "btn-test-pre": ["tests/test_pre_validator.py"],
        "btn-test-control": ["tests/test_control_totals_validator.py"],
        "btn-golden-tests": ["tests/test_golden_files.py"],
    }

    files = test_files.get(button_id, [])
    if not files:
        return html.P("Unknown test type"), dash.no_update, False, True

    # Build pytest command
    cmd = ["python", "-m", "pytest"] + files

    # Add options
    if "verbose" in options:
        cmd.append("-v")
    if "coverage" in options:
        cmd.extend(["--cov=app", "--cov-report=term-missing"])
    if "stop-first" in options:
        cmd.append("-x")

    # Don't add color output - we'll handle formatting ourselves
    cmd.append("--color=no")

    # Run tests
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,
            timeout=60
        )

        # Parse output
        output = result.stdout + result.stderr

        # Determine status
        if result.returncode == 0:
            status_badge = dbc.Badge("✓ All Tests Passed", color="success", className="me-2")
            status_color = "success"
        else:
            status_badge = dbc.Badge("✗ Tests Failed", color="danger", className="me-2")
            status_color = "danger"

        # Format output with syntax highlighting (basic)
        output_lines = output.split("\n")
        formatted_lines = []

        for line in output_lines:
            if "PASSED" in line:
                formatted_lines.append(html.Div(line, style={"color": "green", "fontFamily": "monospace"}))
            elif "FAILED" in line or "ERROR" in line:
                formatted_lines.append(html.Div(line, style={"color": "red", "fontFamily": "monospace", "fontWeight": "bold"}))
            elif line.startswith("====="):
                formatted_lines.append(html.Div(line, style={"color": "#666", "fontFamily": "monospace"}))
            else:
                formatted_lines.append(html.Div(line, style={"fontFamily": "monospace", "fontSize": "13px"}))

        status_info = dbc.Alert([
            status_badge,
            html.Span(f"Ran {len(files)} test file(s)"),
        ], color=status_color, className="mb-0")

        return formatted_lines, status_info, False, True

    except subprocess.TimeoutExpired:
        return html.Pre("Tests timed out after 60 seconds", style={"color": "red"}), \
               dbc.Alert("⏱ Test Timeout", color="warning"), False, True
    except Exception as e:
        return html.Pre(f"Error running tests: {str(e)}", style={"color": "red"}), \
               dbc.Alert(f"✗ Error: {str(e)}", color="danger"), False, True


# Callback to clear results
@callback(
    Output("test-results-output", "children", allow_duplicate=True),
    Output("test-status", "children", allow_duplicate=True),
    Input("btn-clear-results", "n_clicks"),
    prevent_initial_call=True
)
def clear_results(n_clicks):
    """Clear test results"""
    return html.P("Click a button above to run tests", className="text-muted"), None


# Callback to update system info
@callback(
    Output("system-info", "children"),
    Input("test-status", "children")  # Update when tests run
)
def update_system_info(_):
    """Display system information"""
    import sys
    import platform

    try:
        # Get Python version
        python_version = sys.version.split()[0]

        # Get pytest version
        pytest_result = subprocess.run(
            ["python", "-m", "pytest", "--version"],
            capture_output=True,
            text=True
        )
        pytest_version = pytest_result.stdout.strip().split()[-1] if pytest_result.returncode == 0 else "Not installed"

        # Count test files
        test_dir = Path(__file__).parent.parent.parent.parent / "tests"
        test_files = list(test_dir.glob("test_*.py"))

        return html.Div([
            html.P([html.Strong("Python: "), python_version], className="mb-1"),
            html.P([html.Strong("Pytest: "), pytest_version], className="mb-1"),
            html.P([html.Strong("Platform: "), platform.system()], className="mb-1"),
            html.P([html.Strong("Test Files: "), str(len(test_files))], className="mb-1"),
        ])
    except Exception as e:
        return html.P(f"Error: {str(e)}", className="text-danger")


