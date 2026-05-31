import sys
import os

os.environ["QT_QPA_PLATFORM"] = "wayland"

import sqlite3
import pandas as pd
import qrcode
import cv2
from pyzbar import pyzbar
from io import BytesIO
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox, QFrame
)
from PyQt5.QtGui import QPixmap, QFont, QImage
from PyQt5.QtCore import Qt, QTimer


class QRScannerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Сканирование QR-кода")
        self.setMinimumSize(800, 740)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        
        video_frame = QFrame()
        video_frame.setFrameShape(QFrame.StyledPanel)
        video_frame.setStyleSheet("background-color: black;")
        video_layout = QVBoxLayout(video_frame)
        
        self.video_label = QLabel("Нажмите «Запустить камеру»")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(680, 480)
        video_layout.addWidget(self.video_label)
        main_layout.addWidget(video_frame)
        
        result_title = QLabel("📋 Распознанные данные:")
        result_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        main_layout.addWidget(result_title)
        
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(2)
        self.result_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.result_table.setMinimumHeight(180)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.result_table)
        
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Запустить камеру")
        self.btn_stop = QPushButton("Остановить")
        self.btn_add = QPushButton("Добавить в базу")
        self.btn_add.setEnabled(False)
        
        for btn in (self.btn_start, self.btn_stop, self.btn_add):
            btn.setMinimumHeight(48)
            btn_layout.addWidget(btn)
        main_layout.addLayout(btn_layout)
        
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.scanned_data = None
        self.parsed_data = {}
        
        self.btn_start.clicked.connect(self.start_camera)
        self.btn_stop.clicked.connect(self.stop_camera)
        self.btn_add.clicked.connect(self.accept)

    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            QMessageBox.warning(self, "Ошибка", "Не удалось открыть камеру.")
            return
        self.timer.start(30)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_camera(self):
        if self.timer.isActive():
            self.timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def update_frame(self):
        if not self.cap:
            return
        ret, frame = self.cap.read()
        if not ret:
            return
        
        decoded = pyzbar.decode(frame)
        for obj in decoded:
            data = obj.data.decode('utf-8')
            self.scanned_data = data
            self.parse_and_show_data(data)
            self.btn_add.setEnabled(True)
            cv2.rectangle(frame, (obj.rect.left, obj.rect.top),
                         (obj.rect.left + obj.rect.width, obj.rect.top + obj.rect.height), (0, 255, 0), 5)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg).scaled(680, 500, Qt.KeepAspectRatio))

    def parse_and_show_data(self, data_text):
        self.result_table.setRowCount(0)
        self.parsed_data = {}
        lines = [line.strip() for line in data_text.strip().split('\n') if line.strip()]
        
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                row = self.result_table.rowCount()
                self.result_table.insertRow(row)
                self.result_table.setItem(row, 0, QTableWidgetItem(key))
                self.result_table.setItem(row, 1, QTableWidgetItem(value))
                self.parsed_data[key] = value

    def get_data(self):
        return self.scanned_data, self.parsed_data


