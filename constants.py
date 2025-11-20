# constants.py
"""Application-wide constants and configuration values"""

class UIConstants:
    """UI dimensions and sizing"""
    # Main window
    WINDOW_WIDTH = 900
    WINDOW_HEIGHT = 700
    WINDOW_GEOMETRY = f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
    
    # Sidebar
    SIDEBAR_WIDTH = 240
    LOGO_SIZE = 68
    
    # Splash screen
    SPLASH_WIDTH = 400
    SPLASH_HEIGHT = 120
    
    # AI result window
    RESULT_WINDOW_WIDTH = 600
    RESULT_WINDOW_HEIGHT = 500
    
    # Message boxes
    MESSAGE_BOX_WIDTH = 500
    MESSAGE_BOX_HEIGHT = 220
    
    # Icon sizes
    ICON_SIZES = [16, 32, 48, 64]
    
    # Padding values
    STANDARD_PADDING = 10
    SECTION_PADDING = 5


class FileConstants:
    """File and path related constants"""
    MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_LOGO_SIZE = 5 * 1024 * 1024   # 5MB
    MAX_INPUT_LENGTH = 8000
    DEFAULT_MAX_TEXT_LENGTH = 500


class ValidationConstants:
    """Input validation limits"""
    MIN_PORT = 1
    MAX_PORT = 65535
    
    # Reserved Windows filenames
    RESERVED_NAMES = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
        'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5',
        'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    
    # Invalid path characters
    INVALID_PATH_CHARS = '<>:"|?*'