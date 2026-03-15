# -*- coding: utf-8 -*-
{
    'name': 'AI Analytics Chatbot',
    'version': '1.0',
    'sequence': 99,
    'summary': 'AI-powered business data analytics chatbot',
    'description': '''
        The AI Chatbot module lets users ask questions in English and receive
        business data analysis results from PostgreSQL via AI SQL generation.
    ''',
    'category': 'Reporting',
    'author': 'Cloudify',
    'depends': [
        'base',
        'web',
        'sale',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_chatbot_assets.xml',
        'views/ai_chatbot_view.xml',
        'views/ai_chatbot_menu.xml',
    ],
    'qweb': [
        'static/src/xml/ai_chatbot.xml',
        'static/src/xml/ai_chatbot_systray.xml',
    ],
    # Odoo 11: static assets are injected via web.assets_backend ir.asset records
    # or by inheriting the web asset templates. We use the template approach below.
    'installable': True,
    'application': True,
    'auto_install': False,
}
