# -*- coding: utf-8 -*-
"""footballPlayerTracking.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1wVvkvqxn08LAOlt3InyOCecCqyWIxhY5
"""

import numpy as np
import cv2
import torch
from torch import nn, optim
from torch.autograd import Variable
from torchvision import transforms
from google.colab.patches import cv2_imshow
from PIL import Image

# Commented out IPython magic to ensure Python compatibility.
# %cd '/content/drive/MyDrive/Colab Notebooks/football'

# download pretrained yolo weights
# !wget https://pjreddie.com/media/files/yolov3.weights

def get_output_layers(net):
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    return output_layers


def draw_prediction(img, team, confidence, x, y, x_plus_w, y_plus_h):
    if team==0:
      label = 'Referry'
      color = (255, 215, 0)
    elif team==1:
      label = 'Team 1'
      color = (0, 0, 255)
    else:
      label = 'Team 2'
      color = (255,0,0)
    cv2.rectangle(img, (x,y), (x_plus_w,y_plus_h), color, 2)
    cv2.putText(img, label, (x-10,y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

classes = None
with open('./yolov3.txt', 'r') as f:
    classes = [line.strip() for line in f.readlines()]

net = cv2.dnn.readNet('./yolov3.weights', './yolov3.cfg')

import math
def calculate_avg_color(image):
  shape = image.shape
  print(shape)
  avg_color = [0,0,0]
  num_pix = 0
  for x in range(shape[0]):
    for y in range(shape[1]):
      r,b,g = image[x][y] 
      if not (r <5 and b <5 and g<5):
        avg_color+=image[x][y]
        num_pix += 1
  avg_color = avg_color/num_pix
  print('dist',math.sqrt(avg_color[0]**2+avg_color[1]**2+avg_color[2]**2)/3)
  return avg_color

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
          nn.Linear(4 * 8 * 8, 3)
      )

  # Defining the forward pass    
  def forward(self, x):
      x = self.cnn_layers(x)
      x = x.view(x.size(0), -1)
      x = self.linear_layers(x)
      return x

model = Net()
# load pretrained model
model.load_state_dict(torch.load('./teamCategoryModel.pth'))
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

cap = cv2.VideoCapture('./input_video.mp4')
Width = int(cap.get(3))
Height = int(cap.get(4))
out_vid = cv2.VideoWriter('./final_output.avi',cv2.VideoWriter_fourcc('M','J','P','G'), cap.get(cv2.CAP_PROP_FPS), (Width,Height))
if (cap.isOpened()== False):
  print("Error opening video stream or file")
scale = 0.00392
frame_count = 0
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
# Read until video is completed
while(cap.isOpened()):
    # Capture frame-by-frame
    ret, image = cap.read()
    if not ret:
      break
    blob = cv2.dnn.blobFromImage(image, scale, (416,416), (0,0,0), True, crop=False)
    net.setInput(blob)
    outs = net.forward(get_output_layers(net))
    class_ids = []
    confidences = []
    boxes = []
    conf_threshold = 0.5
    nms_threshold = 0.4
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            if class_id == 0:
                confidence = scores[class_id]
                if confidence > 0.5:
                    center_x = int(detection[0] * Width)
                    center_y = int(detection[1] * Height)
                    w = int(detection[2] * Width)
                    h = int(detection[3] * Height)
                    x = center_x - w / 2
                    y = center_y - h / 2
                    class_ids.append(class_id)
                    confidences.append(float(confidence))
                    boxes.append([x, y, w, h])
        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
    player_num = 0
    for i in indices:
        player_num+=1
        i = i[0]
        box = boxes[i]
        x = max(0,box[0])
        y = max(0,box[1])
        w = box[2]
        h = box[3]
        detected_player = image[round(y):round(y+h), round(x):round(x+w)]
        if w>5 and h>5 and x>=0 and y>=0:
            team = predict_image(detected_player.copy())
            draw_prediction(image, team, confidences[i], round(x), round(y), round(x+w), round(y+h))
        else:
          print(x,y,w,h)
    # # show ouput frame by frame
    # cv2_imshow(image)
    out_vid.write(image)
    if frame_count%10==0:
        print(f'frames done {frame_count}/{total_frames}')
    frame_count+=1

cap.release()
out_vid.release()

