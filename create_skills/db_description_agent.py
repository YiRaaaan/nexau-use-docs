"""
DB Description Agent

读取数据库 Schema 文件，为每个表生成详细描述，包括：
- 表格内容概述
- 使用场景
- 空列
- 每个列的描述（名称、含义、数据类型、示例）
- DDL形式
"""

import os
import json
import logging
import argparse
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ 数据模型 ============

@dataclass
class ColumnDescription:
    """列描述"""
    name: str                    # 列名
    meaning: str                 # 含义/业务语义
    data_type: str               # 数据类型
    examples: List[str]          # 示例值
    is_empty: bool               # 是否为空列


@dataclass
class TableDescription:
    """表描述"""
    table_name: str              # 表名
    overview: str                # 表格内容概述
    usage_scenarios: List[str]   # 使用场景
    empty_columns: List[str]     # 空列列表
    columns: List[ColumnDescription]  # 列描述列表
    ddl: str                     # DDL语句


# ============ LLM 客户端 ============

class LLMClient:
    """LLM客户端封装"""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            base_url=os.getenv('OPENAI_BASE_URL')
        )
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4')
        logger.info(f"LLMClient initialized: model={self.model}")
    
    def chat(self, prompt: str, temperature: float = 0.1) -> str:
        """发送聊天请求"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise


# ============ Prompt 模板 ============

TABLE_DESCRIPTION_PROMPT = """你是一个专业的数据库分析专家。请根据以下数据库表的结构信息，生成该表的详细描述。

## 表基本信息
- 表名: {table_name}
- 表描述: {table_desc}

## DDL 语句
```sql
{ddl}
```

## 字段详情
{columns_info}

## 任务要求
请分析上述表结构，输出以下内容（使用JSON格式）：

```json
{{
    "overview": "表格内容概述，描述该表存储什么数据、主要用途是什么（100-200字）",
    "usage_scenarios": [
        "使用场景1",
        "使用场景2",
        "使用场景3"
    ],
    "empty_columns": ["没有示例数据的空列名1", "空列名2"],
    "columns": [
        {{
            "name": "列名",
            "meaning": "该列的业务含义，解释这个字段在业务场景中代表什么",
            "data_type": "数据类型",
            "examples": ["示例1", "示例2"],
            "is_empty": false
        }}
    ]
}}
```

## 输出要求
1. overview: 概述该表的核心用途，说明存储的数据内容和业务价值
2. usage_scenarios: 列出至少3个该表可能被查询的业务场景
3. empty_columns: 识别所有示例数据为空的列
4. columns: 为每个列提供详细描述，特别要解释业务含义
5. 只输出JSON，不要有其他内容
"""


def build_columns_info(fields: List[Dict]) -> str:
    """构建列信息文本"""
    lines = []
    for i, field in enumerate(fields, 1):
        name = field.get('name', '')
        origin_name = field.get('origin_name', '') or field.get('comment', '')
        data_type = field.get('type', '')
        examples = field.get('example', [])
        
        # 格式化示例
        if examples:
            example_str = ', '.join([str(e)[:50] for e in examples[:5]])
        else:
            example_str = '(无示例数据)'
        
        lines.append(f"""
