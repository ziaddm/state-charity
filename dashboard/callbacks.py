# dashboard/callbacks.py
"""
Callback functions for the Dash application.
"""
import base64
import logging
from pathlib import Path
from dash import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from dash import html

from app.adapters.report_adapter import ReportAdapter
from dashboard.layouts import create_success_results, create_error_results

logger = logging.getLogger(__name__)

# Initialize adapter
adapter = ReportAdapter(config_dir="config", output_dir="output")


def register_callbacks(app):
    """Register all callbacks for the Dash app."""

    # Clientside callback for theme toggle
    app.clientside_callback(
        """
        function(n_clicks, current_theme) {
            if (!n_clicks) {
                const stored = localStorage.getItem('theme-store');
                const theme = stored ? JSON.parse(stored).data : 'light';
                document.documentElement.setAttribute('data-theme', theme);
                return theme;
            }
            const newTheme = current_theme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            return newTheme;
        }
        """,
        Output('theme-store', 'data'),
        Input('theme-toggle', 'n_clicks'),
        State('theme-store', 'data')
    )

    @app.callback(
        Output('toast-notification', 'children'),
        Output('stored-filename', 'data'),
        Output('upload-data', 'children'),
        Input('upload-data', 'contents'),
        State('upload-data', 'filename')
    )
    def handle_upload(contents, filename):
        """Handle file upload and save to temp directory."""
        if contents is None:
            raise PreventUpdate

        try:
            # Decode the uploaded file
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)

            # Save to temp directory
            temp_dir = Path("temp_uploads")
            temp_dir.mkdir(exist_ok=True)
            temp_path = temp_dir / filename

            with open(temp_path, 'wb') as f:
                f.write(decoded)

            logger.info(f"File uploaded: {filename} ({len(decoded)} bytes)")

            # Success message with auto-dismiss
            success_message = dbc.Alert([
                html.I(className="bi bi-check-circle-fill me-2"),
                f"File uploaded: {filename}"
            ], color="success", dismissable=True, duration=4000)

            # Replace cloud icon with file icon and filename
            uploaded_display = html.Div([
                html.I(className="bi bi-file-earmark-text upload-icon-success", style={"fontSize": "48px"}),
                html.Div(style={"height": "10px"}),
                html.Span(filename, className="uploaded-filename", style={"fontWeight": "500"})
            ], style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center", "height": "100%"})

            return success_message, filename, uploaded_display

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            error_message = dbc.Alert([
                html.I(className="bi bi-x-circle-fill me-2"),
                f"Upload failed: {str(e)}"
            ], color="danger", dismissable=True)

            # Keep original upload display on error
            original_display = html.Div([
                html.Div(style={"height": "30px"}),
                html.I(className="bi bi-cloud-upload upload-icon-primary", style={"fontSize": "48px"}),
                html.Div(style={"height": "10px"}),
                html.Span("Drag and Drop or "),
                html.A("Select CSV/Excel File", className="upload-link")
            ])

            return error_message, None, original_display

    @app.callback(
        Output('results-area', 'children'),
        Output('toast-notification', 'children', allow_duplicate=True),
        Input('generate-btn', 'n_clicks'),
        State('stored-filename', 'data'),
        State('tenant-dropdown', 'value'),
        State('state-dropdown', 'value'),
        prevent_initial_call=True
    )
    def generate_report(n_clicks, filename, tenant_id, state_code):
        """Generate compliance report using the adapter."""
        if not filename:
            return dbc.Alert([
                html.I(className="bi bi-exclamation-triangle-fill me-2"),
                "Please upload a file first"
            ], color="warning"), None

        try:
            logger.info(f"Starting report generation: tenant={tenant_id}, state={state_code}, file={filename}")

            # Call the adapter
            source_file = f"temp_uploads/{filename}"
            artifact = adapter.generate(
                tenant_id=tenant_id,
                state_code=state_code,
                source_file=source_file
            )

            logger.info(f"Report generation complete: run_id={artifact.run_id}, status={artifact.status}")

            # Success notification
            success_toast = dbc.Alert([
                html.I(className="bi bi-check-circle-fill me-2"),
                "Report generated successfully!"
            ], color="success", dismissable=True, duration=4000)

            # Build results display based on status
            if artifact.status == "ready":
                return create_success_results(artifact), success_toast
            elif artifact.status == "errors":
                return create_error_results(artifact), None
            elif artifact.status == "failed":
                # Show processing errors
                return create_error_results(artifact), None
            else:
                return dbc.Alert([
                    html.I(className="bi bi-info-circle-fill me-2"),
                    f"Status: {artifact.status}"
                ], color="info"), None

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            return dbc.Alert([
                html.I(className="bi bi-file-earmark-x-fill me-2"),
                f"Configuration error: {str(e)}"
            ], color="danger"), None

        except Exception as e:
            logger.error(f"Report generation failed: {e}", exc_info=True)
            return dbc.Alert([
                html.I(className="bi bi-x-circle-fill me-2"),
                f"Error: {str(e)}"
            ], color="danger"), None

    @app.callback(
        Output('download-submission', 'data'),
        Input('download-submission-btn', 'n_clicks'),
        State('current-run-id', 'data'),
        State('tenant-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_submission_file(n_clicks, run_id, tenant_id):
        """Download the fixed-width submission file."""
        if not run_id:
            raise PreventUpdate

        try:
            # Find the submission file
            output_dir = Path("output") / tenant_id / run_id
            submission_files = list(output_dir.glob("*.txt"))

            if not submission_files:
                logger.error(f"Submission file not found for run_id={run_id}")
                raise PreventUpdate

            submission_file = submission_files[0]
            logger.info(f"Downloading submission file: {submission_file}")

            return {
                'content': submission_file.read_text(encoding='utf-8'),
                'filename': submission_file.name
            }

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise PreventUpdate

    @app.callback(
        Output('download-validation', 'data'),
        Input('download-validation-btn', 'n_clicks'),
        State('current-run-id', 'data'),
        State('tenant-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_validation_report(n_clicks, run_id, tenant_id):
        """Download the validation report."""
        if not run_id:
            raise PreventUpdate

        try:
            output_dir = Path("output") / tenant_id / run_id
            validation_file = output_dir / f"{run_id}_validation.json"

            if not validation_file.exists():
                logger.error(f"Validation file not found for run_id={run_id}")
                raise PreventUpdate

            logger.info(f"Downloading validation report: {validation_file}")

            return {
                'content': validation_file.read_text(encoding='utf-8'),
                'filename': validation_file.name
            }

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise PreventUpdate

    @app.callback(
        Output('download-manifest', 'data'),
        Input('download-manifest-btn', 'n_clicks'),
        State('current-run-id', 'data'),
        State('tenant-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_manifest(n_clicks, run_id, tenant_id):
        """Download the manifest file."""
        if not run_id:
            raise PreventUpdate

        try:
            output_dir = Path("output") / tenant_id / run_id
            manifest_file = output_dir / f"{run_id}_manifest.json"

            if not manifest_file.exists():
                logger.error(f"Manifest file not found for run_id={run_id}")
                raise PreventUpdate

            logger.info(f"Downloading manifest: {manifest_file}")

            return {
                'content': manifest_file.read_text(encoding='utf-8'),
                'filename': manifest_file.name
            }

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise PreventUpdate

    @app.callback(
        Output('download-control', 'data'),
        Input('download-control-btn', 'n_clicks'),
        State('current-run-id', 'data'),
        State('tenant-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_control_totals(n_clicks, run_id, tenant_id):
        """Download the control totals file."""
        if not run_id:
            raise PreventUpdate

        try:
            output_dir = Path("output") / tenant_id / run_id
            control_file = output_dir / f"{run_id}_control_totals.json"

            if not control_file.exists():
                logger.error(f"Control totals file not found for run_id={run_id}")
                raise PreventUpdate

            logger.info(f"Downloading control totals: {control_file}")

            return {
                'content': control_file.read_text(encoding='utf-8'),
                'filename': control_file.name
            }

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise PreventUpdate

    @app.callback(
        Output('download-all', 'data'),
        Input('download-all-btn', 'n_clicks'),
        State('current-run-id', 'data'),
        State('tenant-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_all_files(n_clicks, run_id, tenant_id):
        """Download all files as a zip archive."""
        if not run_id:
            raise PreventUpdate

        try:
            import zipfile
            import io

            output_dir = Path("output") / tenant_id / run_id

            # Create a zip file in memory
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Add submission file
                submission_files = list(output_dir.glob("*.txt"))
                if submission_files:
                    zip_file.write(submission_files[0], submission_files[0].name)

                # Add validation report
                validation_file = output_dir / f"{run_id}_validation.json"
                if validation_file.exists():
                    zip_file.write(validation_file, validation_file.name)

                # Add manifest
                manifest_file = output_dir / f"{run_id}_manifest.json"
                if manifest_file.exists():
                    zip_file.write(manifest_file, manifest_file.name)

                # Add control totals
                control_file = output_dir / f"{run_id}_control_totals.json"
                if control_file.exists():
                    zip_file.write(control_file, control_file.name)

            zip_buffer.seek(0)
            logger.info(f"Created zip archive for run_id={run_id}")

            return {
                'content': base64.b64encode(zip_buffer.read()).decode(),
                'filename': f"{run_id}_all_files.zip",
                'base64': True
            }

        except Exception as e:
            logger.error(f"Bulk download failed: {e}")
            raise PreventUpdate

    @app.callback(
        Output('current-user', 'children'),
        Input('tenant-dropdown', 'value')
    )
    def update_current_user(tenant_id):
        """Update the current user display (placeholder for auth)."""
        # TODO: Replace with actual authenticated user info
        tenant_names = {
            'acme_health': 'ACME Health',
            'metro_clinic': 'Metro Clinic'
        }
        return tenant_names.get(tenant_id, tenant_id)
