# Деплой TimeTracker

Краткая шпаргалка. Полная инструкция — в [`docs/HANDOVER.md`](../docs/HANDOVER.md).

## Подготовка

```powershell
pip install paramiko
copy deploy\credentials.example.json deploy\credentials.json
# вписать host / user / password
```

`deploy/credentials.json` исключён из git (`.gitignore`) — пароль не коммитится.

## Команды

```powershell
# выполнить команду на сервере
python deploy\ssh_exec.py cmd "nginx -t"

# загрузить файл
python deploy\ssh_exec.py put site\index.html /var/www/timetracker/index.html

# скачать файл
python deploy\ssh_exec.py get /etc/nginx/sites-available/timetracker deploy\nginx-timetracker.conf
```

## Обновление сайта

```powershell
python deploy\ssh_exec.py put site\index.html /var/www/timetracker/index.html
python deploy\ssh_exec.py put site\screenshot-light.png /var/www/timetracker/screenshot-light.png
python deploy\ssh_exec.py put site\screenshot-dark.png /var/www/timetracker/screenshot-dark.png
```

## Обновление конфига nginx

```powershell
python deploy\ssh_exec.py put deploy\nginx-timetracker.conf /etc/nginx/sites-available/timetracker
python deploy\ssh_exec.py cmd "nginx -t && systemctl reload nginx"
```

## Скриншоты для лендинга

```powershell
python deploy\make_screenshots.py
# результат: site\screenshot-light.png, site\screenshot-dark.png
```

## Сервер

| | |
|---|---|
| IP | `95.163.220.114` |
| Домен | `трекерзерокод3.рф` / `xn--3-gtbcaaltd9abodcu.xn--p1ai` |
| Корень сайта | `/var/www/timetracker` |
| Конфиг nginx | `/etc/nginx/sites-available/timetracker` |
| Сертификат | Let's Encrypt, автопродление `certbot.timer` |

Не трогайте сайты `balans` и `tracker` — это другие проекты на том же сервере.
