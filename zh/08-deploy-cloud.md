# 第 8 章 · 部署到 NexAU Cloud

**TL;DR**:把前 7 章建好的 `nl2sql_agent/` 打成一个压缩包,在 NexAU Cloud 控制台上**新建项目 → 上传版本 → 激活**,就能拿到一个云端 Playground 和一对 API Key——别人不用装 Python、uv、sqlite、Node 也能用你的智能体。整个过程不写一行新代码。

> **本章假设你**已经跟着第 1–7 章把 `nl2sql_agent/` 在本地跑通了。如果还没,先回到[第 1 章](./01-bash-nl2sql.md)。

## 为什么要上云

前 7 章一直在本地跑,这套组合很适合开发,但有三件事在本地搞不定:

1. **别人用不了。** 同事要用,得先帮他装 Python / uv / sqlite / Node、配 API Key、克隆项目、跑命令。一次还行,十次就烦了。
2. **没有 trace UI。** 你只能在终端看一行行 log。出问题时翻 trace、对比两个 run、按工具调用筛选——这些事手动做太累。
3. **没有版本管理。** 你改完一版 system prompt,想跟昨天那版对比一下效果,本地没有现成的回滚机制。

NexAU Cloud 解决的就是这三件事:**托管运行时 + Trace UI + 版本快照**。你打包一次,云上拿到一个稳定的 Playground 链接和一对 API Key,然后该改 prompt 改 prompt、该换 LLM provider 换 provider,**项目本身不动**。

## 你最后会拿到什么

跑完本章,你会有:

- 一个 NexAU Cloud 上的 **Project**,名字叫 `nl2sql_agent`
- 一个已激活的 **Version**(比如 `v1.0.0`),后面所有调用都打到它
- 一个**云端 Playground 链接**,可以直接发给同事,他打开就能问"海淀区有多少家小型企业?"
- 一对 **Access Key + Secret Key**,可以从你自己的代码里调这个智能体

云上的智能体跟你本地跑的是**同一份 `agent.yaml` + `system_prompt.md` + `bindings.py` + `skills/`**。运行时镜像里已经预装了第 7 章用到的 Node + `pptxgenjs`。

## 思路

NexAU Cloud 的部署模型是**项目(Project) → 版本(Version) → 激活(Activate)**:

| 概念 | 对应你本地的什么 |
|---|---|
| **Project** | 一个智能体的"名字空间"。`nl2sql_agent` 是一个 project,以后再写一个 `customer_support_agent` 是另一个 project |
| **Version** | 某一次打包上传的快照。每次你改了 prompt 或 binding,就上传一个新 Version,旧 Version 仍然能回滚 |
| **Activate** | 把某一个 Version 设为"当前生效的"。Playground 链接和 API Key 永远打到这个激活版本 |

整个过程**没有 git push、没有 CI**——你只是在控制台上拖一个 `.tar.gz`。

## 第 1 步:打包你的项目

回到 `NexAU/`,把 `nl2sql_agent/` 打成一个 `.tar.gz`:

```bash
cd NexAU

# 别把 venv、缓存、本地数据库带上
tar --exclude='nl2sql_agent/__pycache__' \
    --exclude='nl2sql_agent/.venv' \
    --exclude='nl2sql_agent/output' \
    -czf nl2sql_agent-v1.0.0.tar.gz nl2sql_agent/
```

> **Windows / 没有 tar?** 用 `zip -r nl2sql_agent-v1.0.0.zip nl2sql_agent -x "nl2sql_agent/__pycache__/*" "nl2sql_agent/output/*"`,Cloud 同时支持 `.tar.gz` 和 `.zip`。

验证一下里面有该有的东西:

```bash
tar -tzf nl2sql_agent-v1.0.0.tar.gz | head -20
```

至少应该看到:

```
nl2sql_agent/
nl2sql_agent/agent.yaml
nl2sql_agent/system_prompt.md
nl2sql_agent/bindings.py
nl2sql_agent/tools/ExecuteSQL.tool.yaml
nl2sql_agent/tools/TodoWrite.tool.yaml
nl2sql_agent/skills/enterprise_basic/SKILL.md
...
```

**几个常见踩坑**:

