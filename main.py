import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime

import customtkinter as ctk
from plyer import notification

# customtinker
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def get_base_path():
    """Restituisce il percorso base della cartella (gestisce l'exe compilato con PyInstaller)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


LOG_FILE = os.path.join(get_base_path(), "outage_log.txt")
NODICON_FILE = os.path.join(get_base_path(), "nodicon.ico")


class NetworkCheckerApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        # Titolo della finestra di sistema
        self.title("Network Outage Detector (NOD) | BETA")
        self.geometry("620x700")
        self.resizable(False, False)

        if os.path.exists(NODICON_FILE):
            try:
                self.iconbitmap(NODICON_FILE)
            except Exception as e:
                print(f"Impossibile caricare l'icona: {e}")

        # Variabili di stato predefinite
        self.target_host = "www.google.com"
        self.interval = 10
        self.is_monitoring = False
        self.is_testing = False
        self.monitor_thread = None
        self.outage_start_time = None
        self.confirm_timer_id = None

        # Variabili per la gestione dell'Uptime
        self.start_time = None
        self.uptime_timer_id = None

        # --- HEADER / CONTROLS SECTION ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(pady=(10, 5), padx=20, fill="x")

        # Container a sinistra per Titolo + Sottotitolo
        self.title_container = ctk.CTkFrame(
            self.header_frame, fg_color="transparent"
        )
        self.title_container.pack(side="left", anchor="w")

        # Titolo dell'applicazione
        self.title_label = ctk.CTkLabel(
            self.title_container,
            text="Network Outage Detector",
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        self.title_label.pack(side="top", anchor="w")

        # Sottotitolo
        self.subtitle_label = ctk.CTkLabel(
            self.title_container,
            text="Build not final, please read README.txt\nMade by Aken",
            font=ctk.CTkFont(size=12),
            text_color="#A0A0A0",
            anchor="w",
            justify="left",
        )
        self.subtitle_label.pack(side="top", anchor="w", pady=(0, 0))

        # Container per i pulsanti a destra (GITHUB, TEST e START)
        self.btn_container = ctk.CTkFrame(
            self.header_frame, fg_color="transparent"
        )
        self.btn_container.pack(side="right", anchor="e")

        # Pulsante GITHUB (Blu)
        self.btn_github = ctk.CTkButton(
            self.btn_container,
            text="GitHub",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=90,
            height=32,
            fg_color="#1f538d",
            hover_color="#14375e",
            text_color="#FFFFFF",
            command=self.open_github,
        )
        self.btn_github.pack(side="left", padx=(0, 6), pady=0)

        # Pulsante TEST (Giallo)
        self.btn_test = ctk.CTkButton(
            self.btn_container,
            text="TEST",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=90,
            height=32,
            fg_color="#D9A700",
            hover_color="#B58B00",
            text_color="#000000",
            command=self.start_quick_test,
        )
        self.btn_test.pack(side="left", padx=(0, 6), pady=0)

        # Pulsante START / STOP (Verde)
        self.btn_toggle = ctk.CTkButton(
            self.btn_container,
            text="START",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=90,
            height=32,
            fg_color="#28a745",
            hover_color="#218838",
            command=self.toggle_monitoring,
        )
        self.btn_toggle.pack(side="left", pady=0)

        # --- CONFIGURATION FRAME (TARGET & INTERVAL) ---
        self.config_frame = ctk.CTkFrame(
            self, fg_color="#1A1A1A", corner_radius=8
        )
        self.config_frame.pack(pady=10, padx=20, fill="x")

        self.config_frame.grid_columnconfigure(1, weight=1)

        # Row 0: Target Host
        self.target_label = ctk.CTkLabel(
            self.config_frame,
            text="Target:",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.target_label.grid(
            row=0, column=0, padx=(12, 5), pady=8, sticky="w"
        )

        self.target_entry = ctk.CTkEntry(
            self.config_frame, font=ctk.CTkFont(size=12)
        )
        self.target_entry.insert(0, self.target_host)
        self.target_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        # Row 0: Interval (seconds)
        self.interval_label = ctk.CTkLabel(
            self.config_frame,
            text="Interval (seconds):",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.interval_label.grid(
            row=0, column=2, padx=(12, 5), pady=8, sticky="w"
        )

        self.interval_entry = ctk.CTkEntry(
            self.config_frame,
            width=55,
            font=ctk.CTkFont(size=12),
            justify="center",
        )
        self.interval_entry.insert(0, str(self.interval))
        self.interval_entry.grid(
            row=0, column=3, padx=(5, 12), pady=8, sticky="w"
        )

        # Row 1: Apply Button
        self.btn_apply = ctk.CTkButton(
            self.config_frame,
            text="Apply Settings",
            height=30,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.apply_settings,
        )
        self.btn_apply.grid(
            row=1, column=0, columnspan=4, padx=12, pady=(2, 6), sticky="ew"
        )

        # Row 2: Status Label centrata perfettamente
        self.confirm_label = ctk.CTkLabel(
            self.config_frame,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="center",
        )
        self.confirm_label.grid(
            row=2, column=0, columnspan=4, padx=12, pady=(0, 6), sticky="ew"
        )

        self.update_current_status_label()

        # --- LIVE OUTPUT SECTION ---
        self.feed_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.feed_header_frame.pack(pady=(5, 2), padx=20, fill="x")

        # Frame container per le due label affiancate a sinistra
        self.feed_label_container = ctk.CTkFrame(
            self.feed_header_frame, fg_color="transparent"
        )
        self.feed_label_container.pack(side="left")

        # Label 1: Live Output (SEMPRE VERDE)
        self.feed_title_label = ctk.CTkLabel(
            self.feed_label_container,
            text="📡 Live Output ",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#00FF66",
        )
        self.feed_title_label.pack(side="left")

        # Label 2: Uptime (SEMPRE GRIGIO)
        self.uptime_label = ctk.CTkLabel(
            self.feed_label_container,
            text="(Uptime: --:--:--)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#A0A0A0",
        )
        self.uptime_label.pack(side="left")

        self.clear_feed_btn = ctk.CTkButton(
            self.feed_header_frame,
            text="Clear",
            width=50,
            height=20,
            fg_color="transparent",
            border_width=1,
            text_color="gray",
            command=self.clear_feed,
        )
        self.clear_feed_btn.pack(side="right")

        self.feed_textbox = ctk.CTkTextbox(
            self,
            fg_color="#0F0F0F",
            text_color="#00FF66",
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
            activate_scrollbars=False,
        )
        self.feed_textbox.pack(pady=(0, 10), padx=20, fill="both", expand=True)

        # --- OUTAGE LOGS SECTION ---
        self.outage_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.outage_header_frame.pack(pady=(5, 2), padx=20, fill="x")

        self.outage_label = ctk.CTkLabel(
            self.outage_header_frame,
            text="⚠ Outage Logs",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FF5555",
        )
        self.outage_label.pack(side="left")

        self.clear_outage_btn = ctk.CTkButton(
            self.outage_header_frame,
            text="Clear",
            width=50,
            height=20,
            fg_color="transparent",
            border_width=1,
            text_color="gray",
            command=self.clear_outage_logs,
        )
        self.clear_outage_btn.pack(side="right")

        self.outage_textbox = ctk.CTkTextbox(
            self,
            height=90,
            fg_color="#180C0C",
            text_color="#FF6B6B",
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
        )
        self.outage_textbox.pack(pady=(0, 15), padx=20, fill="x")

        self.load_saved_outages()

    def open_github(self):
        """Apre il profilo GitHub nel browser predefinito."""
        webbrowser.open_new_tab("https://github.com/Ak3nyke")

    def send_windows_notification(self, title, message):
        """Invia una notifica popup nativa di Windows."""

        def _notify():
            try:
                nodicon_path = (
                    NODICON_FILE if os.path.exists(NODICON_FILE) else None
                )
                notification.notify(
                    title=title,
                    message=message,
                    app_name="Network Outage Detector",
                    app_icon=nodicon_path,
                    timeout=5,
                )
            except Exception as e:
                print(f"Errore invio notifica: {e}")

        threading.Thread(target=_notify, daemon=True).start()

    def update_uptime_label(self):
        if self.start_time is not None and (
            self.is_monitoring or self.is_testing
        ):
            elapsed_seconds = int(time.time() - self.start_time)
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.uptime_label.configure(
                text=f"(Uptime: {uptime_str})"
            )

            # Aggiorna ogni secondo (1000ms)
            self.uptime_timer_id = self.after(1000, self.update_uptime_label)
        else:
            self.uptime_label.configure(
                text="(Uptime: --:--:--)"
            )

    def update_current_status_label(self):
        self.confirm_label.configure(
            text=f"CURRENT SETTINGS = Target: {self.target_host} | Interval: {self.interval}s",
            text_color="#A0A0A0",
        )

    def apply_settings(self):
        new_target = self.target_entry.get().strip()
        new_interval_str = self.interval_entry.get().strip()

        if new_target:
            self.target_host = new_target

        if new_interval_str.isdigit() and int(new_interval_str) > 0:
            self.interval = int(new_interval_str)

        if self.confirm_timer_id is not None:
            self.after_cancel(self.confirm_timer_id)

        self.confirm_label.configure(
            text="✓ Settings Applied!", text_color="#28a745"
        )
        self.confirm_timer_id = self.after(
            3000, self.update_current_status_label
        )

    def ping_server(self):
        param = "-n" if sys.platform.startswith("win") else "-c"
        timeout_param = "-w" if sys.platform.startswith("win") else "-W"

        # Timeout di 1000ms (1 sec) per evitare blocchi prolungati su host irraggiungibili
        command = ["ping", param, "1", timeout_param, "1000", self.target_host]

        creation_flags = 0
        if sys.platform.startswith("win"):
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            res = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creation_flags,
            )

            if res.returncode == 0:
                match = re.search(
                    r"(?:time|tempo)[=<]\s*(\d+)\s*ms", res.stdout, re.IGNORECASE
                )
                if match:
                    return True, match.group(1)

                if "1ms" in res.stdout.lower():
                    return True, "<1"

                return True, "1"

            return False, None
        except Exception:
            return False, None

    def start_quick_test(self):
        if self.is_testing:
            return

        self.is_testing = True
        self.btn_test.configure(state="disabled", text="TESTING...")

        if not self.is_monitoring:
            self.start_time = time.time()
            self.update_uptime_label()

        def test_runner():
            self.append_text(
                self.feed_textbox,
                f"=== START QUICK TEST (20 PINGS) -> {self.target_host} ===",
                auto_clear_overflow=True,
            )
            for i in range(1, 21):
                time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                success, ms = self.ping_server()
                if success:
                    msg = f"[{time_str}] #{i} Reply from {self.target_host}: Success (time={ms}ms)"
                else:
                    msg = f"[{time_str}] #{i} Request timed out."
                self.append_text(
                    self.feed_textbox, msg, auto_clear_overflow=True
                )
                time.sleep(0.01)

            self.append_text(
                self.feed_textbox,
                "=== TEST COMPLETED ===",
                auto_clear_overflow=True,
            )
            self.btn_test.configure(state="normal", text="TEST")
            self.is_testing = False

            if not self.is_monitoring:
                self.start_time = None
                if self.uptime_timer_id:
                    self.after_cancel(self.uptime_timer_id)
                self.update_uptime_label()

        threading.Thread(target=test_runner, daemon=True).start()

    def record_outage(self, outage_msg):
        date_str = datetime.now().strftime("%Y-%m-%d")
        full_log_entry = f"[{date_str}] {outage_msg}"

        # Ora viene aggiunta la stringa completa con la data direttamente nell'interfaccia grafica
        self.append_text(self.outage_textbox, full_log_entry)

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(full_log_entry + "\n")
        except Exception as e:
            print(f"Errore salvataggio file: {e}")

    def load_saved_outages(self):
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    logs = f.readlines()
                    for log in logs:
                        log_clean = log.strip()
                        if log_clean:
                            self.append_text(self.outage_textbox, log_clean)
            except Exception as e:
                print(f"Errore lettura file log: {e}")

    def monitor_loop(self):
        while self.is_monitoring:
            time_str = datetime.now().strftime("%H:%M:%S")
            success, ms = self.ping_server()

            if success:
                feed_msg = f"[{time_str}] Reply from {self.target_host}: Success (time={ms}ms)"
                self.append_text(
                    self.feed_textbox, feed_msg, auto_clear_overflow=True
                )

                if self.outage_start_time is not None:
                    outage_msg = f"Outage from {self.outage_start_time} to {time_str} (Target: {self.target_host})"
                    self.record_outage(outage_msg)

                    self.send_windows_notification(
                        title="Connessione Ripristinata!",
                        message=f"La rete è di nuovo attiva.\nInterruzione dalle {self.outage_start_time} alle {time_str}.",
                    )

                    self.outage_start_time = None
            else:
                feed_msg = f"[{time_str}] Request timed out."
                self.append_text(
                    self.feed_textbox, feed_msg, auto_clear_overflow=True
                )

                if self.outage_start_time is None:
                    self.outage_start_time = time_str

                    self.send_windows_notification(
                        title="⚠ Connessione Assente!",
                        message=f"Rilevata disconnessione alle {self.outage_start_time}.\nTarget: {self.target_host}",
                    )

            time.sleep(self.interval)

    def toggle_monitoring(self):
        if not self.is_monitoring:
            self.is_monitoring = True
            self.btn_toggle.configure(
                text="STOP", fg_color="#dc3545", hover_color="#c82333"
            )

            self.start_time = time.time()
            self.update_uptime_label()

            self.monitor_thread = threading.Thread(
                target=self.monitor_loop, daemon=True
            )
            self.monitor_thread.start()
        else:
            self.is_monitoring = False
            self.btn_toggle.configure(
                text="START", fg_color="#28a745", hover_color="#218838"
            )

            self.start_time = None
            if self.uptime_timer_id:
                self.after_cancel(self.uptime_timer_id)
            self.update_uptime_label()

            if self.outage_start_time is not None:
                stop_time = datetime.now().strftime("%H:%M:%S")
                outage_msg = f"Outage from {self.outage_start_time} to {stop_time} (Stopped - Target: {self.target_host})"
                self.record_outage(outage_msg)
                self.outage_start_time = None

    def append_text(self, textbox, text, auto_clear_overflow=False):
        # Assicura che l'aggiornamento dell'interfaccia grafica avvenga nel thread principale
        def _update():
            textbox.configure(state="normal")
            textbox.insert("end", text + "\n")
            textbox.see("end")

            if auto_clear_overflow:
                while textbox.yview()[0] > 0.0:
                    textbox.delete("1.0", "2.0")
                    textbox.see("end")

            textbox.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.after(0, _update)

    def clear_feed(self):
        self.feed_textbox.configure(state="normal")
        self.feed_textbox.delete("1.0", "end")
        self.feed_textbox.configure(state="disabled")

    def clear_outage_logs(self):
        self.outage_textbox.configure(state="normal")
        self.outage_textbox.delete("1.0", "end")
        self.outage_textbox.configure(state="disabled")

        if os.path.exists(LOG_FILE):
            try:
                open(LOG_FILE, "w").close()
            except Exception as e:
                print(f"Errore svuotamento file: {e}")


if __name__ == "__main__":
    app = NetworkCheckerApp()
    app.mainloop()