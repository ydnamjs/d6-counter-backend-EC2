from torchvision.transforms import v2
from torchvision import transforms
import torchvision.models as models
import bbox_visualizer as bbv
from io import BytesIO
import base64
import torch
import numpy
import PIL
import cv2

seed = 0
torch.manual_seed(seed)

NUM_CLASSES = 6
DETECTION_STATE_PATH = "../models/detector.pth"
CLASSIFIER_STATE_PATH = "../models/classifier.pth"
BBOX_COLOR = (255, 255, 255)
LABEL_BG_COLOR = (0, 0, 0)
LABEL_TEXT_COLOR = (255, 255, 255)
PAD_COLOR = (0, 0, 0)
PAD_AMT = 25

detection_model = models.detection.fasterrcnn_mobilenet_v3_large_320_fpn(weights=None, num_classes=2)
detection_model.load_state_dict(torch.load(DETECTION_STATE_PATH))
detection_model.eval()

classification_model = models.mobilenet_v3_small(weights=None)
num_features = classification_model.classifier[3].in_features
classification_model.classifier[3] = torch.nn.Linear(num_features, NUM_CLASSES)
classification_model.load_state_dict(torch.load(CLASSIFIER_STATE_PATH))
classification_model.eval()

transform = v2.Compose([
    v2.ToDtype(torch.float32, scale=True),
    v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

tensorify = transforms.Compose([
    transforms.ToTensor(),
])

def preprocess_image(image, threshold1, threshold2):
    imageArray = numpy.array(image)
    
    processed_image_array = cv2.resize(imageArray, (512, 512), interpolation=cv2.INTER_LANCZOS4)
    processed_image_array = cv2.GaussianBlur(processed_image_array, (5, 5), 0)
    processed_image_array = cv2.Canny(processed_image_array, threshold1=threshold1, threshold2=threshold2)

    return processed_image_array

def predict_image(preprocessed_image):

    imageTensor = tensorify(preprocessed_image)
    imageTensor = transform(imageTensor)

    with torch.no_grad():
        prediction = detection_model([imageTensor])

    scores = numpy.array(prediction[0]['scores'])
    boxes = numpy.array(prediction[0]['boxes']).astype(numpy.int32)

    predictions = []
    for box in boxes:
            
        x1, y1, x2, y2 = box

        subImageArray = preprocessed_image[int(y1):int(y2), int(x1):int(x2)]
        subImageArray = cv2.resize(subImageArray, (125, 125), interpolation=cv2.INTER_LANCZOS4)
        subImageTensor = tensorify(subImageArray)
        subImageTensor = transform(subImageTensor)
        subImageTensor = torch.unsqueeze(subImageTensor, 0)
        output = classification_model(subImageTensor)

        predicted_class = torch.argmax(output, dim=1)
        predictions.append(predicted_class.item())

    return boxes, scores, predictions

def process_predictions(image, boxes, scores, predictions, scoreThreshold):
    
    imageArray = numpy.array(image)
    imageArray = cv2.resize(imageArray, (512, 512), interpolation=cv2.INTER_LANCZOS4)
    result = imageArray
    predicted_total = 0
    for i in range(0, len(boxes)):

        if scores[i] < scoreThreshold:
            continue

        label = str(predictions[i] + 1)
        predicted_total = predicted_total + predictions[i] + 1

        result = bbv.draw_rectangle(result, boxes[i], BBOX_COLOR, thickness=1)
        result = bbv.add_label(result, label, boxes[i], text_bg_color=LABEL_BG_COLOR, text_color=LABEL_TEXT_COLOR)

    return PIL.Image.fromarray(result), predicted_total

def image_to_base64(image: PIL.Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')
