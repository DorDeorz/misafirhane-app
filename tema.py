# -*- coding: utf-8 -*-
"""
Tema (görünüm) yönetimi: aydınlık / karanlık / sistem.
- Ayarlar sekmesinden seçilir, 'ayarlar' tablosunda 'tema' anahtarında saklanır.
- Uygulama genelinde palet + stil sunumu tek noktadan uygulanır.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt

TEMA_SISTEM = "sistem"
TEMA_AYDINLIK = "aydinlik"
TEMA_KARANLIK = "karanlik"


def _aydinlik_paleti():
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#f0f0f0"))
    p.setColor(QPalette.WindowText, QColor("#1a1a1a"))
    p.setColor(QPalette.Base, QColor("#ffffff"))
    p.setColor(QPalette.AlternateBase, QColor("#f7f7f7"))
    p.setColor(QPalette.Text, QColor("#1a1a1a"))
    p.setColor(QPalette.Button, QColor("#e6e6e6"))
    p.setColor(QPalette.ButtonText, QColor("#1a1a1a"))
    p.setColor(QPalette.BrightText, QColor("#c0392b"))
    p.setColor(QPalette.Highlight, QColor("#4a90d9"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#2471a3"))
    p.setColor(QPalette.ToolTipBase, QColor("#ffffe6"))
    p.setColor(QPalette.ToolTipText, QColor("#1a1a1a"))
    p.setColor(QPalette.PlaceholderText, QColor("#8a8a8a"))
    for rol in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, rol, QColor("#8a8a8a"))
    return p


def _karanlik_paleti():
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#2b2b2b"))
    p.setColor(QPalette.WindowText, QColor("#e8e8e8"))
    p.setColor(QPalette.Base, QColor("#232323"))
    p.setColor(QPalette.AlternateBase, QColor("#2a2a2a"))
    p.setColor(QPalette.Text, QColor("#e8e8e8"))
    p.setColor(QPalette.Button, QColor("#3a3a3a"))
    p.setColor(QPalette.ButtonText, QColor("#e8e8e8"))
    p.setColor(QPalette.BrightText, QColor("#ff4d4d"))
    p.setColor(QPalette.Highlight, QColor("#3d6fb4"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#6ab0f3"))
    p.setColor(QPalette.ToolTipBase, QColor("#3a3a3a"))
    p.setColor(QPalette.ToolTipText, QColor("#e8e8e8"))
    p.setColor(QPalette.PlaceholderText, QColor("#9a9a9a"))
    # devre dışı öğeler soluk görünür
    for rol in (QPalette.WindowText, QPalette.Text,
                QPalette.ButtonText, QPalette.Highlight,
                QPalette.WindowText, QPalette.Base, QPalette.Window):
        p.setColor(QPalette.Disabled, rol, QColor("#6f6f6f"))
    return p


def _sistem_karanlik_mi():
    """Sistem (Windows) karanlık modda mı? Qt bildirimi, yoksa palet parlaklığına bakar."""
    try:
        from PySide6.QtGui import QGuiApplication
        duzeni = QGuiApplication.styleHints().colorScheme()
        if duzeni == Qt.ColorScheme.Dark:
            return True
        if duzeni == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        renk = app.palette().color(QPalette.Window)
        return renk.lightness() < 128
    return False


def _stil(karanlik):
    if karanlik:
        return _KARANLIK_QSS
    return _AYDINLIK_QSS


def karanlik_mi(tema):
    """Verilen tema seçimi için 'karanlık mı' sonucunu döndürür (sistem için çözümler)."""
    if tema == TEMA_KARANLIK:
        return True
    if tema == TEMA_AYDINLIK:
        return False
    return _sistem_karanlik_mi()


def temayi_uygula(app, tema):
    """app.setStyle('Fusion') sonrası çağrılır. Palet + stil sunumunu uygular."""
    karanlik = karanlik_mi(tema)
    if karanlik:
        app.setPalette(_karanlik_paleti())
    else:
        # Windows koyu modda olsa bile kararlı (gerçekten açık) görünüm
        app.setPalette(_aydinlik_paleti())
    app.setStyleSheet(_stil(karanlik))


def hucre_yazi_rengi(arka_plan):
    """Hücre arka planına göre okunur metin rengi seçer (açık zeminde koyu, koyu zeminde açık)."""
    renk = arka_plan if isinstance(arka_plan, QColor) else QColor(arka_plan)
    if renk.lightness() > 155:
        return QColor("#1a1a1a")
    return QColor("#f2f2f2")


def renklendir(item, arka_plan, yazi=None):
    """QTableWidget hücresine arka plan koyar; yazı rengi otomatik (okunurluk garantili)."""
    item.setBackground(arka_plan if isinstance(arka_plan, QColor) else QColor(arka_plan))
    item.setForeground(yazi if yazi is not None else hucre_yazi_rengi(arka_plan))


# ============================================================
# STİL SUNUMLARI (QSS) — modern, palet ile uyumlu görünüm
# Not: QSpinBox/QComboBox/QDateEdit'in ALT BUTONLARI stil
# motorunun kendisi çizer (imge yok); o yüzden onlarda yalnızca
# dolgu (padding) verilir, renk/arka plan ezilmez.
# ============================================================

_AYDINLIK_QSS = """
#ust_bar { background-color: #ffffff; border-bottom: 1px solid #dce1e9; }
#baslik  { font-size: 16px; font-weight: 700; color: #16233a; }

QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: #556070;
    padding: 7px 12px; margin-right: 2px; border: none;
    border-bottom: 2px solid transparent; border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { color: #16233a; font-weight: 700; border-bottom: 2px solid #2f6fed; }
QTabBar::tab:hover:!selected { background: rgba(47, 111, 237, 0.08); }

QGroupBox {
    border: 1px solid #dce1e9; border-radius: 10px;
    margin-top: 12px; padding: 8px 8px 8px 8px;
    background-color: palette(Base);
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #2b3a55; font-weight: 700;
}

QPushButton { padding: 5px 11px; border-radius: 6px; border: 1px solid #cdd3dd; background: palette(Button); }
QPushButton:hover { background: palette(Midlight); }
QPushButton:pressed { background: palette(Mid); }
QPushButton:disabled { color: #9aa3af; border-color: #e0e4ea; }
QPushButton#birincil {
    background: #2f6fed; color: #ffffff; font-weight: 700;
    border: none; padding: 7px 16px; border-radius: 7px;
}
QPushButton#birincil:hover { background: #245cd0; }
QPushButton#birincil:pressed { background: #1c4db3; }
QPushButton#birincil:disabled { background: #a9bce8; color: #ffffff; }
QPushButton#ikincil { background: transparent; color: #245cd0; border: 1px solid #b9cbf2; }
QPushButton#ikincil:hover { background: rgba(47, 111, 237, 0.08); }

QHeaderView::section {
    background-color: #edf0f5; color: #334155;
    border: none; border-bottom: 1px solid #d7dce5; border-right: 1px solid #e2e7ee;
    padding: 5px 8px; font-weight: 600;
}
QTableCornerButton::section { background-color: #edf0f5; border: none; border-bottom: 1px solid #d7dce5; }
QTableWidget { gridline-color: #e6e9ef; alternate-background-color: palette(AlternateBase); }
QTableWidget::item:selected { background: palette(Highlight); color: palette(HighlightedText); }

QLineEdit, QTextEdit, QPlainTextEdit {
    border: 1px solid #cdd3dd; border-radius: 7px; padding: 4px 8px;
    background-color: palette(Base); color: palette(Text);
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #2f6fed; }
QComboBox, QSpinBox, QDateEdit { padding: 4px 8px; }
QCheckBox, QRadioButton { spacing: 6px; }
QSplitter::handle { background-color: #e4e8ee; }

QScrollBar:vertical { background: #f3f4f6; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #b8c0cc; border-radius: 6px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #9aa6b5; }
QScrollBar:horizontal { background: #f3f4f6; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #b8c0cc; border-radius: 6px; min-width: 20px; }
QScrollBar::handle:horizontal:hover { background: #9aa6b5; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { background-color: #ffffe6; color: #1a1a1a; border: 1px solid #b8c0cc; padding: 4px 6px; border-radius: 4px; }
QMenuBar { background-color: #ffffff; color: #1a1a1a; border-bottom: 1px solid #dce1e9; }
QMenu { background-color: #ffffff; color: #1a1a1a; border: 1px solid #c8d0da; border-radius: 6px; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: #2f6fed; color: #ffffff; }
QCalendarWidget QWidget { alternate-background-color: #f6f7f9; }
QCalendarWidget QAbstractItemView {
    background-color: #ffffff; color: #1a1a1a;
    selection-background-color: #2f6fed; selection-color: #ffffff;
}
QMessageBox QLabel { min-width: 320px; }
"""

_KARANLIK_QSS = """
#ust_bar { background-color: #1f242b; border-bottom: 1px solid #353c46; }
#baslik  { font-size: 16px; font-weight: 700; color: #ffffff; }

QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab {
    background: transparent; color: #9fb0c4;
    padding: 7px 12px; margin-right: 2px; border: none;
    border-bottom: 2px solid transparent; border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { color: #ffffff; font-weight: 700; border-bottom: 2px solid #3b82f6; }
QTabBar::tab:hover:!selected { background: rgba(59, 130, 246, 0.12); }

QGroupBox {
    border: 1px solid #3d4550; border-radius: 10px;
    margin-top: 12px; padding: 8px 8px 8px 8px;
    background-color: palette(Base);
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #dbe3ee; font-weight: 700;
}

QPushButton { padding: 5px 11px; border-radius: 6px; border: 1px solid #49525e; background: palette(Button); }
QPushButton:hover { background: palette(Midlight); }
QPushButton:pressed { background: palette(Mid); }
QPushButton:disabled { color: #6d7886; border-color: #39404b; }
QPushButton#birincil {
    background: #3b82f6; color: #ffffff; font-weight: 700;
    border: none; padding: 7px 16px; border-radius: 7px;
}
QPushButton#birincil:hover { background: #3475d9; }
QPushButton#birincil:pressed { background: #2d66bd; }
QPushButton#birincil:disabled { background: #3d5578; color: #9fb0c4; }
QPushButton#ikincil { background: transparent; color: #7fb0f7; border: 1px solid #3d5a85; }
QPushButton#ikincil:hover { background: rgba(59, 130, 246, 0.12); }

QHeaderView::section {
    background-color: #353a43; color: #dbe3ee;
    border: none; border-bottom: 1px solid #474e59; border-right: 1px solid #414852;
    padding: 5px 8px; font-weight: 600;
}
QTableCornerButton::section { background-color: #353a43; border: none; border-bottom: 1px solid #474e59; }
QTableWidget { gridline-color: #3a414c; alternate-background-color: palette(AlternateBase); }
QTableWidget::item:selected { background: palette(Highlight); color: palette(HighlightedText); }

QLineEdit, QTextEdit, QPlainTextEdit {
    border: 1px solid #4a5260; border-radius: 7px; padding: 4px 8px;
    background-color: palette(Base); color: palette(Text);
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #3b82f6; }
QComboBox, QSpinBox, QDateEdit { padding: 4px 8px; }
QCheckBox, QRadioButton { spacing: 6px; }
QSplitter::handle { background-color: #333a44; }

QScrollBar:vertical { background: #242a32; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #4b5563; border-radius: 6px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #5b6675; }
QScrollBar:horizontal { background: #242a32; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #4b5563; border-radius: 6px; min-width: 20px; }
QScrollBar::handle:horizontal:hover { background: #5b6675; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { background-color: #3a424d; color: #e8e8e8; border: 1px solid #565f6d; padding: 4px 6px; border-radius: 4px; }
QMenuBar { background-color: #1f242b; color: #e8e8e8; border-bottom: 1px solid #353c46; }
QMenu { background-color: #232830; color: #e8e8e8; border: 1px solid #3d4550; border-radius: 6px; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background-color: #3b82f6; color: #ffffff; }
QCalendarWidget QWidget { alternate-background-color: #2b3038; }
QCalendarWidget QAbstractItemView {
    background-color: #232830; color: #e8e8e8;
    selection-background-color: #3b82f6; selection-color: #ffffff;
}
QMessageBox QLabel { min-width: 320px; }
"""