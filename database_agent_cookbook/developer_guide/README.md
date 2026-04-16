# 数据库 Agent 开发者指南

> **写 Skill + 写 Prompt = 一个能用的数据库 Agent。**

本指南面向使用 NexAU 平台构建数据库 Agent 的开发者。你只需要编写 SKILL.md（领域知识）和 System Prompt（工作流），平台处理其余一切——SQL 工具、Skill 路由、对话管理。

---

## 前置条件

- NAC CLI 已安装
- 数据库已接入平台（SQL 查询是内置工具）
- LLM API 凭证已配置

## 目录

| 章节 | 内容 | 阅读时间 |
|---|---|---|
| [01 - 快速开始](./01-quick-start.md) | 3 个文件跑起来一个 Agent | 5 分钟 |
| [02 - 编写 Skill](./02-skill-writing.md) | **核心章节**——如何写 SKILL.md | 15 分钟 |
| [03 - 编写 System Prompt](./03-system-prompt.md) | 如何写系统提示词 | 10 分钟 |
| [04 - Agent 配置参考](./04-agent-config.md) | agent.yaml + nexau.json 字段说明 | 5 分钟 |

## 完整示例

[`examples/bookstore_agent/`](./examples/bookstore_agent/) 包含一个可直接运行的书店数据库 Agent，含 3 个表的 Skill、System Prompt 和 Agent 配置。

```bash
cp -r examples/bookstore_agent/ my_agent/
# 修改 Skills 和 System Prompt 以适配你的数据库
nac deploy
```

## 你不需要关心的事

以下内容由平台处理：

- **SQL 工具**——`execute_sql` 是内置工具，自动可用
- **Skill 路由**——框架根据 `description` 自动决定何时加载 Skill
- **对话管理**——多轮对话、上下文维护由框架处理
- **日志与监控**——由平台提供

---

## 相关资源

- **NexAU 完整教程**（含工具开发、框架原理）：[database_agent_cookbook.ipynb](../database_agent_cookbook.ipynb)
- **Skill 自动生成脚本**：[generate_skills.py](../generate_skills.py) — 从 SQLite 数据库自动生成 SKILL.md 框架
- **示例数据库创建**：[create_sample_db.py](../create_sample_db.py) — 创建书店示例数据库
