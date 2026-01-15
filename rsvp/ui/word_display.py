"""Word display widget with ORP highlighting."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QFontMetrics

from rsvp.core.text_processor import Word
from rsvp.core.settings import get_settings_manager


class ORPWordDisplay(QWidget):
    """Widget that displays a word with ORP (Optimal Recognition Point) highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._word: Word | None = None
        self._font = QFont("Arial", 48)
        self._text_color = QColor("#FFFFFF")
        self._orp_color = QColor("#FF6B6B")
        self._bg_color = QColor("#1E1E1E")

        self.setMinimumHeight(120)
        self._load_settings()

    def _load_settings(self):
        """Load display settings."""
        settings = get_settings_manager().settings
        self._font = QFont(settings.font_family, settings.font_size)
        self._text_color = QColor(settings.text_color)
        self._orp_color = QColor(settings.orp_color)
        self._bg_color = QColor(settings.background_color)

    def update_settings(self):
        """Reload settings and repaint."""
        self._load_settings()
        self.update()

    def set_word(self, word: Word | None):
        """Set the word to display."""
        self._word = word
        self.update()

    def set_font_size(self, size: int):
        """Set the font size."""
        self._font.setPointSize(size)
        self.update()

    def paintEvent(self, event):
        """Paint the word with ORP highlighting."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), self._bg_color)

        if not self._word:
            return

        painter.setFont(self._font)
        fm = QFontMetrics(self._font)

        # Calculate text dimensions
        text = self._word.text
        before = self._word.before_orp
        orp_char = self._word.orp_char
        after = self._word.after_orp

        # Calculate widths
        before_width = fm.horizontalAdvance(before)
        orp_width = fm.horizontalAdvance(orp_char)
        after_width = fm.horizontalAdvance(after)
        total_width = before_width + orp_width + after_width

        # Calculate positions - center the ORP character
        center_x = self.width() // 2
        center_y = self.height() // 2

        # Draw ORP indicator line (vertical red line at center)
        indicator_height = fm.height() + 20
        painter.setPen(self._orp_color)
        painter.drawLine(center_x, center_y - indicator_height // 2,
                        center_x, center_y + indicator_height // 2)

        # Position text so ORP char is centered
        text_y = center_y + fm.ascent() // 2

        # Calculate x position so ORP character is centered
        orp_center = before_width + orp_width // 2
        text_x = center_x - orp_center

        # Draw before ORP
        painter.setPen(self._text_color)
        painter.drawText(int(text_x), int(text_y), before)

        # Draw ORP character in highlight color
        painter.setPen(self._orp_color)
        painter.drawText(int(text_x + before_width), int(text_y), orp_char)

        # Draw after ORP
        painter.setPen(self._text_color)
        painter.drawText(int(text_x + before_width + orp_width), int(text_y), after)


class WordDisplayWidget(QWidget):
    """Complete word display widget with surrounding context."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main word display
        self.word_display = ORPWordDisplay()
        layout.addWidget(self.word_display)

        self.setLayout(layout)

    def set_word(self, word: Word | None):
        """Set the word to display."""
        self.word_display.set_word(word)

    def update_settings(self):
        """Update display settings."""
        self.word_display.update_settings()
