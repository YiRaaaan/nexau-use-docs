# 第 9 章 · 从外部 REST 调用 Cloud Agent

**TL;DR**:用第 8 章拿到的那对 Access Key + Secret Key,通过 `Authorization: Basic base64(ak:sk)` 调 Agent Gateway 的两个端点——`POST /agent-api/sessions` 拿 `session_id`,`POST /agent-api/chat` 发消息拿 SSE 流。**没有 SDK,就是普通 HTTP**,任何能发请求的语言都能接。

> **本章假设你**已经走完第 8 章,在 Cloud 上有一个激活的版本和一对 AK/SK。如果没有,先回到[第 8 章](./08-deploy-cloud.md)。

## 你最后会拿到什么

跑完本章,你手里会有一段不到 80 行的 Python,能从命令行问你云上的智能体任何问题:

```bash
$ python call_nl2sql.py "海淀区有多少家小型企业?"
[reasoning] 我需要先看 enterprise_basic 表的 register_district 列...
[tool_call] execute_sql(sql="SELECT COUNT(*) FROM enterprise_basic WHERE register_district = '海淀区' AND enterprise_scale = '小型'")
[tool_result] [{"count": 1234}]
[answer] 海淀区共有 1234 家注册规模为"小型"的企业。

SQL: SELECT COUNT(*) FROM enterprise_basic WHERE register_district = '海淀区' AND enterprise_scale = '小型'
```

把这段代码塞进你自己的 web 后端、Slack bot、企业微信回调、或者一个 cron job,你的智能体就在产品里跑起来了。

## 两个 API 端点,加一个端口

NexAU Cloud 内部分两个服务:

| 服务 | 干什么的 | 你怎么访问 | 用什么认证 |
|---|---|---|---|
| **Backend**(控制平面) | 建项目、发版本、改 env vars、看历史 trace | `https://<cloud-host>/api/*` | JWT cookie(浏览器)或 PAT(自动化,见第 10 章) |
| **Agent Gateway**(数据平面) | 跟正在跑的 agent 说话(sessions / chat / stop / files) | `https://<gateway-host>/agent-api/*` | **AK/SK Basic auth**(就是这一章用的) |

> **gateway-host 是哪里?** 自托管的话通常是 `gateway.<你的域名>` 或者跟 backend 同域 + 不同 path。SaaS 的话在 Cloud 控制台的 **Settings → API Endpoints** 页能看到完整 URL。本章后面用 `https://gateway.nexau.example` 占位,跑代码前替换成你自己的。

## 思路

整个调用流程**只有两个 HTTP 请求**:

```
1. POST /agent-api/sessions   →  拿 session_id
                                       ↓
2. POST /agent-api/chat       →  SSE 流回来一堆 NexAU 事件
   (带 session_id + version_tag + messages)
```

为什么要先建 session?因为 NexAU 的 agent 是有状态的——一次会话对应一个**沙箱(sandbox)**,沙箱里有它的工作目录、临时文件、上下文。`session_id` 是这个沙箱的句柄。同一个 session 多次 chat,沙箱状态保留;不同 session 互相隔离。

> **session 跨版本。** 第 8 章激活了 `v1.0.0`。如果你后面改了 prompt 发了 `v1.0.1`,旧的 session 仍然有效——下一次 chat 你可以指定新的 `version_tag`,session 会切到新版本继续跑。这是 RFC-0024 的设计意图:session 绑用户(distinct_id),不绑代码版本。

## 第 1 步:认证格式

AK/SK 走标准的 HTTP Basic Auth(RFC 7617):

```
Authorization: Basic <base64(access_key + ":" + secret_key)>
```

Python 的 `requests` 库直接用 `auth=(ak, sk)` 参数就行,它会帮你拼好。`curl` 用 `-u ak:sk`。

> **不要用 `Authorization: Bearer`、`X-Access-Key` 这类自定义头。** Agent Gateway 的代码里只接受 `Basic`(以及一个为了向后兼容的 `AKSK ak:sk`),其它格式直接 401。

## 第 2 步:建一个 session

最小请求:

