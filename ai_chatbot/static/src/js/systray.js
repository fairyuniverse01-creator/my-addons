odoo.define('ai_chatbot.systray', function (require) {
    "use strict";

    var SystrayMenu = require('web.SystrayMenu');
    var Widget = require('web.Widget');
    var session = require('web.session');

    var AIChatbotSystray = Widget.extend({
        template: 'ai_chatbot.systray.AIChatbot',
        events: {
            "click": "_onChatbotClick",
        },

        willStart: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Check if user is admin
                return self._rpc({
                    model: 'res.users',
                    method: 'read',
                    args: [[session.uid], ['is_admin']],
                }).then(function (res) {
                    if (res.length > 0 && res[0].is_admin) {
                        self.is_admin = true;
                    } else if (session.is_admin || session.is_system || session.uid === 1 || session.is_superuser) {
                        self.is_admin = true;
                    } else {
                        self.is_admin = false;
                    }
                }).fail(function () {
                    self.is_admin = session.is_admin || session.is_system || session.uid === 1 || session.is_superuser;
                });
            });
        },

        start: function () {
            var self = this;
            if (!this.is_admin) {
                this.$el.hide();
            }
            return this._super.apply(this, arguments);
        },

        _onChatbotClick: function (event) {
            event.preventDefault();
            this.do_action('ai_chatbot.action_ai_chatbot_open', {
                clear_breadcrumbs: true
            });
        },
    });

    SystrayMenu.Items.push(AIChatbotSystray);

    return AIChatbotSystray;
});
