"""iOS-style theme system for LangTrainer.

Centralized color palette and stylesheet constants for a clean,
minimalist iOS-inspired design language.
"""

# ── iOS Dark Mode Color Palette ──────────────────────────────────────────
class Colors:
    """System colors — iOS Dark Mode inspired."""
    # Backgrounds
    SYSTEM_BG = "#000000"         # True black background
    SYSTEM_GROUPED_BG = "#0E0E0E"  # Slightly raised grouped bg
    CARD_BG = "#1C1C1E"          # iOS card background
    CARD_BG_ALT = "#2C2C2E"      # Slightly lighter card
    SECONDARY_BG = "#242426"      # Secondary grouped bg
    SEPARATOR = "#38383A"         # Thin separator lines
    
    # Text
    PRIMARY_LABEL = "#FFFFFF"     # Primary text
    SECONDARY_LABEL = "#98989D"   # Secondary/subtitle text
    TERTIARY_LABEL = "#636366"    # Placeholder/disabled text
    
    # Accent Colors
    BLUE = "#007AFF"              # iOS blue
    BLUE_LIGHT = "#409CFF"        # Blue hover
    GREEN = "#34C759"             # iOS green
    GREEN_LIGHT = "#40D866"       # Green hover  
    RED = "#FF3B30"               # iOS red
    RED_LIGHT = "#FF6259"         # Red hover
    ORANGE = "#FF9500"            # iOS orange
    YELLOW = "#FFCC00"            # iOS yellow
    PURPLE = "#AF52DE"            # iOS purple
    INDIGO = "#5856D6"            # iOS indigo
    TEAL = "#5AC8FA"              # iOS teal
    
    # Card game specific
    CARD_FRONT_BG = "#1E3A5F"     # Card front (word side)
    CARD_FRONT_BORDER = "#007AFF" # Card front border
    CARD_BACK_BG = "#2C2C2E"      # Card back (hidden)
    CARD_BACK_BORDER = "#007AFF"  # Card back border
    CARD_MATCHED_BG = "#1B3A1B"   # Matched card bg
    CARD_MATCHED_BORDER = "#34C759"

    # Difficulty colors
    EASY_GREEN = "#34C759"
    HARD_ORANGE = "#FF9500"
    CHAOS_RED = "#FF3B30"


class Fonts:
    """Typography constants — SF Pro inspired."""
    LARGE_TITLE = "font-size: 34px; font-weight: bold;"
    TITLE_1 = "font-size: 28px; font-weight: bold;"
    TITLE_2 = "font-size: 22px; font-weight: bold;"
    TITLE_3 = "font-size: 20px; font-weight: semibold;"
    HEADLINE = "font-size: 17px; font-weight: semibold;"
    BODY = "font-size: 17px; font-weight: normal;"
    CALLOUT = "font-size: 16px; font-weight: normal;"
    SUBHEADLINE = "font-size: 15px; font-weight: normal;"
    FOOTNOTE = "font-size: 13px; font-weight: normal;"
    CAPTION_1 = "font-size: 12px; font-weight: normal;"
    CAPTION_2 = "font-size: 11px; font-weight: normal;"


# ── Shared Stylesheet Components ─────────────────────────────────────────

def label_style(font: str = Fonts.BODY, color: str = Colors.PRIMARY_LABEL) -> str:
    return f"color: {color}; {font} padding: 4px;"


def pill_button_style(bg: str = Colors.BLUE, text_color: str = "#FFFFFF",
                       hover_bg: str = None, border: str = "none",
                       height: str = "36px", font_size: str = "15px",
                       weight: str = "semibold") -> str:
    """iOS-style pill button."""
    hover = hover_bg or _lighten(bg)
    return f"""
        QPushButton {{
            background-color: {bg}; color: {text_color}; border: {border};
            border-radius: {_pill_radius(height)}; padding: 6px 20px;
            font-size: {font_size}; font-weight: {weight}; min-height: {height};
        }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {_darken(bg)}; }}
        QPushButton:disabled {{ background-color: {Colors.TERTIARY_LABEL}; color: {Colors.SECONDARY_LABEL}; }}
    """


