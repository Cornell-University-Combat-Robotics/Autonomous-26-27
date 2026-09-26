import os
import time
import cv2
import math
from dotenv import load_dotenv
from ultralytics import YOLO
import numpy as np

# from template_model import TemplateModel # to run in machine
from machine.template_model import TemplateModel  # to run in main

load_dotenv()

FONT = cv2.FONT_HERSHEY_SIMPLEX
DEBUG = False

class YoloModel(TemplateModel):
    # General template for using YOLO to load model files and use them.

    def __init__(self, model_name, model_type, image_size, device=None, SEGMENT=False):
        self.segment = SEGMENT
        task = "segment" if SEGMENT else "detect"
        match model_type:
            case "TensorRT":
                # Works best on NVIDIA GPUs, engine file must be compiled on the PC that it is running on.
                model_extension = ".engine"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}", task=task)
            case "ONNX":
                # Optimal for CPU performance
                model_extension = ".onnx"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}", task=task)
            case "PT":
                # Default kinda
                model_extension = ".pt"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}", task=task)
            case "OpenVINO":
                # Optimal for Intel CPUs, needs a lil work
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}_openvino_model/", task=task)
            case "CoreML":
                # Optimal for M-series Macs
                model_extension = ".mlpackage"
                self.model = YOLO(
                    f"./machine/models/{model_name}/{image_size}/{model_name}{model_extension}", task=task)
            case _:
                raise ValueError(
                    f"Invalid model type: {model_type}. Must be one of 'TensorRT', 'ONNX', 'PT', 'OpenVINO', or 'CoreML'.")

        self.device = device
        self.img_size = image_size
        # compiled_model = core.compile_model(model=model, device_name=device.value)

    def predict(self, img, confidence_threshold=0.10,show=False, track=False, rs=None):
        # Max_det = max number of detections, 3 for housebot + 2 bots. Stops YOLO from hallucinating extra bots when confidence is low. Iou=0.8 to prevent multiple detections on same bot.
        predict_kwargs = {
            "verbose": False, 
            "task": self.model.task,
            "imgsz": self.img_size, 
            # "max_det": 3,
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

        results = self.model(img, **predict_kwargs)

        result = results[0]

        # 1. BATCH EXTRACT EVERYTHING TO CPU ONCE
        # This is the secret sauce. .cpu().numpy() is faster than calling .tolist() inside a loop.
        boxes_xyxy = result.boxes.xyxy.cpu().numpy()
        boxes_xywh = result.boxes.xywh.cpu().numpy()
        boxes_cls = result.boxes.cls.cpu().numpy()
        
        if track and result.boxes.id is not None:
            boxes_id = result.boxes.id.cpu().numpy()
        else:
            boxes_id = [None] * len(boxes_xyxy)

        # Extract masks if segmentation is active and available
        masks = None
        segments = None
        if self.segment and hasattr(result, 'masks') and result.masks is not None:
            masks = result.masks.data.cpu().numpy()
            segments = result.masks.xy

        robots = []
        housebots = []
        class_names = getattr(result, "names", None) or getattr(self.model, "names", {})

        # 2. Iterate over the NumPy arrays (much faster)
        for i in range(len(boxes_xyxy)):
            x1, y1, x2, y2 = boxes_xyxy[i]
            cx, cy, _, _ = boxes_xywh[i]
            cls = int(boxes_cls[i])
            track_id = boxes_id[i]
            
            if isinstance(class_names, dict):
                class_name = str(class_names.get(cls, "")).lower()
            elif cls < len(class_names):
                class_name = str(class_names[cls]).lower()
            else:
                class_name = ""
            normalized_class_name = class_name.replace("_", "").replace(" ", "")

            # 3. Clip coordinates safely
            x1_c, y1_c = max(0, x1), max(0, y1) 
            x2_c, y2_c = min(700, x2), min(700, y2) # TODO: 700 should be pulled from somewhere, not just set here

            cropped_img = img[int(y1_c): int(y2_c), int(x1_c): int(x2_c)]

            # If segmentation is active, mask out pixels outside the detection mask
            segment_points = None
            if masks is not None and i < len(masks):
                # Resize mask to match original image dimensions
                full_mask = cv2.resize(masks[i], (img.shape[1], img.shape[0]))
                # Crop the mask to the bounding box and apply threshold
                mask_crop = (full_mask[int(y1_c): int(y2_c), int(
                    x1_c): int(x2_c)] > 0.5).astype(np.uint8)
                # Apply mask to the cropped image
                cropped_img = cv2.bitwise_and(
                    cropped_img, cropped_img, mask=mask_crop)

                if segments is not None and i < len(segments):
                    segment_points = segments[i].astype(np.int32)

            data = {
                "bbox": [[x1_c, y1_c], [x2_c, y2_c]],
                "center": [cx, cy],
                "img": cropped_img,
                "segment_points": segment_points
            }
            
            if track:
                data["track_id"] = track_id

            if normalized_class_name == "housebot" or (not class_name and cls == 0):
                housebots.append(data)
            else:
                robots.append(data)

        output = {"bots": robots, "housebot": housebots}
        return output

    def show_predictions(self, img, bots_dict):
        for label, bots in bots_dict.items():
            for bot in bots:
                # Choose color based on the class
                if "housebot" in label:
                    color = (0, 0, 255)  # Red for housebot
                else:
                    color = (255, 255, 255)  # White for bots

                # Draw segmentation outline and "cloud" if available
                if "segment_points" in bot and bot["segment_points"] is not None:
                    # Create a semi-transparent "cloud" overlay
                    overlay = img.copy()
                    cv2.fillPoly(overlay, [bot["segment_points"]], color)
                    cv2.addWeighted(overlay, 0.2, img, 0.8, 0, img)
                    # Draw the sharp outline
                    cv2.polylines(img, [bot["segment_points"]],
                                  isClosed=True, color=color, thickness=2)
                else:
                    # Fallback to bounding box if no segmentation data
                    x_min, y_min = bot["bbox"][0]
                    x_max, y_max = bot["bbox"][1]
                    cv2.rectangle(img, (int(x_min), int(y_min)),
                                  (int(x_max), int(y_max)), color, 2)

        return img

# Main code block
if __name__ == "__main__":
    
    # TODO: Make this actually a useful test case!

    print("starting testing with PT model")
    predictor = YoloModel("100epoch11","PT")

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
    print(f"elapsed time: {elapsed:.4f}")

    # predictor.show_predictions(img, bots)
