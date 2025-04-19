from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from llm_interface import DeepSeekLLM
from llm_interface import LocalLLM
import queue
import threading
import asyncio
import json
import GraphCreator as GC

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    allow_methods=["*"]
)

@app.get("/api/visualize_graph")
async def visualize_graph(graph_json: str = Query(...)):
    # Проверяем валидность JSON
    try:
        parsed_data = json.loads(graph_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Неверный формат JSON"
        )
    
    try:
        # Загрузка и проверка данных
        validated_data = GC.load_bpmn_data(parsed_data)
        
        # Генерация графа
        graph = GC.create_bpmn_graph(validated_data, 'procurement_process')
        
        # Сохранение и рендеринг
        graph.render(outfile='procurement_process.png', cleanup=True, format='png')
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Ошибка генерации графа: {str(e)}"
        )
    
    # Возвращаем изображение
    return FileResponse(
        "procurement_process.png",
        media_type="image/png",
        filename="visualization.png"
    )

@app.get("/api/formalize_process")
async def formalize_process(descr: str, api_key: str):
    output_queue = queue.Queue()
    llm = DeepSeekLLM(api_key=api_key, model="v3")

    node_types = "StartEvent, EndEvent, IntermediateCatchEvent, IntermediateThrowEvent, BoundaryEvent, UserTask, ServiceTask, SendTask, ReceiveTask, ManualTask, BusinessRuleTask, ScriptTask, ExclusiveGateway, ParallelGateway, InclusiveGateway, EventBasedGateway, SubProcess, CallActivity, TextAnnotation"

    example = """{
  "nodes": [
    {
      "id": "startEvent",
      "type": "StartEvent",
      "label": "Начало оформления заказа"
    },
    {
      "id": "placeOrder",
      "type": "UserTask",
      "label": "Оформление заказа клиентом"
    },
    {
      "id": "checkStock",
      "type": "ExclusiveGateway",
      "label": "Проверка наличия товара"
    },
    {
      "id": "notifyClient",
      "type": "SendTask",
      "label": "Уведомить о отсутствии товара"
    },
    {
      "id": "processPayment",
      "type": "ServiceTask",
      "label": "Обработка оплаты"
    },
    {
      "id": "splitTasks",
      "type": "ParallelGateway",
      "label": "Параллельные задачи"
    },
    {
      "id": "packGoods",
      "type": "ServiceTask",
      "label": "Упаковка товара"
    },
    {
      "id": "arrangeDelivery",
      "type": "ServiceTask",
      "label": "Организация доставки"
    },
    {
      "id": "checkFraud",
      "type": "InclusiveGateway",
      "label": "Проверка на мошенничество"
    },
    {
      "id": "fraudReview",
      "type": "BusinessRuleTask",
      "label": "Ручная проверка заказа"
    },
    {
      "id": "waitConfirmation",
      "type": "EventBasedGateway",
      "label": "Ожидание подтверждения"
    },
    {
      "id": "deliveryConfirmed",
      "type": "ReceiveTask",
      "label": "Подтверждение доставки"
    },
    {
      "id": "timeoutEvent",
      "type": "IntermediateCatchEvent",
      "label": "Таймаут ожидания"
    },
    {
      "id": "endSuccess",
      "type": "EndEvent",
      "label": "Заказ завершён"
    },
    {
      "id": "endReject",
      "type": "EndEvent",
      "label": "Заказ отменён"
    }
  ],
  "edges": [
    {
      "source": "startEvent",
      "target": "placeOrder"
    },
    {
      "source": "placeOrder",
      "target": "checkStock"
    },
    {
      "source": "checkStock",
      "target": "notifyClient",
      "label": "Товара нет в наличии"
    },
    {
      "source": "checkStock",
      "target": "processPayment",
      "label": "Товар доступен"
    },
    {
      "source": "processPayment",
      "target": "splitTasks"
    },
    {
      "source": "splitTasks",
      "target": "packGoods"
    },
    {
      "source": "splitTasks",
      "target": "arrangeDelivery"
    },
    {
      "source": "packGoods",
      "target": "checkFraud"
    },
    {
      "source": "arrangeDelivery",
      "target": "checkFraud"
    },
    {
      "source": "checkFraud",
      "target": "fraudReview",
      "label": "Сумма > 100 000 ₽"
    },
    {
      "source": "checkFraud",
      "target": "waitConfirmation",
      "label": "Без проверки"
    },
    {
      "source": "fraudReview",
      "target": "waitConfirmation"
    },
    {
      "source": "waitConfirmation",
      "target": "deliveryConfirmed"
    },
    {
      "source": "waitConfirmation",
      "target": "timeoutEvent"
    },
    {
      "source": "deliveryConfirmed",
      "target": "endSuccess"
    },
    {
      "source": "timeoutEvent",
      "target": "endReject"
    }
  ]
}"""

    prompt = f'Изучи текстовое описание процесса. Формально опиши его алгоритм в виде графа с типами узлов, используемых в BPMN 2.0.\nОтвет дай в формате JSON. Используй только типы узлов с соответствующим наименованием: {node_types}\nПример корректного ответа: {example}\nОписание процесса: {descr}'

    # Запуск генерации в отдельном потоке
    thread = threading.Thread(
        target=llm.generate,
        args=(prompt, output_queue),
        daemon=True
    )
    thread.start()

    async def stream_generator():
        reasoning_in_progress = False
        while True:
            try:
                item = output_queue.get_nowait()
                
                if item["type"] == "content":
                    if reasoning_in_progress:
                        yield "\n[REASONING_END]\n"
                        reasoning_in_progress = False
                    yield item['data']
                elif item["type"] == "reasoning":
                    if not reasoning_in_progress:
                        yield "[REASONING_START]\n"
                        reasoning_in_progress = True
                    yield item['data']
                elif item["type"] == "error":
                    yield item['data']
                    break
                elif item["type"] == "end":
                    break
                    
                output_queue.task_done()
            except queue.Empty:
                await asyncio.sleep(0.05)
                
            if not thread.is_alive() and output_queue.empty():
                break

    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.get("/api/generate")
async def generate_stream(prompt: str, api_key: str):
    output_queue = queue.Queue()
    llm = DeepSeekLLM(api_key=api_key, model="r1")

    # Запуск генерации в отдельном потоке
    thread = threading.Thread(
        target=llm.generate,
        args=(prompt, output_queue),
        daemon=True
    )
    thread.start()

    async def stream_generator():
        reasoning_in_progress = False
        while True:
            try:
                item = output_queue.get_nowait()
                
                if item["type"] == "content":
                    if reasoning_in_progress:
                        yield "\n[REASONING_END]\n"
                        reasoning_in_progress = False
                    yield item['data']
                elif item["type"] == "reasoning":
                    if not reasoning_in_progress:
                        yield "[REASONING_START]\n"
                        reasoning_in_progress = True
                    yield item['data']
                elif item["type"] == "error":
                    yield item['data']
                    break
                elif item["type"] == "end":
                    break
                    
                output_queue.task_done()
            except queue.Empty:
                await asyncio.sleep(0.05)
                
            if not thread.is_alive() and output_queue.empty():
                break

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
