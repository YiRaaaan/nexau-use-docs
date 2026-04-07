# /// script
# requires-python = ">=3.10"
# dependencies = ["psycopg[binary]", "PySocks"]
# ///
"""Build enterprise.sqlite from 7 core enterprise tables in north_nova_ei_prod."""
import socket
import socks
import sqlite3
import json
import os
import random
from decimal import Decimal
from datetime import date, datetime, time

# Seed for reproducible mock data
RNG = random.Random(20260407)

socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 53162)
socket.socket = socks.socksocket

import psycopg

CONN = dict(
    host="14.103.94.133", port=5432, dbname="north_nova_ei_prod",
    user="nova_ei_readonly", password="Twmzoo3YHA&f&EYm", connect_timeout=30,
)

CORE_TABLES = [
    "enterprise_basic",
    "enterprise_contact",
    "enterprise_financing",
    "enterprise_product",
    "industry",
    "industry_enterprise",
    "users",
]
SCHEMA = "public"
SAMPLE_LIMIT = 50
OUT_DB = "enterprise.sqlite"

# Postgres → SQLite type mapping
def pg_to_sqlite_type(pg_type: str) -> str:
    t = pg_type.lower()
    if t in ("smallint", "integer", "bigint", "smallserial", "serial", "bigserial"):
        return "INTEGER"
    if t in ("real", "double precision", "numeric", "decimal", "money"):
        return "REAL"
    if t == "boolean":
        return "INTEGER"  # 0/1
    if t == "bytea":
        return "BLOB"
    # text-ish: char/varchar/text/uuid/json/jsonb/timestamp/date/time/interval/array
    return "TEXT"


# --- sanitization ---------------------------------------------------------
SENSITIVE_NAME_COLS = {
    "legal_person_name", "manager_name", "contact_name", "display_name",
    "username", "actual_controller", "controlling_shareholder",
    "actual_controller_nationality",
}

# Pools for plausible-but-fake values
_DISTRICTS = ["朝阳区", "海淀区", "西城区", "东城区", "丰台区", "通州区",
              "南山区", "福田区", "罗湖区", "宝安区",
              "浦东新区", "黄浦区", "徐汇区", "长宁区",
              "天河区", "越秀区", "番禺区", "白云区"]
_STREETS  = ["科技路", "创业大道", "中关村大街", "高新路", "人民路",
             "解放路", "工业园路", "金融街", "长安街", "南京路"]
_CITIES   = ["北京市", "上海市", "深圳市", "广州市", "杭州市", "成都市",
             "南京市", "苏州市", "武汉市", "西安市"]
_CAT_WORDS = ["智能", "数字", "高端", "绿色", "新材料", "生物", "新能源",
              "光电", "半导体", "云计算", "工业", "信息"]
_PROD_TAILS = ["装备", "解决方案", "系统", "平台", "组件", "服务", "材料"]
_LISTING_STATUS = ["未上市", "新三板", "已上市", "拟上市"]

def _rand_capital() -> float:
    return round(RNG.uniform(100, 50000), 2)  # 万元

def _rand_ratio() -> float:
    return round(RNG.uniform(0, 1), 4)

def _rand_phrase(n: int = 2) -> str:
    return "".join(RNG.choice(_CAT_WORDS) for _ in range(n))

def _rand_address() -> str:
    return f"{RNG.choice(_CITIES)}{RNG.choice(_DISTRICTS)}{RNG.choice(_STREETS)}{RNG.randint(1, 999)}号"

def _rand_postal() -> str:
    return f"{RNG.randint(100000, 999999)}"

def _rand_intro(r: int) -> str:
    return (f"测试企业 {r} 是一家专注于{_rand_phrase(2)}领域的高新技术企业,"
            f"主要从事{_rand_phrase()}{RNG.choice(_PROD_TAILS)}的研发与生产,"
            f"产品广泛应用于多个行业。本介绍为脱敏占位文本,仅供本地开发使用。")

