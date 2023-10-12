import threading
import time
from subprocess import Popen, PIPE, CalledProcessError
from redis import Redis
from rq import Queue
import sys
import os
import shutil

# Connect to Redis
redis_conn = Redis(host='localhost', port=6379, db=0)

# Create an RQ queue
queue = Queue(connection=redis_conn)

def read_output(pipe, task_id):
    job = queue.fetch_job(task_id)
    output = ''  # Initialize an empty string to store the output

    for line in iter(pipe.readline, ''):
        output += line  # Accumulate the output as it is generated
        sys.stderr.flush()

        # Save the output to job.meta as it is generated
        job.meta['progress'] = output
        job.save_meta()

def task(task_id, input_path, output_path, model_name, tta=False):
    try:
        upscale_command = [
            './upscale/upscayl',
            '-i', input_path,
            '-o', output_path,
            '-n', model_name
        ]

        if tta:
            upscale_command.append("-x")

        with Popen(upscale_command, stderr=PIPE, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
            stdout_thread = threading.Thread(target=read_output, args=(p.stdout, task_id))
            stderr_thread = threading.Thread(target=read_output, args=(p.stderr, task_id))

            stdout_thread.start()
            stderr_thread.start()

            # Wait for the subprocess to complete
            p.wait()

            # Wait for the output threads to finish
            stdout_thread.join()
            stderr_thread.join()

        if p.returncode != 0:
            raise CalledProcessError(p.returncode, p.args)

    except Exception as e:
        raise e

    finally:
        if os.path.exists(input_path):
            shutil.rmtree(os.path.dirname(input_path))
