# main.py

from fastapi import FastAPI, WebSocket, Depends, HTTPException
from rq import Queue, Worker, Connection
from redis import Redis
import asyncio
import multiprocessing
from job import task
import uuid
import uvicorn
import websockets

app = FastAPI()

# Connect to Redis
redis_conn = Redis(host='localhost', port=6379, db=0)

# Create an RQ queue
queue = Queue(connection=redis_conn)

# Worker configuration
worker = Worker([queue], connection=redis_conn)

# Function to run the worker process
def run_worker():
    worker.work()

@app.on_event("startup")
async def startup_event():
    # Create and start two worker processes
    worker_process = multiprocessing.Process(target=run_worker)
    worker_process.daemon = True
    worker_process.start()

@app.post("/job")
async def enqueue_job():
    task_id = str(uuid.uuid4())
    # Create a custom job instance
    upscale_job = queue.enqueue(task, task_id, job_id=task_id, result_ttl=-1)

    return {"job_id": task_id}

# WebSocket endpoint for streaming terminal output
@app.websocket("/monitor/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()

    # Retrieve the RQ job associated with the given task_id
    job = queue.fetch_job(task_id)

    if job is None:
        await websocket.send_text("Job does not exist.")
        await websocket.close()
        return

    try:
        while not job.is_finished and not job.is_failed:
            progress = job.get_meta().get("progress") #job.get_meta() is a dict
            if progress:
                await websocket.send_text(progress)
            else:
                await websocket.send_text(job.get_status())
            await asyncio.sleep(1)

        # Send the final status after the job has finished
        await websocket.send_text(job.get_status())
    except websockets.exceptions.ConnectionClosedOK:
        print("Connection closed by client...")
    finally:
        await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

