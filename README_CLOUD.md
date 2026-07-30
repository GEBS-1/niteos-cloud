# NITEOS Concept Light Cloud

Минимальная web-версия для серверного запуска.

## Что уже есть

- Web-интерфейс в браузере.
- Проекты в `cloud_data/projects`.
- Общая библиотека загружаемых данных в `cloud_data/library`.
- Загрузка фото фасада, IES и style reference.
- Сохранение prompt.
- Автоцепочка: карта света -> prompt/latest пакет -> RouterAI -> финальный рендер.
- Каждый проект работает в своей папке и не перетирает соседние проекты.

## Локальный запуск

```bat
run_cloud.bat
```

Открыть:

```text
http://127.0.0.1:8080
```

## Серверный запуск

1. Установить Python 3.11+.
2. Положить проект на сервер.
3. Заполнить `routerai_api_key.txt` или задать переменную окружения `ROUTERAI_API_KEY`.
4. Выполнить:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements_cloud.txt
.venv/bin/uvicorn cloud_app:app --host 0.0.0.0 --port 8080
```

Для production лучше поставить reverse proxy Nginx и HTTPS.

## Production deploy checklist

1. Скопировать на сервер файлы проекта без `.venv` и без временных `__pycache__`.
2. Сохранить папку `cloud_data`, если нужно перенести существующие проекты и каталог.
3. Задать ключ через переменную окружения:

```bash
export ROUTERAI_API_KEY="..."
export ROUTERAI_IMAGE_MODEL="google/gemini-2.5-flash-image"
```

4. Запустить приложение через process manager:

```bash
.venv/bin/uvicorn cloud_app:app --host 127.0.0.1 --port 8080
```

5. Поставить Nginx перед приложением:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    client_max_body_size 50m;
}
```

6. Включить HTTPS.
7. Добавить авторизацию перед публичным доступом.

## Deploy target

Текущий сервер:

```text
IP: 194.226.187.101
OS: Ubuntu 24.04 LTS
Region: Москва-2
vCPU/RAM/Disk: 1 / 1GB / 10GB
Backups: включены
```

На таком тарифе приложение запустится, но надо следить за размером `cloud_data`, потому что изображения и история проектов быстро занимают диск.

## .env

На сервере создать файл:

```bash
/opt/niteos-cloud/.env
```

Пример:

```bash
ROUTERAI_API_KEY=...
ROUTERAI_IMAGE_MODEL=google/gemini-2.5-flash-image
NITEOS_HOST=127.0.0.1
NITEOS_PORT=8080
```

Файл `.env` нельзя отдавать в публичный доступ.

Создать файл можно так:

```bash
cat > /opt/niteos-cloud/.env <<'EOF'
ROUTERAI_API_KEY=...
ROUTERAI_IMAGE_MODEL=google/gemini-2.5-flash-image
NITEOS_HOST=127.0.0.1
NITEOS_PORT=8080
EOF
chmod 600 /opt/niteos-cloud/.env
```

## Safe replacement of old project

Если на сервере уже есть другой проект, сначала сделать резервную копию:

```bash
sudo mkdir -p /opt/backups
sudo tar -czf /opt/backups/old-project-$(date +%Y%m%d-%H%M%S).tar.gz /path/to/old/project
```

Дальше новый проект лучше поставить в отдельную папку:

```bash
sudo mkdir -p /opt/niteos-cloud
sudo chown -R $USER:$USER /opt/niteos-cloud
```

Потом запустить новый сервис на `127.0.0.1:8080` и только после проверки переключить Nginx на него.

## Важное

`routerai_api_key.txt` нельзя отдавать наружу и нельзя хранить в публичном репозитории.
