from barazmoon import BarAzmoon
import cv2
import base64
import json

def main():
    # Read and encode a sample image
    im = cv2.imread(r"C:\Users\HP\Desktop\cloud_load_tester\imagenet-sample-images\n01440764_tench.JPEG")
    im = cv2.resize(im, dsize=(256, 256), interpolation=cv2.INTER_CUBIC)
    encoded = base64.b64encode(cv2.imencode(".jpeg", im)[1].tobytes()).decode("utf-8")

    # Workload pattern (requests per second)
    workload = [5, 5, 10, 10, 20, 20, 10, 10, 5, 5]

    # Run load tester
    load_tester = BarAzmoon(
        workload=workload,
        endpoint="http://localhost:5000/predict",
        http_method="post",
        data=json.dumps({"data": encoded})  
    )

    load_tester.start()

if __name__ == '__main__':
    main()