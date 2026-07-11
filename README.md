# Fish Shop Telegram Bot

Telegram-бот для магазина рыбы. Бот показывает товары из Strapi, даёт добавить товар в корзину, удалить товар из корзины и оставить email для связи.

## Что умеет бот

- Показывает меню товаров из Strapi.
- Показывает карточку товара с описанием, ценой и картинкой.
- Добавляет товар в корзину пользователя.
- Показывает корзину текстом.
- Удаляет товары из корзины.
- Просит email для оформления заказа.
- Записывает email клиента в Strapi.


`tg_state_bot.py` остаётся оркестратором: он решает, в каком состоянии находится пользователь и какую функцию вызвать дальше.


## Что нужно установить

Нужны:

- Python 3.10+
- Node.js
- локальная Strapi CMS

Python-зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Настройки окружения

Создайте файл `.env` в корне проекта:

```env
TG_TOKEN=your_telegram_bot_token
STRAPI_TOKEN=your_strapi_api_token

STRAPI_API_URL=http://localhost:1337/api
STRAPI_URL=http://localhost:1337
```

## Настройка Strapi

В Strapi должны быть модели:

- `Product`
- `Cart`
- `Cart Item`
- `Customer`

Минимальные поля:

`Product`:
- `title`
- `description`
- `price`
- `image`

`Cart`:
- `telegram_id`
- связь с `Cart Item`

`Cart Item`:
- `quantity_kg`
- связь с `Cart`
- связь с `Product`

`Customer`:
- `telegram_id`
- `email`

Для API token нужны права на чтение товаров, чтение/создание корзин, создание/удаление позиций корзины и создание клиентов.

## Как запустить

1. Запустите Strapi:

```bash
cd cms
npm run develop
```

2. В отдельной консоли запустите бота:

```bash
source .venv/bin/activate
python tg_state_bot.py
```

## Сценарий работы

1. Пользователь отправляет `/start`.
2. Бот показывает список товаров и кнопку `Моя корзина`.
3. Пользователь выбирает товар.
4. Бот показывает карточку товара с кнопками:
   - `Добавить в корзину`
   - `Моя корзина`
   - `Назад`
5. В корзине доступны кнопки:
   - `Оплатить`
   - `Убрать: <название товара>`
   - `В меню`
6. После нажатия `Оплатить` бот просит email.
7. Email сохраняется в Strapi как `Customer`.