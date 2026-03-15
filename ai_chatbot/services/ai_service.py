# -*- coding: utf-8 -*-
"""
AIService — Integrates Google Gemini API to generate SQL from natural language questions.
"""
import re
import json
import time
import logging

try:
    import requests
except ImportError:
    requests = None

_logger = logging.getLogger(__name__)

GEMINI_API_KEY = 'AIzaSyCbBWd-Lq5n0DuJxUH-rLgacfJktYXHxNI'
GEMINI_BASE_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    '{model}:generateContent?key={api_key}'
)

# Models to try in order — first one that returns 200 is used
GEMINI_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-2.0-flash',
]

# ─── Schema context embedded in the system prompt ───────────────────────────
SCHEMA_CONTEXT = u"""
## DATABASE SCHEMA — ODOO 11 ERP (PostgreSQL)

### NAMING CONVENTIONS
- Odoo model "a.b.c" maps to PostgreSQL table "a_b_c"
- Standard Odoo columns use snake_case; all names are case-sensitive in quoted form
- Always wrap column and table names in double quotes when they conflict with SQL keywords

---

### CORE SALES TABLES

#### sale_order — Sales Orders / Quotations
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Order reference (e.g. SO001) |
| state | varchar | draft / sent / sale / done / cancel |
| date_order | timestamp | Order date/time |
| confirmation_date | timestamp | Date the order was confirmed |
| partner_id | int | FK → res_partner.id (customer) |
| partner_invoice_id | int | FK → res_partner.id (invoice address) |
| partner_shipping_id | int | FK → res_partner.id (delivery address) |
| user_id | int | FK → res_users.id (salesperson) |
| team_id | int | FK → crm_team.id (sales channel) |
| pricelist_id | int | FK → product_pricelist.id |
| currency_id | int | FK → res_currency.id |
| company_id | int | FK → res_company.id |
| amount_untaxed | float | Subtotal (excl. tax) |
| amount_tax | float | Total taxes |
| amount_total | float | Grand total (incl. tax) |
| invoice_status | varchar | upselling / invoiced / to invoice / no |
| payment_term_id | int | FK → account_payment_term.id |
| analytic_account_id | int | FK → account_analytic_account.id |
| client_order_ref | varchar | Customer reference |
| origin | varchar | Source document |
| note | text | Terms and conditions |

#### sale_order_line — Sales Order Lines
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| order_id | int | FK → sale_order.id |
| product_id | int | FK → product_product.id |
| name | text | Product description |
| product_uom_qty | float | Ordered quantity |
| qty_delivered | float | Delivered quantity |
| qty_invoiced | float | Invoiced quantity |
| qty_to_invoice | float | Quantity remaining to invoice |
| price_unit | float | Unit price |
| discount | float | Discount (%) |
| price_subtotal | float | Subtotal (excl. tax) |
| price_tax | float | Tax amount |
| price_total | float | Total (incl. tax) |
| amt_invoiced | float | Amount already invoiced |
| amt_to_invoice | float | Amount remaining to invoice |
| invoice_status | varchar | upselling / invoiced / to invoice / no |
| state | varchar | Mirrors sale_order.state |
| salesman_id | int | FK → res_users.id |
| company_id | int | FK → res_company.id |
| currency_id | int | FK → res_currency.id |
| customer_lead | float | Delivery lead time (days) |
| product_uom | int | FK → product_uom.id |
| is_downpayment | boolean | True if this is a down-payment line |

---

### PRODUCT TABLES

#### product_product — Product Variants
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| product_tmpl_id | int | FK → product_template.id |
| default_code | varchar | Internal reference / SKU |
| active | boolean | Active flag |

#### product_template — Product Templates
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Product name |
| type | varchar | consu / service / product |
| categ_id | int | FK → product_category.id |
| list_price | float | Sales price |
| standard_price | float | Cost price |
| uom_id | int | FK → product_uom.id |
| active | boolean | Active flag |
| sale_ok | boolean | Can be sold |
| purchase_ok | boolean | Can be purchased |

#### product_category — Product Categories
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Category name |
| parent_id | int | FK → product_category.id |
| complete_name | varchar | Full hierarchical name |

---

### PARTNER & USER TABLES

#### res_partner — Partners (Customers, Vendors, Contacts)
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Partner name |
| ref | varchar | Internal reference code |
| email | varchar | Email address |
| phone | varchar | Phone number |
| customer | boolean | True if customer |
| supplier | boolean | True if vendor/supplier |
| company_id | int | FK → res_company.id |
| parent_id | int | FK → res_partner.id (parent company) |
| user_id | int | FK → res_users.id (salesperson responsible) |
| team_id | int | FK → crm_team.id (sales channel) |
| country_id | int | FK → res_country.id |
| city | varchar | City |

#### res_users — Users / Salespersons
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | User full name |
| login | varchar | Login email |
| partner_id | int | FK → res_partner.id |

---

### SALES CHANNEL / TEAM TABLE

#### crm_team — Sales Channels / Teams
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Team name |
| user_id | int | FK → res_users.id (team leader) |
| invoiced_target | int | Monthly invoicing target |
| active | boolean | Active flag |

---

### INVOICING TABLES

#### account_invoice — Customer Invoices & Vendor Bills
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| number | varchar | Invoice number |
| origin | varchar | Source document (SO reference) |
| type | varchar | out_invoice / out_refund / in_invoice / in_refund |
| state | varchar | draft / open / paid / cancel |
| date_invoice | date | Invoice date |
| date_due | date | Due date |
| partner_id | int | FK → res_partner.id |
| user_id | int | FK → res_users.id (salesperson) |
| team_id | int | FK → crm_team.id |
| company_id | int | FK → res_company.id |
| currency_id | int | FK → res_currency.id |
| amount_untaxed | float | Subtotal (excl. tax) |
| amount_tax | float | Tax amount |
| amount_total | float | Grand total |
| residual | float | Amount still due (outstanding) |
| journal_id | int | FK → account_journal.id |

#### account_invoice_line — Invoice Line Items
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| invoice_id | int | FK → account_invoice.id |
| product_id | int | FK → product_product.id |
| name | text | Description |
| quantity | float | Quantity |
| price_unit | float | Unit price |
| discount | float | Discount (%) |
| price_subtotal | float | Subtotal (excl. tax) |
| price_total | float | Total (incl. tax) |
| account_id | int | FK → account_account.id |
| uom_id | int | FK → product_uom.id |

---

### STOCK / INVENTORY TABLES

#### stock_move — Stock Movements
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Move description |
| date | timestamp | Movement date |
| product_id | int | FK → product_product.id |
| location_id | int | FK → stock_location.id (source) |
| location_dest_id | int | FK → stock_location.id (destination) |
| product_uom_qty | float | Initial demand quantity |
| quantity_done | float | Actual done quantity |
| state | varchar | draft / waiting / confirmed / assigned / done / cancel |
| picking_id | int | FK → stock_picking.id |
| sale_line_id | int | FK → sale_order_line.id |
| origin | varchar | Source document |
| price_unit | float | Unit cost |

#### stock_quant — Current Stock On-Hand
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| product_id | int | FK → product_product.id |
| location_id | int | FK → stock_location.id |
| qty | float | Quantity on hand |
| cost | float | Average cost |
| lot_id | int | FK → stock_production_lot.id (serial/lot) |

#### stock_location — Warehouse Locations
| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| name | varchar | Location name |
| complete_name | varchar | Full path name |
| usage | varchar | supplier / view / internal / customer / inventory / procurement / production / transit |
| location_id | int | FK → stock_location.id (parent) |

---

### IMPORTANT NOTES
- Filter by date: use `date_order` on sale_order; `date_invoice` on account_invoice; `date` on stock_move
- Confirmed sales orders: WHERE state IN ('sale', 'done')
- Paid/open invoices: WHERE state IN ('open', 'paid') AND type = 'out_invoice'
- Customer invoices only: type = 'out_invoice' (not 'in_invoice' which are vendor bills)
- Revenue = SUM(amount_untaxed) from account_invoice (state IN ('open','paid'), type='out_invoice')
- Order revenue = SUM(amount_untaxed) from sale_order (state IN ('sale','done'))
- Gross profit per line = (sol.price_unit * (1 - sol.discount/100) - pt.standard_price) * sol.product_uom_qty
- Current month: date_trunc('month', CURRENT_DATE)
- Current year:  date_trunc('year',  CURRENT_DATE)
- Always use double quotes for column/table names that may conflict with SQL keywords
- Default LIMIT: 50 rows unless the question asks for a specific number
"""