```bash
curl -u "$NEXAU_ACCESS_KEY:$NEXAU_SECRET_KEY" \
     -H "Content-Type: application/json" \
     -d '{"distinct_id": "user-1234"}' \
     https://gateway.nexau.example/agent-api/sessions
```

请求体只有一个字段:

| 字段 | 类型 | 说明 |
|---|---|---|
| `distinct_id` | string | **你这边的最终用户 ID**——可以是登录用户的 UUID、邮箱 hash、客户 ID,任何能区分"是哪个真人"的标识符。会进 Langfuse trace 用来按用户聚合 |

> **`project_id` 不在请求体里。** 因为 AK/SK 已经唯一确定了 project——服务端拿到 AK/SK 验证完就知道是哪个 project 了。这是 RFC-0024 的简化:session 跟 version 解耦,跟 project 由 AK/SK 隐式绑定。

返回:

```json
{
  "session_id": "sess_01HXXXXX",
  "created_at": "2026-04-07T12:34:56Z"
}
```

记下 `session_id`,接下来发 chat 要用。

## 第 3 步:发 chat

```bash
curl -u "$NEXAU_ACCESS_KEY:$NEXAU_SECRET_KEY" \
     -H "Content-Type: application/json" \
     -H "Accept: text/event-stream" \
     -d '{
       "session_id": "sess_01HXXXXX",
       "distinct_id": "user-1234",
       "version_tag": "v1.0.0",
       "messages": [
         {"role": "user", "content": "海淀区有多少家小型企业?"}
       ],
       "stream": true,
       "source": "user"
     }' \
     https://gateway.nexau.example/agent-api/chat
```

请求体的核心字段:

| 字段 | 必填 | 说明 |
|---|---|---|
| `session_id` | ✅ | 上一步拿到的 |
| `distinct_id` | ✅ | 跟 session 那一步一致 |
| `version_tag` | ✅(或 `version_id`) | 你要打到哪个版本——**强烈推荐用 tag**(`v1.0.0`),不要用 UUID。换版本时只改这个字段,代码不动 |
| `messages` | ✅ | 跟 OpenAI 一样的 `[{role, content}]` 数组,也可以直接传一个字符串 |
| `stream` | ❌(默认 true) | true 走 SSE,false 一次性返回 JSON |
| `source` | ❌ | `"user"`(默认)或 `"playground"`,只是给 trace 打标用 |
| `agent` | ❌ | 多 agent 项目里指定哪个 agent。第 1–8 章只有一个 agent,不用填 |

> **为什么 `version_tag` 不在 session 里而在 chat 里?** 因为 RFC-0024 让 session 和 version 解耦。你可以用同一个 session 先打 `v1.0.0` 跑几轮,再切到 `v1.0.1` 继续跑(比如灰度对比)。session 是沙箱句柄,version 是代码句柄,它们生命周期不同。

## 第 4 步:解析 SSE 流

返回的 `Content-Type` 是 `text/event-stream`,每行是一个 SSE 事件:

```
data: {"type":"RUN_STARTED","run_id":"run_xxx"}

data: {"type":"TEXT_MESSAGE_CONTENT","delta":"我先看一下 enterprise_basic 表..."}

data: {"type":"TOOL_CALL_START","tool_name":"execute_sql","tool_call_id":"call_1"}

data: {"type":"TOOL_CALL_ARGS","delta":"{\"sql\":\"SELECT COUNT(*) FROM enterprise_basic..."}

data: {"type":"TOOL_CALL_END","tool_call_id":"call_1"}

data: {"type":"TOOL_RESULT","tool_call_id":"call_1","content":"[{\"count\": 1234}]"}

data: {"type":"TEXT_MESSAGE_CONTENT","delta":"海淀区共有 1234 家..."}

data: {"type":"RUN_FINISHED","run_id":"run_xxx"}

data: [DONE]
```

每个事件都是一行 `data: <json>`,行之间用空行分隔(标准 SSE)。最后一行是 `data: [DONE]`,表示流结束——收到这个就可以关闭连接。

**主要事件类型**(你大概率会处理的):

