# PHP Web Integration

Base URL: {{ base_url }}
API Key: {{ api_key }}
Specialization: {{ specialization }}

```php
<?php
$baseUrl = '{{ base_url }}';
$apiKey = '{{ api_key }}';

$ch = curl_init($baseUrl . 'api/your-endpoint/');
$data = json_encode(['q' => 'hello']);
curl_setopt($ch, CURLOPT_POST, 1);
curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
  'Content-Type: application/json',
  'Authorization: Bearer ' . $apiKey
]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);
echo $response;
```