def glass_button_style(bg: str = Colors.BLUE, text_color: str = "#FFFFFF") -> str:
    """iOS frosted glass style button."""
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {_lighten(bg)}, stop:1 {bg});
            color: {text_color}; border: none;
            border-radius: 12px; padding: 12px 20px;
            font-size: 16px; font-weight: semibold; min-height: 44px;
        }}
        QPushButton:hover {{ background-color: {_lighten(bg)}; }}
        QPushButton:pressed {{ background-color: {_darken(bg)}; }}
    """


def action_button_style(bg: str = Colors.BLUE, text_color: str = "#FFFFFF",
                        border: str = "none") -> str:
    """iOS-style toolbar action button — compact geometry shared with destructive_button_style.

    Args:
        bg: Background color (default iOS blue).
        text_color: Label color (default white).
        border: CSS border value (default none).

    Returns:
        QPushButton stylesheet with 8px radius, 6px 14px padding,
        13px normal-weight font, and 28px min-height.
    """
    return f"""
        QPushButton {{
            background-color: {bg}; color: {text_color}; border: {border};
            border-radius: 8px; padding: 6px 14px;
            font-size: 13px; font-weight: normal; min-height: 28px;
        }}
        QPushButton:hover {{ background-color: {_lighten(bg)}; }}
        QPushButton:pressed {{ background-color: {_darken(bg)}; }}
    """


def destructive_button_style() -> str:
    """iOS-style destructive button — red text on neutral bg, same geometry as action_button_style."""
    return action_button_style(
        bg=Colors.CARD_BG_ALT,
        text_color=Colors.RED,
        border=f"1px solid {Colors.SEPARATOR}",
    )


def card_style(bg: str = Colors.CARD_BG, border_radius: str = "14px") -> str:
    """iOS-style card / rounded rect."""
    return f"""
        QFrame {{
            background-color: {bg};
            border: none;
            border-radius: {border_radius};
        }}
    """


def input_field_style() -> str:
    """iOS-style text input field."""
    return f"""
        QLineEdit {{
            background-color: {Colors.SECONDARY_BG}; color: {Colors.PRIMARY_LABEL};
            border: 1px solid {Colors.SEPARATOR}; border-radius: 10px;
            padding: 12px 14px; font-size: 17px; min-height: 22px;
        }}
        QLineEdit:focus {{ border: 2px solid {Colors.BLUE}; }}
        QLineEdit::placeholder {{ color: {Colors.TERTIARY_LABEL}; }}
    """


def combo_box_style() -> str:
    """iOS-style combo box / picker."""
    return f"""
        QComboBox {{
            background-color: {Colors.SECONDARY_BG}; color: {Colors.PRIMARY_LABEL};
            border: 1px solid {Colors.SEPARATOR}; border-radius: 8px;
            padding: 6px 12px; font-size: 15px; min-height: 30px;
        }}
        QComboBox::drop-down {{ border: none; width: 24px; }}
        QComboBox::down-arrow {{ image: none; }}
        QComboBox QAbstractItemView {{
            background-color: {Colors.CARD_BG}; color: {Colors.PRIMARY_LABEL};
            selection-background-color: {Colors.BLUE};
            border-radius: 8px; padding: 4px;
        }}
    """


def progress_bar_style(danger: bool = False) -> str:
    """iOS-style horizontal progress bar — blue fill, card track, red when danger."""
    fill = Colors.RED if danger else Colors.BLUE
    return f"""
        QProgressBar {{
            background-color: {Colors.CARD_BG};
            border: none; border-radius: 5px;
        }}
        QProgressBar::chunk {{
            background-color: {fill};
            border-radius: 5px;
        }}
    """


def segmented_control_style(selected_bg: str = Colors.BLUE) -> str:
    """iOS-style segmented control for QComboBox used as picker."""
    return f"""
        QComboBox {{
            background-color: {Colors.SECONDARY_BG}; color: {Colors.PRIMARY_LABEL};
            border: 1px solid {Colors.SEPARATOR}; border-radius: 8px;
            padding: 4px 12px; font-size: 14px; min-width: 80px;
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {Colors.CARD_BG}; color: {Colors.PRIMARY_LABEL};
            selection-background-color: {selected_bg};
            border-radius: 8px; outline: none;
        }}
        QComboBox::item {{ padding: 6px 12px; }}
    """


def progress_label_style() -> str:
    """iOS-style caption for progress/score labels."""
    return f"color: {Colors.SECONDARY_LABEL}; {Fonts.CAPTION_1} padding: 2px;"


def score_label_style() -> str:
    """iOS-style green score label."""
    return f"color: {Colors.GREEN}; {Fonts.CAPTION_1} padding: 2px;"


# ── Helper Functions ─────────────────────────────────────────────────────
# NOTE: These MUST be defined before module-level f-strings that reference them.

def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lighten(hex_color: str, factor: float = 0.15) -> str:
    """Lighten a hex color by factor (0-1)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken(hex_color: str, factor: float = 0.15) -> str:
    """Darken a hex color by factor (0-1)."""
    r, g, b = _hex_to_rgb(hex_color)
    r = max(0, int(r * (1 - factor)))
    g = max(0, int(g * (1 - factor)))
    b = max(0, int(b * (1 - factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def _pill_radius(height: str) -> str:
    """Calculate pill border-radius from height string (e.g. '36px' → '18px')."""
    try:
        h = int(height.replace("px", ""))
        return f"{h // 2}px"
    except (ValueError, AttributeError):
        return "18px"


# ── Card Game Styles (Memory Palace) ────────────────────────────────────

HIDDEN_CARD_STYLE = f"""
    QPushButton {{
        background-color: {Colors.CARD_BACK_BG}; color: {Colors.PRIMARY_LABEL};
        border: 2px solid {Colors.CARD_BACK_BORDER}; border-radius: 12px;
        padding: 10px; font-size: 15px; font-weight: bold; min-height: 50px;
    }}
    QPushButton:hover {{ background-color: {_lighten(Colors.CARD_BACK_BG)}; }}
    QPushButton:disabled {{ background-color: {Colors.CARD_BG}; color: {Colors.TERTIARY_LABEL}; }}
"""

SELECTED_CARD_STYLE = f"""
    QPushButton {{
        background-color: {Colors.CARD_BG}; color: {Colors.PRIMARY_LABEL};
        border: 2px solid {Colors.BLUE}; border-radius: 12px;
        padding: 10px; font-size: 15px; font-weight: bold; min-height: 50px;
    }}
"""

MATCHED_CARD_STYLE = f"""
    QPushButton {{
        background-color: {Colors.CARD_MATCHED_BG}; color: {Colors.SECONDARY_LABEL};
        border: 2px solid {Colors.CARD_MATCHED_BORDER}; border-radius: 12px;
        padding: 10px; font-size: 14px; min-height: 50px;
    }}
"""

# ── Popup Styles ─────────────────────────────────────────────────────────

POPUP_BASE_STYLE = f"""
    #popupCard {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {_lighten(Colors.CARD_BG)}, stop:1 {Colors.CARD_BG});
        border: 1px solid {Colors.SEPARATOR}; border-radius: 16px;
    }}
    QLabel#wordLabel {{
        color: {Colors.PRIMARY_LABEL}; {Fonts.TITLE_3} padding: 8px;
    }}
    QLabel#hintLabel {{
        color: {Colors.SECONDARY_LABEL}; {Fonts.CAPTION_2}
    }}
"""
