import os
import time
import cv2
import math
from dotenv import load_dotenv
from ultralytics import YOLO
import logging
import logging_config.logging_config 

logger = logging.getLogger(__name__)

# from template_model import TemplateModel # to run in machine

load_dotenv()

ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")
FONT = cv2.FONT_HERSHEY_SIMPLEX
DEBUG = False


class YoloModel():
    # General template for using YOLO to load model files and use them.

    def __init__(self, model_name, model_type, image_size, device=None):
        match model_type:
            case "TensorRT":
                # Works best on NVIDIA GPUs, engine file must be compiled on the PC that it is running on.
                model_extension = ".engine"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}")
            case "ONNX":
                # Optimal for CPU performance
                model_extension = ".onnx"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}")
            case "PT":
                # Default kinda
                model_extension = ".pt"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}")
            case "OpenVINO":
                # Optimal for Intel CPUs, needs a lil work
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}_openvino_model/")
            case "CoreML":
                # Optimal for M-series Macs
                model_extension = ".mlpackage"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}")
            case _:
                raise ValueError(
                    f"Invalid model type: {model_type}. Must be one of 'TensorRT', 'ONNX', 'PT', 'OpenVINO', or 'CoreML'.")

        self.device = device
        self.img_size = image_size
        # compiled_model = core.compile_model(model=model, device_name=device.value)

    def predict(self, img, confidence_threshold=0.10, show=False, track=False, rs=None):
        # Max_det = max number of detections, 3 for housebot + 2 bots. 
        # Stops YOLO from hallucinating extra bots when confidence is low. 
        # Iou=0.8 to prevent multiple detections on same bot.
        predict_kwargs = {
            "verbose": False, 
            "task": self.model.task,
            "imgsz": self.img_size, 
            "max_det": 5,
            "conf": confidence_threshold
        }
        
        if self.device is not None:
            predict_kwargs["device"] = self.device

        if track:
            # persist=True is required to link detections across video frames.
            # tracker="bytetrack.yaml" is usually the best default, but you can also try "botsort.yaml"
            predict_kwargs.pop("task")
            results = self.model.track(img, persist=True, tracker="bytetrack.yaml", **predict_kwargs)
        else:
            results = self.model(img, **predict_kwargs)

        result = results[0]

        # 1. BATCH EXTRACT EVERYTHING TO CPU ONCE
        if result.boxes is None or len(result.boxes) == 0:
             return {"bots": [], "housebot": []}

        boxes_xyxy = result.boxes.xyxy.cpu().numpy()
        boxes_xywh = result.boxes.xywh.cpu().numpy()
        boxes_cls = result.boxes.cls.cpu().numpy()
        
        if track and result.boxes.id is not None:
            boxes_id = result.boxes.id.cpu().numpy()
        else:
            boxes_id = [None] * len(boxes_xyxy)

        robots = []
        housebots = []

        # 2. Iterate over the NumPy arrays (much faster)
        for i in range(len(boxes_xyxy)):
            x1, y1, x2, y2 = boxes_xyxy[i]
            cx, cy, _, _ = boxes_xywh[i]
            cls = boxes_cls[i]
            track_id = boxes_id[i]

            # 3. Clip coordinates safely
            x1_c, y1_c = max(0, x1), max(0, y1)
            x2_c, y2_c = min(700, x2), min(700, y2)

            cropped_img = img[int(y1_c): int(y2_c), int(x1_c): int(x2_c)]

            data = {
                "bbox": [[x1_c, y1_c], [x2_c, y2_c]],
                "center": [cx, cy],
                "img": cropped_img
            }
            if track:
                data["track_id"] = track_id

            if cls == 0:
                housebots.append(data)
            else:
                robots.append(data)

        output = {"bots": robots, "housebot": housebots}
        return output

    def show_predictions(self, img, bots_dict):
        for label, bots in bots_dict.items():

            for bot in bots:

                # Extract bounding box coordinates and class details
                x_min, y_min = bot["bbox"][0]
                x_max, y_max = bot["bbox"][1]

                # Choose color based on the class
                if "housebot" in label:
                    color = (0, 0, 255)  # Red for housebot
                else:
                    color = (255, 255, 255)  # White for bots

                # Draw the bounding box
                cv2.rectangle(img, (int(x_min), int(y_min)),
                              (int(x_max), int(y_max)), color, 2)

        return img

# Main code block
if __name__ == "__main__":

    logger.debug("starting testing with PT model")
    # predictor = YoloModel("100epoch11","PT")
    predictor = YoloModel()

    img_path = (
        os.getcwd() + "/main_files/12567_png.rf.6bb2ea773419cd7ef9c75502af6fe808.jpg"
    )
    img = cv2.imread(img_path)

    # cv2.imshow("Original image", img)
    # cv2.waitKey(0)

    start_time = time.time()
    bots = predictor.predict(img, show=True)
    end_time = time.time()
    elapsed = end_time - start_time
    logger.debug(f"elapsed time: {elapsed:.4f}")

    # predictor.show_predictions(img, bots)
