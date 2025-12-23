import os
import json
import time
import requests
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic
from IPython.display import Javascript, HTML, display

@magics_class
class NotifyMagics(Magics):
    def __init__(self, shell):
        super(NotifyMagics, self).__init__(shell)
        self.watchdog_threshold = 0
        self.start_time = 0
        self._hooks_registered = False
        self._suppress_auto_watchdog = False
        self.webhook_url = os.environ.get('JUPYTER_WATCHDOG_WEBHOOK')

    def _print_status(self, message, success=True):
        color = "#28a745" if success else "#dc3545"
        icon = "✅" if success else "❌"
        html_content = f"""
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
        display(HTML(html_content))

    def _send_browser_notification(self, title, body):
        safe_title = json.dumps(title)
        safe_body = json.dumps(body)
        
        js_code = f"""
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
                new Notification({safe_title}, {{ body: {safe_body} }});
            }} else if (Notification.permission !== "denied") {{
                Notification.requestPermission().then(function (permission) {{
                    if (permission === "granted") {{
                        new Notification({safe_title}, {{ body: {safe_body} }});
                    }}
                }});
            }}
        }})();
        """
        display(Javascript(js_code))

    def _send_discord_notification(self, message):
        if not self.webhook_url:
            return
        
        data = {"content": message}
        try:
            response = requests.post(self.webhook_url, json=data)
            response.raise_for_status()
        except Exception as e:
            self._print_status(f"Failed to send Discord notification: {e}", success=False)

    def _handle_notification(self, result, duration, notification_type='system'):
        success = result.success
        if success:
            status_text = "Success"
            status_icon = "✅"
        else:
            status_text = "Failure"
            status_icon = "❌"
            
        msg_lines = [f"Status: {status_icon} {status_text}", f"Time: {duration:.2f}s"]
        
        if not success and result.error_in_exec:
             msg_lines.append(f"Error: {result.error_in_exec}")

        msg_body = "\n".join(msg_lines)
        title = "Jupyter Watchdog Alert"

        self._print_status(f"Execution finished in {duration:.2f}s", success=success)
        self._send_browser_notification(title, msg_body)

        if self.webhook_url and (notification_type == 'discord' or notification_type == 'watchdog'):
            discord_msg = f"**{title}**\n{msg_body}"
            self._send_discord_notification(discord_msg)

    def pre_run_cell_hook(self, info):
        self.start_time = time.time()

    def post_run_cell_hook(self, result):
        if self.watchdog_threshold <= 0:
            return

        if self._suppress_auto_watchdog:
            return

        duration = time.time() - self.start_time
        if duration > self.watchdog_threshold:
            self._handle_notification(result, duration, notification_type='watchdog')

    @line_magic
    def watchdog_setup(self, line):
        url = line.strip()
        if not url:
            print("Usage: %watchdog_setup <webhook_url>")
            return
        self.webhook_url = url
        print("Discord Webhook URL updated successfully.")

    @line_magic
    def watchdog_auto(self, line):
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
    def notify(self, line, cell):
        args = line.strip().lower()
        mode = args if args else 'system'
        
        start_time = time.time()
        self._suppress_auto_watchdog = True
        try:
            result = self.shell.run_cell(cell)
        finally:
            self._suppress_auto_watchdog = False
            
        duration = time.time() - start_time
        self._handle_notification(result, duration, notification_type=mode)
        return result.result

def load_ipython_extension(ipython):
    ipython.register_magics(NotifyMagics)
    print("Jupyter Watchdog extension loaded.")
