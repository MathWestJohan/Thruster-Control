from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSlider
from PyQt5.QtCore import Qt, QTimer
from serial_handler import shared_data, data_lock

class ThrusterGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Thruster Control")
        self.setGeometry(100, 100, 400, 300)

        layout = QVBoxLayout()

        self.rpm_label = QLabel("RPM: -")
        self.power_label = QLabel("Motor Power: -")
        self.battery_label = QLabel("Battery: -")
        self.throttle_label = QLabel("Throttle: 0")

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(-1000)
        self.slider.setMaximum(1000)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.update_throttle)

        layout.addWidget(self.rpm_label)
        layout.addWidget(self.power_label)
        layout.addWidget(self.battery_label)
        layout.addWidget(self.throttle_label)
        layout.addWidget(self.slider)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_labels)
        self.timer.start(200)

    def update_throttle(self, value):
        with data_lock:
            shared_data["throttle"] = value
        self.throttle_label.setText(f"Throttle: {value}")

    def refresh_labels(self):
        with data_lock:
            rpm = shared_data["rpm"]
            power = shared_data["power"]
            battery = shared_data["battery"]

        self.rpm_label.setText(f"RPM: {rpm}")
        self.power_label.setText(f"Motor Power: {power} %")
        self.battery_label.setText(f"Battery: {battery} %")
