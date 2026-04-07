#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为schema中的每个列添加样本数据
从PostgreSQL数据库采样3条数据，存入example字段
"""

import json
import psycopg2
from psycopg2 import sql
import sys
from pathlib import Path
from typing import List, Any, Optional
import os

from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def connect_to_db(dbname=DB_NAME, user=DB_USER, host=DB_HOST, port=DB_PORT, password=DB_PASSWORD):
    """连接到PostgreSQL数据库"""
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            host=host,
            port=port,
            password=password
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)


def get_column_samples(conn, table_name: str, column_name: str, sample_count: int = 3) -> List[Any]:
    """获取指定列的非空样本数据"""
    try:
        with conn.cursor() as cur:
            # 查询非空的不同值，限制返回数量
            query = sql.SQL("""
                SELECT DISTINCT {column}
                FROM {table}
                WHERE {column} IS NOT NULL 
                  AND CAST({column} AS TEXT) != ''
                LIMIT %s
            """).format(
                column=sql.Identifier(column_name),
                table=sql.Identifier(table_name)
            )
            cur.execute(query, (sample_count,))
            rows = cur.fetchall()
            
            # 提取值并转换为字符串（处理特殊类型）
            samples = []
            for row in rows:
                value = row[0]
                # 转换为可JSON序列化的格式
                if value is not None:
                    samples.append(str(value))
            
            return samples
    except Exception as e:
        print(f"    警告: 查询 {table_name}.{column_name} 失败: {e}")
        return []


def enrich_schema_with_examples(input_file: str, output_file: str, sample_count: int = 3):
    """为schema添加样本数据"""
    print("=" * 80)
    print("Schema样本数据填充工具")
    print("=" * 80)
    
    # 读取JSON文件
    print(f"\n1. 读取JSON文件: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        schema_data = json.load(f)
    
    if 'data' not in schema_data:
        print("错误: JSON文件格式不正确，缺少data字段")
        sys.exit(1)
    
    tables = schema_data['data']
    print(f"   找到 {len(tables)} 个表")
    
    # 连接数据库
    print(f"\n2. 连接数据库: context_server")
    conn = connect_to_db()
    
    try:
        # 处理每个表
        print(f"\n3. 为每个列采样 {sample_count} 条数据")
        print("-" * 80)
        
        total_columns = 0
        enriched_columns = 0
        
        for table_idx, table_info in enumerate(tables, 1):
            data_name = table_info.get('data_name', '')
            dst_conf = table_info.get('dst_conf', {})
            table_name = dst_conf.get('table_name', '')
            table_fields = dst_conf.get('table_fields', [])
            
            if not table_name or not table_fields:
                continue
            
            print(f"\n[{table_idx}/{len(tables)}] {data_name} ({table_name})")
            
            for field in table_fields:
                column_name = field.get('name', '')
                if not column_name:
                    continue
                
                total_columns += 1
                
                # 获取样本数据
                samples = get_column_samples(conn, table_name, column_name, sample_count)
                
                # 添加example字段
                field['example'] = samples
                
                if samples:
                    enriched_columns += 1
                    # 显示简短的样本预览
                    preview = str(samples[0])[:30] + '...' if len(str(samples[0])) > 30 else str(samples[0])
                    print(f"    {column_name}: [{len(samples)}条] {preview}")
                else:
                    print(f"    {column_name}: [无数据]")
        
        print("\n" + "-" * 80)
        
        # 保存结果
        print(f"\n4. 保存结果到: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(schema_data, f, ensure_ascii=False, indent=4)
        
        # 统计
        print("\n" + "=" * 80)
        print("统计信息:")
        print(f"  总表数: {len(tables)}")
        print(f"  总列数: {total_columns}")
        print(f"  成功填充: {enriched_columns} 列")
        print(f"  无数据: {total_columns - enriched_columns} 列")
        print(f"  输出文件: {output_file}")
        print("=" * 80)
        
    finally:
        conn.close()
        print("\n数据库连接已关闭")


def main():
    # 文件路径
    script_dir = Path(__file__).parent.parent
    input_file = script_dir / 'db' / 'chj_db_schema_clean.json'
    output_file = script_dir / 'db' / 'chj_db_schema_with_examples.json'
    
    enrich_schema_with_examples(str(input_file), str(output_file), sample_count=10)


if __name__ == '__main__':
    main()

