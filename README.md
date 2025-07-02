# 🫖 Teapot CLI

> *A Python CLI tool for package installation and configuration management*

Teapot CLI provides a clean interface for managing packages and configurations with modern Python tooling, using my Teapot project to store and retrieve system configurations.

## ✨ What's Inside

- 📦 **Package Management** - Install, search, list, and uninstall packages
- ⚙️ **Configuration System** - YAML-based config with environment variable support
- 🌐 **HTTP API Integration** - Built with HTTPX for reliable backend communication
- 🎨 **Rich Terminal Output** - Progress bars and formatted console display
- 🔧 **Type-Safe** - Built with Pydantic for robust data validation

## 🚀 Installation
**Install pip and python 3.13.5**
```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13
```

**Clone the repository and inside run pip in python3.13**
```bash
python3.13 -m pip install .
``` 
## 🔳 Development setup
**Development setup with uv:**
```bash
git clone <your-repo>
cd teapot-cli
uv sync --dev
```

**Or with pip:**
```bash
pip install -e ".[dev]"
```

## 💻 Usage

```bash
# Get started
python -m teapot_cli.main --help

# Package commands
teapot install <package>
teapot search <query>
teapot list
teapot uninstall <package>

# Configuration commands  
teapot config show
teapot config set <key> <value>
teapot config get <key>
teapot config edit
```

## 🛠️ Development

**Run tests:**
```bash
pytest
```

**Code quality:**
```bash
ruff check .
ruff format .
uvx ty
```

## 📁 Structure

```
teapot_cli/
├── commands/     # CLI command definitions
├── core/         # Business logic and API client
└── main.py      # Entry point
```

Configuration stored at: `~/.config/teapot-cli/config.yaml`