def _rand_legal_entity(r: int) -> dict:
    return {
        "mock": True,
        "row": r,
        "reg_no": f"MOCKREG{RNG.randint(10**9, 10**10 - 1)}",
        "establish_year": RNG.randint(1995, 2024),
        "employee_count": RNG.randint(20, 5000),
        "note": "sanitized",
    }

def _rand_stock_code() -> str:
    return RNG.choice(["", "", "", f"{RNG.randint(1, 999999):06d}"])

# Per-table columns replaced with plausible MOCK values.
# Each entry: (table, col) -> callable(ridx) -> mock value
MOCK_VALUES: dict[tuple[str, str], object] = {
    # enterprise_basic --------------------------------------------------
    ("enterprise_basic", "register_district"):          lambda r: RNG.choice(_DISTRICTS),
    ("enterprise_basic", "jurisdiction_district"):      lambda r: RNG.choice(_DISTRICTS),
    ("enterprise_basic", "street"):                     lambda r: RNG.choice(_STREETS),
    ("enterprise_basic", "register_address"):           lambda r: _rand_address(),
    ("enterprise_basic", "correspondence_address"):     lambda r: _rand_address(),
    ("enterprise_basic", "postal_code"):                lambda r: _rand_postal(),
    ("enterprise_basic", "register_capital"):           lambda r: _rand_capital(),
    ("enterprise_basic", "register_capital_currency"):  lambda r: "人民币",
    ("enterprise_basic", "foreign_capital_ratio"):      lambda r: _rand_ratio(),
    ("enterprise_basic", "main_product_service"):       lambda r: f"{_rand_phrase()}{RNG.choice(_PROD_TAILS)}",
    ("enterprise_basic", "main_product_category"):      lambda r: _rand_phrase(1),
    ("enterprise_basic", "enterprise_introduction"):    lambda r: _rand_intro(r),
    ("enterprise_basic", "website"):                    lambda r: f"https://example.com/mock/{r}",
    ("enterprise_basic", "legal_entity_data"):          lambda r: _rand_legal_entity(r),
    ("enterprise_basic", "financial_outlier_analysis"): lambda r: RNG.choice(["无异常", "无异常", "轻微异常"]),
    ("enterprise_basic", "data_batch"):                 lambda r: f"MOCK_BATCH_{RNG.randint(1, 9):03d}",
    ("enterprise_basic", "sequence_number"):            lambda r: r,
    # enterprise_financing ----------------------------------------------
    ("enterprise_financing", "applied_bank_loan"):        lambda r: RNG.randint(0, 1),
    ("enterprise_financing", "credit_satisfaction_rate"): lambda r: round(RNG.uniform(0.3, 1.0), 2),
    ("enterprise_financing", "loan_purpose"):             lambda r: RNG.choice(["流动资金", "设备采购", "研发投入", "扩大产能"]),
    ("enterprise_financing", "next_financing_plan"):      lambda r: RNG.choice(["暂无", "12个月内", "24个月内"]),
    ("enterprise_financing", "next_financing_demand"):    lambda r: round(RNG.uniform(500, 20000), 2),
    ("enterprise_financing", "next_financing_method"):    lambda r: RNG.choice(["股权融资", "债权融资", "可转债"]),
    ("enterprise_financing", "recent_equity_financing"):  lambda r: round(RNG.uniform(0, 30000), 2),
    ("enterprise_financing", "recent_valuation"):         lambda r: round(RNG.uniform(5000, 500000), 2),
    ("enterprise_financing", "listing_status"):           lambda r: RNG.choice(_LISTING_STATUS),
    ("enterprise_financing", "stock_code"):               lambda r: _rand_stock_code(),
    ("enterprise_financing", "listing_progress"):         lambda r: RNG.choice(["无", "辅导期", "申报中"]),
    ("enterprise_financing", "planned_listing_location"): lambda r: RNG.choice(["无", "上交所", "深交所", "北交所", "港交所"]),
    ("enterprise_financing", "overseas_listing"):         lambda r: RNG.choice(["否", "否", "是"]),
    # enterprise_product ------------------------------------------------
    ("enterprise_product", "product_revenue"): lambda r: round(RNG.uniform(50, 20000), 2),
    ("enterprise_product", "daily_capacity"):  lambda r: f"{RNG.randint(10, 5000)}",
    ("enterprise_product", "capacity_unit"):   lambda r: RNG.choice(["件/日", "吨/日", "台/日", "套/日"]),
    ("enterprise_product", "ip_name_1"):       lambda r: f"示例专利_{r}_{RNG.randint(1000,9999)}",
    ("enterprise_product", "ip_name_2"):       lambda r: f"示例专利_{r}_{RNG.randint(1000,9999)}",
    ("enterprise_product", "ip_name_3"):       lambda r: f"示例专利_{r}_{RNG.randint(1000,9999)}",
}