- **不要把 `enterprise.sqlite` 打进去。** 数据库文件应该单独走对象存储或 Cloud 自带的数据卷,不要塞在 agent 包里——既臃肿又改一次数据就要重发版。第 9 章会专门讲数据怎么挂(本章先用一个内嵌的小样本)。
- **`.env` 一定要排除掉。** 里面有你的 API Key,泄漏到云上的版本快照里会很麻烦。Cloud 上的 secret 走"项目环境变量"配置,不在包里。
- **软链接要展开。** 第 7 章我们做过 `ln -s ~/.agents/skills/pptx nl2sql_agent/skills/pptx`。打包时要让 `tar` 跟着软链接走,加 `-h` 参数:`tar -czhf ...`。否则云端解出来是个空指针。

## 第 2 步:登录 NexAU Cloud 控制台

打开 NexAU Cloud 控制台,用邮箱密码或 OAuth(GitHub / Google)登录。第一次进来会落在一个空的 Projects 列表页。

> **还没有账号?** 在登录页点"注册",用邮箱注册。账号是免费的,跑前几个小项目不收费。

## 第 3 步:新建 Project

点右上角的 **Create Project**,弹出一个表单:

| 字段 | 填什么 |
|---|---|
| **Name** | `nl2sql_agent`(必须,后面 URL 会用到) |
| **Description** | 一句话说明这个智能体是干嘛的,比如"基于 7 张企业表的 NL2SQL + PPT 生成智能体" |

提交后你会落到这个 project 的 Workspace 页,左侧是 Versions 列表(此时是空的),右侧是 Playground(此时灰色不可用——因为还没有激活的版本)。

## 第 4 步:上传第一个 Version

点 **Create Version**,弹出表单:

| 字段 | 填什么 |
|---|---|
| **Tag** | `v1.0.0`(你自己定的版本号,以后回滚靠它) |
| **Artifact** | 选刚才那个 `nl2sql_agent-v1.0.0.tar.gz` |

点上传后,前端会:

1. 跟后端要一个**预签名上传 URL**
2. 把你的 `.tar.gz` 直接 PUT 到对象存储(进度条会动)
3. 上传完之后给后端发一个"确认完成"的请求

整个过程是**直传到对象存储**,所以包大几百 MB 也没事——不走后端转发。

上传成功后,Version 列表会多一行 `v1.0.0`,状态是 **Inactive**。

## 第 5 步:激活

在 `v1.0.0` 这一行点 **Activate**。后端会:

1. 从对象存储拉你的包,解压
2. 启动一个运行时容器,把你的 `nl2sql_agent/` 挂进去
3. 读 `agent.yaml`,跑一次"加载验证"——确认所有 `binding:` 指向的 Python 函数都能 import、所有 `yaml_path:` 指向的 schema 都能解析、所有 `skills:` 目录都存在
4. 把这个版本标为 `is_active = true`

如果 `agent.yaml` 里有写错(比如 binding 路径打错了),激活会失败,Version 这一行会变红,旁边会显示具体的报错——通常是一行 Python ImportError 或 yaml.YAMLError。**修好之后重新打包,上传一个新的 tag**(比如 `v1.0.1`)再激活,不要在原 Version 上反复试。

激活成功后,Workspace 右侧的 Playground 会亮起来。

## 第 6 步:在 Playground 里试一次

Playground 的输入框就是你本地命令行那个 `dotenv run uv run nl2sql_agent/start.py "..."` 的云端版。输入:

```
海淀区有多少家小型企业?
```

应该看到一段流式回复 + 下面一个 **Trace** 面板,里面能展开看到:

- system_prompt 是什么
- 模型读了哪些 Skill
- 调了哪几次 `execute_sql`、参数是什么、返回了什么
- 每一步用了多少 token

这就是本地终端看不到的东西。**Trace 面板是 Cloud 跟本地最大的差别**——以后调 prompt 主要靠这里看,不再靠在终端 print。

再试一次第 7 章的 Mode B:

```
给我做一份海淀区 TOP 10 注册资本企业的简报 PPT
```

云上跑出来的 `.pptx` 会出现在对话窗口下方的"附件"区,点一下就能下载。

## 第 7 步:记下两个东西,留给下一章

光在 Playground 里玩还不够——真正的目的是让其它系统也能调它。下一章会讲怎么从外部用 REST 调,但有两个东西**这一步就该记下来**,因为它们是从 Cloud 控制台里直接看的:

**1. Project ID 和 Version Tag** —— 在 Workspace 页的 URL 里:

