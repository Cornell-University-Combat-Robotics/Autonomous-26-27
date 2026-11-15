"""Tests prediction speed of a given model."""

import logging
import time

import cv2
import numpy as np
from predict import YoloModel

logger = logging.getLogger(__name__)


def test_model(
    model_name: str,
    model_type: str,
    device: str | None = None,
    img: str = "12567_png.rf.6bb2ea773419cd7ef9c75502af6fe808.jpg",
) -> np.ndarray:
    """Records prediction times for a given model.

    Args:
        model_name: Model folder name under machine/models/, e.g.
                    "NanoSegAaron". Also the base name of the weights file.
        model_type: Export format to load, which sets the file extension:
            - "TensorRT": ``.engine``. NVIDIA GPU; must be compiled on the
                machine that runs it.
            - "ONNX": ``.onnx``. CPU.
            - "PT": ``.pt``. Native PyTorch weights.
            - "OpenVINO": ``_openvino_model/`` folder. Intel CPU or GPU.
            - "CoreML": ``.mlpackage``. Apple silicon Macs.
        device: Inference device passed to YOLO, e.g. "cuda", "cpu",
            "intel:gpu". None lets Ultralytics choose.
        img: File name of image to use.

    Returns:
        np.ndarray : Array of 100 prediction times
    """
    logger.info("starting testing with PT model")
    predictor = YoloModel(model_name, model_type, device)

    img = cv2.imread(img)

    # cv2.imshow("Original image", img)
    # cv2.waitKey(0)
    data = np.zeros(100)
    for i in range(100):
        start_time = time.time()
        predictor.predict(img, show=False)
        end_time = time.time()
        elapsed = end_time - start_time
        # logger.debug(f'elapsed time: {elapsed:.4f}')
        data[i] = elapsed
        # predictor.show_predictions(img, bots)
    logger.debug([data])
    return data


if __name__ == "__main__":
    models = ["ONNX", "PT"]
    with open("test_results.txt", "w") as file:
        for model in models:
            data = test_model("YoloModel", "100epoch11", model)
            avg = np.mean(data)
            avgn1 = np.mean(data[1:])
            med = np.median(data)
            file.write(f"{model} = {data}")
            file.write("\n")
            file.write(f"Average: {avg}")
            file.write("\n")
            file.write(f"Average no first: {avgn1}")
            file.write("\n")
            file.write(f"Median: {med}")
            file.write("\n")

        for model in ["PT"]:
            data = test_model("100epoch11", model, device="mps")
            avg = np.mean(data)
            avgn1 = np.mean(data[1:])
            med = np.median(data)
            file.write(f"{model}, mps = {data}")
            file.write("\n")
            file.write(f"Average: {avg}")
            file.write("\n")
            file.write(f"Average no first: {avgn1}")
            file.write("\n")
            file.write(f"Median: {med}")
            file.write("\n")
