"""
Authentication templates.
"""

from typing import Optional

from pydom import Component
from pydom import html as d


class AuthPage(Component):
    """Authentication page content."""
    
    def __init__(self, is_authenticated: bool = False):
        self.is_authenticated = is_authenticated
    
    def render(self):
        if self.is_authenticated:
            return AuthenticatedView()
        return LoginView()


class LoginView(Component):
    """Login view for unauthenticated users."""
    
    def render(self):
        return d.Div(classes="max-w-md mx-auto bg-white shadow rounded-lg p-8 mt-10")(
            d.H1(classes="text-2xl font-bold text-gray-900 mb-4 text-center")("Sign In to Yoto"),
            d.P(classes="text-gray-600 mb-6 text-center")(
                "Use your Yoto account to sign in. You'll be redirected to Yoto's login page."
            ),
            d.Div(classes="flex flex-col space-y-4")(
                d.Button(
                    type="button",
                    classes="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500",
                    hx_post="/auth/oauth-start",
                    hx_target="#auth-content",
                    hx_swap="innerHTML",
                    hx_indicator="#auth-loading",
                )("Start Authentication"),
            ),
            d.Div(id="auth-content", classes="mt-6"),
            d.Div(id="auth-loading", classes="htmx-indicator flex items-center justify-center space-x-2 mt-4 text-gray-500")(
                d.Div(classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"),
                d.Span()("Redirecting to Yoto login..."),
            ),
        )


class AuthenticatedView(Component):
    """View for authenticated users."""
    
    def render(self):
        return d.Div(classes="max-w-md mx-auto bg-white shadow rounded-lg p-8 mt-10 text-center")(
            d.Div(classes="h-16 w-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-4xl mx-auto mb-4")(
                d.Span()("✓")
            ),
            d.H1(classes="text-2xl font-bold text-gray-900 mb-2")("You're Signed In!"),
            d.P(classes="text-gray-600 mb-6")("You have successfully authenticated with your Yoto account."),
            d.Div(classes="flex flex-col space-y-3")(
                d.A(
                    href="/playlists/",
                    classes="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
                )("Go to Playlists"),
                d.Button(
                    type="button",
                    classes="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50",
                    hx_post="/auth/logout",
                    hx_swap="none",
                )("Sign Out"),
            ),
        )


class AuthStatusPartial(Component):
    """Partial for authentication status updates."""
    
    def __init__(
        self,
        is_authenticated: bool = False,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.is_authenticated = is_authenticated
        self.message = message
        self.error = error
    
    def render(self):
        if self.error:
            return d.Div(classes="rounded-md bg-red-50 p-4")(
                d.Div(classes="flex")(
                    d.Div(classes="flex-shrink-0")(
                        d.Span(classes="text-red-400")("⚠️")
                    ),
                    d.Div(classes="ml-3")(
                        d.H3(classes="text-sm font-medium text-red-800")("Authentication Error"),
                        d.Div(classes="mt-2 text-sm text-red-700")(
                            d.P()(self.error)
                        ),
                    ),
                )
            )
        
        if self.is_authenticated:
            # Trigger a redirect or update the page
            return d.Div(
                hx_trigger="load",
                hx_get="/auth/",
                hx_target="body",
                hx_push_url="true",
            )
        
        return d.Div()


class DeviceCodeInstructions(Component):
    """Instructions for device code flow."""
    
    def __init__(self, user_code: str, verification_uri: str, interval: int = 5):
        self.user_code = user_code
        self.verification_uri = verification_uri
        self.interval = interval
    
    def render(self):
        return d.Div(
            classes="bg-gray-50 p-6 rounded-lg border border-gray-200",
            id="device-code-instructions",
        )(
            # Auto-open verification URI link (only once)
            d.Script()(f"""
            (function() {{
                // Only open if not already opened
                if (!window.deviceCodeOpened) {{
                    window.deviceCodeOpened = true;
                    const link = document.querySelector('#device-code-link');
                    if (link) {{
                        window.open(link.href, '_blank');
                    }}
                }}
            }})();
            """),
            
            d.H3(classes="text-lg font-medium text-gray-900 mb-4")("Follow these steps:"),
            d.Ol(classes="list-decimal list-inside space-y-4 text-gray-600")(
                d.Li()(
                    "Copy this code: ",
                    d.Div(classes="flex items-center gap-3 mt-4")(
                        d.Div(
                            classes="text-3xl font-mono font-bold tracking-widest bg-white border border-gray-300 px-4 py-2 rounded text-center flex-1 select-all cursor-pointer",
                            id="user-code",
                            title="Click to select"
                        )(self.user_code),
                        d.Button(
                            type="button",
                            classes="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-medium text-sm transition-colors",
                            onclick="copyUserCode()"
                        )("Copy"),
                    ),
                ),
                d.Li()(
                    "Click this link to open the Yoto login page: ",
                    d.Br(),
                    d.A(
                        href=self.verification_uri,
                        target="_blank",
                        id="device-code-link",
                        classes="text-indigo-600 hover:text-indigo-700 font-medium underline break-all inline-block mt-2"
                    )(self.verification_uri),
                ),
                d.Li()("Paste the code and sign in."),
                d.Li()("Return to this tab - it will update automatically."),
            ),
            # Copy function script
            d.Script()("""
            function copyUserCode() {
                const codeElement = document.getElementById('user-code');
                const text = codeElement.innerText;
                
                // Try modern Clipboard API first
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(() => {
                        showCopyFeedback();
                    }).catch(() => {
                        fallbackCopy(text);
                    });
                } else {
                    fallbackCopy(text);
                }
            }
            
            function fallbackCopy(text) {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                showCopyFeedback();
            }
            
            function showCopyFeedback() {
                const button = event.target;
                const originalText = button.innerText;
                button.innerText = 'Copied!';
                button.classList.add('bg-green-600');
                button.classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
                
                setTimeout(() => {
                    button.innerText = originalText;
                    button.classList.remove('bg-green-600');
                    button.classList.add('bg-indigo-600', 'hover:bg-indigo-700');
                }, 2000);
            }
            """),
            
            # Polling div
            d.Div(
                hx_post="/auth/poll",
                hx_trigger=f"every {self.interval}s",
                hx_target="#auth-content",
                hx_swap="innerHTML",
                classes="mt-6 text-center text-sm text-gray-500"
            )(
                d.Div(classes="flex items-center justify-center space-x-2")(
                    d.Div(classes="animate-pulse h-2 w-2 bg-indigo-400 rounded-full"),
                    d.Div(classes="animate-pulse h-2 w-2 bg-indigo-400 rounded-full delay-75"),
                    d.Div(classes="animate-pulse h-2 w-2 bg-indigo-400 rounded-full delay-150"),
                    d.Span()("Waiting for you to sign in..."),
                )
            ),
        )
