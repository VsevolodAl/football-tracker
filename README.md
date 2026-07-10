# ⚽ Футбольный трекер 2026/27

Трекер матчей и таблиц **Арсенала**, **Спартака** и **Факела**.  
Данные обновляются автоматически каждый день в 09:00 по Москве через GitHub Actions.

---

## Быстрый старт

### 1. Создайте репозиторий на GitHub

- Зайдите на [github.com](https://github.com) → **New repository**
- Название: `football-tracker` (или любое другое)
- Тип: **Public** (обязательно для GitHub Pages)
- Загрузите все файлы из этой папки

### 2. Получите API-ключи (бесплатно)

**football-data.org** (для Арсенала / АПЛ):
1. Зарегистрируйтесь на [football-data.org](https://www.football-data.org/client/register)
2. Скопируйте API Token из личного кабинета

**api-football.com через RapidAPI** (для Спартака и Факела / РПЛ):
1. Зарегистрируйтесь на [rapidapi.com](https://rapidapi.com)
2. Подпишитесь на [API-Football](https://rapidapi.com/api-sports/api/api-football) (есть бесплатный план — 100 запросов/день)
3. Скопируйте `X-RapidAPI-Key`

### 3. Добавьте ключи в GitHub Secrets

В вашем репозитории: **Settings → Secrets and variables → Actions → New repository secret**

| Имя секрета        | Значение                    |
|--------------------|-----------------------------|
| `FOOTBALLDATA_KEY` | Ваш ключ с football-data.org |
| `RAPIDAPI_KEY`     | Ваш ключ с RapidAPI          |

### 4. Включите GitHub Pages

**Settings → Pages → Source: Deploy from a branch → Branch: main / (root)**

Через ~1 минуту сайт будет доступен по адресу:  
`https://ВАШ_ЛОГИН.github.io/football-tracker/`

### 5. Запустите первое обновление

**Actions → "Обновление данных" → Run workflow**

---

## Структура файлов

```
index.html          # Сам сайт (читает data/clubs.json)
fetch_data.py       # Скрипт загрузки данных с API
data/
└── clubs.json      # Данные (обновляются автоматически)
.github/
└── workflows/
    └── update.yml  # Расписание автообновления
```

## Расписание обновлений

Скрипт запускается **каждый день в 06:00 UTC (09:00 МСК)**.  
Если данные изменились — делает коммит в репозиторий.  
Если данных нет (API не ответил) — ничего не меняет, старые данные остаются.

Запустить вручную: **Actions → "Обновление данных" → Run workflow**

---

## API и лимиты (бесплатные планы)

| API | Лимит | Что покрывает |
|-----|-------|---------------|
| football-data.org | 10 запросов/мин | АПЛ: матчи + таблица |
| api-football (RapidAPI) | 100 запросов/день | РПЛ: матчи + таблица |

Скрипт делает ~5 запросов за запуск — уложится в любой бесплатный лимит.
