"""
Linux Commander - Update Manager
Handles hash-based update checking using GitHub API as source of truth.
"""

import json
import hashlib
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
import threading
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# --- Constants ---
GITHUB_API_BASE = "https://api.github.com/repos/crenta/Linux-Commander/contents/commands"
REQUEST_TIMEOUT = 10  # seconds

class UpdateManager:
    """
    Manages command file updates using GitHub API for hash-based version control.
    
    Features:
    - Uses GitHub API SHA hashes (no separate manifest needed!)
    - Selective updates (user chooses what to update)
    - Automatic rollback on failure
    - Progress tracking and detailed logging
    - Handles both .exe and development environments
    """
    
    def __init__(self, parent, commands_dir, theme_config, on_update_complete=None):
        """
        Initialize the Update Manager.
        
        Args:
            parent: Parent Tkinter window
            commands_dir: Path to writable commands directory
            theme_config: Dict with theme colors (BG_DARK, ACCENT_GREEN, etc.)
            on_update_complete: Callback function to reload commands after update
        """
        self.parent = parent
        self.commands_dir = Path(commands_dir)
        self.theme = theme_config
        self.on_update_complete = on_update_complete
        
        # Ensure commands directory exists
        self.commands_dir.mkdir(parents=True, exist_ok=True)
        
        # Local hash tracking (for comparison)
        self.local_hashes_path = self.commands_dir / ".local_hashes.json"
        self.local_hashes = self._load_local_hashes()
        
        # Remote data (populated after check)
        self.remote_files = {}  # filename -> {sha, size, download_url}
        self.available_updates = {}
        
        # UI state
        self.window = None
        self.update_checkboxes = {}
        self.is_checking = False
        
    # ========================================================================
    # HASH CALCULATION
    # ========================================================================
    
    def _calculate_git_sha1(self, filepath):
        """
        Calculate Git-style SHA-1 hash (matching GitHub's 'sha' field).
        
        Git uses: sha1("blob " + filesize + "\0" + content)
        
        Args:
            filepath: Path to file
            
        Returns:
            Hex string of Git SHA-1 hash, or None if file doesn't exist
        """
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # Git prepends "blob <size>\0" before hashing
            git_blob = f"blob {len(content)}\0".encode() + content
            return hashlib.sha1(git_blob).hexdigest()
            
        except Exception as e:
            print(f"Hash calculation error for {filepath}: {e}")
            return None
    
    # ========================================================================
    # LOCAL HASH TRACKING
    # ========================================================================
    
    def _load_local_hashes(self):
        """
        Load locally stored hashes for installed files.
        
        Returns:
            Dict: {filename: sha1_hash}
        """
        if self.local_hashes_path.exists():
            try:
                with open(self.local_hashes_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading local hashes: {e}")
        
        # Generate fresh hashes from existing files
        return self._generate_local_hashes()
    
    def _generate_local_hashes(self):
        """
        Generate hash dictionary from currently installed command files.
        
        Returns:
            Dict: {filename: sha1_hash}
        """
        hashes = {}
        
        # Hash all existing JSON files
        for json_file in self.commands_dir.glob("*.json"):
            if json_file.name.startswith("."):  # Skip hidden files
                continue
            
            file_hash = self._calculate_git_sha1(json_file)
            if file_hash:
                hashes[json_file.name] = file_hash
        
        return hashes
    
    def _save_local_hashes(self):
        """Save local hash tracking to disk."""
        try:
            with open(self.local_hashes_path, 'w', encoding='utf-8') as f:
                json.dump(self.local_hashes, indent=2, fp=f)
            return True
        except Exception as e:
            print(f"Error saving local hashes: {e}")
            return False
    
    # ========================================================================
    # GITHUB API & UPDATE CHECK
    # ========================================================================
    
    def check_for_updates(self):
        """
        Check GitHub API for available updates.
        
        Returns:
            Tuple: (success: bool, message: str, updates_available: int)
        """
        if not REQUESTS_AVAILABLE:
            return False, "requests library not installed", 0
        
        try:
            # Fetch file list from GitHub API
            response = requests.get(GITHUB_API_BASE, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            github_files = response.json()
            
            # Parse GitHub response
            self.remote_files = {}
            for item in github_files:
                if item.get('type') == 'file' and item.get('name', '').endswith('.json'):
                    self.remote_files[item['name']] = {
                        'sha': item['sha'],
                        'size': item['size'],
                        'download_url': item['download_url']
                    }
            
            # Compare with local hashes
            self.available_updates = {}
            
            for filename, remote_info in self.remote_files.items():
                remote_sha = remote_info['sha']
                local_sha = self.local_hashes.get(filename)
                
                if local_sha is None:
                    # New file
                    self.available_updates[filename] = {
                        "status": "new",
                        "remote_sha": remote_sha,
                        "local_sha": None,
                        "size": remote_info['size'],
                        "download_url": remote_info['download_url']
                    }
                elif local_sha != remote_sha:
                    # Updated file
                    self.available_updates[filename] = {
                        "status": "updated",
                        "remote_sha": remote_sha,
                        "local_sha": local_sha,
                        "size": remote_info['size'],
                        "download_url": remote_info['download_url']
                    }
            
            # Check for obsolete local files (deleted from repo)
            for filename in self.local_hashes:
                if filename not in self.remote_files:
                    self.available_updates[filename] = {
                        "status": "obsolete",
                        "remote_sha": None,
                        "local_sha": self.local_hashes[filename],
                        "size": 0,
                        "download_url": None
                    }
            
            # Success message
            update_count = len(self.available_updates)
            if update_count == 0:
                message = f"✅ You're up to date! ({len(self.local_hashes)} files)"
            else:
                new_count = sum(1 for u in self.available_updates.values() if u['status'] == 'new')
                updated_count = sum(1 for u in self.available_updates.values() if u['status'] == 'updated')
                obsolete_count = sum(1 for u in self.available_updates.values() if u['status'] == 'obsolete')
                
                parts = []
                if new_count: parts.append(f"{new_count} new")
                if updated_count: parts.append(f"{updated_count} updated")
                if obsolete_count: parts.append(f"{obsolete_count} obsolete")
                
                message = f"🔄 Updates available: {', '.join(parts)}"
            
            return True, message, update_count
            
        except requests.exceptions.Timeout:
            return False, "Connection timeout - check your internet", 0
        except requests.exceptions.ConnectionError:
            return False, "No internet connection", 0
        except requests.exceptions.HTTPError as e:
            return False, f"GitHub API error: {e.response.status_code}", 0
        except Exception as e:
            return False, f"Unexpected error: {str(e)}", 0
    
    # ========================================================================
    # FILE DOWNLOAD & UPDATE
    # ========================================================================
    
    def download_file(self, filename, download_url):
        """
        Download a single command file from GitHub.
        
        Args:
            filename: Name of the JSON file to download
            download_url: Direct download URL from GitHub API
            
        Returns:
            Tuple: (success: bool, content: bytes or None, error_message: str or None)
        """
        try:
            response = requests.get(download_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return True, response.content, None
            
        except Exception as e:
            return False, None, str(e)
    
    def apply_updates(self, selected_files, progress_callback=None):
        """
        Apply selected updates with rollback capability.
        
        Args:
            selected_files: List of filenames to update
            progress_callback: Optional function(current, total, status_msg)
            
        Returns:
            Tuple: (success: bool, message: str, updated_count: int)
        """
        if not selected_files:
            return False, "No files selected", 0
        
        # Backup system for rollback
        backups = {}
        updated_files = []
        total = len(selected_files)
        
        try:
            for idx, filename in enumerate(selected_files):
                update_info = self.available_updates[filename]
                status = update_info['status']
                
                if progress_callback:
                    action = "Removing" if status == "obsolete" else "Downloading"
                    progress_callback(idx + 1, total, f"{action} {filename}...")
                
                file_path = self.commands_dir / filename
                
                # Handle obsolete files (deleted from repo)
                if status == "obsolete":
                    if file_path.exists():
                        # Backup before deletion
                        with open(file_path, 'rb') as f:
                            backups[filename] = f.read()
                        file_path.unlink()
                    
                    # Remove from tracking
                    if filename in self.local_hashes:
                        del self.local_hashes[filename]
                    
                    updated_files.append(filename)
                    continue
                
                # Handle new/updated files
                # Create backup of existing file
                if file_path.exists():
                    with open(file_path, 'rb') as f:
                        backups[filename] = f.read()
                
                # Download new version
                download_url = update_info['download_url']
                success, content, error = self.download_file(filename, download_url)
                if not success:
                    raise Exception(f"Failed to download {filename}: {error}")
                
                # Verify hash matches GitHub
                downloaded_sha = hashlib.sha1(
                    f"blob {len(content)}\0".encode() + content
                ).hexdigest()
                expected_sha = update_info["remote_sha"]
                
                if downloaded_sha != expected_sha:
                    raise Exception(f"Hash mismatch for {filename} - file may be corrupted")
                
                # Write file
                with open(file_path, 'wb') as f:
                    f.write(content)
                
                # Verify JSON is valid
                with open(file_path, 'r', encoding='utf-8') as f:
                    json.load(f)  # Will raise JSONDecodeError if invalid
                
                updated_files.append(filename)
                
                # Update local hash tracking
                self.local_hashes[filename] = downloaded_sha
            
            # Save updated hash tracking
            self._save_local_hashes()
            
            return True, f"✅ Successfully updated {len(updated_files)} file(s)", len(updated_files)
            
        except Exception as e:
            # ROLLBACK: Restore all backed up files
            if progress_callback:
                progress_callback(0, total, "❌ Error - Rolling back changes...")
            
            for filename, backup_content in backups.items():
                try:
                    with open(self.commands_dir / filename, 'wb') as f:
                        f.write(backup_content)
                except Exception as restore_error:
                    print(f"Critical: Could not restore {filename}: {restore_error}")
            
            return False, f"❌ Update failed: {str(e)}\nAll changes rolled back.", 0
    
    # ========================================================================
    # UI - UPDATE WINDOW
    # ========================================================================
    
    def open_update_window(self):
        """Open the update manager UI window."""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        
        # Calculate window position (centered on parent)
        self.parent.update_idletasks()
        px, py = self.parent.winfo_x(), self.parent.winfo_y()
        pw, ph = self.parent.winfo_width(), self.parent.winfo_height()
        ww, wh = 700, 600
        
        self.window = tk.Toplevel(self.parent)
        self.window.title("Update Manager - Linux Commander")
        self.window.geometry(f"{ww}x{wh}+{px + (pw//2 - ww//2)}+{py + (ph//2 - wh//2)}")
        self.window.transient(self.parent)
        self.window.configure(bg=self.theme["BG_DARK"])
        
        # Header
        header_frame = ttk.Frame(self.window)
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_label = ttk.Label(header_frame, text="Command File Updates", 
                                style="Title.TLabel")
        title_label.pack(anchor="w")
        
        self.status_label = ttk.Label(header_frame, text="Ready to check for updates", 
                                      style="Description.TLabel")
        self.status_label.pack(anchor="w", pady=(5, 0))
        
        # File count info
        version_frame = ttk.Frame(self.window)
        version_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        file_count = len(self.local_hashes)
        self.version_label = ttk.Label(version_frame, 
                                       text=f"Installed Files: {file_count}",
                                       style="Description.TLabel")
        self.version_label.pack(anchor="w")
        
        ttk.Separator(self.window, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)
        
        # Update list (scrollable)
        list_frame = ttk.LabelFrame(self.window, text="Available Updates")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        # Use Canvas for scrolling
        self.list_canvas = tk.Canvas(list_frame, bg=self.theme["BG_DARK"], 
                                     highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", 
                                  command=self.list_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.list_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))
        )
        
        self.list_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initial placeholder
        self.placeholder_label = ttk.Label(self.scrollable_frame, 
                                          text="Click 'Check for Updates' to begin",
                                          style="Description.TLabel")
        self.placeholder_label.pack(pady=20)
        
        # Progress bar (hidden initially)
        self.progress_frame = ttk.Frame(self.window)
        self.progress_label = ttk.Label(self.progress_frame, text="", 
                                        style="Description.TLabel")
        self.progress_label.pack(anchor="w")
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        self.check_btn = ttk.Button(button_frame, text="Check for Updates", 
                                    command=self._threaded_check)
        self.check_btn.pack(side=tk.LEFT)
        
        self.update_btn = ttk.Button(button_frame, text="Install Selected", 
                                     command=self._threaded_apply_updates, 
                                     state=tk.DISABLED,
                                     style="DisabledRed.TButton")
        self.update_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        self.select_all_btn = ttk.Button(button_frame, text="Select All", 
                                         command=self._select_all_updates,
                                         state=tk.DISABLED,
                                         style="DisabledRed.TButton")
        self.select_all_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        close_btn = ttk.Button(button_frame, text="Close", 
                              command=self.window.destroy)
        close_btn.pack(side=tk.RIGHT)
    
    # ========================================================================
    # UI - EVENT HANDLERS
    # ========================================================================
    
    def _threaded_check(self):
        """Check for updates in background thread to prevent UI freeze."""
        if self.is_checking:
            return
        
        self.is_checking = True
        self.check_btn.config(state=tk.DISABLED, text="Checking...")
        self.status_label.config(text="🔄 Checking GitHub for updates...")
        
        def check_task():
            success, message, count = self.check_for_updates()
            
            # Update UI in main thread
            self.window.after(0, lambda: self._handle_check_result(success, message, count))
        
        thread = threading.Thread(target=check_task, daemon=True)
        thread.start()
    
    def _handle_check_result(self, success, message, update_count):
        """Handle check results in main UI thread."""
        self.is_checking = False
        self.check_btn.config(state=tk.NORMAL, text="Check for Updates")
        self.status_label.config(text=message)
        
        if success:
            remote_count = len(self.remote_files)
            local_count = len(self.local_hashes)
            self.version_label.config(
                text=f"Installed: {local_count} files | Available: {remote_count} files"
            )
        
        if success and update_count > 0:
            self._populate_update_list()
            self.update_btn.config(state=tk.NORMAL, style="TButton")
            self.select_all_btn.config(state=tk.NORMAL, style="TButton")
        elif success:
            # No updates available - ensure buttons stay red/disabled
            self.update_btn.config(state=tk.DISABLED, style="DisabledRed.TButton")
            self.select_all_btn.config(state=tk.DISABLED, style="DisabledRed.TButton")
            self.placeholder_label.config(text="✅ All command files are up to date!")
    
    def _populate_update_list(self):
        """Populate the scrollable list with available updates."""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.update_checkboxes = {}
        
        if not self.available_updates:
            self.placeholder_label = ttk.Label(self.scrollable_frame, 
                                              text="No updates available",
                                              style="Description.TLabel")
            self.placeholder_label.pack(pady=20)
            return
        
        # Create checkbox for each update
        for filename, update_info in sorted(self.available_updates.items()):
            frame = ttk.Frame(self.scrollable_frame)
            frame.pack(fill=tk.X, padx=10, pady=5)
            
            var = tk.BooleanVar(value=True)  # Selected by default
            self.update_checkboxes[filename] = var
            
            # Status badge with color coding
            status = update_info["status"]
            if status == "new":
                badge_text = "🆕 NEW"
                badge_color = self.theme["ACCENT_GREEN"]
            elif status == "updated":
                badge_text = "🔄 UPDATED"
                badge_color = "#4fc3f7"
            else:  # obsolete
                badge_text = "🗑️ OBSOLETE"
                badge_color = self.theme["ERROR_RED"]
            
            chk = ttk.Checkbutton(frame, text=filename, variable=var)
            chk.pack(side=tk.LEFT)
            
            badge = ttk.Label(frame, text=badge_text, 
                            foreground=badge_color,
                            font=("Helvetica", 9, "bold"))
            badge.pack(side=tk.LEFT, padx=(10, 0))
            
            # Show file size for new/updated files
            if status != "obsolete":
                size_kb = update_info['size'] / 1024
                size_label = ttk.Label(frame, 
                                      text=f"({size_kb:.1f} KB)",
                                      style="Tooltip.TLabel")
                size_label.pack(side=tk.LEFT, padx=(5, 0))
    
    def _select_all_updates(self):
        """Toggle select/deselect all updates."""
        if not self.update_checkboxes:
            return
        
        # Check if all are currently selected
        all_selected = all(var.get() for var in self.update_checkboxes.values())
        
        # Toggle state
        new_state = not all_selected
        for var in self.update_checkboxes.values():
            var.set(new_state)
        
        # Update button text
        self.select_all_btn.config(text="Deselect All" if new_state else "Select All")
    
    def _threaded_apply_updates(self):
        """Apply selected updates in background thread."""
        selected = [name for name, var in self.update_checkboxes.items() if var.get()]
        
        if not selected:
            self.status_label.config(text="⚠️ No files selected")
            return
        
        # Disable controls during update
        self.check_btn.config(state=tk.DISABLED)
        self.update_btn.config(state=tk.DISABLED)
        self.select_all_btn.config(state=tk.DISABLED)
        
        # Show progress bar
        self.progress_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        self.progress_bar['value'] = 0
        self.progress_bar['maximum'] = len(selected)
        
        def update_task():
            def progress_update(current, total, status):
                self.window.after(0, lambda: self._update_progress(current, total, status))
            
            success, message, count = self.apply_updates(selected, progress_update)
            
            # Update UI in main thread
            self.window.after(0, lambda: self._handle_update_result(success, message, count))
        
        thread = threading.Thread(target=update_task, daemon=True)
        thread.start()
    
    def _update_progress(self, current, total, status):
        """Update progress bar and label."""
        self.progress_bar['value'] = current
        self.progress_label.config(text=f"{status} ({current}/{total})")
        self.window.update_idletasks()
    
    def _handle_update_result(self, success, message, updated_count):
        """Handle update completion in main UI thread."""
        self.status_label.config(text=message)
        
        # Hide progress bar
        self.progress_frame.pack_forget()
        
        # Re-enable controls
        self.check_btn.config(state=tk.NORMAL)
        
        if success and updated_count > 0:
            # Clear update list
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            
            self.placeholder_label = ttk.Label(self.scrollable_frame, 
                                              text="✅ Updates installed successfully!",
                                              style="Description.TLabel")
            self.placeholder_label.pack(pady=20)
            
            # Update file count display
            file_count = len(self.local_hashes)
            self.version_label.config(text=f"Installed Files: {file_count}")
            
            # Trigger reload callback
            if self.on_update_complete:
                self.window.after(1000, self.on_update_complete)
        else:
            # Re-enable update button if failed
            self.update_btn.config(state=tk.NORMAL, style="TButton")
            self.select_all_btn.config(state=tk.NORMAL, style="TButton")