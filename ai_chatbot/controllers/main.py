# -*- coding: utf-8 -*-
"""
HTTP Controller for the AI Chatbot module.

Endpoints:
  POST /ai_chatbot/query        — Submit a question; receive results + SQL + summary
  POST /ai_chatbot/history      — Retrieve the current user's conversation history
  POST /ai_chatbot/feedback     — Rate a result (thumbs up / down)
  POST /ai_chatbot/conversation — Retrieve the detail of a single conversation
"""
import json
import logging
import sys
import os

from odoo import http
from odoo.http import request

# Import services
_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from odoo.addons.ai_chatbot.services.ai_service import AIService
from odoo.addons.ai_chatbot.services.query_executor import QueryExecutor

_logger = logging.getLogger(__name__)


class AIChatbotController(http.Controller):

    @http.route(
        '/ai_chatbot/query',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def query(self, message='', **kwargs):
        """
        Process a question from the chatbot frontend.

        Input (JSON body):
            message (str): the user's natural-language question

        Returns (JSON):
            {
                id: int,               # conversation record id
                sql: str,              # generated SQL
                columns: [...],        # column names
                rows: [...],           # list of dicts
                row_count: int,
                summary: str,          # AI-generated summary
                execution_time_ms: int,
                status: 'success' / 'error' / 'blocked',
                error: str or null
            }
        """
        message = (message or '').strip()
        if not message:
            return {'status': 'error', 'error': u'Please enter a question.'}

        env = request.env
        Conversation = env['ai.chatbot.conversation']

        # Get the current user's branch
        chi_nhanh_id = Conversation.get_user_branch()

        # Create a conversation record (pending)
        conv = Conversation.create({
            'USER_MESSAGE': message,
            'CHI_NHANH_ID': chi_nhanh_id,
            'STATUS': 'pending',
        })

        try:
            # 1) Generate SQL via AI
            ai_service = AIService()
            sql = ai_service.generate_sql(message, chi_nhanh_id)

            # 2) Execute SQL safely
            executor = QueryExecutor(env.cr)
            result = executor.execute(sql)

            if result['error']:
                # Distinguish blocked vs execution error
                is_blocked = any(
                    kw in (result['error'] or '')
                    for kw in [u'Only SELECT', u'not allowed', u'blocked keyword']
                )
                status = 'blocked' if is_blocked else 'error'
                conv.write({
                    'GENERATED_SQL': sql,
                    'STATUS': status,
                    'ERROR_MESSAGE': result['error'],
                    'EXECUTION_TIME_MS': result['execution_time_ms'],
                })
                return {
                    'id': conv.id,
                    'sql': sql,
                    'columns': [],
                    'rows': [],
                    'row_count': 0,
                    'summary': u'',
                    'execution_time_ms': result['execution_time_ms'],
                    'status': status,
                    'error': result['error'],
                }

            # 3) Convert rows to JSON-serializable format
            rows_dicts = executor.rows_to_json(
                result['columns'], result['rows']
            )

            # 4) Summarize results via AI
            summary = ai_service.summarize_results(
                message,
                result['columns'],
                rows_dicts,
                result['row_count'],
            )

            # 5) Save results to the conversation record
            conv.write({
                'GENERATED_SQL': sql,
                'AI_RESPONSE': summary,
                'RESULT_JSON': json.dumps(
                    [list(r.values()) for r in rows_dicts],
                    ensure_ascii=False,
                    default=str,
                ),
                'RESULT_COLUMNS': json.dumps(
                    result['columns'], ensure_ascii=False
                ),
                'RESULT_COUNT': result['row_count'],
                'EXECUTION_TIME_MS': result['execution_time_ms'],
                'STATUS': 'success',
            })

            return {
                'id': conv.id,
                'sql': sql,
                'columns': result['columns'],
                'rows': rows_dicts,
                'row_count': result['row_count'],
                'summary': summary,
                'execution_time_ms': result['execution_time_ms'],
                'status': 'success',
                'error': None,
            }

        except Exception as e:
            _logger.exception('AIChatbot error for message: %s', message)
            error_msg = u'Processing error: %s' % str(e)
            conv.write({
                'STATUS': 'error',
                'ERROR_MESSAGE': error_msg,
            })
            return {
                'id': conv.id,
                'sql': '',
                'columns': [],
                'rows': [],
                'row_count': 0,
                'summary': '',
                'execution_time_ms': 0,
                'status': 'error',
                'error': error_msg,
            }

    @http.route(
        '/ai_chatbot/history',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def history(self, limit=20, **kwargs):
        """Return the conversation history for the current user."""
        env = request.env
        convs = env['ai.chatbot.conversation'].search(
            [('USER_ID', '=', env.user.id)],
            order='create_date desc',
            limit=limit,
        )
        result = []
        for c in convs:
            result.append({
                'id': c.id,
                'message': c.USER_MESSAGE,
                'summary': c.AI_RESPONSE or '',
                'status': c.STATUS,
                'row_count': c.RESULT_COUNT,
                'create_date': c.create_date if c.create_date else '',
                'feedback': c.FEEDBACK or '',
            })
        return {'history': result}

    @http.route(
        '/ai_chatbot/feedback',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def feedback(self, conversation_id=None, feedback=None, **kwargs):
        """Save a thumbs-up or thumbs-down rating."""
        if not conversation_id or feedback not in ('up', 'down'):
            return {'ok': False, 'error': u'Invalid parameters.'}

        env = request.env
        conv = env['ai.chatbot.conversation'].browse(int(conversation_id))
        if not conv.exists():
            return {'ok': False, 'error': u'Conversation not found.'}

        conv.write({'FEEDBACK': feedback})
        return {'ok': True}

    @http.route(
        '/ai_chatbot/conversation/<int:conv_id>',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_conversation(self, conv_id, **kwargs):
        """Return the full detail of a single conversation (SQL + all result rows)."""
        env = request.env
        conv = env['ai.chatbot.conversation'].browse(conv_id)
        if not conv.exists():
            return {'error': u'Conversation not found.'}

        rows_dicts = []
        columns = []
        try:
            columns = json.loads(conv.RESULT_COLUMNS or '[]')
            raw_rows = json.loads(conv.RESULT_JSON or '[]')
            rows_dicts = [
                dict(zip(columns, row)) for row in raw_rows
            ]
        except Exception:
            pass

        return {
            'id': conv.id,
            'message': conv.USER_MESSAGE,
            'sql': conv.GENERATED_SQL or '',
            'summary': conv.AI_RESPONSE or '',
            'columns': columns,
            'rows': rows_dicts,
            'row_count': conv.RESULT_COUNT,
            'execution_time_ms': conv.EXECUTION_TIME_MS,
            'status': conv.STATUS,
            'error': conv.ERROR_MESSAGE or '',
            'feedback': conv.FEEDBACK or '',
        }
