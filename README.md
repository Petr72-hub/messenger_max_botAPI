# maxgram

**Асинхронный фреймворк для Bot API мессенджера MAX, спроектированный по образу и подобию [aiogram](https://github.com/aiogram/aiogram).**

Если вы писали ботов на aiogram — вы уже умеете писать ботов на maxgram. Те же `Dispatcher` и `Router`, те же декораторы-хендлеры, тот же магический фильтр `F`, тот же FSM, те же middleware и та же инъекция зависимостей в хендлеры.

```python
from maxgram import Bot, Dispatcher, F
from maxgram.filters import Command
from maxgram.types import Message

dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет из MAX!")

@dp.message(F.text.lower().contains("спасибо"))
async def thanks(message: Message):
    await message.reply("Всегда пожалуйста 🙂")

if __name__ == "__main__":
    dp.run_polling(Bot("ВАШ_ТОКЕН"))
```

---

## Содержание

- [Возможности](#возможности)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Получение токена](#получение-токена)
- [Основные концепции](#основные-концепции)
  - [Bot — клиент API](#bot--клиент-api)
  - [Dispatcher и Router](#dispatcher-и-router)
  - [Типы событий](#типы-событий)
- [Фильтры](#фильтры)
  - [Магический фильтр F](#магический-фильтр-f)
  - [Command](#command)
  - [Text, Regexp, ContentType](#text-regexp-contenttype)
  - [Фильтры чатов и пользователей](#фильтры-чатов-и-пользователей)
  - [Свои фильтры](#свои-фильтры)
- [Клавиатуры и кнопки](#клавиатуры-и-кнопки)
- [CallbackData — типизированные payload'ы](#callbackdata--типизированные-payloadы)
- [Работа с медиа](#работа-с-медиа)
- [FSM — машина состояний](#fsm--машина-состояний)
- [Middleware](#middleware)
- [Обработка ошибок](#обработка-ошибок)
- [Инъекция зависимостей](#инъекция-зависимостей)
- [Webhook вместо polling](#webhook-вместо-polling)
- [Форматирование текста](#форматирование-текста)
- [Полный справочник методов Bot](#полный-справочник-методов-bot)
- [Исключения](#исключения)
- [Отличия от aiogram](#отличия-от-aiogram)
- [Ограничения MAX API](#ограничения-max-api)
- [Тесты и разработка](#тесты-и-разработка)
- [Лицензия](#лицензия)

---

## Возможности

| Возможность | Статус |
|---|---|
| Полное покрытие REST-методов MAX Bot API | ✅ |
| Long polling с автоматическим переподключением | ✅ |
| Webhook-сервер на aiohttp + проверка секрета | ✅ |
| Типизированные модели на pydantic v2 | ✅ |
| `Dispatcher` / `Router` с неограниченной вложенностью | ✅ |
| Магический фильтр `F` | ✅ |
| FSM: `State`, `StatesGroup`, `FSMContext` | ✅ |
| Хранилища FSM: память, JSON-файл, свои | ✅ |
| Middleware (внешние и внутренние) | ✅ |
| Инъекция зависимостей по сигнатуре хендлера | ✅ |
| Билдер инлайн-клавиатур | ✅ |
| `CallbackData` — типизированные payload'ы кнопок | ✅ |
| Загрузка фото / видео / аудио / документов | ✅ |
| Клиентский rate limiting (2 msg/sec на чат) | ✅ |
| Автоматические ретраи при 429 / 5xx / сетевых сбоях | ✅ |
| Шорткаты `message.answer()`, `message.reply()`, `.edit()`, `.delete()` | ✅ |

## Установка

```bash
pip install maxgram
```

Или из исходников:

```bash
git clone https://github.com/<ваш-аккаунт>/maxgram.git
cd maxgram
pip install -e ".[dev]"
```

Требования: **Python 3.10+**, `aiohttp`, `pydantic>=2.6`, `certifi`.

## Быстрый старт

```python
import asyncio
import os

from maxgram import Bot, Dispatcher
from maxgram.filters import Command
from maxgram.types import Message

dp = Dispatcher()


@dp.message(Command("start", "help"))
async def on_start(message: Message):
    await message.answer("Бот запущен. Напишите что-нибудь.")


@dp.message()
async def echo(message: Message):
    await message.reply(f"Вы написали: {message.text}")


async def main():
    bot = Bot(os.environ["MAX_BOT_TOKEN"])
    async with bot:                      # закроет HTTP-сессию на выходе
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

Если не хочется писать `async def main()`, есть блокирующая обёртка:

```python
if __name__ == "__main__":
    dp.run_polling(Bot(os.environ["MAX_BOT_TOKEN"]))
```

## Получение токена

1. Откройте в MAX диалог с **@MasterBot**.
2. Отправьте `/create` и следуйте инструкциям — придумайте имя и username бота.
3. MasterBot выдаст токен вида `abcd1234...`. Это и есть значение для `Bot(token)`.
4. Чтобы бот работал в канале или группе — добавьте его туда **администратором**.

Токен держите в переменной окружения, а не в коде:

```bash
export MAX_BOT_TOKEN="ваш-токен"      # Linux/macOS
$env:MAX_BOT_TOKEN="ваш-токен"        # Windows PowerShell
```

---

## Основные концепции

### Bot — клиент API

`Bot` — это асинхронный HTTP-клиент к `https://platform-api2.max.ru`. Он отвечает за авторизацию, ретраи, троттлинг и парсинг ответов в модели.

```python
from maxgram import Bot, DefaultBotProperties, TextFormat
from maxgram.client import RetryPolicy

bot = Bot(
    token="...",
    default=DefaultBotProperties(
        parse_mode=TextFormat.MARKDOWN,   # применяется ко всем сообщениям
        disable_link_preview=False,
        notify=True,
    ),
    timeout=60.0,                          # таймаут HTTP-запроса
    retry=RetryPolicy(max_attempts=4),     # ретраи при 429/5xx/сетевых сбоях
    rate_limit=2.0,                        # сообщений в секунду на один чат
    proxy="http://user:pass@host:3128",    # опционально
)
```

Объекты, полученные от бота, «привязаны» к нему — поэтому у них работают шорткаты:

```python
me = await bot.get_me()
chat = await bot.get_chat(123)
await chat.send("Привет!")           # эквивалент bot.send_message(chat_id=123, ...)
```

### Dispatcher и Router

`Router` — группа хендлеров. `Dispatcher` — корневой роутер, который дополнительно умеет опрашивать сервер, хранить FSM и ловить ошибки.

```python
# handlers/admin.py
from maxgram import Router
from maxgram.filters import Command, IsAdmin

admin_router = Router(name="admin")

@admin_router.message(Command("stats"), IsAdmin([111, 222]))
async def stats(message): ...
```

```python
# main.py
from maxgram import Dispatcher
from handlers.admin import admin_router
from handlers.user import user_router

dp = Dispatcher()
dp.include_routers(admin_router, user_router)   # порядок = приоритет
```

Поиск хендлера идёт сверху вниз: сначала свои хендлеры роутера, затем дочерние роутеры по порядку подключения. **Выполняется первый подошедший хендлер**, дальше поиск останавливается.

Чтобы явно провалиться к следующему хендлеру, бросьте `SkipHandler`:

```python
from maxgram.exceptions import SkipHandler

@dp.message()
async def maybe(message):
    if not interesting(message):
        raise SkipHandler
```

### Типы событий

У роутера есть отдельный наблюдатель (observer) на каждый тип события MAX. Имена подобраны так, чтобы читались привычно:

| Декоратор | `update_type` в MAX | Что приходит в хендлер |
|---|---|---|
| `@router.message()` | `message_created` | `Message` |
| `@router.edited_message()` | `message_edited` | `Message` |
| `@router.deleted_message()` | `message_removed` | `MessageRemoved` |
| `@router.callback_query()` | `message_callback` | `MessageCallback` |
| `@router.chat_created()` | `message_chat_created` | `MessageChatCreated` |
| `@router.bot_added()` | `bot_added` | `BotAdded` |
| `@router.bot_removed()` | `bot_removed` | `BotRemoved` |
| `@router.bot_started()` | `bot_started` | `BotStarted` |
| `@router.bot_stopped()` | `bot_stopped` | `BotStopped` |
| `@router.user_added()` | `user_added` | `UserAdded` |
| `@router.user_removed()` | `user_removed` | `UserRemoved` |
| `@router.chat_title_changed()` | `chat_title_changed` | `ChatTitleChanged` |
| `@router.dialog_cleared()` | `dialog_cleared` | `DialogCleared` |
| `@router.dialog_removed()` | `dialog_removed` | `DialogRemoved` |
| `@router.dialog_muted()` | `dialog_muted` | `DialogMuted` |
| `@router.dialog_unmuted()` | `dialog_unmuted` | `DialogUnmuted` |
| `@router.comment_created()` | `comment_created` | `CommentCreated` |
| `@router.comment_edited()` | `comment_edited` | `CommentEdited` |
| `@router.comment_removed()` | `comment_removed` | `CommentRemoved` |
| `@router.update()` | любое | объект события |
| `@router.errors()` | — | исключение |

Для событий, которых ещё нет в этом списке (MAX добавляет новые), есть универсальный доступ:

```python
@dp.observer("some_new_event")()
async def handler(event):
    ...
```

Неизвестные события не роняют бота — они приходят как базовый `Update`.

---

## Фильтры

Фильтры — это позиционные аргументы декоратора. Хендлер срабатывает, только если **все** фильтры вернули истину.

```python
@dp.message(Command("ban"), IsAdmin([1, 2]), F.chat_type == "chat")
async def ban(message): ...
```

Фильтр, вернувший `dict`, не только пропускает событие, но и **передаёт свои ключи в хендлер** как именованные аргументы.

### Магический фильтр F

`F` строит ленивое выражение по атрибутам события:

```python
from maxgram import F

F.text == "/start"                       # точное совпадение
F.text.lower().startswith("привет")      # цепочка методов
F.text.contains("скидка")
F.text.regexp(r"^\d{4}$")
F.chat_type.in_({"chat", "channel"})
F.sender.username == "ivan"
F.body.attachments.is_not_none()
~F.sender.is_bot                         # отрицание
(F.text.startswith("/")) & (F.chat_type == "dialog")   # И
(F.text == "да") | (F.text == "нет")                   # ИЛИ
```

Цепочка безопасна к «дыркам»: если по пути встретился `None`, всё выражение спокойно вернёт ложь, а не упадёт с `AttributeError`.

Результат выражения можно передать в хендлер под своим именем:

```python
@dp.message(F.text.regexp(r"#(\w+)").as_("tag"))
async def by_tag(message: Message, tag):
    ...
```

Доступные методы: `.in_()`, `.not_in()`, `.contains()`, `.startswith()`, `.endswith()`, `.regexp()`, `.lower()`, `.upper()`, `.len()`, `.is_none()`, `.is_not_none()`, `.func()`, `.cast()`, `.as_()` и все операторы сравнения.

### Command

```python
from maxgram.filters import Command, CommandObject

@dp.message(Command("start"))
async def start(message: Message, command: CommandObject):
    print(command.prefix)     # "/"
    print(command.command)    # "start"
    print(command.args)       # текст после команды или None
    print(command.arg_list()) # аргументы, разбитые по пробелам

@dp.message(Command("help", "info"))        # несколько алиасов
@dp.message(Command(re.compile(r"item_\d+")))  # регулярка
@dp.message(Command("start", prefix="/!."))    # свои префиксы
```

Для `/start` с deep-link есть отдельный фильтр, который понимает и текстовую команду, и событие `bot_started`:

```python
from maxgram.filters import CommandStartFilter

@dp.message(CommandStartFilter(deep_link=True))
async def deep(message, command: CommandObject):
    payload = command.args
```

### Text, Regexp, ContentType

```python
from maxgram.filters import Text, Regexp, ContentType, HasAttachment

Text("да", "нет", ignore_case=True)
Text(startswith="купить")
Text(contains=["промо", "скидк"])

@dp.message(Regexp(r"заказ №(\d+)"))
async def order(message, match):          # match — это re.Match
    order_id = match.group(1)

ContentType("image", "video")             # по типу первого вложения
HasAttachment("file")                     # есть вложение указанного типа
```

### Фильтры чатов и пользователей

```python
from maxgram.filters import ChatTypeFilter, IsDialog, IsChannel, IsGroup, IsAdmin, IsBot

@dp.message(IsChannel())                       # только посты в канале
@dp.message(ChatTypeFilter(["chat", "dialog"]))
@dp.message(IsAdmin([111222333]))              # белый список user_id
@dp.message(~IsBot())                          # только от людей
```

### Свои фильтры

Фильтром может быть любая функция или класс:

```python
# Обычная функция
def long_text(message) -> bool:
    return bool(message.text) and len(message.text) > 500

@dp.message(long_text)
async def handler(message): ...


# Класс — если нужны параметры и внедрение данных
from maxgram.filters import Filter

class HasHashtag(Filter):
    def __init__(self, tag: str):
        self.tag = f"#{tag}"

    async def __call__(self, message, **kwargs):
        if message.text and self.tag in message.text:
            return {"hashtag": self.tag}   # попадёт в хендлер как hashtag=
        return False

@dp.message(HasHashtag("news"))
async def news(message, hashtag: str): ...
```

Фильтры-классы комбинируются операторами `&`, `|`, `~`.

---

## Клавиатуры и кнопки

В MAX клавиатура передаётся как вложение, но maxgram прячет это за привычным `reply_markup=`.

```python
from maxgram import Intent
from maxgram.utils import InlineKeyboardBuilder

kb = InlineKeyboardBuilder()
kb.button(text="👍 Да", payload="vote:yes", intent=Intent.POSITIVE)
kb.button(text="👎 Нет", payload="vote:no", intent=Intent.NEGATIVE)
kb.url("Подробнее", "https://dev.max.ru/docs-api")
kb.request_contact("Поделиться контактом")
kb.request_location("Отправить геопозицию")
kb.adjust(2, 1, 1)          # разложить по строкам: 2, потом по 1

await message.answer("Голосуем?", reply_markup=kb.as_markup())
```

Или напрямую, без билдера:

```python
from maxgram.types import InlineKeyboardMarkup, CallbackButton, LinkButton

markup = InlineKeyboardMarkup(buttons=[
    [CallbackButton(text="Да", payload="yes"), CallbackButton(text="Нет", payload="no")],
    [LinkButton(text="Сайт", url="https://example.com")],
])
```

Типы кнопок: `CallbackButton`, `LinkButton`, `RequestContactButton`, `RequestGeoLocationButton`, `ChatButton`, `OpenAppButton`, `MessageButton`.
Акценты (`Intent`): `POSITIVE` (зелёная), `NEGATIVE` (красная), `DEFAULT`.

Обработка нажатия:

```python
from maxgram.types import MessageCallback

@dp.callback_query(F.data == "vote:yes")
async def on_yes(event: MessageCallback):
    await event.answer("Голос учтён!")        # всплывающее уведомление
    await event.edit_text("Спасибо за голос") # правка исходного сообщения
```

> Нажатие обязательно нужно подтвердить через `event.answer(...)`, иначе у пользователя кнопка «зависнет» в состоянии загрузки.

## CallbackData — типизированные payload'ы

Вместо ручной склейки строк:

```python
from maxgram.filters import CallbackData

class Vote(CallbackData, prefix="vote"):
    poll_id: int
    choice: str

# упаковка
payload = Vote(poll_id=42, choice="yes").pack()     # "vote:42:yes"

# распаковка выполняется фильтром автоматически
@dp.callback_query(Vote.filter())
async def on_vote(event: MessageCallback, callback_data: Vote):
    print(callback_data.poll_id, callback_data.choice)   # 42 yes
```

Можно дополнительно фильтровать по полям:

```python
@dp.callback_query(Vote.filter(F.choice == "yes"))
async def only_yes(event, callback_data: Vote): ...
```

## Работа с медиа

Загрузка в MAX двухшаговая (получить URL → залить файл), но `Bot` делает это за вас:

```python
# Локальный файл — будет загружен
await bot.send_photo(chat_id=chat_id, photo="cat.jpg", text="Котик")

# Внешняя ссылка — MAX скачает сам, загрузка не нужна
await bot.send_photo(chat_id=chat_id, photo="https://example.com/cat.jpg")

# Байты
await bot.send_document(chat_id=chat_id, document=pdf_bytes, text="Отчёт")

# Альбом из нескольких фото
await bot.send_media_group(chat_id=chat_id, photos=["1.jpg", "2.jpg"], text="Галерея")

# Шорткаты у сообщения
await message.answer_photo("cat.jpg", caption="Котик")
await message.answer_video("clip.mp4")
await message.answer_document("report.pdf")
```

Если нужен контроль над токенами — низкоуровневый путь:

```python
from maxgram import UploadType
from maxgram.types import image, video, file

token = await bot.upload("cat.jpg", UploadType.IMAGE)
await bot.send_message(chat_id=chat_id, text="Фото", attachments=[image(token=token)])
```

Лимиты MAX: изображения до 50 МБ, видео до 250 МБ, аудио до 256 МБ, файлы до 4 ГБ.

> Свежезагруженное видео и аудио несколько секунд обрабатывается на стороне MAX. Метод `send_message_with_retry()` (его используют все `send_*` шорткаты) сам ждёт и повторяет отправку при ошибке `attachment.not.ready`.

## FSM — машина состояний

```python
from maxgram.fsm import State, StatesGroup

class Order(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


@dp.message(Command("order"))
async def start_order(message: Message, state):
    await state.set_state(Order.waiting_name)
    await message.answer("Как вас зовут?")


@dp.message(Order.waiting_name)          # состояние можно указывать как фильтр
async def got_name(message: Message, state):
    await state.update_data(name=message.text)
    await state.set_state(Order.waiting_phone)
    await message.answer("Ваш телефон?")


@dp.message(Order.waiting_phone)
async def got_phone(message: Message, state):
    data = await state.update_data(phone=message.text)
    await state.clear()
    await message.answer(f"Заказ принят: {data['name']}, {data['phone']}")
```

Аргумент `state` — это `FSMContext`:

| Метод | Назначение |
|---|---|
| `await state.set_state(Order.waiting_name)` | установить состояние |
| `await state.get_state()` | текущее состояние (строка или `None`) |
| `await state.update_data(key=value)` | дописать данные, вернуть все |
| `await state.get_data()` | все данные |
| `await state.get_value("key", default)` | одно значение |
| `await state.set_data({...})` | заменить данные целиком |
| `await state.clear()` | сбросить состояние и данные |

Фильтры состояний:

```python
from maxgram.filters import StateFilter

StateFilter(None)                 # пользователь вне сценария
StateFilter("*")                  # любое состояние
StateFilter(Order)                # любое состояние из группы
StateFilter(Order.waiting_name)
```

Хранилища:

```python
from maxgram.fsm import MemoryStorage, JSONFileStorage

dp = Dispatcher(storage=MemoryStorage())                    # по умолчанию
dp = Dispatcher(storage=JSONFileStorage("fsm_state.json"))  # переживает рестарт
```

Своё хранилище — унаследуйте `BaseStorage` и реализуйте `get_state` / `set_state` / `get_data` / `set_data`.

## Middleware

**Внешние** (`outer_middleware`) выполняются для каждого события, ещё до фильтров — удобно для логирования, антифлуда, подгрузки пользователя из БД. **Внутренние** (`middleware`) — только если хендлер уже найден.

```python
from maxgram import BaseMiddleware

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        print("→", type(event).__name__)
        result = await handler(event, data)
        print("←", result)
        return result


class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, pool):
        self.pool = pool

    async def __call__(self, handler, event, data):
        async with self.pool.acquire() as conn:
            data["db"] = conn            # станет аргументом хендлера
            return await handler(event, data)


dp.update.outer_middleware(LoggingMiddleware())   # на все события
dp.message.middleware(DatabaseMiddleware(pool))   # только на сообщения

@dp.message()
async def handler(message, db):        # db придёт из middleware
    ...
```

Чтобы прервать обработку из middleware — бросьте `CancelHandler`.

## Обработка ошибок

```python
from maxgram.exceptions import MaxAPIError

@dp.errors()
async def on_error(exception: Exception, event_update):
    logging.exception("Ошибка на событии %s", event_update.update_type)
    return True     # True = ошибка обработана, бот продолжает работу
```

Если ни один `@dp.errors()` не зарегистрирован, исключение просто логируется — polling из-за него не останавливается.

## Инъекция зависимостей

Хендлер получает только те аргументы, которые объявил в сигнатуре. Доступны:

| Аргумент | Что это |
|---|---|
| первый позиционный | само событие (`Message`, `MessageCallback`, …) |
| `bot` | текущий `Bot` |
| `dispatcher` | текущий `Dispatcher` |
| `state` | `FSMContext` этого диалога |
| `raw_state` | текущее состояние строкой |
| `event_update` | исходный объект `Update` |
| `event_from_user` | автор события (`User`) |
| `event_chat_id` | id чата |
| `event_router` | роутер, обработавший событие |
| `handler` | объект хендлера |
| ключи из фильтров | `command`, `match`, `callback_data`, ваши `dict`-и |
| ключи из middleware | всё, что положили в `data` |
| `workflow_data` | всё, что передали в `Dispatcher(...)` |

```python
dp = Dispatcher(config=my_config, db=my_db)

@dp.message()
async def handler(message: Message, bot: Bot, state, config, db):
    ...
```

## Webhook вместо polling

```python
from aiohttp import web
from maxgram import Bot, Dispatcher
from maxgram.webhook import setup_application

bot = Bot(TOKEN)
dp = Dispatcher()

await bot.set_webhook(
    "https://bot.example.com/webhook",
    update_types=["message_created", "message_callback"],
    secret=SECRET,
)

app = web.Application()
setup_application(app, dp, bot, path="/webhook", secret=SECRET)
web.run_app(app, host="0.0.0.0", port=8080)
```

Секрет проверяется по заголовку `X-Max-Bot-Api-Secret`. События обрабатываются в фоне, а MAX сразу получает `200 OK` — так вы не упираетесь в таймаут доставки.

Управление подписками:

```python
subs = await bot.get_subscriptions()
await bot.delete_webhook("https://bot.example.com/webhook")
```

## Форматирование текста

MAX принимает два формата — `markdown` и `html`:

```python
from maxgram import TextFormat
from maxgram.utils import bold, italic, link, hbold, hlink, escape_md, split_text

await bot.send_message(
    chat_id=chat_id,
    text=f"{bold('Важно')}: {link('читайте документацию', 'https://dev.max.ru')}",
    parse_mode=TextFormat.MARKDOWN,
)

await bot.send_message(chat_id=chat_id, text=hbold("Заголовок"), parse_mode=TextFormat.HTML)

# Пользовательский ввод внутри разметки нужно экранировать
text = f"Запрос: {escape_md(user_input)}"

# Длинный пост нарезать на части (лимит MAX — 4000 символов)
for chunk in split_text(long_post):
    await bot.send_message(chat_id=chat_id, text=chunk)
```

---

## Полный справочник методов Bot

### Профиль бота

| Метод | Эндпоинт |
|---|---|
| `get_me(cached=False)` | `GET /me` |
| `set_my_info(name=, description=, commands=, photo=)` | `PATCH /me` |
| `set_my_commands(commands)` | `PATCH /me/commands` |

### Чаты

| Метод | Эндпоинт |
|---|---|
| `get_chats(count=, marker=)` | `GET /chats` |
| `get_chat(chat_id)` | `GET /chats/{chatId}` |
| `get_chat_by_link(link)` | `GET /chats/{chatLink}` |
| `edit_chat(chat_id, title=, icon=, pin=, notify=)` | `PATCH /chats/{chatId}` |
| `send_chat_action(chat_id, action)` | `POST /chats/{chatId}/actions` |
| `leave_chat(chat_id)` | `DELETE /chats/{chatId}/members/me` |
| `get_pinned_message(chat_id)` | `GET /chats/{chatId}/pin` |
| `pin_message(chat_id, message_id, notify=)` | `PUT /chats/{chatId}/pin` |
| `unpin_message(chat_id)` | `DELETE /chats/{chatId}/pin` |
| `get_my_membership(chat_id)` | `GET /chats/{chatId}/members/me` |
| `get_chat_admins(chat_id)` | `GET /chats/{chatId}/members/admins` |
| `add_chat_admins(chat_id, admins)` | `POST /chats/{chatId}/members/admins` |
| `remove_chat_admin(chat_id, user_id)` | `DELETE /chats/{chatId}/members/admins/{userId}` |
| `get_chat_members(chat_id, ...)` | `GET /chats/{chatId}/members` |
| `add_chat_members(chat_id, user_ids)` | `POST /chats/{chatId}/members` |
| `remove_chat_member(chat_id, user_id, block=)` | `DELETE /chats/{chatId}/members` |

### Сообщения

| Метод | Эндпоинт |
|---|---|
| `send_message(chat_id=/user_id=, text=, attachments=, reply_markup=, link=, notify=, parse_mode=, disable_link_preview=)` | `POST /messages` |
| `edit_message(message_id, ...)` | `PUT /messages` |
| `delete_message(message_id)` | `DELETE /messages` |
| `get_message(message_id)` | `GET /messages/{messageId}` |
| `get_messages(chat_id=, message_ids=, from_time=, to_time=, count=)` | `GET /messages` |
| `answer_callback(callback_id, notification=, message=, show_alert=)` | `POST /answers` |
| `get_video(video_token)` | `GET /videos/{videoToken}` |

### Комментарии к постам канала

| Метод | Эндпоинт |
|---|---|
| `get_comments(message_id, count=, marker=)` | `GET /messages/{messageId}/comments` |
| `send_comment(message_id, text=, attachments=, reply_to=)` | `POST /messages/{messageId}/comments` |
| `edit_comment(message_id, comment_id, text=)` | `PUT /messages/{messageId}/comments` |
| `delete_comment(message_id, comment_id)` | `DELETE /messages/{messageId}/comments` |

### Загрузка файлов

| Метод | Назначение |
|---|---|
| `get_upload_url(upload_type)` | `POST /uploads` — получить URL |
| `upload(file, upload_type)` | оба шага, возвращает токен |
| `send_photo / send_video / send_audio / send_document` | загрузка + отправка |
| `send_media_group(photos=[...])` | альбом |

### Транспорт

| Метод | Эндпоинт |
|---|---|
| `get_updates(limit=, timeout=, marker=, types=)` | `GET /updates` |
| `get_subscriptions()` | `GET /subscriptions` |
| `set_webhook(url, update_types=, secret=, version=)` | `POST /subscriptions` |
| `delete_webhook(url)` | `DELETE /subscriptions` |

### Шорткаты объекта `Message`

```python
await message.answer(text)              # новое сообщение в тот же чат
await message.reply(text)               # ответ-цитата
await message.forward(chat_id=...)      # переслать
await message.edit(text)                # отредактировать
await message.delete()                  # удалить
await message.pin()                     # закрепить
await message.answer_photo(path)
await message.answer_video(path)
await message.answer_document(path)
```

Полезные свойства: `message.text`, `.message_id`, `.chat_id`, `.user_id`, `.chat_type`, `.from_user`, `.attachments`, `.content_type`, `.is_channel_post`, `.reply_to`, `.forwarded_from`, `.url`, `.stat.views`.

## Исключения

Все наследуются от `MaxgramError`:

| Исключение | Когда |
|---|---|
| `MaxBadRequest` | HTTP 400 |
| `MaxUnauthorizedError` | HTTP 401 — токен неверен или отозван |
| `MaxForbiddenError` | HTTP 403 — нет прав |
| `MaxNotFound` | HTTP 404 |
| `MaxRetryAfter` | HTTP 429, поле `.retry_after` |
| `MaxEntityTooLarge` | HTTP 413 — файл больше лимита |
| `MaxServerError` | HTTP 5xx |
| `AttachmentNotReady` | медиа ещё обрабатывается |
| `MaxNetworkError` | сеть, DNS, TLS, таймаут |
| `ClientDecodeError` | сервер вернул не JSON |
| `SkipHandler` | пропустить хендлер (бросается вами) |
| `CancelHandler` | прервать обработку (бросается вами) |

`MaxRetryAfter`, `MaxServerError`, `MaxNetworkError` и `AttachmentNotReady` повторяются автоматически по `RetryPolicy` — до вас они долетают, только когда попытки исчерпаны.

## Отличия от aiogram

| aiogram | maxgram | Почему |
|---|---|---|
| `message.message_id` — `int` | `message.message_id` — `str` | в MAX идентификатор сообщения строковый (`mid`) |
| `reply_markup` — отдельное поле | внутри `attachments` | так устроен MAX API; maxgram оборачивает сам |
| `CallbackQuery` | `MessageCallback` | название события в MAX |
| `parse_mode="HTML"` | `parse_mode=TextFormat.HTML` | MAX принимает `markdown` / `html` |
| `bot.send_photo(photo=FSInputFile(...))` | `bot.send_photo(photo="path.jpg")` | путь, байты, файловый объект или URL |
| нет | `send_message_with_retry()` | обход `attachment.not.ready` |
| нет | клиентский rate limiter | лимит MAX: 2 сообщения/сек на чат |

## Ограничения MAX API

- Текст сообщения — до **4000** символов.
- До **2 сообщений в секунду** на один чат (maxgram выдерживает это автоматически).
- Авторизация только заголовком `Authorization` — токен в query-параметрах больше не поддерживается.
- `GET /chats` объявлен устаревшим: надёжнее вести свой список чатов по событиям `bot_added` / `bot_removed`.
- Ссылки на медиа между платформами не переносятся — файл нужно скачать и загрузить заново.

## Тесты и разработка

```bash
pip install -e ".[dev]"
pytest -q          # тесты
ruff check .       # линтер
mypy maxgram       # типы
```

Тесты не ходят в сеть: `tests/conftest.py` подменяет транспорт классом `FakeSession`, который записывает исходящие вызовы и отдаёт заготовленные ответы. Тот же приём удобен и для тестов вашего бота:

```python
from maxgram import Bot
from tests.conftest import FakeSession

session = FakeSession()
bot = Bot("test-token", session=session)
await dp.feed_raw_update(bot, {"update_type": "message_created", ...})
assert session.calls[-1][1] == "/messages"
```

## Лицензия

MIT. Проект не аффилирован с MAX / VK — это независимая реализация клиента к публичному Bot API.

Официальная документация API: <https://dev.max.ru/docs-api>
