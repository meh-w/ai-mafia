# Мафия: Протокол Тень

[![Lint & test](https://github.com/meh-w/ai-mafia/actions/workflows/ci.yml/badge.svg)](https://github.com/meh-w/ai-mafia/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Flake8](https://img.shields.io/badge/flake8-checked-blueviolet.svg)](https://flake8.pycqa.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)

Реализация мафии-онлайн, которая превращается в нуарное расследование. В отличие от классических правил,
каждый игрок получает возможность кастомизации своего персонажа и создания отличительных поведенческих черт,
а ИИ-ведущий генерирует уникальные наводки на игроков, запутывая или приближая их к истине.

Проект занял 3 призовое место в проектной деятельности Яндекс Лицея (апрель, 2026).

## Механика

Соблюдаются традиционные правила игры — день для обсуждения и голосования, ночь для действий мафии, комиссара и доктора.

* **Реальное время**: все действия происходят синхронно, игроки видят обновления мгновенно.

* **Удобный интерфейс**: интуитивно понятная навигация, чёткое отображение ролей и хода игры.

* **Создание комнат**: игроки могут создавать собственные игровые комнаты с настраиваемым размером стола.

* **Система лобби**: просмотр доступных комнат и присоединение к ним.

* **Адаптивный дизайн**: игра корректно отображается на ПК и мобильных устройствах.

* **ИИ-детектив и метафоричные улики**: Главная особенность проекта — уникальная система генерации улик. Каждое ночное действие оставляет след, который нейросеть превращает в туманный нуарный образ. Игрокам предстоит не просто гадать, а заниматься настоящей дедукцией, сопоставляя описания внешности персонажей с метафорами ИИ.

## Необходимое ПО

* [**Python 3.13**](https://www.python.org/)
* [**Git**](https://git-scm.com/)
* [**Docker**](https://www.docker.com/)
* **gettext** (для локализации)
   * Linux
      ```bash
      sudo apt-get install gettext
      ```
   * MacOS
      ```bash
      brew install gettext
      ```
   * Windows — Рекомендуется из [Git for Windows](https://gitforwindows.org)

## Установка и запуск (Dev-режим)

1. **Клонируйте репозиторий удобным способом:**

   * Клонировать по SSH
      ```bash
      git clone git@gitlab.crja72.ru:django/2026/spring/course/projects/team-4.git
      ```

   * Клонировать по HTTPS
      ```bash
      git clone https://gitlab.crja72.ru/django/2026/spring/course/projects/team-4.git
      ```

2. **Перейдите в папку team-4:**

   ```bash
   cd team-4
   ```

3. **Создайте и активируйте виртуальное окружение:**
   * Linux/MacOS

      ```bash
      python3 -m venv venv
      source venv/bin/activate
      ```

   * Windows

      ```powershell
      python -m venv venv
      venv\Scripts\activate
      ```

4. **Установите зависимости:**

   * Разработка (включает prod и test)
      ```bash
      pip install -r requirements/dev.txt
      ```

   * Тесты (опционально; включает prod)
      ```bash
      pip install -r requirements/test.txt
      ```

   * Продакшн (опционально)
      ```bash
      pip install -r requirements/prod.txt
      ```

5. **Настройте переменные окружения:**

   * Linux/MacOS
      ```bash
      cp .env.example .env
      ```

   * Windows
      ```bash
      copy .env.example .env
      ```

   Откройте файл `.env` в любом редакторе и замените плейсхолдеры на реальные значения.

6. **Преднастройте проект:**

   * Перейдите в папку проекта
      ```bash
      cd mafia
      ```

   * Запустите Docker-контейнеры
      ```bash
      docker compose up -d
      ```

   * Примените миграции
      ```bash
      python manage.py migrate
      ```

   * Создайте суперпользователя
      ```bash
      python manage.py createsuperuser
      ```

   * Соберите статику:
      ```bash
      python manage.py collectstatic --noinput
      ```

7. **Запустите сервер:**
   
   * Терминал 1 — Django
      ```bash
      python manage.py runserver
      ```

   * Терминал 2 — Celery worker
      ```bash
      celery -A mafia worker -P solo -l info
      ```

   * Терминал 3 — Celery beat
      ```bash
      celery -A mafia beat -l info
      ```

   ---

   Проект будет доступен по адресу: [127.0.0.1:8000](http://127.0.0.1:8000/)

   Административный раздел будет доступен по адресу: [127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## Состав команды
   * Баландинская Алина (Ментор)
   * Шайдуллин Радмир (Лид)
   * Андреева Анна
   * Новиков Владислав

## Обратная связь

Если нашли баг или хотите предложить улучшение — откройте issue или отправьте pull request в этот репозиторий.