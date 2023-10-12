# main.py

import uuid
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, Depends, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi.responses import FileResponse
from redis import Redis
from rq import Queue, Worker, Connection
from pydantic import BaseModel, Field, validator
from enum import Enum
from job import task
import asyncio
import multiprocessing
import os
import shutil
import tempfile
import zipfile
import string
import random
import re
import subprocess
import threading
from PIL import Image
import io
import uvicorn
import websockets
from models.models import UpscaleModel, UpscaleData
from utils.utils import generate_random_filename

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT")

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

# Route to upscale images
@app.post("/upscale")
async def post_job(image: UploadFile = File(...), tta: bool = Form(...), model_name: UpscaleModel = Form(...)):
    try:
        if not image:
            raise HTTPException(status_code=400, detail="No image file provided")

        # Read the uploaded image
        image_data = await image.read()

        # Convert the image to PNG format if it's not already in PNG
        with Image.open(io.BytesIO(image_data)) as img:
            if img.format != "PNG":
                # Convert to PNG
                png_buffer = io.BytesIO()
                img.save(png_buffer, format="PNG")
                image_data = png_buffer.getvalue()

        # Process the binary image as needed
        temp_dir = tempfile.mkdtemp(dir="/tmp")
        source_path = os.path.join(temp_dir, "input" + '.png')

        output_random_filename = generate_random_filename()
        output_path = os.path.join(temp_dir, "output" + '.png')

        # Save the binary image to the source_path
        with open(source_path, "wb") as tmpfile:
            tmpfile.write(image_data)

        job_id = str(uuid.uuid4())

        # Replace the following line with your job processing logic
        job_instance = queue.enqueue(task,
                                     task_id=job_id,
                                     input_path=source_path,
                                     output_path=output_path,
                                     model_name=model_name,
                                     tta=tta,
                                     meta={'output_path': output_path, 'source_path': source_path, 'progress': ''},
                                     job_id=job_id,
                                     result_ttl=3600)

        return {"success": True, "job_id": job_instance.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


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

    elif job.is_finished:
         await websocket.send_text("finished")
         await websocket.close()
         return

    elif job.is_failed:
         await websocket.send_text("failed")
         await websocket.close()
         return


    previous_progress = None  # Initialize previous progress to None

    try:
        while not job.is_finished:

            if job.is_queued:
                while not job.is_finished:
                    progress = job.get_meta().get("progress")
                    if not progress:
                        await websocket.send_text("queued")
                        await asyncio.sleep(1)
                    else:
                        progress = job.get_meta().get("progress")

                        if progress != previous_progress:
                            await websocket.send_text(progress)
                            previous_progress = progress
                        else:
                            await asyncio.sleep(1)

            elif job.is_started:
                progress = job.get_meta().get("progress")

                if progress != previous_progress:
                    await websocket.send_text(progress)
                    previous_progress = progress
                else:
                    await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)

        # Send the final status after the job has finished
        try:
            await websocket.send_text(job.get_status())
            if websocket.application_state != websockets.protocol.State.CLOSED:
               await websocket.close()
        except websockets.exceptions.ConnectionClosedOK:
            print("Connection closed by client...")
    except websockets.exceptions.ConnectionClosedOK:
        print("Connection closed by client...")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
