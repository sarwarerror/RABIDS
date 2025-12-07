import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt5.QtGui import QFont


class DocsWidget(QWidget):
    """Documentation tab widget."""
    
    def __init__(self, script_dir, parent=None):
        super().__init__(parent)
        self.script_dir = script_dir
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        subtitle_font = QFont()
        subtitle_font.setPointSize(9)

        self.docs_text = QTextEdit()
        self.docs_text.setFont(subtitle_font)
        self.docs_text.setReadOnly(True)

        # Embedded documentation (previously in DOC.md)
        DOC_CONTENT = """
**RABIDS: Modules, Tabs & Settings**

This document summarizes the purpose of each module in `MODULE/`, the function of each UI tab in `TABS/`, and the configuration settings surfaced by the application. The intent is to provide a code-oriented reference for maintainers and reviewers. This file intentionally avoids step-by-step operational advice or guidance that could be used to misuse the code.

**Legal / Ethical Use:**
- **NOTE:** This repository contains code that can be used to produce offensive tooling. Use, modification, or deployment must occur only in controlled, legal, authorized environments (research labs, red-team engagements with written consent, or education). The author and maintainers are not responsible for misuse.

**Contents**
- **Modules:** Brief description of each file in `MODULE/`.
- **Tabs:** Explanation of each tab widget in `TABS/` and the UI controls they expose.
- **Settings & Persistence:** Where settings live and how widgets expose configuration.

**Modules (folder `MODULE/`)**
- **`ctrlvamp.nim`**: High-level description: a module that targets clipboard contents to replace cryptocurrency addresses. Key concepts: collects clipboard text, compares for known address formats, and replaces with attacker-provided addresses. Configurable aspects (in the Builder UI) typically include persistence and target patterns.
- **`dumpster.nim`**: High-level description: collects and archives files from a specified directory into a single archive (a “dumpster”). Configurable items include input directory, output/archive name and possibly file filters.
- **`ghostintheshell.nim`**: High-level description: a reverse shell / remote access backdoor that uses an out-of-band transport. The UI provides a Command & Control tab to interact with this module.
- **`krash.nim`**: High-level description: an encryption module (ransomware-style). The UI provides a decryptor builder for artifacts produced by this module (key, IV, extension). The decryptor builder accepts values such as encryption key, IV, extension, target OS/arch, and exe name.
- **`poof.nim`**: High-level description: recursively deletes files from a target directory. Typical configuration: target directory and any safe/ignore patterns.
- **`undeleteme.nim`**: High-level description: persistence helper; sets up autorun/persistence and may interact with security tools settings. Configurable: persistence toggle, optional defender exclusion flags.
- **`bankruptsys.nim`**: High-level description: an integration-style module intended to demonstrate interactions with ATM middleware (XFS). This module represents a specialized payload shape and will include parameters for target systems and middleware interactions.
- **`winkrashv2.nim`**: High-level description: an alternate ransomware implementation that uses low-level Windows techniques (e.g., direct syscalls) to attempt to avoid API instrumentation. Configurable options may mirror `krash`.
- **`poof.nim` / `dumpster.nim` etc.**: Many modules share common option types (paths, file lists, booleans for persistence). The Builder exposes those options — see the Builder section below.
- **`shaihulud.asm`**: Assembly utility that enumerates files and can modify `package.json` files it finds (the file in this repository traverses user profile directories looking for `package.json`, examines `preinstall`, and patches it before running a system command). This is low-level native code intended for platform-specific operations. (This file contains direct filesystem and process interactions; maintainers should review it carefully before reuse.)

**UI Tabs (folder `TABS/`)**
Each UI tab is implemented as a widget class. The main application (`main.py`) imports these widgets and adds them to the main `QTabWidget` in the following order.

- **`BUILDER` — `TABS/builder/builder.py`**
  - **Purpose:** Select and chain modules, configure module-specific options, and configure build options.
  - **Key controls:**
    - **Module selection combo:** choose from available modules and add to the module chain.
    - **Module chain table:** reorder or remove modules; the order determines how modules are combined.
    - **Module options pane:** per-module fields created from `module_options` provided by configuration (fields may be text inputs or checkboxes for booleans like `persistence` or `defenderExclusion`).
    - **Build Options:** `EXE NAME`, `OS` (`windows`, `linux`, `macos`), `PROCESSOR` (`amd64`, `arm64`), `HIDE CONSOLE` (Windows-only), `OBFUSCATE` and `OLLVM` flags.
    - **BUILD button:** Emits a build request; the main app builds a command line invoking `compiler.py`.
  - **Signals / API:** Emits `build_requested` with a build configuration dict; the main app listens and spawns `compiler.py` in a thread.

- **`OUTPUT` — `TABS/output/output.py`**
  - **Purpose:** Show build logs and provide access to the `LOOT/` folder where build artifacts or extracted files are stored.
  - **Key controls:**
    - **Log area:** receives messages from other parts of the app (build thread, installers, C2). Use `log_message()` to append color-coded messages.
    - **LOOT list and controls:** refresh and open the `LOOT/` directory in the OS file manager; lists files by modification time.

- **`C2` — `TABS/c2/c2.py`**
  - **Purpose:** Command-and-control interface for interacting with remote agents implemented by the `ghostintheshell` module.
  - **Key controls:** `Connect` (emits connect request), command input, `Send` button, and a log area. The widget emits `connect_requested` and `send_message_requested` signals.

- **`KRASH` — `TABS/krash/krash.py`**
  - **Purpose:** Build a standalone decryptor for files encrypted with the `krash` module; also displays a live list of encrypted devices reported via the configured HTTP listener.
  - **Key controls:** fields for `Key`, `IV`, `Extension` and build options (`EXE Name`, `OS`, `Processor`) and a `BUILD DECRYPTOR` button. Also includes controls to start/refresh a listener and a table of live encrypted devices.

- **`GARBAGE COLLECTOR` — `TABS/garbage/garbage.py`**
  - **Purpose:** Restore files from a `dumpster` archive created by the `dumpster` module.
  - **Key controls:** `Dumpster File Path` and `Destination Directory` inputs, `Browse...` dialogs, and `Restore` button. The widget emits `restore_requested(dumpster_file, output_dir)` when the user starts a restore.

- **`WHISPERS` — `TABS/whispers/whispers.py`**
  - **Purpose:** Integrates with a Node.js bridge (`whatsapp_bridge.js`) to control WhatsApp Web for sending messages or reaction-spam testing; includes optional plotting when `matplotlib` is available.
  - **Key controls:** `Start Client` (launches `node whatsapp_bridge.js`), QR code display, phone number input, `DELAY` (ms), `START SPAM` / `STOP SPAM` controls, and a small log + optional graph view. The widget communicates with a background `WhatsAppWebThread` which reads JSON lines from the Node bridge.
  - **Dependencies:** Node.js + the local Node bridge script. The tab exposes `get_settings()` and `load_settings()` for persistence.

- **`DOCUMENTATION` — `TABS/docs/docs.py`**
  - **Purpose:** Embedded in-app documentation; the widget displays a Markdown string describing the project and basic usage. This content is read-only and serves as a quick reference for users of the GUI.

- **`SETTINGS` — `TABS/settings/settings.py`**
  - **Purpose:** Configure application-level settings and install helper tools (Nim, Rust, Python packages, Nimble packages, Rust targets, Docker image for obfuscation).
  - **Key controls:**
    - **`HTTP Server URL`** (`server_url` input): the URL used by modules/C2/daemon features for callbacks (default visible fallback is `http://localhost:8080`).
    - **Dependency Installation group:** Buttons to install or bootstrap runtimes:
      - `Install Nim` — triggers `install_nim_tool_requested`
      - `Install Rust` — triggers `install_rust_tool_requested`
      - `Install Python Packages` — triggers `install_python_requested`
      - `Install Nimble Packages` — triggers `install_nimble_requested`
      - `Install Rust Targets` — triggers `install_rust_targets_requested`
      - `Pull Docker Image` — triggers `install_docker_requested` (used for the optional obfuscator image)
    - **Save Settings button:** emits `save_requested` so the main app can persist settings.
  - **Signals / API:** Exposes `get_settings()` (returns a dict like `{'server_url': ...}`) and `load_settings(settings)` to populate the UI.

**Configuration Persistence**
- **Where settings are stored:** The application reads and writes JSON to `rabids_config.json` in the project root. Widgets provide `get_settings()` and `load_settings()` helper methods which the main app calls when saving or loading settings.
- **Builder module options:** The Builder reads a `module_options` mapping from the application config (presented to `BuilderWidget` during initialization). Typical option keys observed in UI code include:
  - `nimFile`, `embedFiles`, `dumpsterFile`, `inputDir`, `outputDir`, `targetDir` (file/directory paths)
  - `persistence`, `defenderExclusion` (boolean flags represented as checkboxes)
  - Arbitrary module-specific values (the Builder collects these and passes them to the build step under `option_values`)

**How the Build Flow Works (high-level, non-actionable)**
- The Builder tab collects the selected module chain and option values and emits a `build_requested` event with a dict that includes `selected_modules`, build options, and `option_values`.
- The main application (`main.py`) receives this event and constructs a command line that invokes `compiler.py` with flags (e.g., `--module=...`, `--exe_name=...`) and runs it in a background thread so the UI remains responsive.

**Signals & Integration Points (for maintainers)**
- `BuilderWidget.build_requested` → handled in `main.py` by `handle_build()` which starts `BuildThread`.
- `OutputWidget.log_message` → used by other widgets to append messages to the central log area.
- `SettingsWidget` emits install signals (e.g., `install_nim_tool_requested`) which `main.py` maps to `get_install_cmd()` and runs in `DependencyInstallerThread`.

**Safety & Review Notes (for maintainers and reviewers)**
- Several modules perform low-level or privileged operations (file system enumeration/modification, network callbacks, process invocation). Treat these areas as high-risk and review them closely before building or running on any system.
- The repository includes cross-language code (Nim, Rust wrappers, and assembly). Ensure toolchains are isolated and sandboxed when compiling or testing.
- The `WHISPERS` tab starts an external Node process (`whatsapp_bridge.js`) and expects streaming JSON output. Be mindful of dependencies (Node, `qrcode`, `matplotlib`) when testing.

**Quick file pointers**
- Main entry: `main.py` — application bootstrap, tab wiring, config load/save, and install/build orchestration.
- Config file: `rabids_config.json` — JSON persisted settings.
- Builder UI: `TABS/builder/builder.py` — module selection, option collection, build config.
- Output UI: `TABS/output/output.py` — build logs, LOOT folder view.
- C2 UI: `TABS/c2/c2.py` — connect/send interface for reverse shell module.
- Krash UI: `TABS/krash/krash.py` — decryptor builder and live device view.
- Garbage UI: `TABS/garbage/garbage.py` — restore from dumpster archives.
- Whispers UI + bridge: `TABS/whispers/whispers.py`, `TABS/whispers/whatsapp_bridge.js`, `TABS/whispers/package.json`.
- Modules: `MODULE/*.nim`, `MODULE/shaihulud.asm` — core payload sources and native utilities.
"""

        self.docs_text.setMarkdown(DOC_CONTENT)
        self.docs_text.setStyleSheet("background-color: #0e0e0e;")
        layout.addWidget(self.docs_text)
