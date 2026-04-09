# Python Telegram Integration

Base URL: {{ base_url }}
API Key: {{ api_key }}
Specialization: {{ specialization }}

```python
from telegram.ext import ApplicationBuilder, MessageHandler, filters
import requests

API_KEY = '{{ api_key }}'
BASE_URL = '{{ base_url }}'

async def handle_message(update, context):
    text = update.message.text
    headers = {'Authorization': f'Bearer {API_KEY}'}
    resp = requests.post(BASE_URL + 'api/your-endpoint/', json={'q': text}, headers=headers)
    await update.message.reply_text(str(resp.json()))

app = ApplicationBuilder().token('YOUR_TELEGRAM_BOT_TOKEN').build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
app.run_polling()
```