# Shared cross-table remap so credit_code/enterprise_name stay consistent
class SanitizeCtx:
    def __init__(self):
        self.credit_map: dict[str, str] = {}
        self.name_map: dict[str, str] = {}

    def fake_credit(self, real: str) -> str:
        if real not in self.credit_map:
            self.credit_map[real] = f"MOCKCREDIT{len(self.credit_map)+1:010d}"
        return self.credit_map[real]

    def fake_name(self, credit_code_real: str) -> str:
        if credit_code_real not in self.name_map:
            self.name_map[credit_code_real] = f"测试企业_{len(self.name_map)+1}"
        return self.name_map[credit_code_real]


def sanitize_row(table: str, col_names: list[str], row: tuple, ridx: int, ctx: SanitizeCtx) -> tuple:
    out = list(row)
    # find credit_code value in this row (for name remap)
    cc_idx = col_names.index("credit_code") if "credit_code" in col_names else None
    cc_real = row[cc_idx] if cc_idx is not None else None

    for i, col in enumerate(col_names):
        n = col.lower()
        v = row[i]

        # 1) per-(table,col) MOCK override (replaces sensitive real values
        #    with plausible randomized data — even if original is NULL)
        mock_fn = MOCK_VALUES.get((table, col))
        if mock_fn is not None:
            out[i] = mock_fn(ridx)
            continue

        if v is None:
            continue

        # 2) credit_code → fake mapped
        if n == "credit_code":
            out[i] = ctx.fake_credit(v)
            continue

        # 3) enterprise_name → fake mapped (tied to credit_code)
        if n == "enterprise_name" and cc_real:
            out[i] = ctx.fake_name(cc_real)
            continue

        # 4) product_name in enterprise_product
        if table == "enterprise_product" and n == "product_name":
            out[i] = f"产品_{ridx}"
            continue

        # 5) credentials / tokens
        if "password" in n or "pwd" in n or "secret" in n or "token" in n:
            out[i] = "REDACTED"
            continue
        if "sso_raw" in n or n == "sso_user_id":
            out[i] = "REDACTED"
            continue

        # 6) email / phone / fax
        if "email" in n:
            out[i] = f"user{ridx}@example.com"
            continue
        if "phone" in n or "mobile" in n or n == "fax":
            out[i] = f"138{ridx:08d}"
            continue

        # 7) personal names / controllers
        if n in SENSITIVE_NAME_COLS:
            out[i] = f"REDACTED_{ridx}"
            continue

        # 8) internal pipeline file names
        if n == "data_source":
            out[i] = None
            continue

    return tuple(out)


def py_to_sqlite(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float, str, bytes)):
        return v
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    # list/dict/tuple/uuid/etc → JSON text
    try:
        return json.dumps(v, ensure_ascii=False, default=str)
    except Exception:
        return str(v)


