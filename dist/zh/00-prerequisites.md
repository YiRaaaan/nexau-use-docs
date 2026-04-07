# 开始之前

这一页把后面 6 章会用到的所有前置工具列清楚。**全部装好之后再翻第 1 章**，中途撞 `command not found` 会非常烦。

## 你至少要有

| 组件 | 用来做什么 | 检查命令 |
|---|---|---|
| Python ≥ 3.10 | 跑智能体本身 | `python3 --version` |
| `uv` 或 `pip` | 安装 NexAU 和依赖 | `uv --version` |
| `dotenv` CLI | 把 `.env` 加载到环境变量，再跑后面的命令 | `dotenv --version` |
| `sqlite3` CLI | 第 1 章直接调它跑 SQL | `sqlite3 --version` |
| `git` | clone NexAU 源码 | `git --version` |
| 一个 LLM API key | 任意 OpenAI 兼容的端点都行 | —— |

下面挨个说怎么装。

## Python

NexAU 要求 Python 3.10 及以上。

- **macOS**:`brew install python@3.12`，或者用 [pyenv](https://github.com/pyenv/pyenv) 装。
- **Linux** (Debian / Ubuntu):`sudo apt-get install python3.12 python3.12-venv`。
- **Windows**:从 [python.org](https://www.python.org/downloads/) 装，安装时勾上 "Add Python to PATH"。也可以 `winget install Python.Python.3.12`。

装完后:

```bash
python3 --version
# Python 3.12.x
```

## uv

`uv` 是新一代的 Python 包管理工具，跑得比 `pip` 快很多。装它最简单:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

也可以直接 `pip install uv`。装不上也没关系——后面所有 `uv pip install` / `uv run` 都可以替换成 `pip install` / `python`。

## dotenv CLI

教程里所有运行命令都长这样:

```bash
dotenv run uv run nl2sql_agent/start.py "..."
```

`dotenv run` 是 `python-dotenv` 提供的 CLI，作用是先把当前目录的 `.env` 加载到环境变量，再跑后面的命令。安装时要带 `[cli]` extra:

```bash
uv pip install "python-dotenv[cli]"
# 或:pip install "python-dotenv[cli]"
```

验证:

```bash
dotenv --version
```

如果你不想装 `dotenv` CLI，也可以手动 `export $(cat .env | xargs)` 然后直接跑后半截命令。

## sqlite3 CLI

只有第 1 章会直接用它(后面章节会换成 Python 自带的 `sqlite3` 库)，但还是早装上比较省事。

- **macOS**:系统自带，通常不用装。
- **Linux** (Debian / Ubuntu):`sudo apt-get install sqlite3`。
- **Windows**:`winget install SQLite.SQLite`，或去 [sqlite.org/download.html](https://sqlite.org/download.html) 下 `sqlite-tools-win-*.zip`，解压后把目录加到 `PATH`。

```bash
sqlite3 --version
```

## LLM API key

教程默认用 `nex-agi/deepseek-v3.1-nex-1` 模型，但**任何 OpenAI 兼容端点**都能跑——OpenAI、Azure OpenAI、Together、Groq、OpenRouter、本地 vLLM 都行。准备好这三样:

- `LLM_MODEL` —— 模型名，比如 `gpt-4o-mini` / `claude-sonnet-4-5` / `nex-agi/deepseek-v3.1-nex-1`
- `LLM_BASE_URL` —— API 入口，比如 `https://api.openai.com/v1`
- `LLM_API_KEY` —— 你的 key

第 1 章会教你把这三个写进 `.env` 文件。

## 仓库长什么样

教程里会用到两个仓库，先理清它们的关系:

| 仓库 | 作用 | 你怎么用它 |
|---|---|---|
| **NexAU** ([github.com/nex-agi/NexAU](https://github.com/nex-agi/NexAU)) | 框架本体 | `git clone` 之后 `pip install -e .`,**整个教程的工作目录就是这个 `NexAU/`** |
| **nexau-use-docs**(就是这份文档的仓库) | 文档 + 一个完整可跑的 `nl2sql_agent/` 示例 + `enterprise.sqlite` 数据库 | 你只需要从这里下载两样东西:`enterprise.sqlite` 和(可选地)`nl2sql_agent/` 整套作为参考 |

教程的写法是**手把手在 `NexAU/` 下建一个新的 `nl2sql_agent/`**。如果你愿意一步步敲，就跟着第 1 章往下走;如果你想直接看成品，把 nexau-use-docs 仓库里的 `nl2sql_agent/` 文件夹整个复制到 `NexAU/` 下也能跑——两者文件结构是一样的。

## 检查清单

开始第 1 章前，这五条命令应该全部成功:

```bash
python3 --version    # ≥ 3.10
uv --version         # 或 pip --version
dotenv --version
sqlite3 --version
git --version
```

外加:你已经有一个 LLM API key 在手边。

OK，开 [第 1 章](./01-bash-nl2sql.md)。
