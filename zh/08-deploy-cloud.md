# 第 8 章 · 部署到 NexAU Cloud

**TL;DR**：将前 7 章的 `enterprise_data_agent/` 打成压缩包，在 NexAU Cloud 控制台**新建项目 → 上传版本 → 激活**，获得一个云端 Playground 和一对 API Key。他人无需安装 Python、uv、sqlite、Node 即可使用该智能体，零新代码。

> **本章假设你**已经跟着第 1–7 章把 `enterprise_data_agent/` 在本地跑通了。如果还没，先回到[第 1 章](./01-bash-nl2sql.md)。

## 为什么要上云

本地开发很顺手，但有三件事本地搞不定：

1. **别人用不了。** 同事要用得先装 Python / uv / sqlite / Node、配 API Key、克隆项目。一次还行，十次就烦了。
2. **没有 trace UI。** 终端只能看一行行 log。翻 trace、对比两个 run、按工具调用筛选——手动做太累。
3. **没有版本管理。** 改完一版 system prompt 想跟昨天那版对比，本地没有回滚机制。

Cloud 提供的是 **托管运行时 + Trace UI + 版本快照**。打包一次，拿到一个稳定的 Playground 链接和一对 API Key——之后改 prompt、换 provider，**项目本身不动**。

## 你最后会拿到什么

- Cloud 上的一个 **Project**，名字叫 `enterprise_data_agent`
- 一个激活的 **Version**（`v1.0.0`），所有调用都打到它
- 一个**云端 Playground 链接**，发给同事就能问"海淀区有多少家小型企业?"
- 一对 **Access Key + Secret Key**，从代码里调这个智能体

云上跑的是**同一份 `agent.yaml` + `system_prompt.md` + `bindings.py` + `skills/`**。运行时镜像里预装了第 7 章用到的 Node + `pptxgenjs`。

## 思路

NexAU Cloud 的部署模型是**项目（Project） → 版本（Version） → 激活（Activate）**：

| 概念 | 对应你本地的什么 |
|---|---|
| **Project** | 一个智能体的"名字空间"。`enterprise_data_agent` 是一个 project，以后再写一个 `customer_support_agent` 就是另一个 |
| **Version** | 一次打包上传的快照。改 prompt 或 binding 就发一个新 Version，旧的能回滚 |
| **Activate** | 把某个 Version 设为"当前生效的"。Playground 链接和 API Key 永远打到这个激活版本 |

**没有 git push、没有 CI**——就是在控制台上拖一个 `.tar.gz`。

## 第 1 步：打包你的项目

回到 `nexau-tutorial/`，把 `enterprise_data_agent/` 打成一个 `.tar.gz`：

```bash
cd NexAU

# 别把 venv、缓存、本地数据库带上
tar --exclude='enterprise_data_agent/__pycache__' \
    --exclude='enterprise_data_agent/.venv' \
    --exclude='enterprise_data_agent/output' \
    -czf enterprise_data_agent-v1.0.0.tar.gz enterprise_data_agent/
```

> **Windows / 没有 tar?** 用 `zip -r enterprise_data_agent-v1.0.0.zip enterprise_data_agent -x "enterprise_data_agent/__pycache__/*" "enterprise_data_agent/output/*"`，Cloud 同时支持 `.tar.gz` 和 `.zip`。

验证一下里面有该有的东西：

```bash
tar -tzf enterprise_data_agent-v1.0.0.tar.gz | head -20
```

至少应该看到：

```
enterprise_data_agent/
enterprise_data_agent/agent.yaml
enterprise_data_agent/system_prompt.md
enterprise_data_agent/bindings.py
enterprise_data_agent/tools/ExecuteSQL.tool.yaml
enterprise_data_agent/tools/TodoWrite.tool.yaml
enterprise_data_agent/skills/enterprise_basic/SKILL.md
...
```

**常见踩坑**：

