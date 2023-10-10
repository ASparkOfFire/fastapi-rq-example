# job.py

import threading
import time
from subprocess import Popen, PIPE, CalledProcessError
from redis import Redis
from rq import Queue

# Connect to Redis
redis_conn = Redis(host='localhost', port=6379, db=0)

# Create an RQ queue
queue = Queue(connection=redis_conn)

def read_output(pipe, task_id):
    job = queue.fetch_job(task_id)

    for line in iter(pipe.readline, ''):
        job.meta['progress'] = line
        job.save_meta()

cmd = "./count"

def task(task_id):
    print(task_id)
    with Popen(cmd, stdout=PIPE, bufsize=1, universal_newlines=True) as p:
        output_thread = threading.Thread(target=read_output, args=(p.stdout, task_id))
        output_thread.start()

        # Wait for the subprocess to complete
        p.wait()

        # Wait for the output thread to finish
        output_thread.join()

    if p.returncode != 0:
        raise CalledProcessError(p.returncode, p.args)
