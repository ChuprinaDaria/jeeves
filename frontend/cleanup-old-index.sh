#!/bin/bash
echo "Видалення старого index.htm..."
lftp -u f017cd3a,f5mPnpwnsotcoNraN4zF w020c360.kasserver.com << 'LFTPEOF'
rm index.htm
ls -la | grep index
quit
LFTPEOF
echo "✅ Готово! Старий файл видалено."