- **不要把 `enterprise.sqlite` 打进去。** 数据库走对象存储或 Cloud 数据卷，塞进 agent 包既臃肿、改一次数据又要重发版。本章先用内嵌小样本，接外部数据是第 9 章的事。
- **`.env` 一定要排除。** 里面有 API Key，进了版本快照就麻烦了。Cloud 上的 secret 走"项目环境变量"，不在包里。
- **软链接要展开。** 第 7 章做过 `ln -s ~/.agents/skills/pptx enterprise_data_agent/skills/pptx`。打包时加 `-h` 让 `tar` 跟着软链接走：`tar -czhf ...`，否则云端解出来是空指针。

## 第 2 步：登录 Cloud 控制台

邮箱密码或 OAuth（GitHub / Google）登录。第一次进来落在空的 Projects 列表页。

> **没有账号?** 登录页点"注册"。账号免费，前几个小项目不收费。

## 第 3 步：新建 Project

点右上角 **Create Project**：

| 字段 | 填什么 |
|---|---|
| **Name** | `enterprise_data_agent`（必填，URL 里会用到） |
| **Description** | 一句话说明，例如"基于 7 张企业表的企业数据分析 + PPT 生成 Agent" |

提交后进入 project 的 Workspace 页：左侧是 Versions 列表（空），右侧是 Playground（灰色——还没有激活版本）。

## 第 4 步：上传第一个 Version

点 **Create Version**：

| 字段 | 填什么 |
|---|---|
| **Tag** | `v1.0.0`（你自己定的版本号，回滚靠它） |
| **Artifact** | 刚才那个 `enterprise_data_agent-v1.0.0.tar.gz` |

点上传后，前端会：

1. 跟后端要一个**预签名上传 URL**
2. 把 `.tar.gz` 直接 PUT 到对象存储（进度条会动）
3. 上传完给后端发一个"确认完成"请求

**直传到对象存储，不走后端转发**——包大几百 MB 也没事。

完成后 Version 列表多一行 `v1.0.0`，状态 **Inactive**。

## 第 5 步：激活

在 `v1.0.0` 这一行点 **Activate**。后端会：

1. 从对象存储拉包、解压
2. 启动一个运行时容器，挂进 `enterprise_data_agent/`
3. 读 `agent.yaml` 跑一次"加载验证"——确认所有 `binding:` 指向的 Python 函数都能 import、所有 `yaml_path:` 指向的 schema 都能解析、所有 `skills:` 目录都存在
4. 把这个版本标为 `is_active = true`

`agent.yaml` 有错（比如 binding 路径打错）激活会失败，Version 行变红，旁边是具体报错——通常是一行 Python ImportError 或 yaml.YAMLError。**修好后重新打包，上传一个新 tag**（`v1.0.1`）再激活，不要在原 Version 上反复试。

激活成功后，右侧 Playground 亮起来。

## 第 6 步：在 Playground 里试一次

Playground 的输入框等价于你本地的 `uv run enterprise_data_agent/start.py "..."`。输入：

```
海淀区有多少家小型企业?
```

会看到一段流式回复 + 一个 **Trace** 面板，展开能看到：

- system_prompt 是什么
- 模型读了哪些 Skill
- 调了几次 `execute_sql`、参数是什么、返回了什么
- 每一步用了多少 token

**Trace 面板是 Cloud 跟本地最大的差别。** 以后调 prompt 主要靠它，不再靠在终端 print。

再试一次第 7 章的 Mode B：

```
给我做一份海淀区 TOP 10 注册资本企业的简报 PPT
```

生成的 `.pptx` 出现在对话窗口下方的"附件"区，点一下就能下载。

## 第 7 步：记下两个东西，留给下一章

Playground 跑通只是开始——真正的目的是让其它系统也能调它。下一章讲外部 REST 调用，但有两个值**现在就要从控制台抄走**：

**1. Project ID 和 Version Tag** —— 在 Workspace 页的 URL 里：

```
https://<你的 cloud 域名>/agents/<project-id>/<version-id>/workspaces/build
                            ^^^^^^^^^^^^   ^^^^^^^^^^^^
                            这是 project_id   这是 version_id(也能用 v1.0.0 这个 tag 替代)
```

记下 `project_id` 和你刚才填的 `tag`（`v1.0.0`）。

**2. 一对 Access Key + Secret Key** —— 在 Project 设置的 **Keys** 标签页，点 **Create Key**：

