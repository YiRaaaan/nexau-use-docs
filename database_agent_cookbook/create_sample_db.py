"""Create a sample 3-table SQLite database (bookstore) for the cookbook demo.

Usage:
    python create_sample_db.py            # creates ./sample.sqlite
    python create_sample_db.py output.db  # creates output.db
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sample.sqlite"


def main() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()

    conn = sqlite3.connect(str(OUTPUT))
    cur = conn.cursor()

    # ── customers ──────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE customers (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        email       TEXT    UNIQUE,
        city        TEXT,
        member_level TEXT   DEFAULT '普通',   -- 普通 / 银卡 / 金卡 / 钻石
        created_at  TEXT    DEFAULT (datetime('now'))
    );
    """)
    customers = [
        ("张三", "zhangsan@example.com", "北京", "金卡"),
        ("李四", "lisi@example.com", "上海", "普通"),
        ("王五", "wangwu@example.com", "广州", "银卡"),
        ("赵六", "zhaoliu@example.com", "深圳", "钻石"),
        ("孙七", "sunqi@example.com", "杭州", "普通"),
        ("周八", "zhouba@example.com", "成都", "金卡"),
        ("吴九", "wujiu@example.com", "北京", "银卡"),
        ("郑十", "zhengshi@example.com", "上海", "普通"),
        ("钱十一", "qian11@example.com", "广州", "金卡"),
        ("陈十二", "chen12@example.com", "深圳", "普通"),
    ]
    cur.executemany(
        "INSERT INTO customers (name, email, city, member_level) VALUES (?, ?, ?, ?)",
        customers,
    )

    # ── books ──────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE books (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT    NOT NULL,
        author      TEXT    NOT NULL,
        genre       TEXT,               -- 文学 / 技术 / 历史 / 科幻 / 经管
        price       TEXT    NOT NULL,   -- 注意：TEXT 类型，需要 CAST 才能数字比较
        stock       INTEGER DEFAULT 0,
        publisher   TEXT,
        publish_year INTEGER
    );
    """)
    books = [
        ("三体", "刘慈欣", "科幻", "36.00", 150, "重庆出版社", 2008),
        ("活着", "余华", "文学", "29.00", 200, "作家出版社", 1993),
        ("Python编程从入门到实践", "Eric Matthes", "技术", "89.00", 80, "人民邮电出版社", 2020),
        ("明朝那些事儿", "当年明月", "历史", "168.00", 60, "浙江人民出版社", 2009),
        ("原则", "瑞·达利欧", "经管", "98.00", 45, "中信出版社", 2018),
        ("流浪地球", "刘慈欣", "科幻", "32.00", 120, "中国华侨出版社", 2000),
        ("深度学习", "Ian Goodfellow", "技术", "168.00", 30, "人民邮电出版社", 2017),
        ("百年孤独", "马尔克斯", "文学", "55.00", 90, "南海出版公司", 2011),
        ("人类简史", "尤瓦尔·赫拉利", "历史", "68.00", 75, "中信出版社", 2014),
        ("从零到一", "彼得·蒂尔", "经管", "45.00", 55, "中信出版社", 2015),
        ("设计模式", "GoF", "技术", "79.00", 40, "机械工业出版社", 2000),
        ("围城", "钱钟书", "文学", "25.00", 180, "人民文学出版社", 1947),
    ]
    cur.executemany(
        "INSERT INTO books (title, author, genre, price, stock, publisher, publish_year) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        books,
    )

    # ── orders ─────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL REFERENCES customers(id),
        book_id     INTEGER NOT NULL REFERENCES books(id),
        quantity    INTEGER NOT NULL DEFAULT 1,
        total_price TEXT    NOT NULL,   -- TEXT，与 books.price 一致
        order_date  TEXT    NOT NULL,
        status      TEXT    DEFAULT '已完成'  -- 已完成 / 待发货 / 已取消
    );
    """)
    orders = [
        (1, 1, 2, "72.00", "2025-01-15", "已完成"),
        (1, 3, 1, "89.00", "2025-02-20", "已完成"),
        (2, 2, 1, "29.00", "2025-01-10", "已完成"),
        (2, 5, 1, "98.00", "2025-03-01", "待发货"),
        (3, 1, 1, "36.00", "2025-02-14", "已完成"),
        (3, 8, 2, "110.00", "2025-03-05", "已完成"),
        (4, 7, 1, "168.00", "2025-01-22", "已完成"),
        (4, 4, 1, "168.00", "2025-02-28", "已取消"),
        (5, 6, 3, "96.00", "2025-03-10", "待发货"),
        (6, 3, 1, "89.00", "2025-01-05", "已完成"),
        (6, 11, 1, "79.00", "2025-02-15", "已完成"),
        (7, 9, 1, "68.00", "2025-03-12", "已完成"),
        (8, 12, 1, "25.00", "2025-01-20", "已完成"),
        (9, 10, 2, "90.00", "2025-02-25", "待发货"),
        (10, 1, 1, "36.00", "2025-03-15", "已完成"),
    ]
    cur.executemany(
        "INSERT INTO orders (customer_id, book_id, quantity, total_price, order_date, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        orders,
    )

    conn.commit()
    conn.close()

    print(f"✅ Sample database created: {OUTPUT}")
    print(
        f"   Tables: customers ({len(customers)} rows), "
        f"books ({len(books)} rows), orders ({len(orders)} rows)"
    )


if __name__ == "__main__":
    main()
