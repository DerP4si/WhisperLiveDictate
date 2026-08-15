import customtkinter as ctk
import tkinter as tk
from tkinter import Text

MODELS = ["distil-large-v3", "distil-medium.en", "large-v3", "medium", "small", "base"]
DEVICES = ["auto", "cuda", "cpu"]
COMPUTE_TYPES = ["int8", "float16", "float32"]
LANGUAGES = {
    "German": "de", "English": "en", "Dutch": "nl"
}

class DictationUI(ctk.CTk):
    def __init__(self, settings, on_toggle_record, on_hotkey_toggle, on_lang_change):
        super().__init__()

        # Initial compact window constraints
        self.title("WhisperLiveDictate")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        
        self.settings = settings
        self.on_lang_change = on_lang_change
        
        # State variables for expanding panels
        self.editor_visible = False
        self.settings_visible = False
        
        # --- Top Row ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        self.btn_settings = ctk.CTkButton(self.top_frame, text="⚙", width=40, height=40, command=self.toggle_settings)
        self.btn_settings.pack(side="left")
        
        self.btn_hotkey = ctk.CTkButton(self.top_frame, text="⌨", width=40, height=40, command=on_hotkey_toggle)
        self.btn_hotkey.pack(side="right")
        
        # --- Middle Row ---
        self.btn_mic = ctk.CTkButton(
            self, text="🎤", width=65, height=65, corner_radius=200, 
            font=("Segoe UI Emoji", 26), fg_color="#10B981", hover_color="#059669",
            command=on_toggle_record
        )
        self.btn_mic.pack(pady=2)
        
        self.status_label = ctk.CTkLabel(self, text="Initialisiere...", text_color="#D97706", font=("Segoe UI", 12))
        self.status_label.pack()
        
        # --- Bottom Row ---
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.btn_editor = ctk.CTkButton(self.bottom_frame, text="📝", width=35, command=self.toggle_editor)
        self.btn_editor.pack(side="left")
        
        langs = [
            "de German",
            "en English",
            "nl Dutch",
            "af Afrikaans",
            "sq Albanian",
            "am Amharic",
            "ar Arabic",
            "hy Armenian",
            "as Assamese",
            "az Azerbaijani",
            "ba Bashkir",
            "eu Basque",
            "be Belarusian",
            "bn Bengali",
            "bs Bosnian",
            "br Breton",
            "bg Bulgarian",
            "yue Cantonese",
            "ca Catalan",
            "zh Chinese",
            "hr Croatian",
            "cs Czech",
            "da Danish",
            "et Estonian",
            "fo Faroese",
            "fi Finnish",
            "fr French",
            "gl Galician",
            "ka Georgian",
            "el Greek",
            "gu Gujarati",
            "ht HaitianCreole",
            "ha Hausa",
            "haw Hawaiian",
            "he Hebrew",
            "hi Hindi",
            "hu Hungarian",
            "is Icelandic",
            "id Indonesian",
            "it Italian",
            "ja Japanese",
            "jw Javanese",
            "kn Kannada",
            "kk Kazakh",
            "km Khmer",
            "ko Korean",
            "lo Lao",
            "la Latin",
            "lv Latvian",
            "ln Lingala",
            "lt Lithuanian",
            "lb Luxembourgish",
            "mk Macedonian",
            "mg Malagasy",
            "ms Malay",
            "ml Malayalam",
            "mt Maltese",
            "mr Marathi",
            "mn Mongolian",
            "my Myanmar",
            "mi Maori",
            "ne Nepali",
            "no Norwegian",
            "nn Nynorsk",
            "oc Occitan",
            "ps Pashto",
            "fa Persian",
            "pl Polish",
            "pt Portuguese",
            "pa Punjabi",
            "ro Romanian",
            "ru Russian",
            "sa Sanskrit",
            "sr Serbian",
            "sn Shona",
            "sd Sindhi",
            "si Sinhala",
            "sk Slovak",
            "sl Slovenian",
            "so Somali",
            "es Spanish",
            "su Sundanese",
            "sw Swahili",
            "sv Swedish",
            "tl Tagalog",
            "tg Tajik",
            "ta Tamil",
            "tt Tatar",
            "te Telugu",
            "th Thai",
            "bo Tibetan",
            "tr Turkish",
            "tk Turkmen",
            "uk Ukrainian",
            "ur Urdu",
            "uz Uzbek",
            "vi Vietnamese",
            "cy Welsh",
            "yi Yiddish",
            "yo Yoruba"
            ]
        current_lang = self.settings.get("General", "language", fallback="de")
        start_val = next((l for l in langs if current_lang in l), langs[1])
        start_emoji = start_val.split(" ")[0]

        self.lang_var = ctk.StringVar(value=start_emoji)
        self.dropdown_lang = ctk.CTkOptionMenu(
            self.bottom_frame, values=langs, variable=self.lang_var, 
            width=60, command=self._lang_changed
        )
        self.dropdown_lang.pack(side="right")
        
        # --- Collapsible Editor Frame ---
        self.editor_frame = ctk.CTkFrame(self)
        self.editor_text = Text(
            self.editor_frame, wrap="word", height=6, bg="#1E1E1E", fg="white", 
            insertbackground="white", font=("Consolas", 10)
        )
        self.editor_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # --- Collapsible Settings Frame ---
        self.settings_frame = ctk.CTkScrollableFrame(self, height=280)
        self.build_settings_panel()
        
        self.update_hotkey_btn()
        self.update_window_geometry()

    def update_window_geometry(self):
        """Dynamically scales window layout based on expanded sub-panels."""
        width = 380 if self.settings_visible else 240
        height = 190
        
        if self.editor_visible:
            height += 150
        if self.settings_visible:
            height += 300
            
        self.geometry(f"{width}x{height}")

    def build_settings_panel(self):
        """Populates the embedded configuration panel."""
        parent = self.settings_frame
        
        # Current Value Retrieval
        model_val = self.settings.get("Model", "model_size", fallback="base")
        device_val = self.settings.get("Model", "device", fallback="auto")
        compute_val = self.settings.get("Model", "compute_type", fallback="int8")
        engine_val = self.settings.get("Injection", "engine", fallback="dotool")
        
        self.model_var = ctk.StringVar(value=model_val if model_val in MODELS else MODELS[0])
        self.device_var = ctk.StringVar(value=device_val if device_val in DEVICES else DEVICES[0])
        self.compute_var = ctk.StringVar(value=compute_val if compute_val in COMPUTE_TYPES else COMPUTE_TYPES[0])
        self.engine_var = ctk.StringVar(value=engine_val)
        
        self.custom_path_var = ctk.StringVar(value=self.settings.get("Model", "custom_model_path", fallback=""))
        self.hotkey_var = ctk.StringVar(value=self.settings.get("General", "hotkey", fallback="<super>+o"))
        self.rate_var = ctk.StringVar(value=self.settings.get("General", "update_rate_ms", fallback="250"))
        self.context_var = ctk.StringVar(value=self.settings.get("General", "context_window_seconds", fallback="5.0"))
        
        self.auto_punct_var = ctk.BooleanVar(value=self.settings.getboolean("General", "auto_punctuation", fallback=True))
        self.autocorrect_var = ctk.BooleanVar(value=self.settings.getboolean("General", "autocorrect", fallback=True))

        # UI Matrix setup
        grid_args = {"padx": 5, "pady": 4, "sticky": "w"}
        
        ctk.CTkLabel(parent, text="Model Size:").grid(row=0, column=0, **grid_args)
        ctk.CTkOptionMenu(parent, variable=self.model_var, values=MODELS).grid(row=0, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Device:").grid(row=1, column=0, **grid_args)
        ctk.CTkOptionMenu(parent, variable=self.device_var, values=DEVICES).grid(row=1, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Precision:").grid(row=2, column=0, **grid_args)
        ctk.CTkOptionMenu(parent, variable=self.compute_var, values=COMPUTE_TYPES).grid(row=2, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Engine:").grid(row=3, column=0, **grid_args)
        ctk.CTkOptionMenu(parent, variable=self.engine_var, values=["dotool", "ydotool", "pynput"]).grid(row=3, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Custom Path:").grid(row=4, column=0, **grid_args)
        ctk.CTkEntry(parent, textvariable=self.custom_path_var).grid(row=4, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Hotkey:").grid(row=5, column=0, **grid_args)
        ctk.CTkEntry(parent, textvariable=self.hotkey_var).grid(row=5, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Update (ms):").grid(row=6, column=0, **grid_args)
        ctk.CTkEntry(parent, textvariable=self.rate_var).grid(row=6, column=1, **grid_args)

        ctk.CTkLabel(parent, text="Context (s):").grid(row=7, column=0, **grid_args)
        ctk.CTkEntry(parent, textvariable=self.context_var).grid(row=7, column=1, **grid_args)

        ctk.CTkCheckBox(parent, text="Auto Punctuation", variable=self.auto_punct_var).grid(row=8, column=0, columnspan=2, pady=(10, 5), sticky="w")
        ctk.CTkCheckBox(parent, text="Dynamic Auto-Correct", variable=self.autocorrect_var).grid(row=9, column=0, columnspan=2, pady=5, sticky="w")

        save_btn = ctk.CTkButton(parent, text="Save Settings & Reload", command=self.save_settings)
        save_btn.grid(row=10, column=0, columnspan=2, pady=15, sticky="ew")

    def toggle_settings(self):
        self.settings_visible = not self.settings_visible
        if self.settings_visible:
            self.settings_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
            self.btn_settings.configure(fg_color=["#3B8ED0", "#1F6AA5"])
        else:
            self.settings_frame.pack_forget()
            self.btn_settings.configure(fg_color="transparent")
        
        self.update_window_geometry()

    def toggle_editor(self):
        self.editor_visible = not self.editor_visible
        if self.editor_visible:
            self.editor_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        else:
            self.editor_frame.pack_forget()
            
        self.update_window_geometry()

    def save_settings(self):
        self.settings.set("Model", "model_size", self.model_var.get())
        self.settings.set("Model", "device", self.device_var.get())
        self.settings.set("Model", "compute_type", self.compute_var.get())
        self.settings.set("Model", "custom_model_path", self.custom_path_var.get().strip())
        
        self.settings.set("Injection", "engine", self.engine_var.get())
        self.settings.set("General", "hotkey", self.hotkey_var.get().strip())
        self.settings.set("General", "update_rate_ms", self.rate_var.get().strip())
        self.settings.set("General", "context_window_seconds", self.context_var.get().strip())
        
        self.settings.set("General", "auto_punctuation", str(self.auto_punct_var.get()).lower())
        self.settings.set("General", "autocorrect", str(self.autocorrect_var.get()).lower())
        
        # Collapse panel and reload application state
        self.toggle_settings()
        
        if hasattr(self, 'master_app'):
            self.master_app.injector.reload_engine()
            self.master_app.restart_hotkey_listener()
            self.master_app.reload_model_thread()

    def _lang_changed(self, choice):
        parts = choice.split(" ")
        emoji = parts[0]
        lang_code = parts[1].lower()[:2]
        self.on_lang_change(lang_code)
        self.lang_var.set(emoji)

    def set_recording_state(self, is_recording):
        if is_recording:
            self.btn_mic.configure(fg_color="#EF4444", hover_color="#DC2626", text="⏹")
        else:
            self.btn_mic.configure(fg_color="#10B981", hover_color="#059669", text="🎤")

    def update_status(self, text, color):
        self.after(0, lambda: self.status_label.configure(text=text, text_color=color))
        
    def update_hotkey_btn(self):
        is_enabled = self.settings.getboolean("General", "hotkey_enabled", fallback=True)
        if is_enabled:
             self.btn_hotkey.configure(fg_color=["#3B8ED0", "#1F6AA5"], text="⌨")
        else:
             self.btn_hotkey.configure(fg_color="gray", text="⌨")