### {i}. {name}
- 原始名称: {origin_name}
- 数据类型: {data_type}
- 示例值: {example_str}
""")
    
    return '\n'.join(lines)


def build_prompt(table_data: Dict) -> str:
    """构建完整的 prompt"""
    # 提取表信息
    table_name = table_data.get('src_conf', {}).get('table_name', '') or \
                 table_data.get('dst_conf', {}).get('table_name', '')
    table_desc = table_data.get('data_desc', '') or table_data.get('data_name', '')
    
    # 提取 DDL
    ddl = table_data.get('dst_conf', {}).get('create_table', 'DDL 不可用')
    
    # 提取字段信息
    fields = table_data.get('dst_conf', {}).get('table_fields', [])
    columns_info = build_columns_info(fields)
    
    return TABLE_DESCRIPTION_PROMPT.format(
        table_name=table_name,
        table_desc=table_desc,
        ddl=ddl,
        columns_info=columns_info
    )


# ============ Schema 读取 ============

def load_schema(schema_path: str) -> List[Dict]:
    """加载 schema 文件"""
    with open(schema_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 处理数据结构
    if isinstance(data, dict) and 'data' in data:
        return data['data']
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unexpected schema format: {type(data)}")


# ============ 结果解析 ============

def parse_llm_response(response: str, table_data: Dict) -> Optional[TableDescription]:
    """解析 LLM 返回的 JSON"""
    # 提取表名和DDL
    table_name = table_data.get('src_conf', {}).get('table_name', '') or \
                 table_data.get('dst_conf', {}).get('table_name', '')
    ddl = table_data.get('dst_conf', {}).get('create_table', '')
    
    try:
        # 尝试提取 JSON 块
        if '```json' in response:
            json_start = response.find('```json') + 7
            json_end = response.find('```', json_start)
            json_str = response[json_start:json_end].strip()
        elif '```' in response:
            json_start = response.find('```') + 3
            json_end = response.find('```', json_start)
            json_str = response[json_start:json_end].strip()
        else:
            json_str = response.strip()
        
        data = json.loads(json_str)
        
        # 构建列描述
        columns = []
        for col in data.get('columns', []):
            columns.append(ColumnDescription(
                name=col.get('name', ''),
                meaning=col.get('meaning', ''),
                data_type=col.get('data_type', ''),
                examples=col.get('examples', []),
                is_empty=col.get('is_empty', False)
            ))
        
        return TableDescription(
            table_name=table_name,
            overview=data.get('overview', ''),
            usage_scenarios=data.get('usage_scenarios', []),
            empty_columns=data.get('empty_columns', []),
            columns=columns,
            ddl=ddl
        )
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response for {table_name}: {e}")
        logger.debug(f"Response: {response[:500]}...")
        return None
    except Exception as e:
        logger.error(f"Error parsing response for {table_name}: {e}")
        return None


# ============ 主处理类 ============

class DBDescriptionAgent:
    """数据库描述生成 Agent"""
    
    def __init__(self, schema_path: str, output_dir: str, max_workers: int = 3):
        self.schema_path = schema_path
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.llm_client = LLMClient()
        self.jsonl_lock = threading.Lock()  # 用于 jsonl 文件写入的线程锁
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    
    def _save_single_table_json(self, result: TableDescription):
        """保存单个表的 JSON 文件"""
        output_path = os.path.join(self.output_dir, 'tables', f"{result.table_name}.json")
        
        # 确保目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved single table JSON: {output_path}")
    
    def process_single_table(self, table_data: Dict) -> Optional[TableDescription]:
        """处理单个表"""
        table_name = table_data.get('src_conf', {}).get('table_name', '') or \
                     table_data.get('dst_conf', {}).get('table_name', '')
        
        try:
            # 构建 prompt
            prompt = build_prompt(table_data)
            
            # 调用 LLM
            response = self.llm_client.chat(prompt)
            
            # 解析结果
            result = parse_llm_response(response, table_data)
            
            if result:
                logger.info(f"Successfully processed table: {table_name}")
                # 立即保存单个表的 JSON 文件
                self._save_single_table_json(result)
            else:
                logger.warning(f"Failed to parse result for table: {table_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing table {table_name}: {e}")
            return None
    
    def process_all_tables(self, limit: Optional[int] = None) -> List[TableDescription]:
        """处理所有表"""
        # 加载 schema
        tables = load_schema(self.schema_path)
        
        if limit:
            tables = tables[:limit]
        
        logger.info(f"Processing {len(tables)} tables...")
        
        results = []
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_single_table, table): table
                for table in tables
            }
            
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing tables"):
                result = future.result()
                if result:
                    results.append(result)
        
        logger.info(f"Successfully processed {len(results)}/{len(tables)} tables")
        return results
    
    def save_results(self, results: List[TableDescription], output_format: str = 'both'):
        """保存结果"""
        if output_format in ('json', 'both'):
            self._save_json(results)
        
        if output_format in ('markdown', 'both'):
            self._save_markdown(results)
    
    def _save_json(self, results: List[TableDescription]):
        """保存为 JSON"""
        output_path = os.path.join(self.output_dir, 'table_descriptions.json')
        
        data = [asdict(r) for r in results]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved JSON to: {output_path}")
    
    def _save_markdown(self, results: List[TableDescription]):
        """保存为 Markdown"""
        output_path = os.path.join(self.output_dir, 'table_descriptions.md')
        
        lines = ['# 数据库表描述文档\n']
        lines.append(f'> 共 {len(results)} 个表\n')
        lines.append('---\n')
        
        for table in results:
            lines.append(f'## {table.table_name}\n')
            
            # 概述
            lines.append('### 概述\n')
            lines.append(f'{table.overview}\n')
            
            # 使用场景
            lines.append('### 使用场景\n')
            for i, scenario in enumerate(table.usage_scenarios, 1):
                lines.append(f'{i}. {scenario}\n')
            lines.append('\n')
            
            # 空列
            if table.empty_columns:
                lines.append('### 空列\n')
                lines.append(f'以下列没有数据: {", ".join(table.empty_columns)}\n')
            
            # 列描述
            lines.append('### 列描述\n')
            lines.append('| 列名 | 含义 | 数据类型 | 示例 |\n')
            lines.append('|------|------|----------|------|\n')
            for col in table.columns:
                examples = ', '.join(str(e)[:30] for e in col.examples[:3]) if col.examples else '-'
                empty_flag = ' (空)' if col.is_empty else ''
                lines.append(f'| {col.name}{empty_flag} | {col.meaning} | {col.data_type} | {examples} |\n')
            lines.append('\n')
            
            # DDL
            lines.append('### DDL\n')
            lines.append('```sql\n')
            lines.append(f'{table.ddl}\n')
            lines.append('```\n')
            
            lines.append('---\n')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info(f"Saved Markdown to: {output_path}")


# ============ CLI 入口 ============

def main():
    parser = argparse.ArgumentParser(description='DB Description Agent')
    parser.add_argument(
        '--schema', '-s',
        type=str,
        default='db/chj_db_schema_with_examples.json',
        help='Schema 文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='db/descriptions',
        help='输出目录'
    )
    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['json', 'markdown', 'both'],
        default='both',
        help='输出格式'
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='限制处理的表数量（用于测试）'
    )
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=3,
        help='并行处理的工作线程数'
    )
    
    args = parser.parse_args()
    
    # 创建 agent 并运行
    agent = DBDescriptionAgent(
        schema_path=args.schema,
        output_dir=args.output,
        max_workers=args.workers
    )
    
    results = agent.process_all_tables(limit=args.limit)
    agent.save_results(results, output_format=args.format)
    
    logger.info("Done!")


if __name__ == '__main__':
    main()

