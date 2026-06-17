import os
import json
import asyncio

from dotenv import load_dotenv
from fastapi import FastAPI
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.cosmos import CosmosClient
from groq import Groq

# =========================
# LOAD ENV FILE
# =========================
load_dotenv("key.env")

app = FastAPI(title="Pipeline API with Groq")

# =========================
# ENV VARIABLES
# =========================
SB_CONN_STR = os.getenv("SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = os.getenv("QUEUE_NAME", "input-queue")

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
COSMOS_DATABASE = os.getenv("COSMOS_DATABASE", "PipelineDB")
COSMOS_CONTAINER = os.getenv("COSMOS_CONTAINER", "Items")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =========================
# VALIDATION
# =========================
required_vars = {
    "SERVICE_BUS_CONNECTION_STRING": SB_CONN_STR,
    "COSMOS_URI": COSMOS_URI,
    "COSMOS_KEY": COSMOS_KEY,
    "GROQ_API_KEY": GROQ_API_KEY,
}

for name, value in required_vars.items():
    if not value:
        raise ValueError(f"{name} is missing in key.env")

# =========================
# COSMOS CLIENT
# =========================
container = None

try:
    cosmos_client = CosmosClient(
        COSMOS_URI,
        credential=COSMOS_KEY
    )

    database = cosmos_client.get_database_client(COSMOS_DATABASE)
    container = database.get_container_client(COSMOS_CONTAINER)

    print("✅ Cosmos DB Connected")

except Exception as e:
    print("❌ Cosmos DB Error:", e)

# =========================
# GROQ CLIENT
# =========================
groq_client = Groq(api_key=GROQ_API_KEY)

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def health():
    return {"status": "running"}

# =========================
# INGEST API
# =========================
@app.post("/ingest")
async def ingest_data(payload: dict):

    async with ServiceBusClient.from_connection_string(
        conn_str=SB_CONN_STR
    ) as client:

        sender = client.get_queue_sender(queue_name=QUEUE_NAME)

        async with sender:
            message = ServiceBusMessage(json.dumps(payload))
            await sender.send_messages(message)

    return {"status": "queued"}

# =========================
# EXTEND API
# =========================
@app.get("/extend/{item_id}")
async def extend_with_groq(item_id: str):

    if container is None:
        return {"error": "Cosmos not connected"}

    item = container.read_item(
        item=item_id,
        partition_key=item_id
    )

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": f"Summarize:\n{item}"
            }
        ],
        temperature=0.2,
        max_tokens=512
    )

    return {
        "item": item,
        "analysis": response.choices[0].message.content
    }

# =========================
# BACKGROUND PROCESSOR
# =========================
async def queue_processor():

    while True:
        try:
            if container is None:
                await asyncio.sleep(5)
                continue

            async with ServiceBusClient.from_connection_string(
                conn_str=SB_CONN_STR
            ) as client:

                receiver = client.get_queue_receiver(queue_name=QUEUE_NAME)

                async with receiver:
                    msgs = await receiver.receive_messages(
                        max_message_count=1,
                        max_wait_time=5
                    )

                    for msg in msgs:
                        container.upsert_item({
                            "id": str(msg.sequence_number),
                            "content": str(msg)
                        })

                        await receiver.complete_message(msg)

        except Exception as e:
            print("Queue Error:", e)

        await asyncio.sleep(2)

# =========================
# STARTUP
# =========================
@app.on_event("startup")
async def startup():
    asyncio.create_task(queue_processor())
    print("Started")