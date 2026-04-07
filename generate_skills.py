# /// script
# requires-python = ">=3.10"
# dependencies = ["psycopg[binary]", "PySocks"]
# ///
"""Generate SKILL.md files for the 7 tables in enterprise.sqlite.

Mirrors the format produced by `create_skills/table_description_json_to_skills.py`,
but the table/column descriptions are hand-written (no LLM call) so the script can
run offline.

Example values are sampled with a hybrid strategy:
  - ID / name / contact / credential columns -> pulled from enterprise.sqlite
    (already sanitized placeholders, so the SKILL doesn't leak PII).
  - Everything else -> pulled live from the real Postgres source via the
    SOCKS5 proxy on 127.0.0.1:53162, so the agent sees realistic distinct
    values (industry classifications, addresses, scales, statuses, etc.).
"""

import socket
import socks
import sqlite3
from pathlib import Path

# Route TCP through local SOCKS5 proxy for the Postgres connection
socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 53162)
socket.socket = socks.socksocket

import psycopg

DB_PATH = Path(__file__).parent / "enterprise.sqlite"
OUT_DIR = Path(__file__).parent / "skills_table_7"
EXAMPLE_LIMIT = 3

PG_CONN = dict(
    host="14.103.94.133",
    port=5432,
    dbname="north_nova_ei_prod",
    user="nova_ei_readonly",
    password="Twmzoo3YHA&f&EYm",
    connect_timeout=30,
)
PG_SCHEMA = "public"

# Columns whose example values must come from enterprise.sqlite (placeholder data),
# never from real PG, because they identify entities or are PII / credentials.
MOCK_ONLY_COLS: set[str] = {
    # numeric / string identifiers
    "id", "credit_code", "sequence_number", "sso_user_id", "product_index",
    # entity & person names
    "enterprise_name",
    "legal_person_name", "manager_name", "contact_name",
    "controlling_shareholder", "actual_controller",
    "display_name", "username",
    # contact info
    "legal_person_phone", "legal_person_mobile",
    "manager_phone", "manager_mobile",
    "contact_phone", "contact_mobile",
    "fax", "email",
    # credentials / opaque blobs
    "password_hash", "sso_raw_data",
    # internal pipeline file names — leaks ingestion-source structure
    "data_source",
    # long-form free text & JSON that may contain founder names / real phones
    "enterprise_introduction", "legal_entity_data",
    # real company URLs
    "website",
}

# ----------------------------------------------------------------------
# Hand-written table & column descriptions
# ----------------------------------------------------------------------

