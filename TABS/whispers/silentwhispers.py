from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QGroupBox, QTextEdit, QComboBox, QSpinBox
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
import os
import subprocess
import json
import time
try:
    import matplotlib
    matplotlib.use('Qt5Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
class WhatsAppWebThread(QThread):
    """Thread for interacting with WhatsApp Web Node.js bridge"""
    log_signal = pyqtSignal(str, str)
    qr_signal = pyqtSignal(str)
    status_signal = pyqtSignal(bool)
    spam_data_signal = pyqtSignal(dict)  
    def __init__(self, script_dir):
        super().__init__()
        self.script_dir = script_dir
        self.process = None
        self.running = False
    def run(self):
        self.running = True
        bridge_script = os.path.join(os.path.dirname(__file__), 'whatsapp_bridge.js')
        try:
            node_version = subprocess.check_output(['node', '--version'], text=True).strip()
            node_path = subprocess.check_output(['which', 'node'], text=True).strip()
            self.log_signal.emit(f"[*] Node.js found: {node_version} at {node_path}", "system")
        except Exception as e:
            self.log_signal.emit(f"[Error] Check node failed: {e}", "error")
        self.log_signal.emit(f"[*] Starting bridge script: {bridge_script}", "system")
        cwd = os.path.dirname(bridge_script)
        self.process = subprocess.Popen(
            ['node', bridge_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd  
        )
        try:
            time.sleep(1) 
            gone = self.process.poll()
            if gone is not None:
                stderr_output = self.process.stderr.read()
                self.log_signal.emit(f"[Error] Process crashed (code {gone}): {stderr_output}", "error")
                self.status_signal.emit(False)
                return
        except Exception as e:
            self.log_signal.emit(f"[Error] Monitor failed: {e}", "error")
        while self.running and self.process.poll() is None:
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                data = json.loads(line.strip())
                self._handle_bridge_message(data)
            except json.JSONDecodeError:
                if line.strip():
                    self.log_signal.emit(f"[Bridge] {line.strip()}", "system")
        self.log_signal.emit("[*] WhatsApp Web client stopped.", "system")
        self.status_signal.emit(False)
    def _handle_bridge_message(self, data):
        msg_type = data.get('type')
        message = data.get('message', '')
        if msg_type == 'qr':
            self.log_signal.emit(f"[*] {message}", "system")
            self.qr_signal.emit(data.get('data'))
        elif msg_type == 'ready':
            self.log_signal.emit(f"[+] {message}", "success")
            self.status_signal.emit(True)
        elif msg_type == 'authenticated':
            self.log_signal.emit(f"[+] {message}", "success")
        elif msg_type == 'success':
            self.log_signal.emit(f"[+] {message}", "success")
        elif msg_type == 'error':
            self.log_signal.emit(f"[-] {message}", "error")
        elif msg_type == 'info':
            self.log_signal.emit(f"[*] {message}", "system")
        elif msg_type == 'status':
            is_ready = data.get('ready', False)
            self.status_signal.emit(is_ready)
        elif msg_type == 'ack':
            ack = data.get('ack', 0)
            ack_name = data.get('ackName', 'UNKNOWN')
            time_formatted = data.get('timeSinceSentFormatted', '?')
            if ack == 1:  
                self.log_signal.emit(f"[✓] Single tick after {time_formatted}", "system")
            elif ack == 2:  
                self.log_signal.emit(f"[✓✓] Double tick after {time_formatted}", "success")
            elif ack == 3:  
                self.log_signal.emit(f"[✓✓] Read (blue tick) after {time_formatted}", "success")
            elif ack == 4:  
                self.log_signal.emit(f"[▶] Played after {time_formatted}", "success")
            elif ack == -1:  
                self.log_signal.emit(f"[✗] Message error after {time_formatted}", "error")
            else:
                self.log_signal.emit(f"[*] ACK {ack_name} after {time_formatted}", "system")
        elif msg_type == 'ack_timing':
            single_tick_ms = data.get('singleTickMs', 0)
            double_tick_ms = data.get('doubleTickMs', 0)
            single_to_double_ms = data.get('singleToDoubleMs', 0)
            self.log_signal.emit(f"[⏱] Timing: Single tick @ {single_tick_ms}ms → Double tick @ {double_tick_ms}ms", "system")
            self.log_signal.emit(f"[⏱] Single→Double: {single_to_double_ms}ms ({single_to_double_ms/1000:.2f}s)", "success")
            self.spam_data_signal.emit({
                'type': 'ack_timing',
                'singleTickMs': single_tick_ms,
                'doubleTickMs': double_tick_ms,
                'singleToDoubleMs': single_to_double_ms
            })
        elif msg_type == 'spam_start':
            self.log_signal.emit(f"[🚀] {message}", "success")
            self.spam_data_signal.emit({'type': 'spam_start', 'totalCount': data.get('totalCount', 0)})
        elif msg_type == 'spam_iteration':
            index = data.get('index', 0)
            total = data.get('totalCount', 0)
            send_time = data.get('sendTimeMs', 0)
            react_add = data.get('reactionAddTimeMs', 0)
            react_remove = data.get('reactionRemoveTimeMs', 0)
            iteration_time = data.get('iterationTimeMs', 0)
            self.log_signal.emit(f"[{index}/{total}] Send: {send_time}ms | React+: {react_add}ms | React-: {react_remove}ms | Total: {iteration_time}ms", "system")
            self.spam_data_signal.emit({
                'type': 'spam_iteration',
                'index': index,
                'sendTimeMs': send_time,
                'reactionAddTimeMs': react_add,
                'reactionRemoveTimeMs': react_remove,
                'iterationTimeMs': iteration_time
            })
        elif msg_type == 'spam_complete':
            self.log_signal.emit(f"[✅] {message}", "success")
            self.spam_data_signal.emit({'type': 'spam_complete'})
        elif msg_type == 'spam_error':
            self.log_signal.emit(f"[❌] {message}", "error")
    def send_command(self, command):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(json.dumps(command) + '\n')
                self.process.stdin.flush()
            except Exception as e:
                self.log_signal.emit(f"[Error] Failed to send command: {e}", "error")
        else:
             self.log_signal.emit("[Error] WhatsApp client is not running.", "error")
    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
class SilentWhispersWidget(QWidget):
    """Silent Whispers - Clean WhatsApp Reaction Spam Tool"""
    def __init__(self, script_dir, parent=None):
        super().__init__(parent)
        self.script_dir = script_dir
        self.whatsapp_thread = None
        self.is_spamming = False
        self.spam_data = {'indices': [], 'iteration_times': []}
        self.init_ui()
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        top_section = QHBoxLayout()
        top_section.setSpacing(15)
        qr_container = QVBoxLayout()
        qr_container.setSpacing(8)
        self.qr_label = QLabel("Scan QR Code")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(160, 160)
        self.qr_label.setStyleSheet("""
            QLabel {
                border: 1px solid #2a2a2e;
                border-radius: 10px;
                background-color: #1D1D1F;
                color: #666;
                font-size: 11px;
            }
        """)
        qr_container.addWidget(self.qr_label)
        self.wa_web_btn = QPushButton("Start Client")
        self.wa_web_btn.setFont(subtitle_font)
        self.wa_web_btn.setFixedWidth(160)
        self.wa_web_btn.clicked.connect(self.toggle_whatsapp_client)
        qr_container.addWidget(self.wa_web_btn)
        self.wa_web_status = QLabel("Disconnected")
        self.wa_web_status.setAlignment(Qt.AlignCenter)
        self.wa_web_status.setStyleSheet("color: #FF3B30; font-size: 10px;")
        qr_container.addWidget(self.wa_web_status)
        top_section.addLayout(qr_container)
        controls_container = QVBoxLayout()
        controls_container.setSpacing(8)
        phone_label = QLabel("PHONE NUMBER")
        phone_label.setFont(subtitle_font)
        controls_container.addWidget(phone_label)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("923001234567")
        self.phone_input.setFont(subtitle_font)
        controls_container.addWidget(self.phone_input)
        delay_row = QHBoxLayout()
        delay_label = QLabel("DELAY")
        delay_label.setFont(subtitle_font)
        self.spam_delay_input = QSpinBox()
        self.spam_delay_input.setMinimum(50)
        self.spam_delay_input.setMaximum(5000)
        self.spam_delay_input.setValue(100)
        self.spam_delay_input.setSuffix(" ms")
        self.spam_delay_input.setFont(subtitle_font)
        delay_row.addWidget(delay_label)
        delay_row.addWidget(self.spam_delay_input, 1)
        controls_container.addLayout(delay_row)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.spam_btn = QPushButton("START SPAM")
        self.spam_btn.setFont(subtitle_font)
        self.spam_btn.clicked.connect(self.start_reaction_spam)
        self.spam_btn.setStyleSheet("""
            QPushButton {
                background-color: #34C759;
                color: white;
                border-radius: 10px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #2DB84D; }
            QPushButton:disabled { background-color: #1D1D1F; color: #555; }
        """)
        btn_row.addWidget(self.spam_btn)
        self.stop_spam_btn = QPushButton("STOP SPAM")
        self.stop_spam_btn.setFont(subtitle_font)
        self.stop_spam_btn.clicked.connect(self.stop_reaction_spam)
        self.stop_spam_btn.setEnabled(False)
        self.stop_spam_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF3B30;
                color: white;
                border-radius: 10px;
                padding: 8px;
            }
            QPushButton:hover { background-color: #E0342B; }
            QPushButton:disabled { background-color: #1D1D1F; color: #555; }
        """)
        btn_row.addWidget(self.stop_spam_btn)
        controls_container.addLayout(btn_row)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(60)
        self.log_output.setFont(subtitle_font)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1D1D1F;
                border-radius: 5px;
                color: #888;
                font-size: 9px;
                padding: 4px;
            }
        """)
        controls_container.addWidget(self.log_output)
        top_section.addLayout(controls_container, 1)
        main_layout.addLayout(top_section)
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(8, 3), dpi=100, facecolor='#111113')
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            self._style_graph()
            self.figure.tight_layout(pad=2)
            main_layout.addWidget(self.canvas, 1)
            self.clear_graph_btn = QPushButton("Clear Graph")
            self.clear_graph_btn.setFont(subtitle_font)
            self.clear_graph_btn.clicked.connect(self.clear_graph)
            main_layout.addWidget(self.clear_graph_btn)
        else:
            no_graph = QLabel("Install matplotlib for graph")
            no_graph.setStyleSheet("color: #555;")
            no_graph.setAlignment(Qt.AlignCenter)
            main_layout.addWidget(no_graph)
        self.message_input = QTextEdit()
        self.message_input.hide()
        self.add_reaction_check = QComboBox()
        self.add_reaction_check.addItems(["No Reaction", "True Reaction"])
        self.add_reaction_check.hide()
        self.send_btn = QPushButton()
        self.send_btn.hide()
        self.log_message("[+] Ready", "success")
    def _style_graph(self):
        """Apply dark theme to graph matching main app"""
        self.ax.set_facecolor('#1D1D1F')
        self.ax.tick_params(colors='#666', labelsize=8)
        self.ax.xaxis.label.set_color('#888')
        self.ax.yaxis.label.set_color('#888')
        self.ax.set_xlabel('Iteration', fontsize=9)
        self.ax.set_ylabel('Time (ms)', fontsize=9)
        for spine in self.ax.spines.values():
            spine.set_color('#2a2a2e')
        self.ax.grid(True, alpha=0.1, color='#444')
    def log_message(self, message, msg_type="system"):
        """Add a message to the log output"""
        color_map = {
            "success": "#00B85B",
            "error": "#FF3B30",
            "system": "#00A9FD"
        }
        color = color_map.get(msg_type, "#e0e0e0")
        self.log_output.append(f'<span style="color: {color};">{message}</span>')
    def toggle_whatsapp_client(self):
        """Start or stop the WhatsApp Web client"""
        if self.whatsapp_thread and isinstance(self.whatsapp_thread, WhatsAppWebThread) and self.whatsapp_thread.isRunning():
            self.whatsapp_thread.stop()
            self.whatsapp_thread.wait()
            self.whatsapp_thread = None
            self.wa_web_status.setText("Status: Stopped")
            self.wa_web_btn.setText("Start WhatsApp Client")
            self.wa_web_btn.setStyleSheet("")
            self.qr_label.setText("Click Start to generate QR Code")
            self.qr_label.setPixmap(QPixmap()) 
        else:
            self.whatsapp_thread = WhatsAppWebThread(self.script_dir)
            self.whatsapp_thread.log_signal.connect(self.log_message)
            self.whatsapp_thread.qr_signal.connect(self.display_qr_code)
            self.whatsapp_thread.status_signal.connect(self.update_client_status)
            self.whatsapp_thread.spam_data_signal.connect(self.handle_spam_data)
            self.whatsapp_thread.start()
            self.wa_web_status.setText("Status: Starting...")
            self.wa_web_btn.setText("Stop WhatsApp Client")
            self.wa_web_btn.setStyleSheet("background-color: #d32f2f; color: white;")
    def display_qr_code(self, qr_data):
        """Generate and display QR code from data"""
        try:
            import qrcode
            from io import BytesIO
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qim = QPixmap()
            qim.loadFromData(buffer.getvalue(), "PNG")
            scaled_pixmap = qim.scaled(self.qr_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_label.setPixmap(scaled_pixmap)
            self.qr_label.setText("") 
        except Exception as e:
            self.log_message(f"Error generating QR: {e}", "error")
            self.qr_label.setText(f"Error: {str(e)}")
    def update_client_status(self, is_ready):
        if is_ready:
            self.wa_web_status.setText("Status: Connected & Ready")
            self.wa_web_status.setStyleSheet("color: #4caf50;")
            self.qr_label.setText("Connected to WhatsApp Web")
            self.qr_label.setPixmap(QPixmap())
        else:
            self.wa_web_status.setText("Status: Disconnected")
            self.wa_web_status.setStyleSheet("color: #f44336;")
    def send_whatsapp_message(self):
        """Send WhatsApp message using Node.js bridge"""
        phone_number = self.phone_input.text().strip()
        message = self.message_input.toPlainText().strip()
        add_reaction = self.add_reaction_check.currentIndex()
        if not phone_number:
            self.log_message("[-] Phone number is required!", "error")
            return
        if not message:
            self.log_message("[-] Message cannot be empty!", "error")
            return
        if not self.whatsapp_thread or not isinstance(self.whatsapp_thread, WhatsAppWebThread) or not self.whatsapp_thread.isRunning():
            self.log_message("[-] WhatsApp Web client is not running!", "error")
            self.log_message("[*] Click 'Start WhatsApp Client' and scan the QR code first", "system")
            return
        self.send_btn.setText("SENDING...")
        self.send_btn.setEnabled(False)
        self.log_output.clear()
        formatted_number = phone_number
        if not formatted_number.endswith("@c.us") and not formatted_number.endswith("@g.us"):
            formatted_number = f"{formatted_number}@c.us"
        self.log_message(f"[*] Sending message to {formatted_number}", "system")
        if add_reaction == 1:  
            self.whatsapp_thread.send_command({
                "action": "sendMessageAndReact",
                "chatId": formatted_number,
                "message": message,
                "emoji": "👍"
            })
        else:
            self.whatsapp_thread.send_command({
                "action": "sendMessage",
                "chatId": formatted_number,
                "message": message
            })
        QTimer.singleShot(1000, lambda: self.send_btn.setEnabled(True))
        QTimer.singleShot(1000, lambda: self.send_btn.setText("SEND MESSAGE"))
    def on_send_finished(self, success, message):
        """Handle completion of WhatsApp send operation"""
        pass
    def get_settings(self):
        """Get current settings for saving"""
        return {
            'phone_number': self.phone_input.text(),
            'message': self.message_input.toPlainText(),
            'add_reaction': self.add_reaction_check.currentIndex()
        }
    def load_settings(self, settings):
        """Load settings from saved configuration"""
        if 'phone_number' in settings:
            self.phone_input.setText(settings['phone_number'])
        if 'message' in settings:
            self.message_input.setPlainText(settings['message'])
        if 'add_reaction' in settings:
            self.add_reaction_check.setCurrentIndex(settings['add_reaction'])
    def toggle_reaction_spam(self):
        """Start or stop reaction spam"""
        if self.is_spamming:
            self.stop_reaction_spam()
        else:
            self.start_reaction_spam()
    def start_reaction_spam(self):
        """Start indefinite reaction spam on last message"""
        phone_number = self.phone_input.text().strip()
        delay = self.spam_delay_input.value()
        if not phone_number:
            self.log_message("[-] Phone number is required!", "error")
            return
        if not self.whatsapp_thread or not isinstance(self.whatsapp_thread, WhatsAppWebThread) or not self.whatsapp_thread.isRunning():
            self.log_message("[-] WhatsApp Web client is not running!", "error")
            self.log_message("[*] Click 'Start Client' and scan QR code first", "system")
            return
        self.is_spamming = True
        self.spam_btn.setText("SPAMMING...")
        self.spam_btn.setEnabled(False)
        self.stop_spam_btn.setEnabled(True)
        self.log_output.clear()
        self.clear_graph()
        formatted_number = phone_number
        if not formatted_number.endswith("@c.us") and not formatted_number.endswith("@g.us"):
            formatted_number = f"{formatted_number}@c.us"
        self.log_message(f"[*] Starting reaction spam on {formatted_number}", "system")
        self.log_message(f"[*] Delay: {delay}ms", "system")
        self.whatsapp_thread.send_command({
            "action": "startReactionSpam",
            "chatId": formatted_number,
            "delayMs": delay,
            "emoji": "thumbsup"
        })
    def stop_reaction_spam(self):
        """Stop the reaction spam"""
        if self.whatsapp_thread and isinstance(self.whatsapp_thread, WhatsAppWebThread) and self.whatsapp_thread.isRunning():
            self.whatsapp_thread.send_command({
                "action": "stopReactionSpam"
            })
        self.is_spamming = False
        self.spam_btn.setText("START SPAM")
        self.spam_btn.setEnabled(True)
        self.spam_btn.setStyleSheet("background-color: #34C759; color: white;")
        self.stop_spam_btn.setEnabled(False)
        self.send_btn.setEnabled(True)
    def handle_spam_data(self, data):
        """Handle spam data for graphing"""
        data_type = data.get('type')
        if data_type == 'spam_start':
            self.spam_data = {
                'indices': [],
                'iteration_times': []
            }
        elif data_type == 'spam_iteration':
            self.spam_data['indices'].append(data.get('index', 0))
            self.spam_data['iteration_times'].append(data.get('iterationTimeMs', 0))
            self.update_graph()
        elif data_type == 'spam_stopped' or data_type == 'spam_stopping':
            self.is_spamming = False
            self.spam_btn.setText("START SPAM")
            self.spam_btn.setEnabled(True)
            self.stop_spam_btn.setEnabled(False)
    def update_graph(self):
        """Update the matplotlib graph with current data"""
        if not MATPLOTLIB_AVAILABLE:
            return
        self.ax.clear()
        self._style_graph()
        indices = self.spam_data['indices']
        if indices and self.spam_data['iteration_times']:
            self.ax.scatter(indices, self.spam_data['iteration_times'], 
                          c='#FF6B9D', s=6, alpha=0.9, edgecolors='none', linewidths=0)
        self.canvas.draw()
    def clear_graph(self):
        """Clear the graph and reset data"""
        self.spam_data = {
            'indices': [],
            'iteration_times': []
        }
        if MATPLOTLIB_AVAILABLE:
            self.ax.clear()
            self._style_graph()
            self.canvas.draw()