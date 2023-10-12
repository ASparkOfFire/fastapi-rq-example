from pydantic import BaseModel, Field, validator
from enum import Enum

# Function to generate a random filename
def generate_random_filename():
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(10))

class UpscaleModel(str, Enum):
    _4x_NMKD_Superscale_SP_178000_G = "4x_NMKD-Superscale-SP_178000_G"
    realesrgan_x4plus_anime = "realesrgan-x4plus-anime"
    realesrgan_x4plus = "realesrgan-x4plus"
    RealESRGAN_General_x4_v3 = "RealESRGAN_General_x4_v3"
    remacri = "remacri"
    ultramix_balanced = "ultramix_balanced"
    ultrasharp = "ultrasharp"

class UpscaleData(BaseModel):
    image: str
    tta: bool = False
    model_name: UpscaleModel = UpscaleModel.remacri
