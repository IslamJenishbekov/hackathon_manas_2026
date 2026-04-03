# План реализации `save_doc` и `chat`

## 1. Цель документа

Этот документ фиксирует лучший практический план для следующих AI-функций проекта:

- `POST /ai/save_doc`
- `POST /ai/chat`

План построен не только от API-контракта, но и от:

- основного ТЗ: [`docs/final_tz.docx`](./final_tz.docx)
- AI-контракта: [`docs/ai_endpoints.txt`](./ai_endpoints.txt)
- тестовых данных: [`docs/test-seed/README.md`](./test-seed/README.md)
- тестовых вопросов: [`docs/test-seed/queries.md`](./test-seed/queries.md)

Главная задача: сделать такой индекс и такой пайплайн поиска, чтобы система хорошо отвечала и на вопросы про конкретного человека, и на общие архивные вопросы, и на сравнительные вопросы.


## 2. Главный вывод

Для этого проекта нельзя строить поиск по схеме:

`всегда сначала найти человека -> потом искать ответ`

Причина в том, что тестовые вопросы делятся на несколько классов:

- вопросы про одного человека
- вопросы про несколько людей
- общие статистические вопросы
- сравнительные вопросы
- вопросы, где нужно использовать и документы, и структурные карточки людей

Поэтому правильный первый шаг в `chat` — не person resolution сам по себе, а:

`query routing -> выбрать режим поиска -> потом делать person resolution только там, где он действительно нужен`


## 3. Что видно по тестовым данным

### 3.1. Вопросы про конкретного человека

Примеры:

- "За что арестовали Байтемирова?"
- "Кто такая Сыдыкова Бурул?"
- "Что случилось с семьёй Ибраимова?"
- "Когда был реабилитирован Байтемиров?"

Лучший путь:

- определить персону;
- найти её карточку;
- найти связанные документы;
- делать retrieval только внутри этого скоупа.


### 3.2. Общие и статистические вопросы

Примеры:

- "Сколько человек было арестовано в Ошской области в 1938 году?"
- "Какие категории людей чаще всего арестовывали?"
- "Какие нарушения были при расследовании дел?"

Лучший путь:

- не искать одного человека;
- сразу искать по сводным документам и отчетам.

Ключевые источники:

- [`docs/test-seed/test_data/test_data/documents/spisok_oshskaya_1938.txt`](./test-seed/test_data/test_data/documents/spisok_oshskaya_1938.txt)
- [`docs/test-seed/test_data/test_data/documents/pismo_komissiya_1956.txt`](./test-seed/test_data/test_data/documents/pismo_komissiya_1956.txt)


### 3.3. Сравнительные и multi-source вопросы

Примеры:

- "Как жёны узнавали о судьбе своих мужей?"
- "Чем отличается дело Токтогулова от других?"
- "Почему некоторых реабилитировали только в 1989 году?"

Лучший путь:

- находить несколько источников;
- в ряде случаев находить несколько персон;
- затем делать synthesis только на их основе.


### 3.4. Вопросы, где одних документов недостаточно

Примеры:

- "За что преследовали манасчи Алымкулова?"
- "Почему некоторых реабилитировали только в 1989 году?"

Здесь тестовые документы не всегда содержат полный материал.
Например:

- Алымкулов кратко упоминается в письме комиссии;
- Эшматов есть в seed-данных, но не в явном наборе загруженных `.txt` документов.

Значит, для качественного ответа нужна не только document-RAG часть, но и структурный архив карточек людей.


## 4. Архитектурный принцип

Лучший дизайн для проекта:

`structured archive + document index + query router + scoped retrieval`

То есть система должна опираться одновременно на:

1. карточки людей
2. документы
3. чанки и embeddings
4. metadata и entity map
5. роутинг вопроса перед поиском


## 5. Какие слои данных нужны

### 5.1. Structured archive layer

Это локально доступная структурная информация о людях.

Минимальные поля:

- `person_id`
- `full_name`
- `normalized_name`
- `birth_year`
- `death_year`
- `region`
- `district`
- `charge`
- `biography`
- `status`
- `source`

Источником этого слоя должен быть основной backend или seed-импорт.

Зачем он нужен:

- person resolution
- ответы, где документов мало
- гибридный ответ "карточка + цитаты из документов"
- поиск по имени и году рождения