| 类型 | 含义 |
|---|---|
| `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` | 一次 run 的生命周期 |
| `TEXT_MESSAGE_CONTENT` | LLM 的文字回复增量,字段 `delta` |
| `TEXT_MESSAGE_END` | 一段文字结束 |
| `REASONING_CONTENT` | o1 / DeepSeek-R1 这类模型的思考过程,字段 `delta` |
| `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` | 工具调用,参数也是分块流式给的 |
| `TOOL_RESULT` | 工具返回的结果 |
| `IMAGE_MESSAGE` | 模型返回了一张图 |

> **完整事件清单**在 `services/agent-runtime/.../events.py`(自托管的话直接看代码),或者在 Cloud 控制台的 **Docs → SSE Events** 里有列表。**90% 的应用只用 `TEXT_MESSAGE_CONTENT`**——把 delta 拼起来就是给用户看的回复,其它事件用来做 UI 动效(比如显示"正在调用工具…")。

## 第 5 步:把它写成一段 Python

```python
# call_nl2sql.py
import json
import os
import sys

import requests

GATEWAY = os.environ["NEXAU_GATEWAY_URL"]      # https://gateway.nexau.example
AK = os.environ["NEXAU_ACCESS_KEY"]
SK = os.environ["NEXAU_SECRET_KEY"]
VERSION_TAG = os.environ.get("NEXAU_VERSION_TAG", "v1.0.0")
DISTINCT_ID = os.environ.get("NEXAU_DISTINCT_ID", "cli-user")


def create_session() -> str:
    resp = requests.post(
        f"{GATEWAY}/agent-api/sessions",
        auth=(AK, SK),
        json={"distinct_id": DISTINCT_ID},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["session_id"]


def chat(session_id: str, question: str) -> None:
    resp = requests.post(
        f"{GATEWAY}/agent-api/chat",
        auth=(AK, SK),
        headers={"Accept": "text/event-stream"},
        json={
            "session_id": session_id,
            "distinct_id": DISTINCT_ID,
            "version_tag": VERSION_TAG,
            "messages": [{"role": "user", "content": question}],
            "stream": True,
            "source": "user",
        },
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    for raw in resp.iter_lines(decode_unicode=True):
        if not raw or not raw.startswith("data:"):
            continue
        data = raw[5:].strip()
        if data == "[DONE]":
            break
        event = json.loads(data)
        handle_event(event)


def handle_event(event: dict) -> None:
    etype = event.get("type", "")

    if etype == "TEXT_MESSAGE_CONTENT":
        # 把每个 delta 拼起来就是最终回复
        sys.stdout.write(event.get("delta", ""))
        sys.stdout.flush()

    elif etype == "TOOL_CALL_START":
        print(f"\n[tool_call] {event.get('tool_name')}", flush=True)

    elif etype == "TOOL_RESULT":
        content = event.get("content", "")
        preview = content[:80] + ("…" if len(content) > 80 else "")
        print(f"[tool_result] {preview}", flush=True)

    elif etype == "RUN_ERROR":
        print(f"\n[error] {event.get('message')}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python call_nl2sql.py '你的问题'", file=sys.stderr)
        sys.exit(1)

    sid = create_session()
    chat(sid, sys.argv[1])
    print()  # 收尾换行
```

跑:

```bash
export NEXAU_GATEWAY_URL="https://gateway.nexau.example"
export NEXAU_ACCESS_KEY="ak_xxxxx"
export NEXAU_SECRET_KEY="sk_xxxxx"
export NEXAU_VERSION_TAG="v1.0.0"

python call_nl2sql.py "海淀区有多少家小型企业?"
```

**就这些。** 80 行不到的代码就把第 1–8 章那个智能体接进了任何一个能装 Python 的环境。换成 Node.js / Go / Rust 是同一回事——只是 SSE 解析的库不一样。

## 进阶:停止一个跑飞的 run

万一用户发了个会跑 5 分钟的查询,前端按了"取消",你需要主动停掉这个 run:

```bash
curl -u "$NEXAU_ACCESS_KEY:$NEXAU_SECRET_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "session_id": "sess_01HXXXXX",
       "distinct_id": "user-1234",
       "version_tag": "v1.0.0",
       "force": true
     }' \
     https://gateway.nexau.example/agent-api/stop
```

