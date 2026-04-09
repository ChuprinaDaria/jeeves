# Python Web Integration

Base URL: {{ base_url }}
API Key: {{ api_key }}
Specialization: {{ specialization }}

```python
import requests

BASE_URL = '{{ base_url }}'
API_KEY = '{{ api_key }}'

headers = {'Authorization': f'Bearer {API_KEY}'}

resp = requests.post(BASE_URL + 'api/your-endpoint/', json={'q': 'hello'}, headers=headers)
print(resp.json())
```