def main():
    if os.path.exists(OUT_DB):
        os.remove(OUT_DB)

    sqlite = sqlite3.connect(OUT_DB)
    sqlite.execute("PRAGMA foreign_keys = OFF;")
    ctx = SanitizeCtx()
    # Set after enterprise_basic is sampled, used to scope FK-dependent tables
    parent_credit_codes: list[str] = []

    with psycopg.connect(**CONN) as pg:
        with pg.cursor() as cur:
            for tbl in CORE_TABLES:
                print(f"\n=== {SCHEMA}.{tbl} ===")

                # columns
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema=%s AND table_name=%s
                    ORDER BY ordinal_position;
                """, (SCHEMA, tbl))
                cols = cur.fetchall()
                if not cols:
                    print(f"  SKIP: table not found")
                    continue

                # primary key
                cur.execute("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = %s::regclass AND i.indisprimary
                    ORDER BY array_position(i.indkey, a.attnum);
                """, (f'"{SCHEMA}"."{tbl}"',))
                pk_cols = [r[0] for r in cur.fetchall()]

                # build CREATE TABLE
                col_defs = []
                for name, dtype, nullable, _default in cols:
                    sqlite_type = pg_to_sqlite_type(dtype)
                    parts = [f'"{name}"', sqlite_type]
                    if nullable == "NO" and name not in pk_cols:
                        parts.append("NOT NULL")
                    col_defs.append(" ".join(parts))
                if pk_cols:
                    pk_list = ", ".join(f'"{c}"' for c in pk_cols)
                    col_defs.append(f"PRIMARY KEY ({pk_list})")
                ddl = f'CREATE TABLE "{tbl}" (\n  ' + ",\n  ".join(col_defs) + "\n);"
                print(ddl)
                sqlite.execute(ddl)

                # sample rows
                col_names = [c[0] for c in cols]
                quoted_cols = ", ".join(f'"{c}"' for c in col_names)
                order_clause = f"ORDER BY {', '.join(chr(34)+c+chr(34) for c in pk_cols)}" if pk_cols else ""

                # FK-scoped tables: only sample rows whose credit_code is in parent set
                child_tables_with_cc = {
                    "enterprise_contact", "enterprise_financing",
                    "enterprise_product", "industry_enterprise",
                }
                if tbl in child_tables_with_cc and parent_credit_codes:
                    cur.execute(
                        f'SELECT {quoted_cols} FROM "{SCHEMA}"."{tbl}" '
                        f'WHERE credit_code = ANY(%s) {order_clause} LIMIT {SAMPLE_LIMIT}',
                        (parent_credit_codes,),
                    )
                else:
                    cur.execute(
                        f'SELECT {quoted_cols} FROM "{SCHEMA}"."{tbl}" '
                        f'{order_clause} LIMIT {SAMPLE_LIMIT}'
                    )
                rows = cur.fetchall()

                # capture parent credit_codes for downstream FK scoping
                if tbl == "enterprise_basic" and "credit_code" in col_names:
                    cc_idx = col_names.index("credit_code")
                    parent_credit_codes = [r[cc_idx] for r in rows if r[cc_idx]]
                print(f"  fetched {len(rows)} rows")

                if rows:
                    placeholders = ", ".join(["?"] * len(col_names))
                    insert_sql = f'INSERT INTO "{tbl}" ({quoted_cols}) VALUES ({placeholders})'
                    converted = [
                        tuple(
                            py_to_sqlite(v)
                            for v in sanitize_row(tbl, col_names, row, ridx, ctx)
                        )
                        for ridx, row in enumerate(rows, start=1)
                    ]
                    sqlite.executemany(insert_sql, converted)

    sqlite.commit()

    # report
    print("\n=== enterprise.sqlite summary ===")
    cur2 = sqlite.cursor()
    for tbl in CORE_TABLES:
        try:
            n = cur2.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
            print(f"  {tbl}: {n} rows")
        except sqlite3.OperationalError as e:
            print(f"  {tbl}: ERR {e}")
    sqlite.close()
    print(f"\nWrote {OUT_DB} ({os.path.getsize(OUT_DB)} bytes)")


if __name__ == "__main__":
    main()