### 5.2. Document layer

Это сохранённые документы архива.

Минимальные поля:

- `document_id`
- `person_id`
- `filename`
- `raw_text`
- `doc_type`
- `primary_full_name`
- `primary_normalized_name`
- `primary_birth_year`
- `primary_region`
- `primary_charge`
- `created_at`
- `updated_at`

Назначение:

- хранение исходного документа
- привязка документа к архивной сущности
- быстрые metadata-фильтры до векторного поиска


### 5.3. Entity map layer

Это связи между документом и людьми, которые в нём фигурируют.

Минимальные поля:

- `document_id`
- `normalized_name`
- `raw_name`
- `birth_year`
- `role`

`role`:

- `primary`
- `mentioned`

Этот слой критичен для:

- `plural` документов
- групповых дел
- person-first поиска через многосубъектные документы


### 5.4. Chunk layer

Минимальные поля:

- `chunk_id`
- `document_id`
- `chunk_index`
- `chunk_text`
- `char_start`
- `char_end`
- `embedding_json`

Назначение:

- retrieval
- показ источников
- топ-k поиск по документному корпусу


## 6. Предлагаемая схема хранения

Для MVP лучше использовать `SQLite`.

### Таблица `persons_shadow`

Локальная теневая копия минимальных данных о людях.

Поля:

- `person_id INTEGER PRIMARY KEY`
- `full_name TEXT NOT NULL`
- `normalized_name TEXT NOT NULL`
- `birth_year INTEGER`
- `death_year INTEGER`
- `region TEXT`
- `district TEXT`
- `charge TEXT`
- `biography TEXT`
- `status TEXT`
- `source TEXT`
- `updated_at TEXT NOT NULL`


### Таблица `documents`

Поля:

- `document_id INTEGER PRIMARY KEY`
- `person_id INTEGER NOT NULL`
- `filename TEXT NOT NULL`
- `raw_text TEXT NOT NULL`
- `doc_type TEXT NOT NULL`
- `primary_full_name TEXT`
- `primary_normalized_name TEXT`
- `primary_birth_year INTEGER`
- `primary_region TEXT`
- `primary_charge TEXT`
- `embedding_model TEXT NOT NULL`
- `chunk_count INTEGER NOT NULL`
- `updated_at TEXT NOT NULL`


### Таблица `document_entities`

Поля:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `document_id INTEGER NOT NULL`
- `normalized_name TEXT NOT NULL`
- `raw_name TEXT`
- `birth_year INTEGER`
- `role TEXT NOT NULL`

Индексы:

- по `document_id`
- по `normalized_name`
- по `normalized_name, birth_year`


### Таблица `chunks`

Поля:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `document_id INTEGER NOT NULL`
- `chunk_index INTEGER NOT NULL`
- `chunk_text TEXT NOT NULL`
- `char_start INTEGER NOT NULL`
- `char_end INTEGER NOT NULL`
- `embedding_json TEXT NOT NULL`

Индексы:

- по `document_id`
- по `document_id, chunk_index`


## 7. Лучший дизайн `POST /ai/save_doc`

### 7.1. Задача эндпойнта

`save_doc` должен не просто "сохранить текст и embeddings", а подготовить документ к умному поиску.

Значит он должен:

1. сохранить документ;
2. определить тип документа;
3. извлечь metadata;
4. выделить людей, фигурирующих в документе;
5. нарезать документ на чанки;
6. посчитать embeddings;
7. записать всё в локальный индекс.


### 7.2. Пайплайн `save_doc`

Шаги:

1. Провалидировать request.
2. Очистить и нормализовать `text`.
3. Внутренне вызвать `get_info`-логику:
   - classification `single/plural`
   - metadata extraction
4. Построить metadata документа.
5. Построить entity map.
6. Нарезать текст на чанки.
7. Посчитать embeddings для чанков.
8. Переиндексировать документ по `document_id`.
9. Вернуть `{"status":"ok"}`.


### 7.3. Что сохранять для `single`

- `doc_type = single`
- `primary_full_name`
- `primary_normalized_name`
- `primary_birth_year`
- `primary_region`
- `primary_charge`
- одна строка в `document_entities` с `role = primary`

