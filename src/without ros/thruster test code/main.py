import sys
import threading
from PyQt5.QtWidgets import QApplication
from gui import ThrusterGUI
from serial_handler import serial_loop

print("Starting serial thread…")


if __name__ == "__main__":
    threading.Thread(target=serial_loop, daemon=True).start()

    app = QApplication(sys.argv)
    window = ThrusterGUI()
    window.show()
    sys.exit(app.exec_())