| 字段 | 填什么 |
|---|---|
| **Name** | `prod-readonly`（随便取，只是给自己看） |

生成后会显示一对：

```
NEXAU_ACCESS_KEY=ak_xxxxxxxxxxxxxxxx
NEXAU_SECRET_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Secret Key 只显示一次。** 关掉对话框就没了，立刻存进密码管理器或 secret store。丢了只能 reset 重发。

这是 **AK/SK** 模式（跟 AWS S3、阿里云 OSS 同一套思路），作用范围是**这个 project**。同 project 下所有 active version 共享这一对 Key——不用每个版本单独发。

> **第 9 章**用这对 Key 从外部代码调智能体。**第 10 章**用另一种 Key（Personal Access Token，绑用户）自动化发版。两种 Key 解决不同的问题，别搞混。

## 这一版给了你什么

| 概念 | 在这一章里的体现 |
|---|---|
| 项目和版本分离 | 智能体的"身份"（project）和"代码"（version）解耦，改一版发一版，旧版能回滚 |
| 激活就是验证 | Activate 那一步会把 `agent.yaml` 完整 load 一遍，语法和 binding 错误在这里抛出来 |
| 一份代码两种入口 | 同一个 active version，Playground 和 API Key 行为一致 |
| Trace 是云上的核心 | Playground 不只是聊天框，主要价值在右边那个 Trace 面板 |

**渐进检查表**：

| | 第 7 章末 | 第 8 章末 |
|---|---|---|
| 智能体跑在哪 | 你本地终端 | NexAU Cloud 托管运行时 |
| 别人怎么用 | 帮他装一遍环境 | 给他 Playground 链接 |
| 怎么调 prompt | 改文件 → 终端跑 → 看 print | 改文件 → 重新打包上传一个新 Version → 看 Trace |
| 怎么让别的系统调 | —— | 一对 Access/Secret Key + REST |
| 数据库 | 本地 `enterprise.sqlite` | （本章先用包内的小样本，第 9 章接外部数据） |

## 局限与权衡

**重发版的成本是"重新打包 + 上传"。** 改一个字也要走完整的 tar + upload + activate。密集调 prompt 时先在本地用第 1–7 章的工具链调到差不多，再上云做最后一公里的 trace 验证。**不要把云当本地 IDE 用。**

**没有 hot reload。** 上传新版本后旧的运行时容器会被换掉，进行中的会话会断开。生产上挑流量低的时候发版。

**数据库本章没接。** 用的是包内的小样本（假设 `enterprise_data_agent/data/enterprise.sqlite` 里塞了个轻量版）。生产里数据库通常是外部 RDS / PostgreSQL，连接串走环境变量——在 Cloud 控制台的 **Settings → Environment Variables** 里配，本章不展开。

**Skills 的软链问题。** 第 7 章那个 `pptx -> ~/.agents/skills/pptx` 软链在云上不能用——云端没有那个 home 路径。要么 `tar -h` 把内容展平进包，要么直接 `cp -r` 进项目目录。后者更稳。

## 你现在站在哪里

```
第 1–7 章:在本地建一个能查数据 + 生成 PPT 的智能体
              ↓
第 8 章:打包 → 上传 → 激活 → 在 Playground 跑通(本章)
              ↓
第 9 章:从外部代码用 REST 调它(给同事的 UI、给 Slack bot、给 web 应用接进去)
              ↓
第 10 章:用 REST 自动化整个发版流程,接进 CI/CD
```

本章只解决"**怎么把它放上去**"。**让别的系统用它**和**自动化发版**各占一章——认证模型和坑点不同，混在一起讲会乱。

## 延伸阅读

- [第 7 章 · 加一个做 PPT 的技能](./07-pptx-agent.md) —— 本章部署的就是第 7 章那个版本
- [第 9 章 · 从外部 REST 调用 Cloud Agent](./09-cloud-api.md) —— AK/SK + sessions + chat + SSE，带可跑的 Python 例子
- [第 10 章 · 用 REST 自动化发版](./10-cloud-automation.md) —— PAT + 三步上传 + activate，接进 CI/CD
