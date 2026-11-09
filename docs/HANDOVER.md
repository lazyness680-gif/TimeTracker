# Передача проекта TimeTracker

Документ для передачи заказчику: что входит в проект, где он размещён,
как обновлять сайт и приложение.

Дата: 09.11.2026

---

## 1. Состав проекта (файлы)

Репозиторий: **https://github.com/lazyness680-gif/TimeTracker** (публичный, ветка `main`)

```
TimeTracker/                     исходный код приложения (Python + PySide6)
├── main.py                      точка входа
├── build.bat                    сборка portable .exe
├── requirements.txt
├── README.md                    описание приложения
└── timetracker/
    ├── db.py                    схема SQLite (WAL)
    ├── services.py              бизнес-логика, отчёты, аудит
    ├── single_instance.py
    └── ui/                      доска, карточки, команда, темы (QSS)…

tests/test_acceptance.py         20 приёмочных тестов
site/                            лендинг (статика)
├── index.html
├── screenshot-light.png
└── screenshot-dark.png
deploy/                          скрипты и конфиги деплоя
├── ssh_exec.py                  SSH-хелпер (cmd / put / get)
├── make_screenshots.py          генератор скриншотов для лендинга
├── nginx-timetracker.conf       актуальный конфиг nginx (с HTTPS)
├── release-notes-1.0.0.md       заметки к релизу
└── credentials.json             доступ к серверу (НЕ в git, только локально)
docs/
├── HANDOVER.md                  этот документ
└── landing-hero.jpg             скриншот лендинга для README
README.md                        главная страница репозитория
ТЗ.docx                          техническое задание
```

### Готовые сборки

| Что | Где |
|---|---|
| Portable-версия для Windows (46,9 МБ) | https://github.com/lazyness680-gif/TimeTracker/releases/tag/v1.0.0 |
| Прямая ссылка на скачивание | https://github.com/lazyness680-gif/TimeTracker/releases/latest/download/TimeTracker-1.0.0-win64.zip |
| Архив исходников для офлайн-передачи | `dist/TimeTracker-handover.zip` (создаётся командой из раздела 5) |

Приложение не требует установки: распаковать архив и запустить `TimeTracker.exe`.
Данные хранятся в папке `data` рядом с exe.

---

## 2. Сервер и домен

| Параметр | Значение |
|---|---|
| Провайдер / ОС | Ubuntu 26.04 LTS (OpenSSH 10.2, nginx 1.28) |
| IP-адрес | `95.163.220.114` |
| Пользователь SSH | `root` |
| Пароль SSH | хранится в `deploy/credentials.json` (локально, не в git) |
| Домен | **трекерзерокод3.рф** |
| Punycode | `xn--3-gtbcaaltd9abodcu.xn--p1ai` (+ `www.`) |
| DNS | reg.ru: `ns1.hosting.reg.ru`, `ns2.hosting.reg.ru`; A → `95.163.220.114`; AAAA-записей нет |
| Корень сайта | `/var/www/timetracker/` |
| Конфиг nginx | `/etc/nginx/sites-available/timetracker` → `sites-enabled/timetracker` |
| HTTPS | Let's Encrypt, автопродление через `certbot.timer` |
| Сертификат | `/etc/letsencrypt/live/xn--3-gtbcaaltd9abodcu.xn--p1ai/` (действует до 07.02.2027) |

### Важно: на сервере есть чужие сайты

Не изменяйте и не удаляйте конфиги `balans` и `tracker` — они обслуживают
другие проекты (`xn--2-…` и `xn--1-…`). Наш сайт — только `timetracker`.

### Доступ к серверу

Пароль **не хранится в репозитории**. Локально он лежит в
`deploy/credentials.json` (файл в `.gitignore`). Формат:

```json
{
  "host": "95.163.220.114",
  "user": "root",
  "password": "<пароль>"
}
```

Если файл утерян — пароль можно сбросить в панели хостинга и обновить
`deploy/credentials.json`.

Рекомендации по безопасности при передаче:
1. Смените пароль root после передачи.
2. Настройте вход по SSH-ключу и отключите парольную аутентификацию.
3. Заведите отдельного пользователя для деплоя вместо `root`.

---

## 3. Инструкция по деплою

Все команды выполняются из корня проекта на компьютере с Python 3.11+
и установленным `paramiko` (`pip install paramiko`).

