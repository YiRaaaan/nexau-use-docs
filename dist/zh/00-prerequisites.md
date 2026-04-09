# 开始之前

本页列出后续 10 章所需的全部前置工具。**请全部安装完成后再进入第 1 章**，避免操作过程中被 `command not found` 打断节奏。

## 必备组件

| 组件 | 用途 | 检查命令 |
|---|---|---|
| Python ≥ 3.10 | 运行 Agent 本身 | `python3 --version` |
| `uv` 或 `pip` | 安装 NexAU 和依赖 | `uv --version` |
| `sqlite3` CLI | 第 1 章直接调用它执行 SQL | `sqlite3 --version` |
| 一个 LLM API key | 任意 OpenAI 兼容端点均可 | —— |

以下逐项说明安装方式。

## Python

NexAU 要求 Python 3.10 及以上。

- **macOS**：`brew install python@3.12`，或使用 [pyenv](https://github.com/pyenv/pyenv) 安装。
- **Linux**（Debian / Ubuntu）：`sudo apt-get install python3.12 python3.12-venv`。
- **Windows**：从 [python.org](https://www.python.org/downloads/) 下载安装，安装时勾选 "Add Python to PATH"。或使用 `winget install Python.Python.3.12`。

安装完成后：

```bash
python3 --version
# Python 3.12.x
```

## uv

`uv` 是新一代 Python 包管理工具，速度显著快于 `pip`。推荐安装方式：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

也可直接 `pip install uv`。若安装失败，后续所有 `uv pip install` / `uv run` 均可替换为 `pip install` / `python`。

## 安装 NexAU

直接从 GitHub Release 下载 wheel 安装，无需克隆源码：

```bash
# 新建并进入教程工作目录
mkdir nexau-tutorial && cd nexau-tutorial

# 创建虚拟环境（可选，但推荐）
uv venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 安装 NexAU
uv pip install https://github.com/nex-agi/NexAU/releases/download/v0.4.1/nexau-0.4.1-py3-none-any.whl

# 顺手装上教程需要的 python-dotenv
uv pip install python-dotenv
```

> 若未使用 `uv`，把所有 `uv pip install` 替换为 `pip install` 即可。

验证安装：

```bash
python3 -c "from importlib.metadata import version; print(version('nexau'))"
# 应输出版本号，例如 0.4.1
```

**本教程后续所有命令都从 `nexau-tutorial/` 目录发出。** 后续章节会在该目录下逐步构建 `enterprise_data_agent/` 子目录。

## sqlite3 CLI

仅第 1 章直接使用（后续章节改用 Python 自带的 `sqlite3` 库），但建议提前安装以免后续返工。

- **macOS**：系统自带，无需额外安装。
- **Linux**（Debian / Ubuntu）：`sudo apt-get install sqlite3`。
- **Windows**：`winget install SQLite.SQLite`，或从 [sqlite.org/download.html](https://sqlite.org/download.html) 下载 `sqlite-tools-win-*.zip`，解压后将目录加入 `PATH`。

```bash
sqlite3 --version
```

## LLM API key

本教程默认使用 `nex-agi/deepseek-v3.1-nex-1` 模型，但**任何 OpenAI 兼容端点**均可运行——OpenAI、Azure OpenAI、Together、Groq、OpenRouter、本地 vLLM 皆可。需要准备以下四项：

- `LLM_MODEL` —— 模型名，例如 `gpt-4o-mini` / `claude-sonnet-4-5` / `nex-agi/deepseek-v3.1-nex-1`
- `LLM_BASE_URL` —— API 入口，例如 `https://api.openai.com/v1`
- `LLM_API_KEY` —— 你的密钥
- `LLM_API_TYPE` —— 协议类型，例如 `openai_chat_completion`（默认）、`anthropic_chat_completion`、`gemini_rest`

第 1 章将指导你把这四项写入 `.env` 文件。

## 检查清单

进入第 1 章前，以下命令应当全部成功执行：

```bash
python3 --version                           # ≥ 3.10
uv --version                                # 或 pip --version
python3 -c "from importlib.metadata import version; print(version('nexau'))"  # 应输出版本号
sqlite3 --version
```

此外，需要准备好一个可用的 LLM API key。

准备完毕，进入 [第 1 章](./01-bash-nl2sql.md)。
