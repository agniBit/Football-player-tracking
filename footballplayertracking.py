# -*- coding: utf-8 -*-
"""footballPlayerTracking.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1wVvkvqxn08LAOlt3InyOCecCqyWIxhY5
"""

import os
import numpy as np
import cv2
import torch
from torch import nn, optim
from torch.autograd import Variable
from torchvision import transforms
import keras
import numpy as np
from keras import backend as K
from keras.models import model_from_json
import json
from google.colab.patches import cv2_imshow
from PIL import Image

# Commented out IPython magic to ensure Python compatibility.
# %cd '/content/drive/MyDrive/Colab Notebooks/football'

classes = ['FCB', 'crowd', 'ref', 'RMA']
calsses.sort()
player_ids =  {'FCB':[1,3,4,5,6,8,9,10,11,17,18,20,24],'RMA':[1,2,4,7,8,11,12,15,23,19,22,23]}
def get_output_layers(net):
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    return output_layers

def validInt(i):
  try:
    int(i)
    return True
  except:
    return False


def draw_prediction(img, id, confidence, x, y, x_plus_w, y_plus_h, player_id=None):
    if id==0:
      if player_id is not None and validInt(player_id) and int(player_id) in player_ids['FCB']:
        label = f'FCB {player_id}'
      else:
        label = 'FCB'
      color = (0, 0, 255)
    elif id==1:
      return
    elif id == 2:
      label = 'ref'
      color = (255,215,0)
    elif id == 3:
      if player_id is not None and validInt(player_id) and int(player_id) in player_ids['RMA']:
        label = f'RMA {player_id}'
      else:
        label = 'RMA'
      color = (255,255,255)
    elif id==5:
      label = 'ball'
      color = (0,0,0)
    cv2.rectangle(img, (x,y), (x_plus_w,y_plus_h), color, 2)
    cv2.putText(img, label, (x-10,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

# Commented out IPython magic to ensure Python compatibility.
# %cd '/content/drive/MyDrive/Colab Notebooks/football'
net = cv2.dnn.readNet('./yolov3.weights', './yolov3.cfg')

# Commented out IPython magic to ensure Python compatibility.
# %cd '/content/drive/MyDrive/Colab Notebooks/football'
# defining the model architecture
class Net(nn.Module):   
  def __init__(self):
      super(Net, self).__init__()

      self.cnn_layers = nn.Sequential(
          # Defining a 2D convolution layer
          nn.Conv2d(3, 4, kernel_size=3, stride=1, padding=1),
          nn.BatchNorm2d(4),
          nn.ReLU(inplace=True),
          nn.MaxPool2d(kernel_size=2, stride=2),
          # Defining another 2D convolution layer
          nn.Conv2d(4, 4, kernel_size=3, stride=1, padding=1),
          nn.BatchNorm2d(4),
          nn.ReLU(inplace=True),
          nn.MaxPool2d(kernel_size=2, stride=2),
      )

      self.linear_layers = nn.Sequential(
          nn.Linear(4 * 8 * 8, 4)
      )

  # Defining the forward pass    
  def forward(self, x):
      x = self.cnn_layers(x)
      x = x.view(x.size(0), -1)
      x = self.linear_layers(x)
      return x

model = Net()
# load pretrained model
model.load_state_dict(torch.load('./teamCategoryModel3.pth'))
model.eval()
model.cuda()

# transformations to be applied on images
image_transform = transforms.Compose([
                                transforms.Resize((32,32)),
                                transforms.ToTensor(),
                                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                              ])

def predict_image(image):
    # You may need to convert the color.
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(image)
    image_tensor = image_transform(image).float()
    image_tensor = image_tensor.unsqueeze_(0)
    input = Variable(image_tensor)
    input = input.cuda()
    output = model(input)
    index = output.data.cpu().numpy().argmax()
    return index

def decode_nn_res(res_vec, num_digits, num_classes, dummy_class):
    digits = np.array_split(res_vec, num_digits)
    actual_digits = np.argmax(digits,1)+1
    res = actual_digits[actual_digits!=dummy_class]
    return actual_digits, ''.join(map(str, res))

def process_labels(labels,max_digits):
    tmp = []
    for label in labels:
        vec = [int(float(x)) for x in label.split('_')]
        if len(vec) < max_digits:
            vec = vec + [11]*(max_digits-len(vec))
        tmp.append(vec)
    labels = np.array(tmp)
    tmp = []
    num_classes = 11
    for target in labels[:,...]:
        y = np.zeros((len(target), num_classes))
        y[np.arange(target.shape[0]), target-1] = 1
        tmp.append(y)
    labels = np.array(tmp)   
    return labels

# load model for player number detection
base_path = '/content/drive/MyDrive/Colab Notebooks/football/model_weights'
#load digit detection model
with open('./model_weights/digit_detection_cnn_layers.json','r') as json_data:
    model_dict = json.load(json_data)

detect_model = model_from_json(json.dumps(model_dict))
detect_model.load_weights('./model_weights/digit_detection_cnn_weights.h5')

#load digit classification model
with open('./model_weights/digit_classification_cnn_layers.json','r') as json_data:
    model_dict = json.load(json_data)

classification_model = keras.models.model_from_json(json.dumps(model_dict))
classification_model.load_weights(os.path.join('./model_weights/digit_classification_cnn_weights.h5'))

def find_box_and_predict_digit(input_img):
    num_digits = 4
    input_img_shape = input_img.shape
    train_img_size = (64,64)
    proc_input_img = np.array(cv2.normalize(cv2.cvtColor(cv2.resize(input_img,train_img_size), cv2.COLOR_BGR2GRAY).astype(np.float64), 0, 1, cv2.NORM_MINMAX)[...,np.newaxis])[np.newaxis,...]
    box_preds = detect_model.predict(proc_input_img)
    scaled_box = box_preds[0].copy()
    scaled_box[0] = scaled_box[0]/float(train_img_size[0]/input_img_shape[0])
    scaled_box[1] = scaled_box[1]/float(train_img_size[1]/input_img_shape[1])
    scaled_box[2] = scaled_box[2]/float(train_img_size[1]/input_img_shape[1])
    scaled_box[3] = scaled_box[3]/float(train_img_size[0]/input_img_shape[0])
    start_row = np.clip(int(scaled_box[0]),1,input_img_shape[0])
    end_row = np.clip(int(scaled_box[0]+scaled_box[3]),1,input_img_shape[0])
    start_col = np.clip(int(scaled_box[1]),1,input_img_shape[1])
    end_col = np.clip(int(scaled_box[1]+scaled_box[2]),1,input_img_shape[1])
    #need better logic to handle cases where the box is too thin
    if start_col-end_col==0:
        start_col -=1
    if start_row-end_row==0:
        start_row -=1
    #store only the cutouts
    digits_only = input_img[start_row:end_row,start_col:end_col,...]
    digits_only_resized = cv2.resize(digits_only,train_img_size)
    orig_img_box = input_img.copy()
    digit_pred = classification_model.predict(np.array(digits_only_resized)[np.newaxis,...])
    score = np.concatenate(digit_pred, axis=1)
    pred_labels_encoded = np.zeros(score.shape, dtype="int32")
    pred_labels_encoded[score > 0.5] = 1
    pred_labels_decoded = np.array([decode_nn_res(x,num_digits,11,11) for x in pred_labels_encoded])
    pred_labels_decoded_digits = np.array(pred_labels_decoded[:,1])
    final_digit = pred_labels_decoded_digits[0]
    return final_digit

# read video from file
cap = cv2.VideoCapture('/content/y2mate.com - Real Madrid vs FC Barcelona 4K50fps 21112015 04 La Liga_1080pFHR_1.mp4')
Width = int(cap.get(3))
Height = int(cap.get(4))
# create video writer object 
out_vid = cv2.VideoWriter('./predicted_output.avi',cv2.VideoWriter_fourcc('M','J','P','G'), cap.get(cv2.CAP_PROP_FPS), (Width,Height))
scale = 0.00392
frame_count = 0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
if cap.isOpened():
  ret = True
else:
  print("Error opening video stream or file")
  ret = False
# Read until video is completed
while(ret):
    # Capture frame-by-frame and predict
    ret, image = cap.read()
    blob = cv2.dnn.blobFromImage(image, scale, (416,416), (0,0,0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(get_output_layers(net))
    class_ids = []
    confidences = []
    boxes = []
    conf_threshold = 0.5
    nms_threshold = 0.4
    ball_confidence = -1
    ball_cord = None
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            if class_id == 0: # person class
                confidence = scores[class_id]
                if confidence > 0.5 or class_id==32:
                    center_x = int(detection[0] * Width)
                    center_y = int(detection[1] * Height)
                    w = int(detection[2] * Width)
                    h = int(detection[3] * Height)
                    x = center_x - w / 2
                    y = center_y - h / 2
                    class_ids.append(class_id)
                    confidences.append(float(confidence))
                    boxes.append([x, y, w, h])
                    class_ids.append(class_id)
            elif class_id==32 and ball_confidence < float(confidence) and float(confidence) > 0.2: # ball class
                center_x = int(detection[0] * Width)
                center_y = int(detection[1] * Height)
                w = int(detection[2] * Width)
                h = int(detection[3] * Height)
                x = center_x - w / 2
                y = center_y - h / 2
                ball_confidence = float(confidence)
                ball_cord = [x, y, w, h]
        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
    player_num = 0
    # draw ball
    if ball_cord is not None:
        x,y,w,h = ball_cord
        draw_prediction(image, 5, ball_confidence, max(0,round(x)), max(0,round(y)), round(x+w), round(y+h))
    for num,i in enumerate(indices):
        player_num+=1
        i = i[0]
        box = boxes[i]
        x = max(0,box[0])
        y = max(0,box[1])
        w = box[2]
        h = box[3]
        detected_player = image[round(y):round(y+h), round(x):round(x+w)]
        if class_ids[num]==0:
          if w>5 and h>5 and x>=0 and y>=0: # check minimum height and width
              id = predict_image(detected_player.copy())
              player_id = find_box_and_predict_digit(detected_player)
              draw_prediction(image, id, confidences[i], round(x), round(y), round(x+w), round(y+h), player_id)
    # # show ouput frame by frame
    # cv2_imshow(image)
    out_vid.write(image)
    if frame_count%10==0:
        print(f'\rframes done {frame_count}/{total_frames}')
    frame_count+=1
cap.release()
out_vid.release()

