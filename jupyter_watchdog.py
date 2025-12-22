import time
import requests
from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.core.magic_arguments import argument, magic_arguments, parse_argstring
try:
    from plyer import notification
except ImportError:
    notification = None

@magics_class
class NotifyMagics(Magics):
    """
    An IPython extension that introduces the %%notify magic command.
    It executes the cell and sends a notification upon completion.
    """

    def _send_system_notification(self, title, message):
        if notification:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name='Jupyter Watchdog',
                    timeout=10
                )
            except Exception as e:
                print(f"Failed to send system notification: {e}")
        else:
            print("Plyer not installed. System notification skipped.")

    def _send_discord_notification(self, message):
        # Placeholder Webhook URL - User should replace this
        WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE"
        
        if WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE":
            print("Discord Webhook URL not set. Please update jupyter_watchdog.py.")
            return

        data = {
            "content": message
        }
        try:
            response = requests.post(WEBHOOK_URL, json=data)
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")

    @cell_magic
    def notify(self, line, cell):
        """
        Usage: %%notify [system|discord]
        
        Executes the cell and sends a notification with the result and duration.
        Default notification type is 'system'.
        """
        args = line.strip().lower()
        mode = args if args else 'system'
        
        start_time = time.time()
        
        result = self.shell.run_cell(cell)
        
        duration = time.time() - start_time
        
        if result.success:
            status = "✅ Success"
        else:
            status = "❌ Failure"
            
        msg_body = f"Status: {status}\nTime: {duration:.2f}s"
        if not result.success and result.error_in_exec:
             msg_body += f"\nError: {result.error_in_exec}"
        if mode == 'discord':
            self._send_discord_notification(f"**Jupyter Cell Execution Finished**\n{msg_body}")
        else:
            self._send_system_notification("Jupyter Cell Execution Finished", msg_body)
            
        return result.result

def load_ipython_extension(ipython):
    ipython.register_magics(NotifyMagics)
    print("Jupyter Watchdog extension loaded. Use %%notify to watch cells.")
