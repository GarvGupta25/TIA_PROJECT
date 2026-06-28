import os
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import websockets
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SMALLEST_API_KEY = os.getenv("SMALLEST_API_KEY")
SMALLEST_WS_URL = "wss://api.smallest.ai/waves/v1/stt/live?model=pulse&encoding=linear16&sample_rate=16000"

@app.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if not SMALLEST_API_KEY or SMALLEST_API_KEY == "your_api_key_here":
        await websocket.send_text(json.dumps({"error": "SMALLEST_API_KEY is not set or is invalid"}))
        await websocket.close()
        return

    headers = {"Authorization": f"Bearer {SMALLEST_API_KEY}"}
    
    try:
        async with websockets.connect(SMALLEST_WS_URL, extra_headers=headers) as smallest_ws:
            async def forward_to_smallest():
                try:
                    while True:
                        data = await websocket.receive()
                        if "bytes" in data:
                            await smallest_ws.send(data["bytes"])
                        elif "text" in data:
                            await smallest_ws.send(data["text"])
                except WebSocketDisconnect:
                    try:
                        await smallest_ws.send(json.dumps({"type": "close_stream"}))
                    except:
                        pass
                except Exception as e:
                    print(f"Error forwarding to smallest: {e}")

            async def receive_from_smallest():
                try:
                    while True:
                        response = await smallest_ws.recv()
                        if isinstance(response, str):
                            await websocket.send_text(response)
                        else:
                            await websocket.send_bytes(response)
                except websockets.exceptions.ConnectionClosed:
                    print("Smallest connection closed")
                except Exception as e:
                    print(f"Error receiving from smallest: {e}")

            await asyncio.gather(
                forward_to_smallest(),
                receive_from_smallest()
            )
    except Exception as e:
        print(f"WebSocket connection error: {e}")
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8500)
