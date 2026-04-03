# Тестовые данные для хакатона «Голос из архива»

## Структура

```
test_data/
├── README.md
├── seed.json                  # 20 карточек репрессированных (JSON)
├── seed.sql                   # SQL-скрипт для заполнения БД
├── documents/                 # Документы для RAG-модуля (.txt)
│   ├── delo_baytemirova.txt
│   ├── delo_sydykova.txt
│   ├── delo_toktogulova.txt
│   ├── delo_kasymova.txt
│   ├── delo_ibraimova.txt
│   ├── spisok_oshskaya_1938.txt
│   ├── spravka_reabilitatsiya_1958.txt
│   └── pismo_komissiya_1956.txt
└── queries.md                 # Примеры вопросов для тестирования RAG
```

## Как использовать

### 1. Заполнение базы данных
```bash
# SQLite
sqlite3 archive.db < seed.sql

# PostgreSQL
psql -d archive -f seed.sql
```

### 2. Загрузка через API
```bash
# Импорт карточек
curl -X POST http://localhost:8080/api/persons/import \
  -H "Content-Type: application/json" \
  -d @seed.json

# Загрузка документов для RAG
for file in documents/*.txt; do
  curl -X POST http://localhost:8080/api/documents/upload \
    -F "file=@$file"
done
```

### 3. Тестирование RAG
Используйте вопросы из `queries.md` для проверки качества ответов.

## Данные

- **20 карточек** репрессированных из разных регионов Кыргызстана
- **8 документов** для RAG: архивные дела, списки, справки, письма
- **15 тестовых вопросов** с ожидаемыми ответами для проверки

Все данные вымышлены, но основаны на реальных исторических паттернах репрессий 1918–1953 годов в Кыргызстане.