Если в документе явно фигурируют вторичные имена и позже появится потребность, можно добавлять и `mentioned`, но для MVP это не обязательно.


### 7.4. Что сохранять для `plural`

- `doc_type = plural`
- в `documents` основной человек не заполняется
- в `document_entities` добавляются все найденные `normalized_name`
- если удалось извлечь `birth_year` по именам, он тоже должен сохраняться

Это особенно важно для:

- [`spisok_oshskaya_1938.txt`](./test-seed/test_data/test_data/documents/spisok_oshskaya_1938.txt)
- [`delo_toktogulova.txt`](./test-seed/test_data/test_data/documents/delo_toktogulova.txt)
- [`pismo_komissiya_1956.txt`](./test-seed/test_data/test_data/documents/pismo_komissiya_1956.txt)


### 7.5. Переиндексация

Лучший вариант для MVP:

- если `document_id` уже существует, делать полную переиндексацию

То есть:

1. удалить старые строки из `chunks`
2. удалить старые строки из `document_entities`
3. обновить `documents`
4. записать новые данные

Это соответствует рекомендации из [`docs/ai_endpoints.txt`](./ai_endpoints.txt).


## 8. Chunking strategy

ТЗ рекомендует чанки по `500–1000` символов.

Для MVP лучше зафиксировать:

- размер чанка: `~800` символов
- overlap: `~120`

Почему так:

- достаточно контекста для фактов и коротких сюжетных фрагментов;
- не слишком длинно для top-k retrieval;
- overlap снижает риск разрыва важной информации.

Нарезка должна стараться резать:

- по пустым строкам
- по границам абзацев
- по строкам списка или таблицы

Если документ табличный, как `spisok_oshskaya_1938.txt`, не стоит резать его хаотично посередине строки списка.


## 9. Лучший дизайн `POST /ai/chat`

### 9.1. Главный принцип

Первый шаг `chat` — это не embeddings, а `query routing`.


### 9.2. Query routing

Сервис должен определять режим вопроса:

- `person`
- `global`
- `comparative`
- `ambiguous`


### 9.3. Режим `person`

Примеры:

- "За что арестовали Байтемирова?"
- "Кто такая Сыдыкова Бурул?"
- "Когда был реабилитирован Байтемиров?"
- "Что случилось с семьёй Ибраимова?"

Пайплайн:

1. Извлечь из `question + history` возможное имя, год, регион.
2. Искать в `persons_shadow`.
3. Если не хватило, искать в `document_entities`.
4. Ранжировать кандидатов.
5. Если confidence высокий:
   - зафиксировать `person_id`
   - собрать документы этой персоны
   - сделать retrieval только по ним
6. Если confidence низкий:
   - попросить уточнение


### 9.4. Режим `global`

Примеры:

- "Сколько человек было арестовано в Ошской области в 1938 году?"
- "Какие категории людей чаще всего арестовывали?"
- "Какие нарушения были при расследовании дел?"

Пайплайн:

1. Не запускать person resolution.
2. Отфильтровать документы по `doc_type`:
   - `plural`
   - отчёты
   - списки
   - письма комиссии
3. Посчитать embedding вопроса.
4. Искать top-k только в этих документах.
5. Вернуть ответ со ссылкой на источники.


### 9.5. Режим `comparative`

Примеры:

- "Чем отличается дело Токтогулова от других?"
- "Почему некоторых реабилитировали только в 1989 году?"
- "Как жёны узнавали о судьбе своих мужей?"

Пайплайн:

1. Выделить 2+ сущности или 2+ кейса.
2. Собрать карточки и документы по ним.
3. При необходимости добавить глобальные документы.
4. Запустить retrieval по объединённому скоупу.
5. Синтезировать ответ на основе нескольких источников.


### 9.6. Режим `ambiguous`

Если вопрос слишком короткий или ссылка в истории неясна:

- не идти в retrieval по всему корпусу;
- сначала просить уточнение;
- либо использовать явно сохранённый активный контекст диалога.

Это особенно важно для вопросов вроде:

- "А потом что было?"
- "Когда это произошло?"
- "Почему его реабилитировали?"


## 10. Person resolution

### 10.1. Откуда брать кандидатов

Приоритет источников:

1. `persons_shadow`
2. `document_entities`
3. текущий контекст истории диалога


