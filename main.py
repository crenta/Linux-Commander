# main.py
import tkinter as tk
import platform
import sys
import os
from pathlib import Path

from ui_controller import UIController
from logger_config import logger, setup_logger

# Version metadata
__version__ = '1.0.0'
__description__ = 'Linux Command Builder - GUI for generating Linux shell commands'
__author__ = 'Crenta'

def check_minimum_python():
    """Ensure minimum Python version"""
    if sys.version_info < (3, 8):
        import tkinter.messagebox as messagebox
        messagebox.showerror(
            "Python Version Error",
            f"This app requires Python 3.8+\nYou have {sys.version}"
        )
        sys.exit(1)

def get_resource_path(relative_path):
    """Get absolute path to bundled resource"""
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent
    return base_path / relative_path

def get_data_dir():
    """Get persistent user data directory"""
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            data_dir = Path.home() / 'AppData' / 'Local' / 'LinuxCommander'
        elif sys.platform == 'darwin':
            data_dir = Path.home() / 'Library' / 'Application Support' / 'LinuxCommander'
        else:
            data_dir = Path.home() / '.local' / 'share' / 'LinuxCommander'
    else:
        data_dir = Path(__file__).parent
    
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def main():
    # Check Python version first
    check_minimum_python()
    
    # Setup logging with file output
    data_dir = get_data_dir()
    log_file = data_dir / 'app.log'
    
    # Check for debug mode
    debug_mode = os.getenv('DEBUG', '').lower() in ('1', 'true', 'yes')
    
    # Reinitialize logger with file output
    import logging
    setup_logger(
        name="LinuxCommander",
        log_file=str(log_file),
        level=logging.DEBUG if debug_mode else logging.INFO
    )
    
    logger.info(f"Starting Linux Command Builder v{__version__}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.system()}")
    logger.info(f"Data directory: {data_dir}")
    
    if debug_mode:
        logger.debug("DEBUG MODE ENABLED")
        logger.debug(f"Log file: {log_file}")
    
    # Windows taskbar icon fix
    if platform.system() == "Windows":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "lcommander.app.1.0"
            )
        except Exception as e:
            logger.warning(f"Could not set Windows taskbar icon: {e}")
    
    # Setup paths
    bundled_commands = get_resource_path("commands")
    user_commands = data_dir / "commands"
    logo_path = get_resource_path("LOGO.png")
    
    logger.debug(f"Bundled commands: {bundled_commands}")
    logger.debug(f"User commands: {user_commands}")
    logger.debug(f"Logo path: {logo_path}")
    
    # Launch app
    try:
        root = tk.Tk()
        
        if debug_mode:
            # Show widget boundaries in debug mode
            root.config(highlightthickness=2, highlightcolor="red")
        
        app = UIController(root, user_commands, bundled_commands, logo_path)
        
        logger.info("Application initialized successfully")
        root.mainloop()
        
    except Exception as e:
        logger.exception("Fatal error during application startup")
        raise
    finally:
        logger.info("Application shutdown")

if __name__ == "__main__":
    main()