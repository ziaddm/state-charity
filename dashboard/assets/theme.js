// Clientside callback for theme toggling
window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        toggle_theme: function(n_clicks, current_theme) {
            // If no clicks yet, load from storage or default to light
            if (!n_clicks) {
                const stored = localStorage.getItem('theme-store');
                const theme = stored ? JSON.parse(stored).data : 'light';
                document.documentElement.setAttribute('data-theme', theme);
                return theme;
            }

            // Toggle theme
            const newTheme = current_theme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            return newTheme;
        }
    }
});

// Set initial theme on page load
document.addEventListener('DOMContentLoaded', function() {
    const stored = localStorage.getItem('theme-store');
    const theme = stored ? JSON.parse(stored).data : 'light';
    document.documentElement.setAttribute('data-theme', theme);
});
