This is the model that Aaron Harnish (ajh374) trained in summer 2026. It is trained on ~1400 images, with ~200 in validation.
Future steps: Label remaining 1,300 images, then add the test and val set images to training for a final run.
The dataset contains 5 images from every match in 2024/2025. Items were labeled semi randomly, with batches of the 100 worst performing unlabeled images being added to the training set iteratively.
This model was trained for 640x640 image size (resized from 720p video), should be retrained to handle 320x320 or some number in between for better performance.
It is labeled "1349_worst_3_labeled_200" in aaron's google drive folder.