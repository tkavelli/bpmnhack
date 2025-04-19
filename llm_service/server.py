import os, json, logging
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from llama_cpp import Llama
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("llm_server")

# Загружаем .env
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY", "")

# Читаем реестр моделей
try:
    with open("models.json") as f:
        json_content = f.read()
        # Удаляем комментарии JavaScript, если они есть
        lines = [line for line in json_content.split('\n') if not line.strip().startswith('//')]
        clean_json = '\n'.join(lines)
        MODEL_CONFIG = json.loads(clean_json)
    logger.info(f"Загружено {len(MODEL_CONFIG)} моделей из models.json")
except Exception as e:
    logger.error(f"Ошибка загрузки models.json: {str(e)}")
    MODEL_CONFIG = {
        "current": "models/DeepSeek-R1-Distill-Qwen-14B-Q4_K_L.gguf"
    }

# Кэш инстансов
llama_instances = {}

app = FastAPI()

# Настройка загрузчика шаблонов с учетом stable/experimental
template_path = os.getenv("PROMPT_TEMPLATE_PATH", "stable")
prompts_base_dir = "prompts"
templates_dir = os.path.join(prompts_base_dir, template_path)

# Создаем директории, если не существуют
os.makedirs(os.path.join(prompts_base_dir, "stable"), exist_ok=True)
os.makedirs(os.path.join(prompts_base_dir, "experimental"), exist_ok=True)

# Проверяем существование директории и используем её или базовую
if not os.path.exists(templates_dir):
    logger.warning(f"Директория шаблонов {templates_dir} не найдена. Используем базовую директорию prompts/")
    templates_dir = prompts_base_dir

env = Environment(loader=FileSystemLoader(templates_dir))
logger.info(f"Загрузчик шаблонов настроен на директорию: {templates_dir}")

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    max_tokens: int = int(os.getenv("MAX_TOKENS", "2048"))
    n_ctx: int = 4096
    n_gpu_layers: int = -1  # -1 загружает все слои в GPU
    temperature: float = float(os.getenv("TEMPERATURE", "0.8"))
    stream: bool = True

def get_llama(name: str) -> Llama:
    if name not in MODEL_CONFIG:
        raise HTTPException(404, "Model not found")
    if name not in llama_instances:
        path = MODEL_CONFIG[name]
        # создаём Llama‑инстанс с GPU‑опциями
        logger.info(f"Загрузка модели: {name} из {path}")
        llama_instances[name] = Llama(
            model_path=path,
            n_ctx=ChatRequest.model_fields['n_ctx'].default,
            n_gpu_layers=ChatRequest.model_fields['n_gpu_layers'].default
        )
    return llama_instances[name]

@app.get("/")
async def root():
    """Информация о сервере"""
    return {
        "name": "LLM Inference Server",
        "status": "running",
        "models": list(MODEL_CONFIG.keys()),
        "prompt_path": template_path
    }

@app.get("/v1/models")
async def list_models(authorization: str = Header(None)):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Unauthorized")
    return {"models": list(MODEL_CONFIG.keys())}

@app.post("/v1/models/{name}/reload")
async def reload_model(name: str, authorization: str = Header(None)):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Unauthorized")
    
    if name not in MODEL_CONFIG:
        raise HTTPException(404, f"Модель '{name}' не найдена")
        
    # Удаляем из кэша для перезагрузки
    llama_instances.pop(name, None)
    logger.info(f"Модель {name} удалена из кэша и будет перезагружена")
    
    return {"status": "reloaded", "model": name}

@app.get("/v1/prompt/{name}")
async def get_prompt(name: str, authorization: str = Header(None), **kwargs):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Unauthorized")
    try:
        tpl = env.get_template(f"{name}.tpl")
        logger.info(f"Загружен шаблон {name}.tpl из {templates_dir}")
        return {"prompt": tpl.render(**kwargs)}
    except Exception as e:
        logger.error(f"Ошибка загрузки шаблона {name}.tpl: {str(e)}")
        raise HTTPException(404, "Prompt not found")

@app.post("/v1/config/prompt-path")
async def set_prompt_path(request: Request, authorization: str = Header(None)):
    """Изменяет путь к промптам (stable/experimental)"""
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Unauthorized")
    
    try:
        data = await request.json()
        path = data.get("path")
        
        if path not in ["stable", "experimental"]:
            raise HTTPException(400, "Path должен быть 'stable' или 'experimental'")
        
        # Изменяем глобальные переменные
        global env, templates_dir, template_path
        template_path = path
        templates_dir = os.path.join(prompts_base_dir, path)
        
        # Перезагружаем окружение Jinja2
        env = Environment(loader=FileSystemLoader(templates_dir))
        
        logger.info(f"Путь к промптам изменен на: {templates_dir}")
        
        return {"status": "success", "path": path}
    except Exception as e:
        logger.error(f"Ошибка при изменении пути промптов: {str(e)}")
        raise HTTPException(500, str(e))

@app.post("/v1/chat/completions")
async def chat(
    req: ChatRequest,
    authorization: str = Header(None)
):
    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Unauthorized")

    # Загружаем модель
    llama = get_llama(req.model)
    
    # Обновляем параметры инференса
    llama.n_ctx = req.n_ctx
    
    # Формируем промпт из сообщений
    prompt_template = os.getenv("PROMPT_TEMPLATE", "bpmn")
    try:
        # Пытаемся использовать шаблон для системного сообщения
        if prompt_template:
            tpl = env.get_template(f"{prompt_template}.tpl")
            system_content = tpl.render()
            # Заменяем системное сообщение
            for msg in req.messages:
                if msg.role == os.getenv("LLM_SYSTEM_ROLE", "system"):
                    msg.content = system_content
                    break
            logger.info(f"Применен шаблон промпта: {prompt_template}.tpl")
    except Exception as e:
        logger.warning(f"Не удалось применить шаблон {prompt_template}: {str(e)}")

    # Генерируем промпт
    prompt = "\n".join(f"{m.role}: {m.content}" for m in req.messages)
    logger.info(f"Запрос инференса: модель={req.model}, max_tokens={req.max_tokens}")

    # Генерируем ответ
    async def generator():
        try:
            for chunk in llama(
                prompt,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                stream=req.stream
            )["choices"]:
                content = chunk["text"]
                # Формат ответа как у OpenAI
                yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
            
            # Сигнал завершения
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Ошибка инференса: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    # Возвращаем стрим
    from fastapi.responses import StreamingResponse
    return StreamingResponse(generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    logger.info("Запуск LLM Inference Server")
    uvicorn.run("server:app", host="0.0.0.0", port=8080, workers=1)