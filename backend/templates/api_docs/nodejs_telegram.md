# Node.js Telegram Integration

Base URL: {{ base_url }}
API Key: {{ api_key }}
Specialization: {{ specialization }}

```js
import { Telegraf } from 'telegraf';
import fetch from 'node-fetch';

const bot = new Telegraf('YOUR_TELEGRAM_BOT_TOKEN');
const BASE_URL = '{{ base_url }}';
const API_KEY = '{{ api_key }}';

bot.on('text', async (ctx) => {
  const text = ctx.message.text;
  const resp = await fetch(BASE_URL + 'api/your-endpoint/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`
    },
    body: JSON.stringify({ q: text })
  });
  const data = await resp.json();
  ctx.reply(JSON.stringify(data));
});

bot.launch();
```
