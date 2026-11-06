from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from justdownload import __version__
from justdownload.config import APP_NAME, default_output_dir, locate_binary
from justdownload.core.filename import safe_stem
from justdownload.core.job_manager import JobManager
from justdownload.media.pipeline import JobEvent, JobRequest
from justdownload.media.probe import MediaInfo, format_bytes, probe_media
from justdownload.media.remote import RemoteInspection, inspect_remote


BG = "#090D14"
PANEL = "#111925"
PANEL_2 = "#151F2D"
BORDER = "#263447"
TEXT = "#F2F6FC"
MUTED = "#93A2B7"
ACCENT = "#55D7E8"
ACCENT_DARK = "#1E6676"
GREEN = "#66D6A6"
RED = "#FF737A"
AMBER = "#E9B86D"


class JustDownloadApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} — Desktop Media Utility")
        self.root.geometry("1180x820")
        self.root.minsize(980, 720)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", "TkDefaultFont")
        self.events: queue.Queue[tuple] = queue.Queue()
        self.jobs = JobManager(lambda event: self.events.put(("job", event)))
        self.source_kind: str | None = None
        self.source_path: Path | None = None
        self.remote_info: RemoteInspection | None = None
        self.media_info: MediaInfo | None = None
        self.selected_profile = tk.StringVar(value="mp3")
        self.rights_confirmed = tk.BooleanVar(value=False)
        self.url_var = tk.StringVar()
        self.filename_var = tk.StringVar()
        self.output_dir_var = tk.StringVar(value=str(default_output_dir()))
        self.busy_inspecting = False
        self.job_active = False
        self.last_result: Path | None = None
        self._profile_buttons: dict[str, tk.Frame] = {}
        self._build_styles()
        self._build_ui()
        self._refresh_tool_status()
        self.root.after(120, self._drain_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.TEntry", fieldbackground="#0B121C", foreground=TEXT,
                        insertcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER,
                        darkcolor=BORDER, padding=12, relief="flat")
        style.configure("Dark.Horizontal.TProgressbar", troughcolor="#202C3A",
                        background=ACCENT, bordercolor="#202C3A", lightcolor=ACCENT,
                        darkcolor=ACCENT)
        style.configure("Dark.Vertical.TScrollbar", background=PANEL_2,
                        troughcolor=BG, bordercolor=BG, lightcolor=PANEL_2,
                        darkcolor=PANEL_2, arrowcolor=MUTED, relief="flat")
        style.map("Dark.Vertical.TScrollbar", background=[("active", "#304257")])
        style.configure("Dark.TCheckbutton", background=PANEL, foreground=MUTED,
                        indicatorcolor="#0B121C", focuscolor=PANEL)
        style.map("Dark.TCheckbutton", foreground=[("active", TEXT)], background=[("active", PANEL)])

    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self._header()
        scroll_area = tk.Frame(self.root, bg=BG)
        scroll_area.grid(row=1, column=0, sticky="nsew")
        scroll_area.grid_columnconfigure(0, weight=1)
        scroll_area.grid_rowconfigure(0, weight=1)
        self.body_canvas = tk.Canvas(scroll_area, bg=BG, highlightthickness=0, borderwidth=0)
        self.body_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.body_canvas.yview, style="Dark.Vertical.TScrollbar")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.body_canvas.configure(yscrollcommand=scrollbar.set)
        body = tk.Frame(self.body_canvas, bg=BG)
        self.body_window = self.body_canvas.create_window((38, 18), window=body, anchor="nw")
        body.grid_columnconfigure(0, weight=7, uniform="body")
        body.grid_columnconfigure(1, weight=3, uniform="body")
        body.grid_rowconfigure(0, weight=1)
        body.bind("<Configure>", lambda _event: self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all")))
        self.body_canvas.bind("<Configure>", lambda event: self.body_canvas.itemconfigure(self.body_window, width=max(760, event.width - 76)))
        self.root.bind_all("<MouseWheel>", lambda event: self.body_canvas.yview_scroll(int(-event.delta / 120), "units"))
        self.root.bind_all("<Button-4>", lambda _event: self.body_canvas.yview_scroll(-1, "units"))
        self.root.bind_all("<Button-5>", lambda _event: self.body_canvas.yview_scroll(1, "units"))
        self._main_column(body)
        self._side_column(body)
        self._footer()

    def _header(self):
        header = tk.Frame(self.root, bg="#0C121B", height=74, highlightthickness=1, highlightbackground="#1D2A39")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)
        mark = tk.Frame(header, bg=ACCENT_DARK, width=38, height=38)
        mark.grid(row=0, column=0, padx=(38, 12), pady=18)
        mark.grid_propagate(False)
        tk.Label(mark, text="JD", bg=ACCENT_DARK, fg="#E7FBFF", font=("Segoe UI", 11, "bold")).place(relx=.5, rely=.5, anchor="center")
        brand = tk.Frame(header, bg="#0C121B")
        brand.grid(row=0, column=1, sticky="w")
        tk.Label(brand, text="JustDownload", bg="#0C121B", fg=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(brand, text="DESKTOP MEDIA UTILITY", bg="#0C121B", fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(1, 0))
        right = tk.Frame(header, bg="#0C121B")
        right.grid(row=0, column=2, padx=38, sticky="e")
        dot = tk.Canvas(right, width=9, height=9, bg="#0C121B", highlightthickness=0)
        dot.pack(side="left", padx=(0, 8))
        dot.create_oval(1, 1, 8, 8, fill=GREEN, outline="")
        tk.Label(right, text="LOCAL PROCESSING", bg="#0C121B", fg="#B7C6D9", font=("Segoe UI", 8, "bold")).pack(side="left")

    def _main_column(self, parent):
        main = tk.Frame(parent, bg=BG)
        main.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        main.grid_columnconfigure(0, weight=1)
        tk.Label(main, text="Your media.\nYour formats.", bg=BG, fg=TEXT,
                 font=("Segoe UI", 29, "bold"), justify="left").grid(row=0, column=0, sticky="w", pady=(3, 5))
        tk.Label(main, text="Inspect a direct media link or convert a file already on your computer.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=(0, 17))
        self._source_card(main, 2)
        self._media_card(main, 3)
        self._progress_card(main, 4)

    def _card(self, parent, row: int, title: str | None = None, subtitle: str | None = None, pady=(0, 12)) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=pady)
        card.grid_columnconfigure(0, weight=1)
        if title:
            heading = tk.Frame(card, bg=PANEL)
            heading.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 5))
            tk.Label(heading, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
            if subtitle:
                tk.Label(heading, text=subtitle, bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))
        return card

    def _source_card(self, parent, row: int):
        card = self._card(parent, row, "START WITH A SOURCE", "Direct audio/video file links and local media are supported.")
        tabs = tk.Frame(card, bg=PANEL)
        tabs.grid(row=1, column=0, sticky="w", padx=18, pady=(8, 12))
        self.link_tab = self._pill_button(tabs, "Direct media link", lambda: self._set_source_mode("link"), active=True)
        self.link_tab.pack(side="left", padx=(0, 7))
        self.local_tab = self._pill_button(tabs, "Choose local file", self.choose_local, active=False)
        self.local_tab.pack(side="left")
        input_row = tk.Frame(card, bg=PANEL)
        input_row.grid(row=2, column=0, sticky="ew", padx=18)
        input_row.grid_columnconfigure(0, weight=1)
        self.url_entry = ttk.Entry(input_row, textvariable=self.url_var, style="Dark.TEntry")
        self.url_entry.grid(row=0, column=0, sticky="ew", ipady=5)
        self.url_entry.bind("<Return>", lambda _event: self.inspect_link())
        self.inspect_button = tk.Button(input_row, text="Inspect link  →", command=self.inspect_link,
                                        bg=ACCENT, fg="#07121A", activebackground="#88EAF4",
                                        activeforeground="#07121A", relief="flat", bd=0,
                                        font=("Segoe UI", 9, "bold"), padx=18, pady=12, cursor="hand2")
        self.inspect_button.grid(row=0, column=1, padx=(9, 0))
        rights = ttk.Checkbutton(card, text="I own this media or have permission to download and convert it.",
                                 variable=self.rights_confirmed, style="Dark.TCheckbutton")
        rights.grid(row=3, column=0, sticky="w", padx=16, pady=(11, 0))
        notice = tk.Label(card, text="Direct media files only — website pages, private content, DRM and login-protected sources are not processed.",
                          bg=PANEL, fg="#71849C", font=("Segoe UI", 8), wraplength=670, justify="left")
        notice.grid(row=4, column=0, sticky="w", padx=18, pady=(7, 15))
        self.source_status = tk.Label(card, text="No source selected", bg=PANEL, fg=MUTED, font=("Segoe UI", 8))
        self.source_status.grid(row=5, column=0, sticky="w", padx=18, pady=(0, 13))

    def _media_card(self, parent, row: int):
        card = self._card(parent, row, "MEDIA & OUTPUT", "Available output choices will appear after the source is inspected.")
        self.media_card = card
        self.media_placeholder = tk.Label(card, text="Paste a direct media link or choose a local file to begin.",
                                          bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self.media_placeholder.grid(row=1, column=0, sticky="w", padx=18, pady=(7, 16))
        self.media_details = tk.Frame(card, bg=PANEL)
        self.media_details.grid_columnconfigure(0, weight=1)
        self.media_title = tk.Label(self.media_details, text="", bg=PANEL, fg=TEXT, font=("Segoe UI", 11, "bold"), anchor="w")
        self.media_title.grid(row=0, column=0, sticky="ew", pady=(9, 3))
        self.media_summary = tk.Label(self.media_details, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.media_summary.grid(row=1, column=0, sticky="w")
        self.media_note = tk.Label(self.media_details, text="", bg=PANEL, fg="#73869D", font=("Segoe UI", 8), anchor="w", wraplength=690, justify="left")
        self.media_note.grid(row=2, column=0, sticky="w", pady=(5, 12))
        sep = tk.Frame(self.media_details, bg=BORDER, height=1)
        sep.grid(row=3, column=0, sticky="ew", pady=(0, 11))
        tk.Label(self.media_details, text="CHOOSE AN OUTPUT", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=4, column=0, sticky="w")
        self.profiles_frame = tk.Frame(self.media_details, bg=PANEL)
        self.profiles_frame.grid(row=5, column=0, sticky="ew", pady=(8, 10))
        self.profiles_frame.grid_columnconfigure((0, 1), weight=1, uniform="profiles")
        name_row = tk.Frame(self.media_details, bg=PANEL)
        name_row.grid(row=6, column=0, sticky="ew", pady=(2, 8))
        name_row.grid_columnconfigure(1, weight=1)
        tk.Label(name_row, text="File name", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=0, column=0, padx=(0, 10))
        self.filename_entry = ttk.Entry(name_row, textvariable=self.filename_var, style="Dark.TEntry")
        self.filename_entry.grid(row=0, column=1, sticky="ew", ipady=2)
        folder_row = tk.Frame(self.media_details, bg=PANEL)
        folder_row.grid(row=7, column=0, sticky="ew", pady=(0, 13))
        folder_row.grid_columnconfigure(1, weight=1)
        tk.Label(folder_row, text="Save to", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=0, column=0, padx=(0, 10))
        self.folder_label = tk.Label(folder_row, textvariable=self.output_dir_var, bg="#0B121C", fg="#B9C7D9", anchor="w", padx=10, pady=9, font=("Segoe UI", 8))
        self.folder_label.grid(row=0, column=1, sticky="ew")
        tk.Button(folder_row, text="Browse", command=self.choose_output_folder, bg=PANEL_2, fg=TEXT, activebackground="#26364A", relief="flat", bd=0, padx=12, pady=8, cursor="hand2").grid(row=0, column=2, padx=(8, 0))
        self.start_button = tk.Button(self.media_details, text="Process media  →", command=self.start_job,
                                      bg=ACCENT, fg="#07121A", activebackground="#88EAF4", relief="flat", bd=0,
                                      font=("Segoe UI", 10, "bold"), padx=18, pady=12, cursor="hand2")
        self.start_button.grid(row=8, column=0, sticky="ew", pady=(0, 15))
        self.media_details.grid(row=1, column=0, sticky="ew", padx=18)
        self.media_details.grid_remove()

    def _progress_card(self, parent, row: int):
        card = self._card(parent, row, "JOB STATUS", "Progress is reported from the actual download or FFmpeg process.", pady=(0, 0))
        self.progress_card = card
        self.progress_title = tk.Label(card, text="Waiting for a job", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w")
        self.progress_title.grid(row=1, column=0, sticky="ew", padx=18, pady=(9, 3))
        self.progress_message = tk.Label(card, text="No media is being processed.", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.progress_message.grid(row=2, column=0, sticky="ew", padx=18)
        self.progressbar = ttk.Progressbar(card, style="Dark.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.progressbar.grid(row=3, column=0, sticky="ew", padx=18, pady=(10, 5))
        metrics = tk.Frame(card, bg=PANEL)
        metrics.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))
        metrics.grid_columnconfigure(0, weight=1)
        self.progress_metrics = tk.Label(metrics, text="", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.progress_metrics.grid(row=0, column=0, sticky="w")
        actions = tk.Frame(metrics, bg=PANEL)
        actions.grid(row=0, column=1, sticky="e")
        self.cancel_button = tk.Button(actions, text="Cancel", command=self.cancel_job, bg=PANEL_2, fg=TEXT,
                                       activebackground="#26364A", relief="flat", bd=0, padx=11, pady=6, cursor="hand2", state="disabled")
        self.cancel_button.pack(side="left", padx=(0, 6))
        self.open_button = tk.Button(actions, text="Open file", command=self.open_result, bg=ACCENT_DARK, fg="#E8FAFC",
                                     activebackground="#2C8497", relief="flat", bd=0, padx=11, pady=6, cursor="hand2", state="disabled")
        self.open_button.pack(side="left")

    def _side_column(self, parent):
        side = tk.Frame(parent, bg=BG)
        side.grid(row=0, column=1, sticky="nsew")
        side.grid_columnconfigure(0, weight=1)
        card = tk.Frame(side, bg="#111925", highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=0, column=0, sticky="ew", pady=(6, 12))
        tk.Label(card, text="BUILT FOR YOUR DESKTOP", bg="#111925", fg=ACCENT, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=17, pady=(17, 7))
        tk.Label(card, text="Your files stay\non your computer.", bg="#111925", fg=TEXT, font=("Segoe UI", 18, "bold"), justify="left").pack(anchor="w", padx=17)
        tk.Label(card, text="Processing runs locally. Files are saved to the folder you choose; no account or cloud upload is required.",
                 bg="#111925", fg=MUTED, font=("Segoe UI", 9), wraplength=250, justify="left").pack(anchor="w", padx=17, pady=(9, 16))
        self._side_feature(side, 1, "01", "Inspect first", "See available source information before starting a job.")
        self._side_feature(side, 2, "02", "Convert for real", "FFmpeg performs the conversion. No renamed files or simulated progress.")
        self._side_feature(side, 3, "03", "Verify the result", "FFprobe checks the finished output before it is marked ready.")
        sources = tk.Frame(side, bg="#111925", highlightthickness=1, highlightbackground=BORDER)
        sources.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        tk.Label(sources, text="SOURCE SUPPORT", bg="#111925", fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(15, 8))
        self.tools_status = tk.Label(sources, text="Checking FFmpeg tools…", bg="#111925", fg=MUTED, font=("Segoe UI", 8), justify="left", wraplength=250)
        self.tools_status.pack(anchor="w", padx=16, pady=(0, 8))
        tk.Label(sources, text="SUPPORTED NOW\n• Direct audio/video file URLs\n• Local audio and video files\n\nNOT SUPPORTED\n• Website pages and streaming-platform extraction\n• DRM, private or login-protected media",
                 bg="#111925", fg=MUTED, font=("Segoe UI", 8), justify="left", wraplength=250).pack(anchor="w", padx=16, pady=(0, 15))

    def _side_feature(self, parent, row, number, title, body):
        line = tk.Frame(parent, bg=BG)
        line.grid(row=row, column=0, sticky="ew", pady=8)
        line.grid_columnconfigure(1, weight=1)
        n = tk.Label(line, text=number, bg="#172536", fg=ACCENT, font=("Segoe UI", 9, "bold"), width=4, pady=8)
        n.grid(row=0, column=0, sticky="n", padx=(0, 10))
        text = tk.Frame(line, bg=BG)
        text.grid(row=0, column=1, sticky="ew")
        tk.Label(text, text=title, bg=BG, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(text, text=body, bg=BG, fg=MUTED, font=("Segoe UI", 8), wraplength=230, justify="left").pack(anchor="w", pady=(3, 0))

    def _footer(self):
        footer = tk.Frame(self.root, bg="#0C121B", height=31)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        tk.Label(footer, text=f"JUSTDOWNLOAD  ·  VERSION {__version__}", bg="#0C121B", fg="#72839A", font=("Segoe UI", 8)).pack(side="left", padx=38, pady=7)
        tk.Label(footer, text="Use only media you are authorized to download.", bg="#0C121B", fg="#72839A", font=("Segoe UI", 8)).pack(side="right", padx=38, pady=7)

    def _pill_button(self, parent, text, command, active=False):
        return tk.Button(parent, text=text, command=command,
                         bg="#1B2A3B" if active else PANEL_2,
                         fg=ACCENT if active else MUTED,
                         activebackground="#26384C", activeforeground=TEXT,
                         relief="flat", bd=0, font=("Segoe UI", 8, "bold"), padx=12, pady=8, cursor="hand2")

    def _set_source_mode(self, mode: str):
        if mode == "local":
            self.local_tab.configure(bg="#1B2A3B", fg=ACCENT)
            self.link_tab.configure(bg=PANEL_2, fg=MUTED)
        else:
            self.link_tab.configure(bg="#1B2A3B", fg=ACCENT)
            self.local_tab.configure(bg=PANEL_2, fg=MUTED)
            self.url_entry.focus_set()

    def _refresh_tool_status(self):
        ffmpeg = locate_binary("ffmpeg")
        ffprobe = locate_binary("ffprobe")
        if ffmpeg and ffprobe:
            self.tools_status.configure(text="FFmpeg + FFprobe detected. Local conversion and output verification are available.", fg=GREEN)
        else:
            missing = " and ".join(name for name, path in (("FFmpeg", ffmpeg), ("FFprobe", ffprobe)) if not path)
            self.tools_status.configure(text=f"{missing} not detected. Install FFmpeg and add its bin folder to PATH to process media.", fg=AMBER)

    def _set_busy_inspecting(self, busy: bool):
        self.busy_inspecting = busy
        self.inspect_button.configure(state="disabled" if busy or self.job_active else "normal", text="Inspecting…" if busy else "Inspect link  →")
        self.url_entry.configure(state="disabled" if busy or self.job_active else "normal")

    def inspect_link(self):
        if self.busy_inspecting or self.job_active:
            return
        if not self.rights_confirmed.get():
            messagebox.showinfo("Permission required", "Confirm that you own this media or have permission to download and convert it.")
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Add a link", "Paste a direct audio or video file URL first.")
            self.url_entry.focus_set()
            return
        self._clear_source()
        self._set_busy_inspecting(True)
        self._set_source_mode("link")
        self.source_status.configure(text="Checking the URL and source headers…", fg=ACCENT)
        def task():
            try:
                result = inspect_remote(url)
                self.events.put(("remote_inspected", result))
            except Exception as exc:
                self.events.put(("inspect_error", str(exc)))
        threading.Thread(target=task, name="JustDownloadInspect", daemon=True).start()

    def choose_local(self):
        if self.busy_inspecting or self.job_active:
            return
        if not self.rights_confirmed.get():
            messagebox.showinfo("Permission required", "Confirm that you own this media or have permission to convert it.")
            return
        filename = filedialog.askopenfilename(
            title="Choose an audio or video file",
            filetypes=[("Media files", "*.mp4 *.m4v *.mov *.mkv *.webm *.avi *.mp3 *.m4a *.aac *.ogg *.opus *.wav *.flac *.aiff *.mpeg *.mpg *.ts"), ("All files", "*.*")],
        )
        if not filename:
            return
        self._clear_source()
        self._set_busy_inspecting(True)
        self._set_source_mode("local")
        self.source_status.configure(text=f"Inspecting {Path(filename).name}…", fg=ACCENT)
        def task():
            try:
                info = probe_media(Path(filename))
                self.events.put(("local_inspected", (Path(filename), info)))
            except Exception as exc:
                self.events.put(("inspect_error", str(exc)))
        threading.Thread(target=task, name="JustDownloadLocalInspect", daemon=True).start()

    def _clear_source(self):
        self.source_kind = None
        self.source_path = None
        self.remote_info = None
        self.media_info = None
        self.last_result = None
        self.media_details.grid_remove()
        self.media_placeholder.grid()
        self.open_button.configure(state="disabled")
        self.progress_title.configure(text="Waiting for a job")
        self.progress_message.configure(text="No media is being processed.")
        self.progressbar.configure(mode="determinate", value=0)
        self.progress_metrics.configure(text="")

    def _show_media(self, title: str, summary: str, note: str, profiles: list[str], source_kind: str):
        self.media_placeholder.grid_remove()
        self.media_details.grid()
        self.media_title.configure(text=title)
        self.media_summary.configure(text=summary)
        self.media_note.configure(text=note)
        self.filename_var.set(safe_stem(Path(title).stem))
        self._render_profiles(profiles)
        if source_kind == "remote":
            default_profile = "mp3" if self.remote_info and self.remote_info.media_kind == "audio" and "mp3" in profiles else "original"
        else:
            default_profile = "mp3" if self.media_info and self.media_info.has_audio and "mp3" in profiles else ("mp4" if "mp4" in profiles else profiles[0])
        self.selected_profile.set(default_profile)
        self._select_profile_card()
        self.start_button.configure(state="normal")

    def _render_profiles(self, profiles: list[str]):
        for child in self.profiles_frame.winfo_children():
            child.destroy()
        self._profile_buttons.clear()
        labels = {
            "original": ("Original file", "Keep the verified source format"),
            "mp3": ("MP3", "High quality · VBR"),
            "m4a": ("M4A / AAC", "192 kb/s audio"),
            "wav": ("WAV", "Uncompressed PCM"),
            "mp4": ("MP4", "H.264 video · AAC audio"),
        }
        for index, profile in enumerate(profiles):
            col = index % 2
            row = index // 2
            frame = tk.Frame(self.profiles_frame, bg="#0D1722", highlightthickness=1, highlightbackground=BORDER, cursor="hand2")
            frame.grid(row=row, column=col, sticky="ew", padx=(0, 7) if col == 0 else (7, 0), pady=(0, 7))
            frame.grid_columnconfigure(0, weight=1)
            title, detail = labels[profile]
            name = tk.Label(frame, text=title, bg="#0D1722", fg=TEXT, font=("Segoe UI", 9, "bold"), anchor="w")
            name.grid(row=0, column=0, sticky="w", padx=11, pady=(9, 2))
            desc = tk.Label(frame, text=detail, bg="#0D1722", fg=MUTED, font=("Segoe UI", 8), anchor="w")
            desc.grid(row=1, column=0, sticky="w", padx=11, pady=(0, 9))
            for widget in (frame, name, desc):
                widget.bind("<Button-1>", lambda _event, p=profile: self._choose_profile(p))
            self._profile_buttons[profile] = frame

    def _choose_profile(self, profile: str):
        self.selected_profile.set(profile)
        self._select_profile_card()

    def _select_profile_card(self):
        selected = self.selected_profile.get()
        for profile, frame in self._profile_buttons.items():
            frame.configure(highlightbackground=ACCENT if profile == selected else BORDER, bg="#142B39" if profile == selected else "#0D1722")
            for child in frame.winfo_children():
                child.configure(bg="#142B39" if profile == selected else "#0D1722")

    def _choose_output_profiles(self, has_video: bool, has_audio: bool) -> list[str]:
        profiles = ["original"]
        if has_audio:
            profiles += ["mp3", "m4a", "wav"]
        if has_video:
            profiles += ["mp4"]
        return profiles

    def choose_output_folder(self):
        current = self.output_dir_var.get()
        folder = filedialog.askdirectory(title="Choose output folder", initialdir=current if Path(current).is_dir() else str(Path.home()))
        if folder:
            self.output_dir_var.set(folder)

    def start_job(self):
        if self.job_active or self.busy_inspecting:
            return
        if not self.rights_confirmed.get():
            messagebox.showinfo("Permission required", "Confirm that you own this media or have permission to download and convert it.")
            return
        if not self.source_kind:
            messagebox.showwarning("No media inspected", "Inspect a direct media URL or choose a local file first.")
            return
        folder = Path(self.output_dir_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if not folder.is_dir():
                raise OSError("The output location is not a folder.")
        except OSError as exc:
            messagebox.showerror("Output folder unavailable", str(exc))
            return
        raw_name = self.filename_var.get().strip()
        name = safe_stem(Path(raw_name).stem if Path(raw_name).suffix else raw_name)
        if not name:
            messagebox.showwarning("Choose a file name", "Enter a name for the output file.")
            return
        request = JobRequest(
            source_kind=self.source_kind,
            source=str(self.source_path) if self.source_path else (self.remote_info.url if self.remote_info else ""),
            remote_inspection=self.remote_info,
            profile=self.selected_profile.get(),
            output_dir=folder,
            output_name=name,
        )
        try:
            self.jobs.submit(request)
        except RuntimeError as exc:
            messagebox.showwarning("Job already running", str(exc))
            return
        self.job_active = True
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.inspect_button.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.progress_title.configure(text="Queued")
        self.progress_message.configure(text="Preparing the media job…")
        self.progressbar.configure(mode="indeterminate")
        self.progressbar.start(12)
        self.progress_metrics.configure(text="This runs on your computer. You can cancel at any time.")
        self.open_button.configure(state="disabled")

    def cancel_job(self):
        self.jobs.cancel()
        self.cancel_button.configure(state="disabled")
        self.progress_message.configure(text="Cancellation requested…")

    def _drain_events(self):
        try:
            while True:
                item = self.events.get_nowait()
                kind, payload = item
                if kind == "remote_inspected":
                    self._set_busy_inspecting(False)
                    result: RemoteInspection = payload
                    self.remote_info = result
                    self.source_kind = "remote"
                    self.source_path = None
                    size = format_bytes(result.size_bytes) if result.size_bytes is not None else "Size not reported"
                    self._show_media(
                        result.filename,
                        f"{result.media_kind.title()} media  ·  {result.content_type}  ·  {size}",
                        "This link inspection used HTTP headers only. Duration, codec and stream availability will be verified after the source is downloaded for processing.",
                        self._choose_output_profiles(result.media_kind == "video", result.media_kind in {"audio", "video"}),
                        "remote",
                    )
                    self.source_status.configure(text=f"Direct media link inspected · {Path(result.final_url).name or result.final_url}", fg=GREEN)
                elif kind == "local_inspected":
                    self._set_busy_inspecting(False)
                    path, info = payload
                    self.source_kind = "local"
                    self.source_path = path
                    self.media_info = info
                    self._show_media(
                        path.name,
                        f"{info.summary}  ·  {format_bytes(info.size_bytes)}  ·  {info.format_name}",
                        f"Source streams verified with FFprobe. Format choices below are conversion outputs, not claims about the source formats.",
                        self._choose_output_profiles(info.has_video, info.has_audio),
                        "local",
                    )
                    self.source_status.configure(text=f"Local file inspected · {path}", fg=GREEN)
                elif kind == "inspect_error":
                    self._set_busy_inspecting(False)
                    self.source_status.configure(text="Inspection failed", fg=RED)
                    messagebox.showerror("Could not inspect media", payload)
                elif kind == "job":
                    self._handle_job_event(payload)
        except queue.Empty:
            pass
        self.root.after(120, self._drain_events)

    def _handle_job_event(self, event: JobEvent):
        self.progress_title.configure(text=event.stage)
        self.progress_message.configure(text=event.message)
        if event.percent is None:
            if str(self.progressbar.cget("mode")) != "indeterminate":
                self.progressbar.stop()
                self.progressbar.configure(mode="indeterminate")
                self.progressbar.start(12)
        else:
            self.progressbar.stop()
            self.progressbar.configure(mode="determinate", value=event.percent)
        metrics = []
        if event.downloaded_bytes is not None:
            metrics.append(format_bytes(event.downloaded_bytes))
        if event.total_bytes is not None:
            metrics.append(f"of {format_bytes(event.total_bytes)}")
        if event.speed_bytes_per_second is not None and event.speed_bytes_per_second > 0:
            metrics.append(f"{format_bytes(int(event.speed_bytes_per_second))}/s")
        if event.eta_seconds is not None and event.eta_seconds >= 0:
            metrics.append(f"~{event.eta_seconds}s left")
        self.progress_metrics.configure(text="  ·  ".join(metrics) if metrics else "")
        if event.state in {"ready", "failed", "cancelled"}:
            self.progressbar.stop()
            self.job_active = False
            self.cancel_button.configure(state="disabled")
            self.inspect_button.configure(state="normal")
            self.url_entry.configure(state="normal")
            self.start_button.configure(state="normal")
            if event.state == "ready":
                self.progressbar.configure(mode="determinate", value=100)
                self.last_result = event.result_path
                self.open_button.configure(state="normal")
                self.progress_title.configure(fg=GREEN)
                self.progress_metrics.configure(text=str(event.result_path) if event.result_path else "")
                messagebox.showinfo("Media ready", f"Your verified file is ready:\n\n{event.result_path}")
            elif event.state == "failed":
                self.progress_title.configure(fg=RED)
                self.progressbar.configure(mode="determinate", value=0)
                messagebox.showerror("Processing failed", event.error or event.message)
            else:
                self.progress_title.configure(fg=AMBER)
                self.progressbar.configure(mode="determinate", value=0)

    def open_result(self):
        if not self.last_result or not self.last_result.exists():
            return
        import os
        import subprocess
        import sys
        try:
            if sys.platform == "win32":
                os.startfile(self.last_result)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.last_result)])
            else:
                subprocess.Popen(["xdg-open", str(self.last_result)])
        except OSError as exc:
            messagebox.showerror("Could not open file", str(exc))

    def _on_close(self):
        if self.job_active and not messagebox.askyesno("Processing in progress", "A media job is still running. Cancel it and close JustDownload?"):
            return
        self.jobs.shutdown()
        self.root.destroy()


def main():
    root = tk.Tk()
    JustDownloadApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
