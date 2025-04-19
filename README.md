# Архитектура системы с локальным LLM-инференсом для BPMN

## Текущая структура проекта

📦 1. Контейнер LLM‑Inference (мой)
```
llm_service/                         ← контекст сборки
├── Dockerfile               *      ← в ОБРАЗ
├── server.py                *      ← обновлен с поддержкой промптов
├── requirements.txt         *
├── models.json              *
└── docker-compose.yml       *      ← добавлен для управления контейнером

# наружно, НЕ в образ
├── start.sh                        ← скрипт запуска и настройки
├── remote_llm.py                   ← скрипт удаленного управления
├── models/                         ← GGUF‑файлы (‑v ./models:/app/models:ro)
├── .env                            ← ключи / роли (‑v ./.env:/app/.env:ro)
└── prompts/                        ← шаблоны (‑v ./prompts:/app/prompts:ro)
    ├── stable/                     ← стабильные промпты
    │   └── bpmn.tpl                ← основной промпт
    └── experimental/               ← экспериментальные промпты
        └── bpmn.tpl                ← тестовые версии
```

📦 2. Контейнер UI + Back‑end BPMN (товарища, ТЕКУЩЕЕ СОСТОЯНИЕ)
```
sistema-postroeniya-diagramm/
├── backend/
│   ├── Dockerfile           *      ← в ОБРАЗ
│   ├── requirements.txt     *
│   ├── main.py              *      ← содержит хардкод промптов (нужно убрать)
│   ├── GraphCreator.py      *
│   ├── GraphWrapper.py      *
│   └── llm_interface.py     *      ← содержит хардкод DeepSeek (нужно изменить)
├── frontend/
│   ├── Dockerfile           *      ← в ОБРАЗ
│   ├── src/ …               *
│   └── public/ …            *
└── docker-compose.yml       *      ← в ОБРАЗ

# наружно, НЕ в образ
.env                                  ← API_URL и OPENAI_API_KEY (‑v ./.env:/app/.env:ro)
```

📦 2. Контейнер UI + Back‑end BPMN (товарища, ЦЕЛЕВОЕ СОСТОЯНИЕ)
```
sistema-postroeniya-diagramm/
├── backend/
│   ├── Dockerfile           *      ← в ОБРАЗ
│   ├── requirements.txt     *
│   ├── main.py              *      ← использует ConfigurableLLM, промпты из .env
│   ├── GraphCreator.py      *
│   ├── GraphWrapper.py      *
│   └── llm_interface.py     *      ← добавлен ConfigurableLLM для локального LLM
├── frontend/
│   ├── Dockerfile           *      ← в ОБРАЗ
│   ├── src/ …               *
│   └── public/ …            *
└── docker-compose.yml       *      ← в ОБРАЗ

# наружно, НЕ в образ
.env                                  ← API_URL и OPENAI_API_KEY (‑v ./.env:/app/.env:ro)
```

## Что нужно изменить у товарища

### 1. В llm_interface.py
Добавить класс `ConfigurableLLM`, который будет брать все настройки из `.env`:
```python
class ConfigurableLLM:
    def __init__(self,
                 base_url=os.getenv("API_URL", "http://localhost:8080"),
                 api_key=os.getenv("OPENAI_API_KEY", ""),
                 model=os.getenv("LLM_MODEL_ALIAS", "current")):
        self.url = base_url.rstrip("/") + "/v1/chat/completions"
        self.key = api_key
        self.model = model
        # Остальные параметры из .env
```

### 2. В main.py
Заменить хардкод промптов и DeepSeek на ConfigurableLLM:
```python
@app.get("/api/formalize_process")
async def formalize_process(descr: str):
    """Генерируем BPMN-граф из текстового описания"""
    q = queue.Queue()
    llm = ConfigurableLLM()  # Всё берёт из .env

    # Избавляемся от хардкода examples и node_types
    prompt = f"Изучи текстовое описание процесса: {descr}"
    
    # ...остальной код...
```

## Схема взаимодействия

```
flowchart LR
  subgraph LLM_Service["LLM Service Container"]
    direction TB
    LLM_Code["server.py + docker-compose.yml"]  
    LLM_Port["Exposes port 8080"]
    subgraph Volumes["Mounted Volumes (не в образе)"]
      Models[(models/)]
      Prompts[(prompts/)]
      PromptStable["stable/bpmn.tpl"]
      PromptExp["experimental/bpmn.tpl"]
      Env[(.env)]
    end
    RemoteTool["remote_llm.py\nУдаленное управление"]
    
    Models --> LLM_Code
    Prompts --> LLM_Code
    Env --> LLM_Code
    LLM_Code --> LLM_Port
    RemoteTool -.->|"models, switch-prompt"| LLM_Port
  end

  subgraph Backend["Backend BPMN"]
    direction TB
    BE_Code["main.py + GraphCreator.py"]
    LLM_Client["ConfigurableLLM\n(llm_interface.py)"]
    BE_Code --> LLM_Client
  end
  
  subgraph Frontend["Frontend (React/Vite)"]
    direction TB
    UI_Code["React компоненты"]
    UI_Port["Exposes port 5173"]
    UI_Env[(.env with API_URL\nand OPENAI_API_KEY)]
    UI_Env --> UI_Code
    UI_Code --> UI_Port
  end

  LLM_Client -->|"OpenAI API\n/v1/chat/completions"| LLM_Port
  Frontend -->|"API calls"| Backend
  
  Developer["Разработчик\nнаш коллега"] -.->|"Удаленное управление\nремя хакатона"| RemoteTool
```

## Преимущества новой архитектуры

| Компонент | Преимущество |
|-----------|--------------|
| `prompts/stable` и `prompts/experimental` | Возможность безопасно экспериментировать с промптами, быстро переключаться |
| `remote_llm.py` | Удаленное управление LLM-сервером для коллеги, без необходимости доступа к машине |
| Конфигурация из `.env` | Гибкие настройки без необходимости пересборки контейнеров |
| OpenAI API-совместимый интерфейс | Стандартный интерфейс, легко интегрируется с существующими приложениями |

## Текущий статус

- ✅ Разработан LLM-сервер с поддержкой локальных моделей
- ✅ Создана структура промптов (stable/experimental)
- ✅ Подготовлен инструмент удаленного управления
- ❌ Хардкод в main.py и llm_interface.py у товарища пока не убран
- ❌ Интеграция UI-контейнера с LLM-сервером не завершена

## Следующие шаги

1. Убрать хардкод из файлов товарища
2. Заменить DeepSeek на ConfigurableLLM
3. Настроить .env для UI-контейнера с правильным API_URL и OPENAI_API_KEY
4. Протестировать интеграцию