### 3.1. Проверка доступа

```powershell
python deploy\ssh_exec.py cmd "hostname; nginx -v"
```

### 3.2. Обновление лендинга

1. Отредактируйте `site/index.html` (или скриншоты в `site/`).
2. Загрузите файлы на сервер:

```powershell
python deploy\ssh_exec.py put site\index.html /var/www/timetracker/index.html
python deploy\ssh_exec.py put site\screenshot-light.png /var/www/timetracker/screenshot-light.png
python deploy\ssh_exec.py put site\screenshot-dark.png /var/www/timetracker/screenshot-dark.png
```

3. Проверьте:

```powershell
curl.exe -sI https://xn--3-gtbcaaltd9abodcu.xn--p1ai/
```

### 3.3. Изменение конфига nginx

```powershell
python deploy\ssh_exec.py put deploy\nginx-timetracker.conf /etc/nginx/sites-available/timetracker
python deploy\ssh_exec.py cmd "nginx -t && systemctl reload nginx"
```

Если `nginx -t` выдал ошибку — конфиг не применён, сайт продолжает работать
на старой версии. Исправьте и повторите.

### 3.4. Обновление приложения

```powershell
Stop-Process -Name TimeTracker -Force -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING='utf-8'
python tests\test_acceptance.py          # должно быть 20/20
cd TimeTracker
cmd /c build.bat                         # результат: dist\TimeTracker\TimeTracker.exe
```

Затем соберите zip без папки `data` (демо-БД) и приложите к новому релизу:

```powershell
gh release create v1.0.1 "<путь к zip>" --title "TimeTracker 1.0.1" --notes-file deploy\release-notes-1.0.0.md
```

### 3.5. Сертификат HTTPS

Продление автоматическое. Проверить:

```powershell
python deploy\ssh_exec.py cmd "certbot certificates | grep -E 'Certificate Name|Expiry'"
```

Принудительно продлить:

```powershell
python deploy\ssh_exec.py cmd "certbot renew --force-renewal && systemctl reload nginx"
```

### 3.6. Резервная копия

```powershell
python deploy\ssh_exec.py cmd "tar czf /root/timetracker-backup-$(date +%F).tar.gz /var/www/timetracker /etc/nginx/sites-available/timetracker"
python deploy\ssh_exec.py get /root/timetracker-backup-2026-11-09.tar.gz dist\timetracker-backup.tar.gz
```

### 3.7. Откат

Вернуть предыдущую версию файлов из бэкапа:

```powershell
python deploy\ssh_exec.py put dist\index.html /var/www/timetracker/index.html
```

Или откатить конфиг:

```powershell
python deploy\ssh_exec.py cmd "cp /etc/nginx/sites-available/timetracker.bak /etc/nginx/sites-available/timetracker && nginx -t && systemctl reload nginx"
```

---

## 4. Проверочный чек-лист после деплоя

- [ ] `https://трекерзерокод3.рф` открывается (200).
- [ ] `http://…` перенаправляет на HTTPS (301).
- [ ] `https://www.…` открывается.
- [ ] Скриншоты на лендинге загружаются.
- [ ] Ссылка «Скачать для Windows» ведёт на актуальный релиз.
- [ ] `nginx -t` без ошибок.
- [ ] Сертификат действителен, `certbot.timer` активен.

---

## 5. Архив для офлайн-передачи

Готовый комплект лежит в `dist\Передача-клиенту\`:

| Файл | Что это |
|---|---|
| `TimeTracker-handover.zip` | исходники проекта (без `.git`, сборок и секретов) |
| `TimeTracker-1.0.0-win64.zip` | portable-сборка приложения |
| `ИНСТРУКЦИЯ-ПО-ДЕПЛОЮ.md` | копия этого документа |

Пересоздать архив исходников:

```powershell
git archive --format=zip --output="dist\Передача-клиенту\TimeTracker-handover.zip" HEAD
```

В архив попадают только файлы из репозитория. Пароль сервера в архив
**не входит** — передайте его отдельным защищённым каналом.

---

## 6. Что дальше (этап 2)

Веб-версия трекера: доска, карточки, участники и таймеры в браузере.
План: API на Python + фронтенд, размещение на этом же сервере
(поддомен или путь `/app`), SQLite с регулярным бэкапом.
