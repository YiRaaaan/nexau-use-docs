# NexAU 教程导读

这是一套围绕 **NexAU** 展开的实战教程。目标不是解释抽象概念，而是带你从零搭出一个真正可运行的 Agent：它能够理解自然语言问题、编写 SQL、查询企业数据库，并把结果用自然语言回答出来。

## 你会得到什么

- 一个可本地运行的企业数据分析 Agent
- 一套可复用的 NexAU 组织方式：`agent.yaml`、工具 schema、Python binding、Skills、中间件
- 一条从本地开发到云端部署、再到 API 接入与自动化发版的完整路径

## 推荐阅读顺序

教程分成两段：

1. **第 1–7 章**：把本地 Agent 从最小可用逐步打磨到生产可用，并扩展 PPT 生成能力
2. **第 8–10 章**：接入云端部署、外部 REST API 与自动化发版

建议按顺序阅读：

- [开始之前](./00-prerequisites.md)
- [第 1 章 · 从做一个企业数据分析 Agent 开始](./01-bash-nl2sql.md)
- [第 2 章 · 写自定义 SQL 工具](./02-custom-tool.md)
- [第 3 章 · 用 Skills 注入领域知识](./03-skills.md)
- [第 4 章 · 高级内置工具教学](./04-builtin-tools.md)
- [第 5 章 · 生产级中间件](./05-middlewares.md)
- [第 6 章 · 跨 Provider 运行](./llm-api-types.md)
- [第 7 章 · 加一个做 PPT 的技能](./07-pptx-agent.md)
- [第 8 章 · 部署到 NexAU Cloud](./08-deploy-cloud.md)
- [第 9 章 · 从外部 REST 调用 Cloud Agent](./09-cloud-api.md)
- [第 10 章 · 用 REST 自动化发版](./10-cloud-automation.md)

## 从哪里开始

若已安装 Python、`uv`、`sqlite3` 并准备好 LLM API Key，直接进入 [第 1 章](./01-bash-nl2sql.md)。
若尚未准备环境，先查看 [开始之前](./00-prerequisites.md)。
