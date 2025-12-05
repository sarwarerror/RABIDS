**RABIDS** (Roving Autonomous Bartmoss Interface Drones) is a comprehensive framework for building custom offensive security payloads. To chain together various modules—such as ransomware, clipboard hijackers, and persistence loaders—into a single, compiled executable for Windows, Linux, or macOS.

This tool is designed for security researchers, red teamers, and educational purposes to simulate advanced adversaries and study malware behavior in a controlled environment.

## Getting Started

1.  **Install GUI Dependency:**

    The user interface requires `PyQt5` and `discord`. Install them using pip:

    ```bash
    pip install PyQt5 discord
    ```

2.  **Run the Application:**

    ```bash
    python3 main.py
    ```

## Features

- **Modular Payload Creation:** Chain multiple modules together to create sophisticated, multi-stage payloads.
- **Cross-Platform Compilation:** Build executables for Windows, Linux, and macOS, with support for both `amd64` and `arm64` architectures.
- **Optional Obfuscation:** Leverage a Dockerized Obfuscator-LLVM toolchain to apply advanced obfuscation techniques to Windows payloads.
- **Intuitive Graphical User Interface:** A clean and modern UI makes it easy to select modules, configure options, and build payloads without writing any code.
- **Standalone Tooling:** Includes dedicated tabs for building a file decryptor (`UNKRASH`) and a file restorer (`Garbage Collector`).
- **In-Memory Execution:** On Windows, payloads are wrapped in a Rust loader that executes the core Nim binary directly from memory, helping to evade basic static analysis.
- **Integrated C2:** A dedicated tab provides a Command & Control interface for interacting with the `ghostintheshell` reverse shell module.

## Payload Architecture

RABIDS payloads are constructed with a multi-language approach to maximize flexibility and evasiveness:

- **Core Logic (Nim):** The primary functionality of each module is written in Nim, a high-performance, statically-typed language that compiles to native C, C++, or JavaScript. This allows for fast, efficient, and dependency-free binaries.
- **Windows Wrapper (Rust):** For Windows targets, the compiled Nim payload is embedded within a Rust-based loader. This loader is responsible for executing the Nim binary directly from memory (`memexec`), which can bypass some filesystem-based security controls. The Rust wrapper also handles the embedding of necessary DLLs and other files, ensuring the final executable is self-contained.

## Available Modules

- **`ctrlvamp`**: Hijacks clipboard crypto addresses (BTC, ETH, BEP-20, SOL).
- **`dumpster`**: Collects files from a directory and archives them into a single file.
- **`ghostintheshell`**: Provides a reverse shell over Discord for remote access.
- **`krash`**: A ransomware module that encrypts files using AES and can report success via Discord.
- **`poof`**: Recursively deletes all files and folders from a target directory.
- **`undeleteme`**: Gains persistence and can add a Windows Defender exclusion.
- **`bankruptsys`**: An ATM malware module designed to dispense cash by interacting with the XFS middleware.
- **`winkrashv2`**: A stealthy ransomware module for Windows that uses direct syscalls for file operations to evade common API hooking.
- **`byovf`**: "Bring Your Own File" - A flexible module that allows you to embed your own Nim code and secondary files (like drivers or DLLs) into the payload.

## Documentation & Setup

All documentation, including detailed installation instructions, setup guides, and in-depth module descriptions, can be found within the application itself under the **"DOCUMENTATION" tab**.

This in-app guide provides everything you need to know to:

- Install dependencies (Python, Nim, Rust, Docker).
- Configure build options.
- Understand each module and its parameters.
- Build and find your payloads.

## Legal Disclaimer

This tool is intended for **educational purposes, authorized security testing, and red team operations only**. The author is not responsible for any misuse, damage, or legal consequences that may result from the use of this software. You must have explicit, written permission from the target system's owner before using this tool. Unauthorized use is strictly prohibited and may be illegal.

## License

MIT License. See the `LICENSE` file for details.
