import re

with open('MASTER/settings.py', 'r') as f:
    content = f.read()

# Змінюємо налаштування STATICFILES_DIRS, щоб воно вказувало на існуючу директорію
if 'STATICFILES_DIRS = [' in content:
    content = re.sub(r'STATICFILES_DIRS\s*=\s*\[[^\]]*\]', 'STATICFILES_DIRS = []', content)
    
with open('MASTER/settings.py', 'w') as f:
    f.write(content)

print("STATICFILES_DIRS fixed")
