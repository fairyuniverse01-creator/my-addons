# AI Analytics Chatbot

**AI Analytics Chatbot** is a powerful Odoo 11 module that integrates Artificial Intelligence to help you analyze your business data using natural language. Instead of navigating through multiple menus, configuring filters, or building complex reports, you can simply ask the chatbot a question in plain English. The AI will instantly generate the necessary SQL, execute it safely, and present the results in an easy-to-understand summary.

## ✨ Key Features
- **Natural Language Queries:** Ask questions about your business data in plain English.
- **Instant Data Analysis:** Get insights on Sales, Customers, Inventory, Accounting, and Business performance instantly.
- **Safe SQL Generation & Execution:** The module safely translates your questions into read-only SQL queries (`SELECT` only) with strict validations to prevent any data modification.
- **AI-Powered Summaries:** Receive clear, conversational summaries alongside tabular data results directly in the chat interface.
- **Conversation History:** Easily access your past questions, generated SQL, and AI responses.
- **User Feedback:** Rate the AI responses (Thumbs up/down) to help monitor and improve its accuracy.
- **Quick Suggestions:** Clickable popular questions like *"Revenue this month by sales channel?"* or *"Top 10 customers this quarter?"* to get started immediately.

## 📊 Supported Data Context
The AI is fully aware of the standard Odoo 11 schema for core business operations:
- **Sales:** `sale.order`, `sale.order.line`, `crm.team`
- **Products:** `product.product`, `product.template`
- **Contacts:** `res.partner`
- **Invoicing:** `account.invoice`, `account.invoice.line`
- **Inventory:** `stock.move`, `stock.quant`, `stock.location`

## 🛠️ Technical Details
- **Compatibility:** Odoo 11.0 (Community and Enterprise)
- **AI Engine:** Google Gemini API integrations.
- **Security:** Strict regex validation ensures only harmless `SELECT` queries are executed, blocking all dangerous keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.).
- **Performance:** Includes a hard limit on rows returned (e.g., 500 rows) and statement timeouts to ensure system stability.

## 🚀 Usage Instructions
1. Navigate to the **AI Chatbot** application from the main Odoo menu.
2. Type a question related to your data, for example: 
   - *"Which salesperson generated the most revenue in the last 30 days?"*
   - *"List the products with the highest quantity currently in stock."*
   - *"What is the total outstanding invoice amount per customer?"*
3. The AI will process your request and return a detailed response.
4. You can click on **&lt;/&gt; Xem SQL** (View SQL) to audit the exact database query generated.

---
*Created for the Odoo App Store to modernize data analytics with AI.*
