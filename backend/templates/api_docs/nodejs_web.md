# Node.js Web Integration

Base URL: {{ base_url }}
API Key: {{ api_key }}
Specialization: {{ specialization }}

```js
import fetch from 'node-fetch';

const BASE_URL = '{{ base_url }}';
const API_KEY = '{{ api_key }}';

const resp = await fetch(BASE_URL + 'api/your-endpoint/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_KEY}`
  },
  body: JSON.stringify({ q: 'hello' })
});
console.log(await resp.json());
```