SYSTEM_PROMPT_SQL = u"""You are a senior SQL and business-data analyst for an Odoo 11 ERP system running on PostgreSQL.

Task: Convert the user's natural-language question into a precise, safe PostgreSQL SELECT statement.

{schema}

### MANDATORY RULES
1. Only generate SELECT statements — NEVER generate INSERT / UPDATE / DELETE / DROP / TRUNCATE
2. Always qualify ambiguous column names with the table alias
3. Always include a meaningful ORDER BY and a LIMIT (default: LIMIT 50)
4. Return exactly ONE SQL block formatted as ```sql ... ```
5. Do NOT explain the SQL — return only the code block
6. If the question is unrelated to business data, return:
   ```sql SELECT 'Sorry, I can only answer questions about business data.' AS message ```

### EXAMPLE QUERIES

Question: "What is this month's revenue by sales channel?"
SQL:
```sql
SELECT
    ct.name                          AS sales_channel,
    COUNT(DISTINCT so.id)            AS order_count,
    SUM(sol.price_subtotal)          AS revenue_excl_tax,
    SUM(sol.price_total)             AS revenue_incl_tax
FROM sale_order so
JOIN sale_order_line sol ON sol.order_id = so.id
LEFT JOIN crm_team ct ON ct.id = so.team_id
WHERE so.state IN ('sale', 'done')
  AND so.date_order >= date_trunc('month', CURRENT_DATE)
  AND so.date_order <  date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'
GROUP BY ct.name
ORDER BY revenue_excl_tax DESC
LIMIT 20
```

Question: "Top 10 customers by sales this quarter?"
SQL:
```sql
SELECT
    rp.name                          AS customer,
    rp.ref                           AS customer_code,
    COUNT(DISTINCT so.id)            AS order_count,
    SUM(sol.product_uom_qty)         AS total_qty,
    SUM(sol.price_subtotal)          AS total_revenue
FROM sale_order so
JOIN sale_order_line sol ON sol.order_id = so.id
JOIN res_partner rp ON rp.id = so.partner_id
WHERE so.state IN ('sale', 'done')
  AND so.date_order >= date_trunc('quarter', CURRENT_DATE)
  AND so.date_order <  date_trunc('quarter', CURRENT_DATE) + INTERVAL '3 months'
GROUP BY rp.id, rp.name, rp.ref
ORDER BY total_revenue DESC
LIMIT 10
```

Question: "Which products have the highest gross profit this month?"
SQL:
```sql
SELECT
    pt.name                                                            AS product_name,
    pp.default_code                                                    AS sku,
    SUM(sol.product_uom_qty)                                           AS qty_sold,
    SUM(sol.price_subtotal)                                            AS revenue,
    SUM(pt.standard_price * sol.product_uom_qty)                      AS cogs,
    SUM(sol.price_subtotal - pt.standard_price * sol.product_uom_qty) AS gross_profit
FROM sale_order so
JOIN sale_order_line sol ON sol.order_id = so.id
JOIN product_product pp ON pp.id = sol.product_id
JOIN product_template pt ON pt.id = pp.product_tmpl_id
WHERE so.state IN ('sale', 'done')
  AND so.date_order >= date_trunc('month', CURRENT_DATE)
  AND so.date_order <  date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'
GROUP BY pt.id, pt.name, pp.default_code
ORDER BY gross_profit DESC
LIMIT 20
```
"""