### 10.2. Как ранжировать кандидатов

Приоритеты:

1. exact match по `normalized_name + birth_year`
2. exact match по `normalized_name`
3. exact match по `normalized_name + region`
4. fuzzy match по имени
5. boost из истории диалога


### 10.3. Какое поведение считается правильным

- если кандидат один и уверенность высокая: продолжаем
- если кандидатов несколько: просим уточнение
- если кандидатов нет: честно говорим, что человек не найден

Неправильное поведение:

- тихо выбрать случайного человека
- делать глобальный поиск по всему корпусу, если вопрос явно person-centric


## 11. Retrieval после resolution

### 11.1. Для `person`

Документы берутся так:

1. все документы, где человек `primary`
2. затем документы, где он `mentioned`

Потом:

- считаем embedding вопроса
- ищем top-k только по chunk’ам этих документов


### 11.2. Для `global`

Документы берутся по metadata-фильтрам:

- `doc_type = plural`
- список
- сводка
- письмо комиссии


### 11.3. Для `comparative`

Берётся объединение:

- person-scoped документы
- global документы
- при необходимости структурные карточки


## 12. Как будут покрываться тестовые вопросы

### Вопросы 1, 2, 3, 4, 13, 15

Режим:

- `person`

Источник:

- person card + person-scoped documents


### Вопросы 5, 7, 9, 14

Режим:

- `global`

Источник:

- `spisok_oshskaya_1938.txt`
- `pismo_komissiya_1956.txt`


### Вопрос 6

Режим:

- `person`

Источник:

- person card для Алымкулова
- упоминание в `pismo_komissiya_1956.txt`


### Вопрос 10

Режим:

- `comparative`

Источник:

- `delo_baytemirova.txt`
- `spravka_reabilitatsiya_1958.txt`


### Вопрос 11

Режим:

- `comparative`

Источник:

- `delo_toktogulova.txt`
- `pismo_komissiya_1956.txt`


### Вопрос 12

Режим:

- `comparative`

Источник:

- person cards для Маматов / Эшматов
- если есть, дополнительные документы


## 13. Порядок реализации

### Этап 1. Индексирование

Сделать:

- SQLite storage
- `documents`
- `document_entities`
- `chunks`
- `save_doc`
- chunking
- embeddings

Это база всего остального.


### Этап 2. Structured archive shadow

Сделать:

- локальный импорт карточек людей
- таблицу `persons_shadow`

Без этого часть тестовых вопросов будет покрываться хуже.


### Этап 3. Query router

Сделать:

- определение режима вопроса:
  - `person`
  - `global`
  - `comparative`
  - `ambiguous`


### Этап 4. Person resolution

Сделать:

- поиск кандидатов
- ранжирование
- confidence
- поведение при неоднозначности


### Этап 5. `chat`

Сделать:

- retrieval по scoped corpus
- сбор `sources`
- генерацию ответа строго по найденным данным


## 14. Основные риски

### 14.1. Попытка сделать всегда person-first

Риск:

- сломаются глобальные и статистические вопросы


### 14.2. Попытка делать всегда global search

Риск:

- начнут смешиваться документы разных людей
- ответы станут менее точными


### 14.3. Отсутствие структурного архива людей

Риск:

- часть person-вопросов будет покрыта плохо
- вопросы про Алымкулова и Эшматова будут слабее


### 14.4. Плохая entity map для `plural`

Риск:

- person resolution не сможет использовать групповые документы и списки


## 15. Лучший итоговый дизайн в одной строке

Лучший план для этого проекта:

`save_doc -> extract metadata + entities -> chunk + embed -> store locally -> chat router -> person/global/comparative mode -> scoped retrieval -> answer with sources`


## 16. Что предлагается утвердить

1. `save_doc` делает не только embeddings, но и metadata/entity extraction.
2. Для хранения используется `SQLite`.
3. Индекс состоит минимум из `persons_shadow`, `documents`, `document_entities`, `chunks`.
4. `chat` начинается с query routing, а не с vector search.
5. Person resolution делается только в режимах `person` и части `comparative`.
6. Global-вопросы ищутся по сводным документам без forced person resolution.
7. Ответы всегда должны опираться на ограниченный и объяснимый набор источников.

