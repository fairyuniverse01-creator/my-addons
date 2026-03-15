# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AIChatbotConversation(models.Model):
    _name = 'ai.chatbot.conversation'
    _description = 'AI Chatbot Conversation'
    _order = 'create_date desc'
    _rec_name = 'USER_MESSAGE'

    USER_ID = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True,
    )
    CHI_NHANH_ID = fields.Many2one(
        'res.company',
        string='Branch',
        readonly=True,
    )
    USER_MESSAGE = fields.Text(
        string='Question',
        required=True,
    )
    GENERATED_SQL = fields.Text(
        string='Generated SQL',
        readonly=True,
    )
    AI_RESPONSE = fields.Text(
        string='AI Response',
        readonly=True,
    )
    RESULT_JSON = fields.Text(
        string='Result JSON',
        readonly=True,
    )
    RESULT_COLUMNS = fields.Text(
        string='Result Columns JSON',
        readonly=True,
    )
    RESULT_COUNT = fields.Integer(
        string='Row Count',
        readonly=True,
        default=0,
    )
    EXECUTION_TIME_MS = fields.Integer(
        string='Execution Time (ms)',
        readonly=True,
        default=0,
    )
    STATUS = fields.Selection(
        [
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('error', 'Error'),
            ('blocked', 'Blocked'),
        ],
        string='Status',
        default='pending',
        readonly=True,
    )
    ERROR_MESSAGE = fields.Text(
        string='Error Message',
        readonly=True,
    )
    FEEDBACK = fields.Selection(
        [
            ('up', 'Helpful'),
            ('down', 'Not Helpful'),
        ],
        string='Feedback',
    )
    create_date = fields.Datetime(string='Date', readonly=True)

    @api.model
    def get_user_branch(self):
        """Return the current user's branch from context or settings."""
        user = self.env.user
        if hasattr(user, 'company_id') and user.company_id:
            return user.company_id.id
        # fallback: return the first active branch
        branch = self.env['res.company'].search(limit=1)
        return branch.id if branch else False

    @api.multi
    def get_result_as_dict(self):
        """Parse RESULT_JSON and RESULT_COLUMNS into a list of dicts."""
        self.ensure_one()
        try:
            rows = json.loads(self.RESULT_JSON or '[]')
            cols = json.loads(self.RESULT_COLUMNS or '[]')
            result = []
            for row in rows:
                result.append(dict(zip(cols, row)))
            return result
        except Exception:
            return []
