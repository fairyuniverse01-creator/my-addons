odoo.define('ai_chatbot.AIChatbotWidget', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var ajax = require('web.ajax');

    // ─── Sample queries shown in sidebar ────────────────────────────────────
    var EXAMPLE_QUERIES = [
        { icon: '📈', label: 'Revenue this month by sales channel?', query: 'What is the total revenue for each sales channel this month?' },
        { icon: '🏆', label: 'Top 10 customers this quarter?', query: 'Who are the top 10 customers by sales revenue this quarter?' },
        { icon: '📊', label: 'Compare revenue: this month vs last?', query: 'Compare total revenue between this month and last month.' },
        { icon: '👥', label: 'Best performing salesperson (30 days)?', query: 'Which salesperson generated the most revenue in the last 30 days?' },
        { icon: '📦', label: 'Current stock on hand by product?', query: 'List the products with the highest quantity currently in stock.' },
        { icon: '💳', label: 'Outstanding invoices by customer?', query: 'What is the total outstanding (unpaid) invoice amount per customer?' },
        { icon: '🛒', label: 'Orders not yet invoiced?', query: 'List all confirmed sales orders that have not been fully invoiced yet.' },
        { icon: '💰', label: 'Gross profit by product this month?', query: 'What is the gross profit for each product sold this month?' },
        { icon: '📋', label: 'Quotations sent but not confirmed?', query: 'List all quotations that were sent to customers but not yet confirmed.' },
        { icon: '🔄', label: 'Revenue trend by month this year?', query: 'Show total revenue for each month of the current year.' },
    ];

    // ─── Utility: format number as VN currency ───────────────────────────────
    function formatVND(num) {
        if (num === null || num === undefined || num === '') return '';
        var n = parseFloat(num);
        if (isNaN(n)) return String(num);
        if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + ' tỷ';
        if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + ' triệu';
        if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
        return n.toLocaleString('vi-VN');
    }

    // Columns likely to contain monetary amounts
    var MONEY_COLS = /doanh|tien|gia|von|no|co|nhap|xuat|thanh|phi|lai|chiet|vat/i;
    var NUMBER_COLS = /so_luong|count|sl|luong/i;

    function formatCell(col, val) {
        if (val === null || val === undefined) return '–';
        if (typeof val === 'number') {
            if (MONEY_COLS.test(col)) return formatVND(val);
            if (NUMBER_COLS.test(col)) return val.toLocaleString('vi-VN');
            return val.toLocaleString('vi-VN');
        }
        return String(val);
    }

    // ─── Build result HTML ───────────────────────────────────────────────────
    function buildResultHTML(data) {
        if (data.status === 'error' || data.status === 'blocked') {
            return (
                '<div class="ai_chatbot_summary_text">' +
                '⚠️ Không thể thực thi câu lệnh này.</div>' +
                '<div class="ai_chatbot_error_text">' + _.escape(data.error) + '</div>'
            );
        }

        var html = '';

        // Summary
        if (data.summary) {
            html += '<div class="ai_chatbot_summary_text">' +
                _.escape(data.summary).replace(/\n/g, '<br/>') +
                '</div>';
        }

        // Table
        if (data.columns && data.columns.length > 0 && data.rows && data.rows.length > 0) {
            html += '<div class="ai_chatbot_result_count">';
            html += '📋 ' + data.row_count + ' kết quả';
            if (data.execution_time_ms) {
                html += ' · ' + data.execution_time_ms + 'ms';
            }
            html += '</div>';

            html += '<div class="ai_chatbot_result_table_wrap"><table class="ai_chatbot_result_table">';
            // Header
            html += '<thead><tr>';
            _.each(data.columns, function (col) {
                html += '<th>' + _.escape(col) + '</th>';
            });
            html += '</tr></thead>';
            // Body (show max 100 rows)
            html += '<tbody>';
            var display = data.rows.slice(0, 100);
            _.each(display, function (row) {
                html += '<tr>';
                _.each(data.columns, function (col) {
                    var val = row[col];
                    html += '<td>' + _.escape(formatCell(col, val)) + '</td>';
                });
                html += '</tr>';
            });
            if (data.rows.length > 100) {
                html += '<tr><td colspan="' + data.columns.length + '" style="text-align:center;color:#64748b;font-style:italic;">' +
                    '... còn ' + (data.rows.length - 100) + ' dòng nữa</td></tr>';
            }
            html += '</tbody></table></div>';
        } else if (data.status === 'success') {
            html += '<div class="ai_chatbot_result_count">ℹ️ Không có dữ liệu trả về.</div>';
        }

        return html;
    }

    // ─── Main Widget ─────────────────────────────────────────────────────────
    var AIChatbotWidget = Widget.extend({
        template: 'AIChatbot.Main',

        // Delegated events that work on the static template DOM
        events: {
            'click .ai_chatbot_new_chat': 'newChat',
            'click #ai_chatbot_send_btn': 'sendMessage',
            'keydown #ai_chatbot_input': 'onKeyDown',
        },

        // Runtime state (NOT passed to QWeb — template is static)
        messages: [],
        history: [],
        isLoading: false,

        // Map: conversation_id -> full response object
        _convCache: {},

        init: function (parent) {
            this._super(parent);
            this.messages = [];
            this.history = [];
            this.isLoading = false;
            this._convCache = {};
        },

        start: function () {
            var self = this;
            return this._super().then(function () {
                // Render all dynamic regions after DOM is ready
                self._rerenderExamples();
                self._rerenderMessages();
                self._loadHistory();
                self._autoResizeTextarea();
                self._bindModalEvents();
            });
        },

        // ── Auto-resize textarea ────────────────────────────────────────────
        _autoResizeTextarea: function () {
            var $ta = this.$('#ai_chatbot_input');
            $ta.on('input', function () {
                this.style.height = 'auto';
                this.style.height = Math.min(this.scrollHeight, 180) + 'px';
            });
        },

        // ── SQL modal event bindings ────────────────────────────────────────
        _bindModalEvents: function () {
            var self = this;
            this.$('#ai_chatbot_close_sql').on('click', function () {
                self.$('#ai_chatbot_sql_modal').hide();
            });
            this.$('#ai_chatbot_copy_sql').on('click', function () {
                var sql = self.$('#ai_chatbot_sql_code').text();
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(sql);
                } else {
                    var ta = document.createElement('textarea');
                    ta.value = sql;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                }
                $(this).text('✓ Đã copy!');
                setTimeout(function () {
                    self.$('#ai_chatbot_copy_sql').text('📋 Copy');
                }, 1500);
            });
            // Close on backdrop click
            this.$('#ai_chatbot_sql_modal').on('click', function (e) {
                if ($(e.target).is('#ai_chatbot_sql_modal')) {
                    $(this).hide();
                }
            });
        },

        // ── Keyboard handler ────────────────────────────────────────────────
        onKeyDown: function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        },

        // ── New chat ────────────────────────────────────────────────────────
        newChat: function () {
            this.messages = [];
            this._rerenderMessages();
        },

        // ── Example query click ─────────────────────────────────────────────
        onExampleClick: function (e) {
            var query = $(e.currentTarget).data('query');
            this.$('#ai_chatbot_input').val(query);
            this.sendMessage();
        },

        // ── History item click ───────────────────────────────────────────────
        onHistoryClick: function (e) {
            var convId = parseInt($(e.currentTarget).data('id'), 10);
            var self = this;
            if (this._convCache[convId]) {
                self._pushHistoryMessage(self._convCache[convId]);
                return;
            }
            ajax.jsonRpc('/ai_chatbot/conversation/' + convId, 'call', {})
                .then(function (data) {
                    self._convCache[convId] = data;
                    self._pushHistoryMessage(data);
                });
        },

        _pushHistoryMessage: function (data) {
            this.messages = [
                {
                    role: 'user',
                    text: data.message,
                    html: _.escape(data.message),
                },
                {
                    role: 'assistant',
                    id: data.id,
                    html: buildResultHTML(data),
                },
            ];
            this._rerenderMessages();
        },

        // ── SQL view (called from _rerenderMessages button binding) ────────────
        showSQL: function (e) {
            var convId = parseInt($(e.currentTarget).data('id'), 10);
            var cached = this._convCache[convId];
            if (cached && cached.sql) {
                this._openSQLModal(cached.sql);
                return;
            }
            var self = this;
            ajax.jsonRpc('/ai_chatbot/conversation/' + convId, 'call', {})
                .then(function (data) {
                    self._convCache[convId] = data;
                    self._openSQLModal(data.sql || '-- SQL không có sẵn');
                });
        },

        thumbUp: function (e) {
            this._sendFeedback($(e.currentTarget).data('id'), 'up');
            $(e.currentTarget).addClass('active');
        },

        thumbDown: function (e) {
            this._sendFeedback($(e.currentTarget).data('id'), 'down');
            $(e.currentTarget).addClass('active');
        },

        _sendFeedback: function (convId, type) {
            ajax.jsonRpc('/ai_chatbot/feedback', 'call', {
                conversation_id: convId,
                feedback: type,
            });
        },

        _openSQLModal: function (sql) {
            this.$('#ai_chatbot_sql_code').text(sql);
            this.$('#ai_chatbot_sql_modal').show();
        },

        // ── Send message ─────────────────────────────────────────────────────
        sendMessage: function () {
            if (this.isLoading) return;
            var $input = this.$('#ai_chatbot_input');
            var message = $input.val().trim();
            if (!message) return;

            $input.val('').css('height', 'auto');

            // Push user bubble
            this.messages.push({ role: 'user', text: message, html: _.escape(message) });

            // Show loading
            this.isLoading = true;
            this._rerenderMessages();
            this._scrollBottom();

            var self = this;
            ajax.jsonRpc('/ai_chatbot/query', 'call', { message: message })
                .then(function (data) {
                    self.isLoading = false;

                    // Cache the result
                    if (data.id) {
                        self._convCache[data.id] = data;
                    }

                    // Push AI bubble
                    self.messages.push({
                        role: 'assistant',
                        id: data.id,
                        html: buildResultHTML(data),
                    });

                    self._rerenderMessages();
                    self._scrollBottom();
                    self._loadHistory();  // refresh sidebar
                })
                .fail(function (err) {
                    self.isLoading = false;
                    self.messages.push({
                        role: 'assistant',
                        html: '<div class="ai_chatbot_error_text">Lỗi kết nối. Vui lòng thử lại.</div>',
                    });
                    self._rerenderMessages();
                    self._scrollBottom();
                });
        },

        // ── Render example queries in the sidebar ─────────────────────────────
        _rerenderExamples: function () {
            var $ex = this.$('#ai_chatbot_examples');
            var self = this;
            if (!$ex.length) return;
            var html = '<p class="ai_chatbot_examples_title">Popular questions</p>';
            _.each(EXAMPLE_QUERIES, function (eq) {
                html += '<div class="ai_chatbot_example_item" data-query="' +
                    _.escape(eq.query) + '">' +
                    '<span class="ai_chatbot_example_icon">' + eq.icon + '</span>' +
                    '<span class="ai_chatbot_example_text">' + _.escape(eq.label) + '</span>' +
                    '</div>';
            });
            $ex.html(html);
            $ex.find('.ai_chatbot_example_item').on('click', function () {
                var query = $(this).data('query');
                self.$('#ai_chatbot_input').val(query);
                self.sendMessage();
            });
        },

        // ── Re-render message list ───────────────────────────────────────────
        _rerenderMessages: function () {
            var $msgs = this.$('#ai_chatbot_messages');
            var $input = this.$('#ai_chatbot_send_btn');

            var html = '';

            if (this.messages.length === 0 && !this.isLoading) {
                // Welcome screen
                html = '<div class="ai_chatbot_welcome">' +
                    '<div class="ai_chatbot_welcome_icon">🤖</div>' +
                    '<h2>AI Analytics Chatbot</h2>' +
                    '<p>Ask any questions about your business data</p>' +
                    '<p class="ai_chatbot_welcome_sub">Data: Sales · Purchases · Inventory · Accounting · Payables</p>' +
                    '</div>';
            }

            var self = this;
            _.each(this.messages, function (msg) {
                html += '<div class="ai_chatbot_msg ai_chatbot_msg_' + msg.role + '">';
                html += '<div class="ai_chatbot_msg_avatar">' +
                    (msg.role === 'user' ? '👤' : '🤖') + '</div>';
                html += '<div class="ai_chatbot_msg_content">';
                html += '<div class="ai_chatbot_msg_text">' + (msg.html || _.escape(msg.text || '')) + '</div>';

                // Action buttons for assistant messages with an id
                if (msg.role === 'assistant' && msg.id) {
                    html += '<div class="ai_chatbot_msg_actions">';
                    html += '<button class="ai_chatbot_action_btn ai_chatbot_show_sql_btn" ' +
                        'data-conv-id="' + msg.id + '">&lt;/&gt; Xem SQL</button>';
                    html += '<button class="ai_chatbot_action_btn ai_chatbot_thumb ai_chatbot_thumb_up" ' +
                        'data-conv-id="' + msg.id + '" title="Helpful">👍</button>';
                    html += '<button class="ai_chatbot_action_btn ai_chatbot_thumb ai_chatbot_thumb_down" ' +
                        'data-conv-id="' + msg.id + '" title="Not helpful">👎</button>';
                    html += '</div>';
                }

                html += '</div></div>';
            });

            // Thinking indicator
            if (this.isLoading) {
                html += '<div class="ai_chatbot_msg ai_chatbot_msg_assistant">' +
                    '<div class="ai_chatbot_msg_avatar">🤖</div>' +
                    '<div class="ai_chatbot_msg_content">' +
                    '<div class="ai_chatbot_thinking">' +
                    '<span class="ai_chatbot_dot"></span>' +
                    '<span class="ai_chatbot_dot"></span>' +
                    '<span class="ai_chatbot_dot"></span>' +
                    '</div></div></div>';
            }

            $msgs.html(html);

            // Re-bind action button events after DOM update
            $msgs.find('.ai_chatbot_show_sql_btn').on('click', function () {
                var convId = parseInt($(this).data('conv-id'), 10);
                var cached = self._convCache[convId];
                if (cached && cached.sql) {
                    self._openSQLModal(cached.sql);
                } else {
                    ajax.jsonRpc('/ai_chatbot/conversation/' + convId, 'call', {})
                        .then(function (data) {
                            self._convCache[convId] = data;
                            self._openSQLModal(data.sql || '-- không có SQL');
                        });
                }
            });
            $msgs.find('.ai_chatbot_thumb_up').on('click', function () {
                self._sendFeedback($(this).data('conv-id'), 'up');
                $(this).addClass('active').siblings('.ai_chatbot_thumb').removeClass('active');
            });
            $msgs.find('.ai_chatbot_thumb_down').on('click', function () {
                self._sendFeedback($(this).data('conv-id'), 'down');
                $(this).addClass('active').siblings('.ai_chatbot_thumb').removeClass('active');
            });

            // Toggle send button
            if ($input) { $input.prop('disabled', this.isLoading); }
        },

        _scrollBottom: function () {
            var el = this.$('#ai_chatbot_messages')[0];
            if (el) { el.scrollTop = el.scrollHeight; }
        },

        // ── Load history sidebar ─────────────────────────────────────────────
        _loadHistory: function () {
            var self = this;
            ajax.jsonRpc('/ai_chatbot/history', 'call', { limit: 30 })
                .then(function (res) {
                    self.history = res.history || [];
                    self._rerenderHistory();
                });
        },

        _rerenderHistory: function () {
            var $list = this.$('#ai_chatbot_history_list');
            if (!$list.length) return;
            var html = '';
            if (!this.history.length) {
                html = '<div class="ai_chatbot_history_empty">No history</div>';
            } else {
                var self = this;
                _.each(this.history, function (item) {
                    var icon = item.status === 'success' ? '💬'
                        : item.status === 'error' ? '❌'
                            : '⏳';
                    var text = (item.message || '').substring(0, 42);
                    if (item.message && item.message.length > 42) text += '…';
                    html += '<div class="ai_chatbot_history_item" data-id="' + item.id + '">' +
                        '<span class="ai_chatbot_history_icon">' + icon + '</span>' +
                        '<span class="ai_chatbot_history_text">' + _.escape(text) + '</span>' +
                        '</div>';
                });
            }
            $list.html(html);
            var self = this;
            $list.find('.ai_chatbot_history_item').on('click', function () {
                var convId = parseInt($(this).data('id'), 10);
                if (self._convCache[convId]) {
                    self._pushHistoryMessage(self._convCache[convId]);
                    return;
                }
                ajax.jsonRpc('/ai_chatbot/conversation/' + convId, 'call', {})
                    .then(function (data) {
                        self._convCache[convId] = data;
                        self._pushHistoryMessage(data);
                    });
            });
        },
    });

    // ─── Register as client action ────────────────────────────────────────────
    core.action_registry.add('ai_chatbot.action', AIChatbotWidget);

    return AIChatbotWidget;
});
