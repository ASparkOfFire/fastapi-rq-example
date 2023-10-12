import os
import shutil
import tempfile
import zipfile
import string
import random

# Function to generate a random filename
def generate_random_filename():
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(10))