返回 `{"status": "success"}` 就是停成功了。`"noop"` 表示这个 session 当前没有正在跑的 run。

## 进阶:给沙箱传文件

如果用户要上传一个 CSV 让 agent 分析,走 `multipart/form-data`:

```bash
curl -u "$NEXAU_ACCESS_KEY:$NEXAU_SECRET_KEY" \
     -F "session_id=sess_01HXXXXX" \
     -F "file=@./local_data.csv" \
     "https://gateway.nexau.example/agent-api/files?project_id=<pid>&version_id=<vid>&distinct_id=user-1234&source=user"
```

返回里有一个 `path`,这就是文件在 sandbox 里的绝对路径。把这个路径塞进下一次 chat 的 message 里(比如"分析一下 `/sandbox/uploads/local_data.csv` 这个文件"),agent 就能读到。

> 文件相关的端点还有 `/agent-api/files/list` 和 `/agent-api/files/delete`,语义跟名字一样,这里不展开。

## 这一版给了你什么

| 概念 | 在这一章里的体现 |
|---|---|
| 控制平面 vs 数据平面 | Backend(`/api/*`)管发版和元数据,Gateway(`/agent-api/*`)管运行时调用——两个端口、两套认证 |
| AK/SK 是 project-scoped | 一对 Key 等于"我有权调这个 project 的所有 active version" |
| Session 跟 version 解耦 | 同一个 session 可以跨版本切换,这是灰度发布的基础 |
| SSE 是默认通道 | 90% 的事件你只要拼 `TEXT_MESSAGE_CONTENT`,其它给 UI 动效用 |
| `distinct_id` 是 trace 聚合的钥匙 | 你给的越准,后面在 Langfuse / 控制台按用户筛 trace 越好用 |

## 局限与权衡

**SSE 不是 WebSocket。** 它是单向的(server → client),客户端不能"在 chat 跑到一半补一句"。要双向交互,通常的做法是:让 agent 跑完一轮后返回控制权给客户端,客户端拿用户的下一句话再发一次 chat,带上同一个 `session_id`。

**没有官方 SDK**(写本章时)。所有调用都是手写 HTTP——好处是任何语言都能接,坏处是事件类型、认证 header、错误处理都得自己读这一章再实现。如果你的团队同时要支持多种语言,**优先在 backend 写一个 thin wrapper,前端只调你自己的 wrapper**——比每个客户端都直接对着 Gateway 强。

**`distinct_id` 不能为空。** Gateway 会直接 400。如果你的产品允许匿名用户,塞一个 `"anonymous-<short uuid>"` 过去,别留空字符串。

**版本切换不是原子的。** 把 `version_tag` 从 `v1.0.0` 改成 `v1.0.1` 之后,新的 chat 请求会路由到新版本,但**旧版本的运行时容器不会立刻被回收**——它要等空闲超时。这意味着发完版的几分钟内,理论上同一个 session 的两次连续 chat 可能打到不同的容器实例(虽然版本一致)。如果你的 agent 在 sandbox 里写了不持久化的临时状态,这一点要小心。

## 接下来

第 8、9 章解决了"**人用**"和"**别的系统用**"这两件事。还差一件——**自动发版**。每次改完 prompt 都要打开浏览器拖文件,这不是工程化的做法。

[第 10 章](./10-cloud-automation.md)讲怎么用一对 PAT(Personal Access Token)从命令行或 CI 里走完"build tar → 创建 version → 上传 artifact → activate"全过程,接进 GitHub Actions 是几十行 yaml 的事。

## 延伸阅读

- [第 8 章 · 部署到 NexAU Cloud](./08-deploy-cloud.md) —— 拿 AK/SK 的地方
- [第 10 章 · 用 REST 自动化发版](./10-cloud-automation.md) —— 把发版接进 CI/CD
- RFC-0010 / RFC-0024 / RFC-0061 —— 这一章的认证和路由设计依据,在 NexAU 仓库的 `docs/rfcs/` 下
