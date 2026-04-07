# NL2SQL Skill 创建工具

本目录包含用于自动生成 NL2SQL Agent 技能文件的完整工具链。通过从数据库采样、智能生成表描述，最终输出标准化的技能文档。

## 概述

Skill 是 NL2SQL Agent 的核心组件，为 Agent 提供数据库表的详细知识，包括：
- 表结构和字段定义
- 业务语义和使用场景
- 示例数据
- 查询指导

本工具链通过三个步骤自动完成 Skill 创建：

1. **数据采样** - 从数据库提取示例数据
2. **智能描述生成** - 使用 LLM 生成表和列的详细描述
3. **Skill 格式化** - 输出标准化的技能文件

## 工具组件

### 1. enrich_schema_with_examples.py
**用途**: 从 PostgreSQL 数据库采样，为每个列添加示例数据

**功能**:
- 连接数据库并采样非空数据
- 为每个列添加 `example` 字段
- 输出带示例的增强版 schema 文件

**用法**:
```bash
cd workspace/nl2sql/create_skills
python enrich_schema_with_examples.py
```

**配置**:
- 默认采样数量: 10 条/列
- 输入文件: `db/chj_db_schema_clean.json`
- 输出文件: `db/chj_db_schema_with_examples.json`

**环境要求**:
```bash
# .env 文件需要包含以下配置:
DB_NAME=context_server
DB_USER=your_username
DB_HOST=your_host
DB_PORT=5432
DB_PASSWORD=your_password
```

### 2. db_description_agent.py
**用途**: 使用 LLM 为每个表生成详细的自然语言描述

**功能**:
- 读取带示例的 schema 文件
- 调用 LLM 分析表结构和业务含义
- 生成表概述、使用场景、列描述
- 支持多线程并行处理
- 输出 JSON 和 Markdown 格式

**用法**:
```bash
# 基本用法
python db_description_agent.py

# 自定义参数
python db_description_agent.py \
    --schema db/chj_db_schema_with_examples.json \
    --output db/descriptions \
    --format both \
    --workers 5 \
    --limit 10
```

**参数说明**:
- `--schema`: 输入 schema 文件路径
- `--output`: 输出目录
- `--format`: 输出格式 (`json`, `markdown`, `both`)
- `--workers`: 并行工作线程数
- `--limit`: 限制处理的表数量（用于测试）

**输出文件**:
- `table_descriptions.json` - 所有表的 JSON 描述
- `table_descriptions.md` - 人类可读的 Markdown 文档
- `tables/<table_name>.json` - 单个表的详细描述

**环境要求**:
```bash
# .env 文件需要包含:
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
OPENAI_MODEL=gpt-5
```

### 3. table_description_json_to_skills.py
**用途**: 将表描述转换为标准 Skill 文件

**功能**:
- 读取 `table_descriptions.json`
- 为每个表生成 `SKILL.md` 文件
- 包含表结构、字段说明、使用场景
- 输出标准化的技能目录结构

**用法**:
```bash
python table_description_json_to_skills.py
```

**配置**:
- 输入文件: `table_descriptions.json`
- 输出目录: `skills_table_70/`
- 每个表一个目录，包含 `SKILL.md`

**输出结构**:
```
skills_table_70/
├── table1/
│   └── SKILL.md
├── table2/
│   └── SKILL.md
└── ...
```

## 完整工作流程

### 步骤 1: 准备环境
```bash
cd workspace/nl2sql/create_skills

# 安装依赖
pip install psycopg2-binary python-dotenv openai tqdm

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入数据库和 LLM 配置
```

### 步骤 2: 数据采样
```bash
# 从数据库采样示例数据
python enrich_schema_with_examples.py

# 检查输出
ls -lh db/chj_db_schema_with_examples.json
```

### 步骤 3: 生成表描述
```bash
# 使用 LLM 生成表描述
python db_description_agent.py \
    --schema db/chj_db_schema_with_examples.json \
    --output db/descriptions \
    --format both \
    --workers 3

# 查看结果
ls db/descriptions/
```

### 步骤 4: 生成 Skill 文件
```bash
# 转换为 Skill 格式
python table_description_json_to_skills.py

# 检查生成的技能
ls skills_table_70/
```

### 步骤 5: 使用技能
```bash
# 将技能文件复制到 Agent 的技能目录
cp -r skills_table_70/* ../../skills/

# 或在 Agent 配置中引用
# 编辑 nl2sql_agent.yaml，添加技能路径
```

## 实现细节

### 数据流
```
原始 Schema (chj_db_schema_clean.json)
    ↓
[enrich_schema_with_examples.py]
    ↓ 添加 example 字段
增强 Schema (chj_db_schema_with_examples.json)
    ↓
[db_description_agent.py]
    ↓ LLM 分析
表描述 (table_descriptions.json)
    ↓
[table_description_json_to_skills.py]
    ↓ 格式化
Skill 文件 (SKILL.md)
```

### 关键特性

**智能采样**:
- 自动跳过空值和空字符串
- 使用 DISTINCT 避免重复
- 限制采样数量以控制文件大小

**LLM 优化**:
- 结构化 prompt 确保输出一致性
- 多线程并行处理提高效率
- JSON 解析容错处理

**Skill 标准化**:
- 符合 NL2SQL Agent 技能格式
- 包含完整的表结构 DDL
- 业务友好的描述语言

## 故障排查

### 数据库连接失败
```bash
# 测试数据库连接
python -c "import psycopg2; conn = psycopg2.connect(dbname='context_server'); print('OK')"

# 检查环境变量
echo $DB_NAME $DB_HOST $DB_PORT
```

### LLM 调用失败
```bash
# 测试 OpenAI API
python -c "from openai import OpenAI; client = OpenAI(); print(client.models.list())"

# 检查 API 配额和网络连接
```

### 输出文件缺失
```bash
# 检查文件路径
ls -la db/
ls -la db/descriptions/

# 检查权限
chmod +x *.py
```

## 最佳实践

1. **增量更新**: 修改单个表时，使用 `--limit 1` 参数测试
2. **并发控制**: 根据 API 限制调整 `--workers` 数量
3. **版本控制**: 将生成的技能文件纳入 Git 管理
4. **质量检查**: 定期审查生成的描述，优化 prompt

## 扩展开发

### 添加新的输出格式
修改 `table_description_json_to_skills.py`，添加新的格式化函数

### 自定义 Prompt
编辑 `db_description_agent.py` 中的 `TABLE_DESCRIPTION_PROMPT`

### 支持其他数据库
修改 `enrich_schema_with_examples.py` 的连接逻辑

