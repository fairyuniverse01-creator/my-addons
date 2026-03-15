# -*- coding: utf-8 -*-
"""
QueryExecutor — Safe SQL execution (SELECT only).

Protections:
- Only SELECT statements are allowed
- Dangerous keywords are blocked
- LIMIT is automatically added if missing
- 30-second statement timeout
"""
import re
import logging
import time
import json

_logger = logging.getLogger(__name__)

# Blocked keywords (case-insensitive)
BLOCKED_KEYWORDS = [
    r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b',
    r'\bCREATE\b', r'\bALTER\b', r'\bTRUNCATE\b', r'\bEXEC\b',
    r'\bEXECUTE\b', r'\bGRANT\b', r'\bREVOKE\b', r'\bCOMMIT\b',
    r'\bROLLBACK\b', r'\bSAVEPOINT\b', r'\bCOPY\b', r'\bVACUUM\b',
    r'\bANALYZE\b(?!\s+PLAN)', r'\bREINDEX\b', r'\bCLUSTER\b',
    r'\bLOCK\b', r'\bUNLOCK\b', r'\bCALL\b', r'\bDO\b\s',
    r'pg_sleep', r'pg_read_file', r'lo_import', r'lo_export',
    r'dblink', r'pg_terminate_backend', r'pg_cancel_backend',
]

MAX_ROWS = 500


class QueryExecutor(object):
    """Safely execute SELECT statements against the Odoo database."""

    def __init__(self, cr):
        self._cr = cr

    def validate(self, sql):
        """
        Check whether the SQL statement is safe to execute.
        Returns (True, '') if OK, or (False, error_message).
        """
        sql_stripped = sql.strip()

        # Statement must start with SELECT, WITH (CTE), or EXPLAIN
        first_word = re.split(r'\s+', sql_stripped)[0].upper()
        if first_word not in ('SELECT', 'WITH', 'EXPLAIN'):
            return False, (
                u'Only SELECT statements are allowed. '
                u'The statement "%s" is not allowed.' % first_word
            )

        # Check for blocked keywords
        for pattern in BLOCKED_KEYWORDS:
            if re.search(pattern, sql_stripped, re.IGNORECASE):
                keyword = re.search(
                    pattern, sql_stripped, re.IGNORECASE
                ).group(0).strip()
                return False, (
                    u'Statement contains a blocked keyword: "%s".' % keyword
                )

        # Block multiple statements separated by semicolons (SQL injection guard)
        # A trailing semicolon is allowed (some clients append it)
        without_trailing = sql_stripped.rstrip(';').rstrip()
        if ';' in without_trailing:
            return False, (
                u'Multiple SQL statements in a single request are not allowed.'
            )

        return True, ''

    def add_limit(self, sql, limit=MAX_ROWS):
        """Append LIMIT to the SQL statement if one is not already present."""
        sql_stripped = sql.strip().rstrip(';')
        if not re.search(r'\bLIMIT\b', sql_stripped, re.IGNORECASE):
            sql_stripped = sql_stripped + ' LIMIT %d' % limit
        return sql_stripped

    def execute(self, sql, timeout_ms=30000):
        """
        Execute the SQL statement and return the results.

        Returns:
            dict with keys:
                - columns: list of column names
                - rows: list of tuples
                - row_count: number of rows returned
                - execution_time_ms: wall-clock time in milliseconds
                - error: None if successful, or an error message string
        """
        result = {
            'columns': [],
            'rows': [],
            'row_count': 0,
            'execution_time_ms': 0,
            'error': None,
        }

        # Validate
        ok, err = self.validate(sql)
        if not ok:
            result['error'] = err
            return result

        # Enforce row limit
        sql = self.add_limit(sql)

        t0 = time.time()
        try:
            # Set statement timeout
            self._cr.execute(
                'SET LOCAL statement_timeout = %s', (timeout_ms,)
            )
            self._cr.execute(sql)
            if self._cr.description:
                result['columns'] = [
                    desc[0] for desc in self._cr.description
                ]
                result['rows'] = self._cr.fetchall()
                result['row_count'] = len(result['rows'])
        except Exception as e:
            result['error'] = u'SQL execution error: %s' % str(e)
            _logger.warning('QueryExecutor SQL error: %s\nSQL: %s', e, sql)
        finally:
            result['execution_time_ms'] = int((time.time() - t0) * 1000)

        return result

    def rows_to_json(self, columns, rows):
        """Convert rows (list of tuples) into a JSON-serializable list of dicts."""
        result = []
        for row in rows:
            d = {}
            for i, col in enumerate(columns):
                val = row[i]
                # Handle non-JSON-serializable types
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                elif val is None:
                    val = None
                else:
                    try:
                        json.dumps(val)
                    except TypeError:
                        val = str(val)
                d[col] = val
            result.append(d)
        return result