TABLE_META: dict[str, dict] = {
    "enterprise_basic": {
        "overview": (
            "enterprise_basic 是企业基础信息主表,存储申报主体的工商注册要素(信用代码、"
            "企业名称、注册地、注册资本、注册日期等)、行业分类(国民经济行业四级)、"
            "申报属性(申报年度、申报类型、专精特新等级、独角兽分类)及法人实体快照。"
            "该表是企业域所有子表(联系人、融资、产品、产业链)通过 credit_code 进行 JOIN 的核心。"
            "可用于企业画像、行业分布统计、申报批次跟踪、专精特新/独角兽筛选与质量审计等场景。"
        ),
        "usage_scenarios": [
            "企业画像查询:按 credit_code 或 enterprise_name 定位企业的注册、规模、行业、资本等基本信息",
            "行业分布统计:按 industry_level1 ~ industry_level4 进行四级行业聚合统计",
            "专精特新筛选:通过 zhuanjingtexin_level、declaration_type、declaration_year 找出特定批次的入选企业",
            "独角兽企业分析:用 unicorn_category、unicorn_year 筛选独角兽企业并按行业/年份分组",
            "区域招商分析:按 register_district、jurisdiction_district 统计辖区内企业数量与规模分布",
            "数据治理:用 data_batch、created_at、updated_at 进行批次比对和数据更新审计",
        ],
        "columns": {
            "id":                              "自增主键,内部唯一行 ID",
            "credit_code":                     "统一社会信用代码,企业的法定唯一标识,跨表 JOIN 的主键",
            "enterprise_name":                 "企业法定全称",
            "declaration_year":                "申报年度,用于按年份维度过滤申报批次",
            "data_batch":                      "数据批次号,标识本条记录所属的导入批次",
            "sequence_number":                 "申报序号,批次内的排序编号",
            "register_district":               "注册地行政区划(区/县)",
            "jurisdiction_district":           "管辖地行政区划(区/县),通常与注册地相同",
            "street":                          "注册街道",
            "register_address":                "注册地详细地址",
            "correspondence_address":          "通讯/办公地址",
            "postal_code":                     "邮政编码",
            "register_date":                   "工商注册成立日期",
            "register_capital":                "注册资本(单位:万元),按 register_capital_currency 标识币种",
            "register_capital_currency":       "注册资本币种(人民币/美元/港币等)",
            "enterprise_scale":                "企业规模分类(微型/小型/中型/大型)",
            "enterprise_type":                 "企业经济类型(内资/合资/外资/有限责任公司等)",
            "foreign_capital_ratio":           "外资比例(0~1 之间的小数),用于内外资统计",
            "industry_level1":                 "国民经济行业分类一级(门类)",
            "industry_level2":                 "国民经济行业分类二级(大类)",
            "industry_level3":                 "国民经济行业分类三级(中类)",
            "industry_level4":                 "国民经济行业分类四级(小类)",
            "main_product_service":            "主营产品/服务的简短描述",
            "main_product_category":           "主营产品大类标签",
            "market_years":                    "进入市场年限(年)",
            "enterprise_introduction":         "企业自我介绍/简介长文本",
            "website":                         "企业官方网站 URL",
            "declaration_type":                "申报类型(新申报/复审/更新/专精特新中小企业/小巨人等)",
            "zhuanjingtexin_level":            "专精特新等级标签(如 专精特新中小企业 / 小巨人 / 单项冠军)",
            "financial_outlier_analysis":      "财务异常分析结果(0=无异常 / 1=有异常 等编码)",
            "municipal_high_level_enterprise": "是否市级高新技术企业的二值标识(0/1)",
            "data_source":                     "数据来源标识,记录条目的导入来源",
            "created_at":                      "记录创建时间",
            "updated_at":                      "记录最后更新时间",
            "unicorn_category":                "独角兽企业分类(独角兽/潜在独角兽/瞪羚等),非独角兽为空",
            "unicorn_year":                    "认定为独角兽的年份",
            "legal_entity_data":               "法人实体补充数据(JSON 字符串),包含登记号、成立年份、员工数等结构化字段",
        },
    },
    "enterprise_contact": {
        "overview": (
            "enterprise_contact 是企业联系人信息表,记录每家企业的法人代表、企业高管(总经理)、"
            "日常对接联系人三组人员的姓名、职务、座机、手机,以及企业传真、邮箱、控股股东、"
            "实际控制人及其国籍。该表通过 credit_code 与 enterprise_basic 一对一关联,"
            "用于触达企业、识别控制关系、合规审查等场景。注意:本表含 PII,生产环境查询需脱敏。"
        ),
        "usage_scenarios": [
            "企业触达:按 credit_code 查询企业法人/总经理/对接人的电话、邮箱以发起业务沟通",
            "控制关系识别:通过 controlling_shareholder、actual_controller、actual_controller_nationality 分析企业实控人结构与外资背景",
            "高管画像:统计法人代表与高管的职务分布",
            "数据完整度审计:检查关键联系字段的填充率,定位需补全的企业",
            "合规筛查:筛选 actual_controller_nationality 非中国大陆的企业以满足外资监管要求",
        ],
        "columns": {
            "id":                            "自增主键",
            "credit_code":                   "统一社会信用代码,关联 enterprise_basic.credit_code",
            "legal_person_name":             "法定代表人姓名(PII)",
            "legal_person_position":         "法定代表人职务",
            "legal_person_phone":            "法定代表人座机(PII)",
            "legal_person_mobile":           "法定代表人手机号(PII)",
            "manager_name":                  "企业总经理姓名(PII)",
            "manager_position":              "企业总经理职务",
            "manager_phone":                 "总经理座机(PII)",
            "manager_mobile":                "总经理手机号(PII)",
            "contact_name":                  "日常对接联系人姓名(PII)",
            "contact_position":              "联系人职务",
            "contact_phone":                 "联系人座机(PII)",
            "contact_mobile":                "联系人手机号(PII)",
            "fax":                           "企业传真号码",
            "email":                         "企业对外联络邮箱(PII)",
            "controlling_shareholder":       "控股股东名称",
            "actual_controller":             "实际控制人姓名/名称",
            "actual_controller_nationality": "实际控制人国籍",
            "data_source":                   "数据来源标识",
            "created_at":                    "记录创建时间",
            "updated_at":                    "记录最后更新时间",
        },
    },
    "enterprise_financing": {
        "overview": (
            "enterprise_financing 是企业融资与资本市场信息表,记录企业的银行授信申请情况、"
            "授信满足率、贷款用途、未来融资计划与金额、近期股权融资额与估值、"
            "上市状态(未上市/新三板/已上市)、股票代码、计划上市进度与目的地等。"
            "通过 credit_code 与 enterprise_basic 一对一关联。"
            "可用于资金面分析、上市辅导筛选、估值排行、融资缺口识别等金融场景。"
        ),
        "usage_scenarios": [
            "上市企业筛选:按 listing_status 找出已上市/拟上市企业,结合 stock_code 关联行情",
            "融资需求分析:按 next_financing_demand、next_financing_method 统计未来融资规模与方式分布",
            "估值排行:按 recent_valuation 排序找出高估值企业",
            "授信满足度分析:通过 credit_satisfaction_rate 评估银行对中小企业的授信落地情况",
            "上市辅导跟踪:按 listing_progress、planned_listing_location 跟踪进入辅导期或申报期的企业",
            "海外上市监测:按 overseas_listing 标识筛选拟在境外/已在境外上市的企业",
        ],
        "columns": {
            "id":                          "自增主键",
            "credit_code":                 "统一社会信用代码,关联 enterprise_basic",
            "applied_bank_loan":           "是否申请过银行贷款的二值标识(0/1)",
            "credit_satisfaction_rate":    "授信满足率(0~1 之间的小数),银行实际授信/申请额度",
            "loan_purpose":                "贷款用途(流动资金/设备采购/研发投入/扩大产能等)",
            "next_financing_plan":         "下一轮融资计划时间窗(暂无/12个月内/24个月内等)",
            "next_financing_demand":       "下一轮融资需求金额(单位:万元)",
            "next_financing_method":       "下一轮融资方式(股权融资/债权融资/可转债等)",
            "recent_equity_financing":     "近期完成的股权融资金额(万元)",
            "recent_valuation":            "近期估值(万元),用于估值排行与变化分析",
            "listing_status":              "上市状态(未上市/新三板/已上市/拟上市)",
            "stock_code":                  "证券代码,已上市企业才有",
            "listing_progress":            "上市进度(无/辅导期/申报中等)",
            "planned_listing_location":    "计划上市地点(上交所/深交所/北交所/港交所等)",
            "overseas_listing":            "是否在境外上市的二值标识(是/否)",
            "data_source":                 "数据来源标识",
            "created_at":                  "记录创建时间",
            "updated_at":                  "记录最后更新时间",
        },
    },
    "enterprise_product": {
        "overview": (
            "enterprise_product 是企业主营产品明细表,以 (credit_code, product_index) "
            "为业务键存储每家企业的主要产品信息,包括产品名称、年度产品收入、日产能与产能单位,"
            "以及该产品对应的最多三条核心知识产权(专利/商标/著作权)名称。"
            "通过 credit_code 与 enterprise_basic 多对一关联。"
            "可用于产品收入排名、产能规模分析、知识产权 - 产品挂钩分析等。"
        ),
        "usage_scenarios": [
            "产品收入排行:按 product_revenue 排序找出高收入产品",
            "产能规模统计:按 daily_capacity + capacity_unit 聚合行业产能,需注意单位归一化",
            "知识产权-产品关联:通过 ip_name_1/2/3 找出哪些产品有专利支撑,定位创新驱动型产品",
            "企业产品多样化分析:GROUP BY credit_code 统计每家企业的产品数量",
            "主营产品命名规律分析:对 product_name 做文本分析定位行业关键词",
        ],
        "columns": {
            "id":              "自增主键",
            "credit_code":     "统一社会信用代码,关联 enterprise_basic",
            "product_index":   "产品序号(企业内自增),与 credit_code 组成业务键",
            "product_name":    "产品名称",
            "product_revenue": "产品年度收入(单位:万元)",
            "daily_capacity":  "日产能数量(字符串以兼容自由格式)",
            "capacity_unit":   "产能计量单位(件/日、吨/日、台/日、套/日 等)",
            "ip_name_1":       "关联知识产权 1 的名称(专利/商标/著作权)",
            "ip_name_2":       "关联知识产权 2 的名称",
            "ip_name_3":       "关联知识产权 3 的名称",
            "data_source":     "数据来源标识",
            "created_at":      "记录创建时间",
            "updated_at":      "记录最后更新时间",
        },
    },
    "industry": {
        "overview": (
            "industry 是产业链节点维表,以树形结构存储某条产业链上的所有节点(上游/中游/下游与各级细分),"
            "通过 (chain_id, parent_id, depth, sort_order, path) 表达层级和顺序,name 为节点名称,"
            "description 为该节点的业务定义。chain_position 标识节点在链条中的位置(up/middle/down),"
            "icon 提供前端图标名。该表是产业链可视化与企业-产业链映射(industry_enterprise)的基础。"
        ),
        "usage_scenarios": [
            "产业链可视化:递归遍历 parent_id 渲染树状或链状产业图谱",
            "节点检索:按 name、description 关键词搜索定位特定产业环节",
            "上下游分析:按 chain_position 区分上游基础设施 / 中游制造 / 下游应用",
            "层级统计:按 depth 统计每层节点数量,衡量产业链复杂度",
            "为企业打标:通过 path 与 industry_enterprise 关联,实现企业到产业链节点的快速归类",
        ],
        "columns": {
            "id":             "节点主键",
            "chain_id":       "所属产业链 ID,标识节点归属哪一条产业链",
            "parent_id":      "父节点 ID,根节点为 NULL",
            "name":           "节点名称(如 上游 / 算力基础设施 / 大模型 / 应用层 等)",
            "description":    "节点的业务定义与说明,可较长",
            "path":           "从根到当前节点的路径(JSON 数组形式存储 ID 序列)",
            "depth":          "节点深度(根为 0)",
            "sort_order":     "同级节点的排序权重",
            "created_at":     "创建时间",
            "updated_at":     "更新时间",
            "chain_position": "在产业链上的位置标识(up=上游 / middle=中游 / down=下游)",
            "icon":           "前端展示用的图标名(如 arrow-up-from-line)",
        },
    },
    "industry_enterprise": {
        "overview": (
            "industry_enterprise 是企业与产业链节点的关联表,记录每家企业被打上了哪些产业链节点标签。"
            "以 (industry_id, credit_code) 为复合主键,industry_path 缓存了节点的路径(JSON 数组,"
            "包含从根到当前节点的全部 ID),便于直接做产业链层级筛选,无需递归回溯 industry 表。"
            "该表是企业-产业链双向检索的核心。"
        ),
        "usage_scenarios": [
            "按产业链节点查企业:WHERE industry_id = ? 返回某节点上的所有企业",
            "按企业查产业链节点:WHERE credit_code = ? 返回该企业被打上的所有标签",
            "按产业链祖先节点过滤:利用 industry_path 包含某祖先 ID,聚合该子树下所有企业",
            "产业链热度统计:GROUP BY industry_id 计算每个节点的企业数量",
            "构造企业-产业的双向 index,用于推荐与匹配",
        ],
        "columns": {
            "industry_id":    "产业链节点 ID,关联 industry.id",
            "credit_code":    "统一社会信用代码,关联 enterprise_basic.credit_code",
            "created_at":     "关联记录创建时间",
            "chain_id":       "所属产业链 ID(冗余自 industry.chain_id 便于过滤)",
            "industry_path":  "节点路径(JSON 数组,包含从根到该节点的 ID 序列),用于按祖先快速过滤",
        },
    },
    "users": {
        "overview": (
            "users 是系统用户表,存储平台账号信息,支持本地账号与单点登录(SSO)双模式。"
            "包含 sso_user_id(SSO 唯一标识)、display_name(展示名)、email、role(角色)、"
            "username/password_hash(本地登录凭证)以及 sso_raw_data(SSO 原始 JSON 资料快照)。"
            "用于鉴权、审计、按角色过滤功能权限等场景。注意:本表含 PII 与凭证,严格按需脱敏访问。"
        ),
        "usage_scenarios": [
            "登录鉴权:按 username + password_hash 或 sso_user_id 校验用户身份",
            "角色过滤:按 role 字段判定用户的功能权限范围",
            "用户审计:按 created_at、updated_at 跟踪账号生命周期",
            "SSO 数据回查:从 sso_raw_data JSON 字段中提取额外的 SSO 属性",
            "用户列表展示:按 display_name、email 检索与展示",
        ],
        "columns": {
            "id":            "自增主键",
            "sso_user_id":   "单点登录系统中的用户唯一 ID",
            "display_name":  "用户展示名(PII)",
            "email":         "用户邮箱(PII)",
            "role":          "用户角色(user / admin / 等),用于权限控制",
            "created_at":    "账号创建时间",
            "updated_at":    "账号最后更新时间",
            "sso_raw_data":  "SSO 返回的用户原始资料(JSON 字符串)",
            "password_hash": "本地登录密码的哈希值(凭证,严禁明文返回)",
            "username":      "本地登录用户名",
        },
    },
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _format_examples(rows: list) -> list[str]:
    out = []
    for r in rows:
        v = r[0] if isinstance(r, tuple) else r
        if v is None:
            continue
        s = str(v).replace("\n", " ").strip()
        if not s:
            continue
        if len(s) > 80:
            s = s[:77] + "..."
        out.append(s)
    return out


def fetch_mock_examples(conn: sqlite3.Connection, table: str, col: str,
                        limit: int = EXAMPLE_LIMIT) -> list[str]:
    try:
        rows = conn.execute(
            f'SELECT DISTINCT "{col}" FROM "{table}" '
            f'WHERE "{col}" IS NOT NULL AND CAST("{col}" AS TEXT) != "" LIMIT ?',
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return _format_examples(rows)


def fetch_pg_examples(pg_cur, table: str, col: str,
                      limit: int = EXAMPLE_LIMIT) -> list[str]:
    try:
        pg_cur.execute(
            f'SELECT DISTINCT "{col}" FROM "{PG_SCHEMA}"."{table}" '
            f'WHERE "{col}" IS NOT NULL AND CAST("{col}" AS TEXT) <> \'\' '
            f'LIMIT %s',
            (limit,),
        )
        rows = pg_cur.fetchall()
        return _format_examples(rows)
    except Exception as e:
        print(f"    PG fetch failed for {table}.{col}: {e}")
        # rollback so the cursor stays usable
        try:
            pg_cur.connection.rollback()
        except Exception:
            pass
        return []


def fetch_examples(table: str, col: str, sqlite_conn: sqlite3.Connection,
                   pg_cur) -> list[str]:
    """Hybrid: mock for ID/PII columns, real PG for everything else."""
    if col in MOCK_ONLY_COLS:
        return fetch_mock_examples(sqlite_conn, table, col)
    real = fetch_pg_examples(pg_cur, table, col)
    if real:
        return real
    # fall back to mock if PG happens to have nothing
    return fetch_mock_examples(sqlite_conn, table, col)


def col_sql_type(sqlite_type: str) -> str:
    t = (sqlite_type or "").upper()
    if t == "INTEGER":
        return "int"
    if t == "REAL":
        return "float"
    if t == "BLOB":
        return "bytea"
    return "text"


def render_skill_md(table: str, meta: dict, col_rows: list[tuple], examples_map: dict) -> str:
    overview = meta["overview"]
    usage_scenarios = meta["usage_scenarios"]
    col_meanings = meta["columns"]

    empty_columns = [c for (c, _t) in col_rows if not examples_map.get(c)]

    parts: list[str] = []
    parts.append("---")
    parts.append(f"name: {table}")
    parts.append(f"description: {overview}")
    parts.append("---")
    parts.append("")
    parts.append(f"# {table}")
    parts.append("")
    parts.append(overview)
    parts.append("")
    parts.append("## 数据表")
    parts.append("")
    parts.append("本技能覆盖以下数据表:")
    parts.append("")
    parts.append(f"- `{table}`")
    parts.append("")
    parts.append("## 使用场景")
    parts.append("")
    for sc in usage_scenarios:
        parts.append(f"- {sc}")
    parts.append("")

    if empty_columns:
        parts.append("## 空列说明")
        parts.append("")
        parts.append("以下列在当前 mock 数据中没有示例值,使用时需注意:")
        parts.append("")
        for c in empty_columns:
            parts.append(f"- `{c}`")
        parts.append("")

    parts.append("## 表详细说明")
    parts.append("")
    parts.append(f"### {table}")
    parts.append("")
    parts.append(f"**用途**: {overview}")
    parts.append("")
    parts.append("**特点**:")
    parts.append("- 本表存储来自数据源的原始数据,包含完整的字段信息")
    parts.append("- 支持数据查询、分析和统计需求")
    parts.append("- 包含创建与更新时间戳,便于数据追踪")
    parts.append("")
    parts.append("**典型查询**:")
    for sc in usage_scenarios[:3]:
        parts.append(f"- {sc}")
    parts.append("")

    parts.append("## 表结构 DDL")
    parts.append("")
    parts.append(f"### {table}")
    parts.append("")
    parts.append("```sql")
    parts.append(f"CREATE TABLE {table} (")
    n = len(col_rows)
    for i, (cname, ctype) in enumerate(col_rows):
        sql_type = col_sql_type(ctype)
        meaning = col_meanings.get(cname, "")
        examples = examples_map.get(cname, [])
        comment_parts = []
        if meaning:
            comment_parts.append(meaning)
        if examples:
            comment_parts.append(f"examples: [{', '.join(examples)}]")
        comment = f" -- {' | '.join(comment_parts)}" if comment_parts else ""
        sep = "" if i == n - 1 else ","
        parts.append(f"    {cname} {sql_type}{sep}{comment}")
    parts.append(")")
    parts.append("```")
    parts.append("")

    return "\n".join(parts)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    if not DB_PATH.exists():
        raise SystemExit(f"missing {DB_PATH}; run build_mock_sqlite.py first")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    print("connecting to PG via SOCKS5 for real example values...")
    pg = psycopg.connect(**PG_CONN)
    pg_cur = pg.cursor()

    for table, meta in TABLE_META.items():
        cols = conn.execute(f'SELECT name, type FROM pragma_table_info("{table}")').fetchall()
        if not cols:
            print(f"  SKIP {table}: not found in enterprise.sqlite")
            continue
        examples = {c: fetch_examples(table, c, conn, pg_cur) for c, _ in cols}

        # warn about meaning gaps
        defined = set(meta["columns"].keys())
        actual = {c for c, _ in cols}
        missing_meaning = actual - defined
        extra_meaning = defined - actual
        if missing_meaning:
            print(f"  ! {table}: columns without meaning: {sorted(missing_meaning)}")
        if extra_meaning:
            print(f"  ! {table}: meaning entries without columns: {sorted(extra_meaning)}")

        md = render_skill_md(table, meta, cols, examples)

        table_dir = OUT_DIR / table
        table_dir.mkdir(parents=True, exist_ok=True)
        skill_file = table_dir / "SKILL.md"
        skill_file.write_text(md, encoding="utf-8")
        print(f"  wrote {skill_file}")

    conn.close()
    pg_cur.close()
    pg.close()
    print(f"\nDone. {len(TABLE_META)} skills under {OUT_DIR}/")


if __name__ == "__main__":
    main()