```
https://<你的 cloud 域名>/agents/<project-id>/<version-id>/workspaces/build
                            ^^^^^^^^^^^^   ^^^^^^^^^^^^
                            这是 project_id   这是 version_id(也能用 v1.0.0 这个 tag 替代)
```

记下 `project_id` 和你刚才填的 `tag`(`v1.0.0`)。

**2. 一对 Access Key + Secret Key** —— 在 Project 设置的 **Keys** 标签页,点 **Create Key**:

| 字段 | 填什么 |
|---|---|
| **Name** | `prod-readonly`(随便取,只是给自己看) |

生成后会显示一对:

```
NEXAU_ACCESS_KEY=ak_xxxxxxxxxxxxxxxx
NEXAU_SECRET_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Secret Key 只在创建那一刻显示一次。** 关掉对话框就看不到了,赶紧存到你自己的密码管理器或者后端 secret store。如果丢了,只能 reset 这把 key 重新生成。

这一对 Key 是 **AK/SK** 模式(Access Key / Secret Key,跟 AWS S3、阿里云 OSS 同一套思路),作用范围是**这个 project**。同一个 project 下的所有 active version 共享这一对 Key——你不需要给每个版本单独发 Key。

> **第 9 章会用到这一对 Key**,把它从外部代码调起来。**第 10 章会用另一种 Key**(Personal Access Token,绑用户而不是绑 project),自动化整个发版流程。两种 Key 解决不同的问题,别搞混。

## 这一版给了你什么

| 概念 | 在这一章里的体现 |
|---|---|
| 项目和版本分离 | 智能体的"身份"(project)和"代码"(version)解耦,改一版就发一版,旧版能回滚 |
| 激活就是验证 | Cloud 在激活那一步把你的 `agent.yaml` 完整 load 一遍,语法和 binding 错误在这里就抛出来 |
| 一份代码两种入口 | 同一个 active version,既给 Playground 用也给 API Key 用,行为一致 |
| Trace 是云上的核心 | Playground 不只是聊天框,主要价值是右边那个 Trace 面板 |

**渐进检查表**:

| | 第 7 章末 | 第 8 章末 |
|---|---|---|
| 智能体跑在哪 | 你本地终端 | NexAU Cloud 托管运行时 |
| 别人怎么用 | 帮他装一遍环境 | 给他 Playground 链接 |
| 怎么调 prompt | 改文件 → 终端跑 → 看 print | 改文件 → 重新打包上传一个新 Version → 看 Trace |
| 怎么让别的系统调 | —— | 一对 Access/Secret Key + REST |
| 数据库 | 本地 `enterprise.sqlite` | (本章先用包内的小样本,第 9 章接外部数据) |

## 局限与权衡

**重发版的成本是"重新打包 + 上传"。** 改一个 system_prompt 的字也要走一次完整的 tar + upload + activate。如果你正在密集调 prompt,先在本地用第 1–7 章的工具链调到差不多,再上云做最后一公里的 trace 验证。**不要把云当本地 IDE 用。**

**没有 hot reload。** 上传新版本后,旧的运行时容器会被换掉,正在进行的会话会断开。生产环境上要小心,挑流量低的时候发版。

**数据库这一章没接。** 我们用的是包内自带的小样本(假设你在 `nl2sql_agent/data/enterprise.sqlite` 里塞了个轻量版)。真实生产里,数据库通常是外部 RDS / PostgreSQL,通过环境变量传连接串。这一块属于"运行时配置",在 Cloud 控制台的 **Settings → Environment Variables** 里配,本章没展开。

**Skills 的软链问题。** 第 7 章那个 `pptx -> ~/.agents/skills/pptx` 软链在云上不能用——云端没有那个 home 路径。打包前要么用 `tar -h` 把内容物展平进去,要么直接 `cp -r` 进项目目录。后者更稳。

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

本章只解决"**怎么把它放上去**"。**让别的系统用它**和**自动化发版**这两件事各占一章——它们有各自的认证模型和坑点,放在一起讲会乱。

## 延伸阅读

- [第 7 章 · 加一个做 PPT 的技能](./07-pptx-agent.md) —— 本章部署的就是第 7 章那个版本
- [第 9 章 · 从外部 REST 调用 Cloud Agent](./09-cloud-api.md) —— AK/SK + sessions + chat + SSE,带可跑的 Python 例子
- [第 10 章 · 用 REST 自动化发版](./10-cloud-automation.md) —— PAT + 三步上传 + activate,接进 CI/CD