class PersonDialog(QDialog):
    def __init__(self, title="Данные сотрудника", data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        layout = QFormLayout(self)
        layout.setSpacing(12)
        
        self.personal_num = QLineEdit()
        self.last_name = QLineEdit()
        self.first_name = QLineEdit()
        self.patronymic = QLineEdit()
        self.birth_date = QLineEdit()
        self.birth_date.setPlaceholderText("ДД.ММ.ГГГГ")
        
        layout.addRow("Личный номер:", self.personal_num)
        layout.addRow("Фамилия:", self.last_name)
        layout.addRow("Имя:", self.first_name)
        layout.addRow("Отчество:", self.patronymic)
        layout.addRow("Дата рождения:", self.birth_date)
        
        if data:
            self.personal_num.setText(str(data[0]))
            self.last_name.setText(str(data[1]))
            self.first_name.setText(str(data[2]))
            self.patronymic.setText(str(data[3]))
            self.birth_date.setText(str(data[4]))
            self.personal_num.setReadOnly(True)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отмена")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)


class QRDialog(QDialog):
    def __init__(self, data_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QR-код сотрудника")
        self.setMinimumSize(460, 540)
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        title = QLabel("QR-код")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data_str)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue())
        qr_label = QLabel()
        qr_label.setPixmap(pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr_label)
        
        info = QLabel(data_str)
        info.setFont(QFont("Segoe UI", 10))
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        close_btn = QPushButton("Закрыть")
        close_btn.setMinimumHeight(45)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("База Сотрудников")
        self.setMinimumSize(1300, 780)
        
        self.conn = sqlite3.connect("employees.db")
        self.create_table()
        
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(15)
        
        title = QLabel("База данных сотрудников")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main.addWidget(title)
        
        control_layout = QHBoxLayout()
        
        self.btn_excel = QPushButton("📥 Добавить из Excel")
        self.btn_manual = QPushButton("➕ Внести вручную")
        self.btn_scan = QPushButton("📷 Сканировать QR")
        self.btn_edit = QPushButton("✏️ Изменить")
        self.btn_export = QPushButton("📤 Экспорт в Excel")
        self.btn_qr = QPushButton("🔳 Показать QR")
        self.btn_refresh = QPushButton("🔄 Обновить")
        
        for btn in (self.btn_excel, self.btn_manual, self.btn_scan, self.btn_edit, 
                   self.btn_export, self.btn_qr, self.btn_refresh):
            btn.setMinimumHeight(48)
            btn.setFont(QFont("Segoe UI", 10))
            control_layout.addWidget(btn)
        
        control_layout.addStretch()
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["По порядку добавления", "По фамилии (А-Я)", "По личному номеру"])
        self.sort_combo.currentIndexChanged.connect(self.load_table)
        control_layout.addWidget(QLabel("Сортировка:"))
        control_layout.addWidget(self.sort_combo)
        
        main.addLayout(control_layout)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по ФИО или личному номеру...")
        self.search_edit.textChanged.connect(self.load_table)
        main.addWidget(self.search_edit)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Личный №", "Фамилия", "Имя", "Отчество", "Дата рождения"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFont(QFont("Segoe UI", 10))
        main.addWidget(self.table)
        
        self.status = QLabel("Готово")
        self.status.setFont(QFont("Segoe UI", 9))
        main.addWidget(self.status)
        
        self.btn_excel.clicked.connect(self.load_from_excel)
        self.btn_manual.clicked.connect(self.add_manual)
        self.btn_scan.clicked.connect(self.scan_qr)
        self.btn_edit.clicked.connect(self.edit_person)
        self.btn_export.clicked.connect(self.export_to_excel)
        self.btn_qr.clicked.connect(self.generate_qr)
        self.btn_refresh.clicked.connect(self.load_table)
        
        self.load_table()

    def create_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS employees (
                    id INTEGER PRIMARY KEY,
                    personal_number TEXT UNIQUE,
                    last_name TEXT,
                    first_name TEXT,
                    patronymic TEXT,
                    birth_date TEXT
                )
            ''')

    def export_to_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Предупреждение", "Нет данных для экспорта.")
            return
        
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить как", 
                                             f"Сотрудники_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                                             "Excel (*.xlsx)")
        if not path:
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM employees ORDER BY id")
            rows = cursor.fetchall()
            df = pd.DataFrame(rows, columns=["ID", "Личный номер", "Фамилия", "Имя", "Отчество", "Дата рождения"])
            df.to_excel(path, index=False)
            QMessageBox.information(self, "Успешно", f"Файл сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def load_from_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите Excel файл", "", "Excel (*.xlsx *.xls)")
        if not path:
            return
        try:
            df = pd.read_excel(path)
            added = 0
            cursor = self.conn.cursor()
            for _, row in df.iterrows():
                try:
                    personal_number = str(row.get('personal_number', row.iloc[0] if len(row) > 0 else "")).strip()
                    if not personal_number:
                        continue
                    last_name = str(row.get('last_name', row.iloc[1] if len(row) > 1 else "")).strip()
                    first_name = str(row.get('first_name', row.iloc[2] if len(row) > 2 else "")).strip()
                    patronymic = str(row.get('middle_name', row.iloc[3] if len(row) > 3 else "")).strip()
                    birth_date = self.excel_date_to_str(row.get('birth_Base', row.iloc[4] if len(row) > 4 else ""))
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO employees 
                        (personal_number, last_name, first_name, patronymic, birth_date)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (personal_number, last_name, first_name, patronymic, birth_date))
                    if cursor.rowcount > 0:
                        added += 1
                except:
                    continue
            self.conn.commit()
            self.load_table()
            QMessageBox.information(self, "✅ Успешно", f"Добавлено записей: {added}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def excel_date_to_str(self, value):
        if pd.isna(value) or value == "" or value is None:
            return ""
        try:
            if isinstance(value, (int, float)):
                date = datetime(1899, 12, 30) + timedelta(days=int(value))
                return date.strftime("%d.%m.%Y")
            return str(value).strip()[:10]
        except:
            return str(value).strip()[:10]

    def add_manual(self):
        dialog = PersonDialog("Добавить нового сотрудника", parent=self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO employees (personal_number, last_name, first_name, patronymic, birth_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    dialog.personal_num.text().strip(),
                    dialog.last_name.text().strip(),
                    dialog.first_name.text().strip(),
                    dialog.patronymic.text().strip(),
                    dialog.birth_date.text().strip()
                ))
                self.conn.commit()
                self.load_table()
                QMessageBox.information(self, "Успешно", "Сотрудник добавлен.")
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Ошибка", "Сотрудник с таким личным номером уже существует!")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def edit_person(self):
        if self.table.currentRow() < 0:
            QMessageBox.warning(self, "Внимание", "Выберите сотрудника!")
            return
        row = self.table.currentRow()
        current_data = [
            self.table.item(row, 1).text(),
            self.table.item(row, 2).text(),
            self.table.item(row, 3).text(),
            self.table.item(row, 4).text(),
            self.table.item(row, 5).text()
        ]
        dialog = PersonDialog("Изменить данные", current_data, self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                cursor = self.conn.cursor()
                cursor.execute('''
                    UPDATE employees SET last_name=?, first_name=?, patronymic=?, birth_date=?
                    WHERE personal_number=?
                ''', (
                    dialog.last_name.text().strip(),
                    dialog.first_name.text().strip(),
                    dialog.patronymic.text().strip(),
                    dialog.birth_date.text().strip(),
                    current_data[0]
                ))
                self.conn.commit()
                self.load_table()
                QMessageBox.information(self, "Успешно", "Данные обновлены.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def scan_qr(self):
        dialog = QRScannerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data_text, parsed = dialog.get_data()
            if data_text:
                self.process_scanned_data(data_text, parsed)

    def process_scanned_data(self, data_text, parsed):
        try:
            personal_number = parsed.get("Личный номер", "")
            if not personal_number and "Личный номер" in data_text:
                personal_number = data_text.split("Личный номер:")[1].split("\n")[0].strip()
            
            if personal_number:
                cursor = self.conn.cursor()
                cursor.execute("SELECT * FROM employees WHERE personal_number = ?", (personal_number,))
                if cursor.fetchone():
                    QMessageBox.information(self, "Уже существует", f"Сотрудник {personal_number} уже есть в базе.")
                else:
                    reply = QMessageBox.question(self, "Добавление", 
                                                f"Добавить сотрудника?\n\n{personal_number} — {parsed.get('ФИО', 'Не указано')}",
                                                QMessageBox.Yes | QMessageBox.No)
                    if reply == QMessageBox.Yes:
                        cursor.execute('''
                            INSERT INTO employees 
                            (personal_number, last_name, first_name, patronymic, birth_date)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            personal_number,
                            parsed.get("Фамилия", ""),
                            parsed.get("Имя", ""),
                            parsed.get("Отчество", ""),
                            parsed.get("Дата рождения", "")
                        ))
                        self.conn.commit()
                        self.load_table()
                        QMessageBox.information(self, "Успешно", "Сотрудник добавлен из QR-кода!")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def load_table(self):
        search_text = ""
        if hasattr(self, "search_edit"):
            search_text = self.search_edit.text().strip()

        cursor = self.conn.cursor()

        if search_text:
            cursor.execute("""
                SELECT * FROM employees
                WHERE personal_number LIKE ?
                   OR last_name LIKE ?
                   OR first_name LIKE ?
                   OR patronymic LIKE ?
                ORDER BY last_name
            """, (
                f"%{search_text}%",
                f"%{search_text}%",
                f"%{search_text}%",
                f"%{search_text}%"
            ))
        else:
            sort_mode = self.sort_combo.currentText()
            order_by = "id" if sort_mode == "По порядку добавления" else                        "last_name" if sort_mode == "По фамилии (А-Я)" else "personal_number"
            cursor.execute(f"SELECT * FROM employees ORDER BY {order_by}")

        rows = cursor.fetchall()

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(val) if val is not None else ""))

        self.status.setText(f"Всего записей: {len(rows)}")

    def generate_qr(self):
        if self.table.currentRow() < 0:
            QMessageBox.warning(self, "Внимание", "Выберите сотрудника!")
            return
        row = self.table.currentRow()
        data = f"Личный номер: {self.table.item(row, 1).text()}\n" \
               f"ФИО: {self.table.item(row, 2).text()} {self.table.item(row, 3).text()} {self.table.item(row, 4).text()}\n" \
               f"Дата рождения: {self.table.item(row, 5).text()}"
        
        dialog = QRDialog(data, self)
        dialog.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())