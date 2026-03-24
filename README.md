# no Telega
проверяет, пользуется ли человек Telega.

# Принцип работы
### Важное замечание: сводка ниже была написана НЕ МНОЙ в соавторстве с ChatGPT. Автор сводки — [@altuskha](https://t.me/altuskha). 

Эта заметка описывает рабочий способ определить, резолвится ли пользователь в calls/Telega-контуре приложения.

По результатам проверки в этой кодовой базе `external_user_id` очень похоже используется как `telegram_id`. Это подтверждается практической проверкой для `1363800669`: backend вернул внутренний `ok_user_id`.
Этот айди взят из комментариев t.me/telegaru

## Креды и базовые значения

- `CALLS_BASE_URL`: `https://calls.okcdn.ru/`
- `CALLS_API_KEY`: `CHKIPMKGDIHBABABA`
- Рабочий host для lookup: `https://calls.okcdn.ru`

Важно:

- Для `vchat.getOkIdsByExternalIds` нужен `session_key`.
- `session_key` можно получить через anonymous login.
- Использовать надо именно `calls.okcdn.ru`.
- Попытка дергать generic host `https://api.ok.ru/api/vchat/getOkIdsByExternalIds` в тесте вернула ошибку `error_code: 4`, `error_msg: "REQUEST : common.finder"`.

## Что именно считаем признаком пользователя Telega

Практическое правило для этой app-схемы:

- если `vchat.getOkIdsByExternalIds` возвращает запись для `external_user_id = <telegram_id>`, то пользователь существует в calls/Telega-контуре;
- если массив `ids` пустой или в нем нет нужного `external_user_id`, то пользователь не найден в этом контуре.

Это не "официальная публичная документация" Telega, а рабочая reverse-engineered схема, подтвержденная кодом и реальным запросом.

## Шаг 1. Получить anonymous session

Endpoint:

- `POST https://calls.okcdn.ru/api/auth/anonymLogin`

Content-Type:

- `application/x-www-form-urlencoded`

Поля формы:

- `application_key`
- `session_data`

Пример `session_data`:

```json
{"device_id":"test","version":2,"client_version":"android_8","client_type":"SDK_ANDROID"}
```

Пример `curl`:

```bash
curl -X POST "https://calls.okcdn.ru/api/auth/anonymLogin" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "application_key=CHKIPMKGDIHBABABA" \
  --data-urlencode "session_data={\"device_id\":\"test\",\"version\":2,\"client_version\":\"android_8\",\"client_type\":\"SDK_ANDROID\"}"
```

Ожидаемый ответ:

```json
{
  "session_key": "<SESSION_KEY>",
  "session_secret_key": "<SESSION_SECRET_KEY>",
  "api_server": "https://calls.okcdn.ru/"
}
```

## Шаг 2. Проверить пользователя по Telegram ID

Endpoint:

- `POST https://calls.okcdn.ru/api/vchat/getOkIdsByExternalIds`

Content-Type:

- `application/x-www-form-urlencoded`

Поля формы:

- `application_key`
- `session_key`
- `externalIds`

Формат `externalIds`:

```json
[{"id":"<TELEGRAM_ID>","ok_anonym":false}]
```

Пример `curl`:

```bash
curl -X POST "https://calls.okcdn.ru/api/vchat/getOkIdsByExternalIds" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "application_key=CHKIPMKGDIHBABABA" \
  --data-urlencode "session_key=<SESSION_KEY>" \
  --data-urlencode "externalIds=[{\"id\":\"1363800669\",\"ok_anonym\":false}]"
```

Успешный ответ:

```json
{
  "ids": [
    {
      "ok_user_id": 1125899936615283,
      "external_user_id": {
        "id": "1363800669",
        "ok_anonym": false
      }
    }
  ]
}
```

## Интерпретация ответа

### Пользователь найден

Если ответ содержит объект в `ids`, например:

```json
{
  "ok_user_id": 1125899936615283,
  "external_user_id": {
    "id": "1363800669",
    "ok_anonym": false
  }
}
```

то:

- `1363800669` успешно резолвится в backend;
- backend считает этот `external_user_id` известным;
- можно считать, что этот пользователь присутствует в calls/Telega-контуре.

### Пользователь не найден

Если backend вернет что-то вроде:

```json
{
  "ids": []
}
```

или в массиве не будет нужного `external_user_id`, то пользователь не найден.

## Быстрый алгоритм детекта

1. Получить `session_key` через `auth.anonymLogin`.
2. Отправить `telegram_id` как `external_user_id` в `vchat.getOkIdsByExternalIds`.
3. Если в `ids` есть запись с этим `id`, вернуть `true`.
4. Если записи нет, вернуть `false`.

Псевдологика:

```text
session = anonymLogin(application_key)
result = getOkIdsByExternalIds(session.session_key, telegram_id)

if result.ids contains external_user_id.id == telegram_id:
    is_telega_user = true
else:
    is_telega_user = false
```

## PowerShell пример

```powershell
$auth = Invoke-RestMethod -Method Post `
  -Uri 'https://calls.okcdn.ru/api/auth/anonymLogin' `
  -ContentType 'application/x-www-form-urlencoded' `
  -Body @{
    application_key = 'CHKIPMKGDIHBABABA'
    session_data = '{"device_id":"test","version":2,"client_version":"android_8","client_type":"SDK_ANDROID"}'
  }

$lookup = Invoke-RestMethod -Method Post `
  -Uri 'https://calls.okcdn.ru/api/vchat/getOkIdsByExternalIds' `
  -ContentType 'application/x-www-form-urlencoded' `
  -Body @{
    application_key = 'CHKIPMKGDIHBABABA'
    session_key = $auth.session_key
    externalIds = '[{"id":"1363800669","ok_anonym":false}]'
  }

$lookup | ConvertTo-Json -Depth 10
```

## Проверенный кейс

Проверено вручную:

- `telegram_id`: `1363800669`
- результат: найден
- `ok_user_id`: `1125899936615283`

## Что видно в коде

- `CALLS_API_KEY` и `CALLS_BASE_URL`: [Extra.java]
- calls SDK получает token info и использует `baseUrl`: [DahlCallManager.java]
- запрос lookup собирается как `vchat.getOkIdsByExternalIds`: [GetOkIdsByExternalIds.java]
- ответ парсится как `external_user_id -> ok_user_id`: [BatchInternalIdResponse.java]
## Ограничения

- Это описание основано на reverse engineering клиента и реальных запросах, а не на официальной документации сервиса.
- Наличие маппинга означает, что пользователь известен calls/backend-контуру приложения.
- Если backend когда-нибудь поменяет смысл `external_user_id`, логику надо будет перепроверить.
