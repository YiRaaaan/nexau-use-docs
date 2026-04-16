# Database Agent Cookbook

> 写 Skill + 写 System Prompt = 一个能用的数据库 Agent。

本 Cookbook 教你如何在 NexAU 平台上构建数据库 Agent。核心内容是两件事：**编写 Skill**（让模型了解你的数据库）和**编写 System Prompt**（定义 Agent 的工作流）。

## 开始阅读

进入 [**开发者指南**](./developer_guide/)，按章节顺序阅读：

| 章节 | 内容 | 阅读时间 |
|---|---|---|
| [01 - 快速开始](./developer_guide/01-quick-start.md) | 3 个文件跑起来一个 Agent | 5 分钟 |
| [02 - 编写 Skill](./developer_guide/02-skill-writing.md) | **核心章节**——如何写 SKILL.md 提升问答准确率 | 15 分钟 |
| [03 - 编写 System Prompt](./developer_guide/03-system-prompt.md) | 如何写系统提示词 | 10 分钟 |
| [04 - Agent 配置参考](./developer_guide/04-agent-config.md) | agent.yaml + nexau.json 字段说明 | 5 分钟 |

## 完整示例

[`developer_guide/examples/bookstore_agent/`](./developer_guide/examples/bookstore_agent/) 包含一个可直接复制使用的书店数据库 Agent（3 张表的 Skill + System Prompt + Agent 配置）。
