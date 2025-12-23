import os
import json
import time
import threading
import logging
from typing import Optional, Any, Literal
import requests
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic
from IPython.core.interactiveshell import ExecutionResult
from IPython.display import Javascript, HTML, display

logger = logging.getLogger("jupyter_watchdog")
logger.addHandler(logging.NullHandler())

NotificationType = Literal["system", "discord", "watchdog"]

HTML_TEMPLATE = """
<div style="
    background-color: {color};
    color: white;
    padding: 8px 12px;
    border-radius: 4px;
    margin-top: 5px;
    font-family: sans-serif;
    font-weight: bold;
">
    {icon} {message}
</div>
"""

JS_TEMPLATE = """
(function() {{
    try {{
        var AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {{
            var ctx = new AudioContext();
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            
            osc.type = 'sine';
            osc.frequency.setValueAtTime(440, ctx.currentTime);
            
            osc.connect(gain);
            gain.connect(ctx.destination);
            
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        }}
    }} catch (e) {{
        console.error("Watchdog Audio Error:", e);
    }}

    if (!("Notification" in window)) {{
        console.warn("This browser does not support desktop notification");
    }} else if (Notification.permission === "granted") {{
        new Notification({title}, {{ body: {body} }});
    }} else if (Notification.permission !== "denied") {{
        Notification.requestPermission().then(function (permission) {{
            if (permission === "granted") {{
                new Notification({title}, {{ body: {body} }});
            }}
        }});
    }}
}})();
"""

@magics_class
class NotifyMagics(Magics):
    """
    An IPython extension that enhances Jupyter with notifications.
    Features:
    - %%notify: Manual notification for a single cell.
    - %watchdog_auto <seconds>: Auto-notification for long-running cells.
    - %watchdog_setup <url>: Configure Discord Webhook.
    """

    def __init__(self, shell: Any):
        super(NotifyMagics, self).__init__(shell)
        self.watchdog_threshold: float = 0.0
        self.start_time: float = 0.0
        self._hooks_registered: bool = False
        self._suppress_auto_watchdog: bool = False
        
        self.webhook_url: Optional[str] = os.environ.get('JUPYTER_WATCHDOG_WEBHOOK')

    def _now(self) -> float:
        return time.time()

    def _print_status(self, message: str, success: bool = True) -> None:
        """Displays a styled status message in the notebook output area using HTML."""
        color = "#28a745" if success else "#dc3545"
        icon = "✅" if success else "❌"
        
        html_content = HTML_TEMPLATE.format(color=color, icon=icon, message=message)
        display(HTML(html_content))

    def _send_browser_notification(self, title: str, body: str) -> None:
        """Sends a native browser notification safely."""
        safe_title = json.dumps(title)
        safe_body = json.dumps(body)
        
        js_code = JS_TEMPLATE.format(title=safe_title, body=safe_body)
        display(Javascript(js_code))

    def _send_discord_request(self, url: str, message: str) -> None:
        """Internal method to execute the Discord request safely in a thread."""
        def request_task():
            data = {"content": message}
            try:
                response = requests.post(url, json=data, timeout=5)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send Discord notification: {e}")
                
        thread = threading.Thread(target=request_task, daemon=True)
        thread.start()

    def _handle_notification(self, result: ExecutionResult, duration: float, notification_type: NotificationType = 'system') -> None:
        """Central logic for constructing and sending notifications."""
        success = result.success
        
        if success:
            status_text = "Success"
            status_icon = "✅"
        else:
            status_text = "Failure"
            status_icon = "❌"
            
        msg_lines = [f"Status: {status_icon} {status_text}", f"Time: {duration:.2f}s"]
        
        if not success and result.error_in_exec:
             try:
                 ex_type = type(result.error_in_exec).__name__
                 ex_msg = str(result.error_in_exec)
                 err_str = f"{ex_type}: {ex_msg}"
             except Exception:
                 err_str = "Unknown Error"
             msg_lines.append(f"Error: {err_str}")

        msg_body = "\n".join(msg_lines)
        title = "Jupyter Watchdog Alert"

        self._print_status(f"Execution finished in {duration:.2f}s", success=success)
        self._send_browser_notification(title, msg_body)

        should_send_discord = (
            self.webhook_url 
            and (notification_type == 'discord' or notification_type == 'watchdog')
        )
        
        if should_send_discord:
            discord_msg = f"**{title}**\n{msg_body}"
            self._send_discord_request(self.webhook_url, discord_msg) # type: ignore

    def pre_run_cell_hook(self, info: Any) -> None:
        self.start_time = self._now()

    def post_run_cell_hook(self, result: ExecutionResult) -> None:
        if self.watchdog_threshold <= 0:
            return

        if self._suppress_auto_watchdog:
            return

        duration = self._now() - self.start_time
        if duration > self.watchdog_threshold:
            self._handle_notification(result, duration, notification_type='watchdog')

    @line_magic
    def watchdog_setup(self, line: str) -> None:
        """
        Usage: %watchdog_setup <webhook_url>
        Sets the Discord Webhook URL for the current session.
        """
        url = line.strip()
        if not url:
            print("Usage: %watchdog_setup <webhook_url>")
            return
        
        if not url.startswith("http"):
            print("Error: Invalid URL. Must start with http:// or https://")
            return

        self.webhook_url = url
        print("Discord Webhook URL updated successfully.")

    @line_magic
    def watchdog_auto(self, line: str) -> None:
        """
        Usage: %watchdog_auto <seconds>
        Enable background monitoring.
        """
        args = line.strip()
        if not args:
            print(f"Current threshold: {self.watchdog_threshold}s (0 = disabled)")
            return

        try:
            seconds = float(args)
        except ValueError:
            print("Error: Seconds must be a number.")
            return

        if seconds < 0:
             print("Error: Seconds cannot be negative.")
             return

        self.watchdog_threshold = seconds

        if self.watchdog_threshold > 0:
            if not self._hooks_registered:
                self.shell.events.register('pre_run_cell', self.pre_run_cell_hook)
                self.shell.events.register('post_run_cell', self.post_run_cell_hook)
                self._hooks_registered = True
                print(f"Watchdog enabled. Alerting if cell execution > {self.watchdog_threshold}s.")
            else:
                print(f"Watchdog threshold updated to {self.watchdog_threshold}s.")
        else:
            if self._hooks_registered:
                self.shell.events.unregister('pre_run_cell', self.pre_run_cell_hook)
                self.shell.events.unregister('post_run_cell', self.post_run_cell_hook)
                self._hooks_registered = False
                print("Watchdog disabled.")
            else:
                print("Watchdog is already disabled.")

    @cell_magic
    def notify(self, line: str, cell: str) -> Any:
        """
        Usage: %%notify [system|discord]
        Executes the cell and triggers a notification.
        """
        args = line.strip().lower()
        mode: NotificationType = 'system'

        if args == 'discord':
            mode = 'discord'
        elif args and args != 'system':
             print(f"Warning: Unknown argument '{args}'. Defaulting to 'system'.")

        start_time = self._now()
        
        self._suppress_auto_watchdog = True
        try:
            result = self.shell.run_cell(cell)
        finally:
            self._suppress_auto_watchdog = False
            
        duration = self._now() - start_time
        
        self._handle_notification(result, duration, notification_type=mode)
            
        return result.result

def load_ipython_extension(ipython: Any) -> None:
    ipython.register_magics(NotifyMagics)
    print("Jupyter Watchdog extension loaded.")