SYSTEM_PROMPT_SUMMARY = u"""You are a business data analyst.
Task: Summarize the query results into a short, clear paragraph in English.

Rules:
- Write 2-4 sentences, highlighting the most important insights
- Use specific numbers from the data
- Format monetary values: use K for thousands, M for millions, B for billions
- Be concise — avoid padding or filler phrases
- Do NOT mention SQL, tables, or any technical terms
"""


class AIService(object):
    """Connects to Gemini API to generate SQL from natural language and summarize query results."""

    def __init__(self, api_key=None):
        self.api_key = api_key or GEMINI_API_KEY
        self._working_model = None  # cached after first successful call

    def _call_gemini(self, system_text, user_text, temperature=0.1):
        """Call Gemini API and return the text response. Automatically tries models in order."""
        if not requests:
            raise Exception(u'The requests library is not installed.')

        payload = {
            'contents': [
                {
                    'role': 'user',
                    'parts': [
                        {'text': system_text + u'\n\n---\n\n' + user_text}
                    ],
                }
            ],
            'generationConfig': {
                'temperature': temperature,
                'topK': 1,
                'topP': 1,
                'maxOutputTokens': 2048,
            },
        }

        # Build list of models to try: cached first, then full list
        models_to_try = []
        if self._working_model:
            models_to_try.append(self._working_model)
        for m in GEMINI_MODELS:
            if m not in models_to_try:
                models_to_try.append(m)

        last_error = None
        for model in models_to_try:
            url = GEMINI_BASE_URL.format(
                model=model, api_key=self.api_key
            )
            # Retry loop for this model (handles 429 rate-limit)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    resp = requests.post(
                        url,
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=60,
                    )

                    if resp.status_code == 404:
                        _logger.warning(
                            'AIService: model %s not found (404).', model
                        )
                        last_error = u'Model %s: 404 Not Found' % model
                        break  # skip to next model

                    if resp.status_code == 429:
                        wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                        _logger.warning(
                            'AIService: rate limit on %s (attempt %d/%d), '
                            'waiting %ds...', model, attempt + 1, max_retries, wait
                        )
                        last_error = u'Model %s: 429 Too Many Requests' % model
                        if attempt < max_retries - 1:
                            time.sleep(wait)
                            continue  # retry same model
                        else:
                            break  # try next model

                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get('candidates', [])
                    if not candidates:
                        raise Exception(
                            u'Gemini API returned no candidates. '
                            u'Response: %s' % str(data)[:300]
                        )

                    # Cache the working model
                    if self._working_model != model:
                        _logger.info('AIService: using model %s', model)
                        self._working_model = model

                    text = (
                        candidates[0]
                        .get('content', {})
                        .get('parts', [{}])[0]
                        .get('text', '')
                    )
                    return text.strip()

                except requests.exceptions.Timeout:
                    raise Exception(
                        u'Connection to Gemini API timed out (60 seconds).'
                    )
                except requests.exceptions.HTTPError as e:
                    last_error = str(e)
                    if '404' in last_error:
                        break  # next model
                    if '429' in last_error:
                        wait = 2 ** (attempt + 1)
                        if attempt < max_retries - 1:
                            time.sleep(wait)
                            continue
                        break  # next model
                    raise Exception(u'Gemini API error: %s' % last_error)
                except requests.exceptions.RequestException as e:
                    raise Exception(u'Gemini API connection error: %s' % str(e))

        raise Exception(
            u'All Gemini API models failed. '
            u'Last error: %s' % (last_error or u'Unknown')
        )

    def generate_sql(self, user_message, chi_nhanh_id=None):
        """
        Generate SQL from a natural-language question.

        Returns:
            str: extracted SQL statement
        """
        system = SYSTEM_PROMPT_SQL.format(schema=SCHEMA_CONTEXT)

        context_info = u''
        if chi_nhanh_id:
            context_info = (
                u'\n\n[Context: current company_id = %d. '
                u'If the question does not specify a particular company, '
                u'filter by this company_id.]' % chi_nhanh_id
            )

        user_text = u'Question: %s%s' % (user_message, context_info)

        raw = self._call_gemini(system, user_text, temperature=0.05)
        return self._extract_sql(raw)

    def _extract_sql(self, text):
        """Extract the SQL statement from a markdown code block in the AI response."""
        # Try ```sql ... ``` block first
        pattern = r'```sql\s*(.*?)\s*```'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # Fallback: try generic ``` ... ``` block
        pattern2 = r'```\s*(.*?)\s*```'
        match2 = re.search(pattern2, text, re.DOTALL)
        if match2:
            sql_candidate = match2.group(1).strip()
            if sql_candidate.upper().startswith('SELECT'):
                return sql_candidate

        # Last resort: if the raw text starts with SELECT, use it directly
        stripped = text.strip()
        if stripped.upper().startswith('SELECT'):
            return stripped

        # Could not extract SQL
        _logger.warning(
            'AIService: Could not extract SQL from response: %s', text[:200]
        )
        return text  # Return as-is so query_executor can validate and reject

    def summarize_results(self, user_message, columns, rows_dicts, row_count):
        """
        Summarize query results into a natural-language English paragraph.

        Args:
            user_message: Original question asked by the user
            columns: list of column names
            rows_dicts: list of dicts (first rows used as a preview for summarization)
            row_count: total number of rows returned
        Returns:
            str: concise English summary of the results
        """
        # Limit preview to 10 rows to stay within token limits
        preview = rows_dicts[:10] if len(rows_dicts) > 10 else rows_dicts

        data_text = u'Results (%d rows):\n' % row_count
        if preview:
            # Header
            data_text += u' | '.join(columns) + u'\n'
            data_text += u'-' * 60 + u'\n'
            for row in preview:
                vals = [
                    str(row.get(c, '')) for c in columns
                ]
                data_text += u' | '.join(vals) + u'\n'
            if row_count > 10:
                data_text += u'... (%d more rows)\n' % (row_count - 10)

        user_text = (
            u'Original question: %s\n\n%s\n\n'
            u'Please summarize these results in English, '
            u'highlighting the most important insights.'
        ) % (user_message, data_text)

        try:
            return self._call_gemini(
                SYSTEM_PROMPT_SUMMARY, user_text, temperature=0.3
            )
        except Exception as e:
            _logger.warning('AIService summarize error: %s', e)
            return u'Found %d results.' % row_count
