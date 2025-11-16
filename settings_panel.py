import tkinter as tk
from tkinter import ttk, messagebox
import settings_manager

class SettingsPanel(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("AI Provider Settings")
        
        # --- CENTERING LOGIC START ---
        window_width, window_height = 500, 600
        
        # Get parent window position and size
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        # Calculate position to center the settings window
        pos_x = parent_x + (parent_width // 2) - (window_width // 2)
        pos_y = parent_y + (parent_height // 2) - (window_height // 2)
        
        # Apply geometry with coordinates
        self.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
        # --- CENTERING LOGIC END ---

        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # --- THEME MATCHING ---
        self.BG_DARK = "#1e1e1e"
        self.BG_DARKER = "#121212"
        self.FG_LIGHT = "#e0e0e0"
        self.ACCENT_GREEN = "#00C853"
        self.ACCENT_DARK = "#005020"
        self.configure(bg=self.BG_DARK)
        # ----------------------

        self.settings = settings_manager.load_settings()
        self.api_key_vars = {}
        self.model_vars = {}

        self._build_ui()
        self._load_current_values()

    def _build_ui(self):
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header = ttk.Label(main_frame, text="AI Configuration", font=("Helvetica", 16, "bold"), foreground=self.ACCENT_GREEN)
        header.pack(pady=(0, 20), anchor="w")

        # 1. Active Provider Selection
        provider_frame = ttk.LabelFrame(main_frame, text="Active Provider")
        provider_frame.pack(fill=tk.X, pady=(0, 20))

        self.provider_var = tk.StringVar()
        providers = ["Mistral", "OpenAI", "Gemini", "Claude"]
        self.provider_combo = ttk.Combobox(provider_frame, textvariable=self.provider_var, values=providers, state="readonly", font=("Helvetica", 11))
        self.provider_combo.pack(fill=tk.X, padx=10, pady=15)

        # 2. API Keys Section
        keys_frame = ttk.LabelFrame(main_frame, text="API Keys & Models")
        keys_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Scrollable canvas for keys if it gets too tall (future proofing)
        canvas = tk.Canvas(keys_frame, bg=self.BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(keys_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Generate fields for each provider
        for provider in providers:
            p_frame = ttk.Frame(scrollable_frame)
            p_frame.pack(fill=tk.X, pady=10)

            ttk.Label(p_frame, text=f"{provider} API Key:", font=("Helvetica", 10, "bold")).pack(anchor="w")
            
            key_var = tk.StringVar()
            # Using show="*" to hide exact keys from casual view
            key_entry = ttk.Entry(p_frame, textvariable=key_var, show="•", font=("Courier", 12))
            key_entry.pack(fill=tk.X, pady=(2, 8))
            
            key_entry.bind("<Return>", self._save_and_close)
            
            self.api_key_vars[provider] = key_var

            # Optional: Model selection (hidden by default to keep it simple, 
            # but data structures exist if you want to enable them later)
            # model_var = tk.StringVar()
            # ttk.Entry(p_frame, textvariable=model_var).pack(fill=tk.X)
            # self.model_vars[provider] = model_var

        # 3. Action Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, anchor="e")

        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        save_btn = ttk.Button(btn_frame, text="Save Settings ✅", command=self._save_and_close, style="TButton")
        save_btn.pack(side=tk.RIGHT)

    def _load_current_values(self):
        """Populates widgets with data from settings.json"""
        self.provider_var.set(self.settings.get("active_provider", "Mistral"))
        
        current_keys = self.settings.get("api_keys", {})
        for provider, var in self.api_key_vars.items():
            var.set(current_keys.get(provider, ""))

    def _save_and_close(self, event=None):
        """Gathers data from widgets and saves to JSON"""
        new_settings = self.settings.copy()
        new_settings["active_provider"] = self.provider_var.get()
        
        for provider, var in self.api_key_vars.items():
            # --- NEW: SANITIZER LOGIC ---
            # Get the raw text from the box
            raw_key = var.get().strip()
            
            # 1. Remove "API_KEY =" if it somehow got in there
            if "API_KEY =" in raw_key:
                raw_key = raw_key.replace("API_KEY =", "").strip()
            
            # 2. Remove any lingering quotes (double or single) from start/end
            raw_key = raw_key.strip('"').strip("'")
            # ----------------------------

            new_settings["api_keys"][provider] = raw_key

        if settings_manager.save_settings(new_settings):
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to save settings file.")
