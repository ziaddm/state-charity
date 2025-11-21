# app/web/shared_callbacks.py
"""
Shared callbacks that work across all pages
"""
from dash import Input, Output, State, clientside_callback, ClientsideFunction


def register_shared_callbacks(app):
    """Register callbacks that are shared across all pages"""

    # Theme toggle - uses clientside callback for instant switching
    app.clientside_callback(
        """
        function(n_clicks, current_theme) {
            if (n_clicks) {
                const new_theme = current_theme === 'light' ? 'dark' : 'light';
                document.documentElement.setAttribute('data-theme', new_theme);
                return new_theme;
            }
            // Initialize theme on page load
            document.documentElement.setAttribute('data-theme', current_theme || 'light');
            return current_theme || 'light';
        }
        """,
        Output('theme-store', 'data'),
        Input('theme-toggle', 'n_clicks'),
        State('theme-store', 'data'),
    )
