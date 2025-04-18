from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtGui import QPalette, QColor, QFont

class StyleManager:
    """Manages application styling and theme settings"""

    @staticmethod
    def apply_dark_theme(app):
        """Apply dark theme to the entire application"""
        app.setStyle(QStyleFactory.create("Fusion"))

        dark_palette = QPalette()

        # Define colors
        dark_color = QColor(45, 45, 48)  # #2D2D30
        dark_gray = QColor(30, 30, 30)  # #1E1E1E
        light_gray = QColor(42, 42, 42)  # #2A2A2A
        white = QColor(255, 255, 255)  # #FFFFFF
        blue = QColor(55, 148, 255)  # #3794FF
        purple = QColor(128, 100, 162)  # #8064A2
        light_blue = QColor(0, 122, 204)  # #007ACC
        gray = QColor(62, 62, 64)  # #3E3E40

        # Set colors for different roles
        dark_palette.setColor(QPalette.Window, dark_color)
        dark_palette.setColor(QPalette.WindowText, white)
        dark_palette.setColor(QPalette.Base, dark_gray)
        dark_palette.setColor(QPalette.AlternateBase, light_gray)
        dark_palette.setColor(QPalette.ToolTipBase, dark_color)
        dark_palette.setColor(QPalette.ToolTipText, white)
        dark_palette.setColor(QPalette.Text, white)
        dark_palette.setColor(QPalette.Button, QColor(58, 58, 58))
        dark_palette.setColor(QPalette.ButtonText, white)
        dark_palette.setColor(QPalette.BrightText, white)
        dark_palette.setColor(QPalette.Highlight, gray)
        dark_palette.setColor(QPalette.HighlightedText, white)
        dark_palette.setColor(QPalette.Link, blue)
        dark_palette.setColor(QPalette.LinkVisited, purple)

        # Apply palette
        app.setPalette(dark_palette)

        # Set stylesheet for specific widgets
        app.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2D2D30;
                color: #FFFFFF;
            }
            QLineEdit, QListWidget {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3E3E40;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #3A3A3A;
                color: #FFFFFF;
                border: 1px solid #3E3E40;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background-color: #44444A;
            }
            QPushButton:pressed {
                background-color: #007ACC;
            }
            QLabel {
                color: #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #007ACC;
            }
            QFrame#sidebar_frame {
                background-color: #252526;
                border-right: 1px solid #1E1E1E;
            }
            QSplitter::handle {
                background-color: #3E3E40;
            }
        """)

    @staticmethod
    def apply_light_theme(app):
        """Apply light theme to the entire application"""
        app.setStyle(QStyleFactory.create("Fusion"))

        light_palette = QPalette()

        # Define colors
        light_color = QColor(240, 240, 240)  # #F0F0F0
        white = QColor(255, 255, 255)  # #FFFFFF
        black = QColor(0, 0, 0)  # #000000
        light_gray = QColor(230, 230, 230)  # #E6E6E6
        medium_gray = QColor(200, 200, 200)  # #C8C8C8
        dark_gray = QColor(160, 160, 160)  # #A0A0A0
        blue = QColor(0, 120, 215)  # #0078D7
        purple = QColor(128, 100, 162)  # #8064A2

        # Set colors for different roles
        light_palette.setColor(QPalette.Window, light_color)
        light_palette.setColor(QPalette.WindowText, black)
        light_palette.setColor(QPalette.Base, white)
        light_palette.setColor(QPalette.AlternateBase, light_gray)
        light_palette.setColor(QPalette.ToolTipBase, white)
        light_palette.setColor(QPalette.ToolTipText, black)
        light_palette.setColor(QPalette.Text, black)
        light_palette.setColor(QPalette.Button, light_gray)
        light_palette.setColor(QPalette.ButtonText, black)
        light_palette.setColor(QPalette.BrightText, black)
        light_palette.setColor(QPalette.Highlight, blue)
        light_palette.setColor(QPalette.HighlightedText, white)
        light_palette.setColor(QPalette.Link, blue)
        light_palette.setColor(QPalette.LinkVisited, purple)

        # Apply palette
        app.setPalette(light_palette)

        # Set stylesheet for specific widgets
        app.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #F0F0F0;
                color: #000000;
            }
            QLineEdit, QListWidget {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #C8C8C8;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #E6E6E6;
                color: #000000;
                border: 1px solid #C8C8C8;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #0078D7;
                color: #FFFFFF;
            }
            QLabel {
                color: #000000;
            }
            QListWidget::item:selected {
                background-color: #0078D7;
                color: #FFFFFF;
            }
            QFrame#sidebar_frame {
                background-color: #E6E6E6;
                border-right: 1px solid #C8C8C8;
            }
            QSplitter::handle {
                background-color: #C8C8C8;
            }
        """)
