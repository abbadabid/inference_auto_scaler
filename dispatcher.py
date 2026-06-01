from fastapi import FastAPI, UploadFile, File
import requests
import cv2
import base64
import json
import numpy as np

app = FastAPI()

# Resnet service URL
RESNET_URL = "http://127.0.0.1:51770/infer"

@app.post("/predict")
async def predict(image: UploadFile = File(...)):
    # Read image
    contents = await image.read()
    img_array = np.frombuffer(contents, np.uint8)
    im = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    im = cv2.resize(im, dsize=(256, 256), interpolation=cv2.INTER_CUBIC)
    
    # Encode to base64
    encoded = base64.b64encode(cv2.imencode(".jpeg", im)[1].tobytes()).decode("utf-8")
    
    # Forward to resnet service
    response = requests.post(RESNET_URL, data=json.dumps({"data": encoded}))
    
    return response.json()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)