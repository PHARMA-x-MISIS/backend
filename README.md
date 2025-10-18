# backend

## VK ID авторизация (без SDK)

1) Настройка в VK:
   - Включите приложение типа «Сайт». 
   - Базовый домен: `mosprom.misis-team.ru`.
   - Redirect URI: `https://mosprom.misis-team.ru`.

2) Переменные окружения:
   - См. `.example.env` и создайте `.env` с:
     - `VK_CLIENT_ID`
     - `VK_CLIENT_SECRET`
     - `VK_REDIRECT_URI=https://mosprom.misis-team.ru`
     - `VK_API_VERSION=5.131`

3) Эндпоинты:
   - `GET /users/auth/vk` — редирект на VK c `state`.
   - `GET /users/auth/vk/callback?code=...&state=...` — callback; в ответе JSON с `access_token` (JWT) и `is_new_user`.

4) Поток:
   - Фронт открывает `/users/auth/vk` (или формирует ссылку из ответа бэкенда).
   - VK редиректит на `VK_REDIRECT_URI` (совпадает с настройками приложения) — ваш фронт получает `code` и `state` и вызывает `/users/auth/vk/callback` с этими параметрами.
   - Бэкенд обменяет `code` на access_token в VK, получит user info, создаст/обновит пользователя и вернёт JWT.

5) Безопасность:
   - Используется параметр `state` для защиты от CSRF.
   - В проде рекомендуется хранить выданные `state` вне памяти процесса (Redis) и/или использовать подписанный state.