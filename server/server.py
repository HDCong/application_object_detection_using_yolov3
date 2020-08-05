import numpy as np
import argparse
import cv2
import os
import my_bb as bb
from flask import Flask, request, Response, jsonify
import io as StringIO
import base64
from io import BytesIO
import io
from PIL import Image
import urllib.request

confthres = 0.5
nmsthres = 0.7

# read label in .names file
def readLabelFromFile(labelsDir):
    res = []
    with open(labelsDir) as f:
        for line in f:
            res.append(line[0:len(line)-1])
    return res

def generateColor(listLabel):
    color =['navy', 'blue', 'aqua', 'teal', 'olive',
     'green', 'lime', 'yellow', 'orange', 'red', 'maroon', 
     'fuchsia', 'purple', 'black', 'gray' ,'silver']
    res =[]
    for x in range(len(listLabel)):
        res.append(color[x%len(color)])
    return res
# Use opencv dnn  
def loadModel(cfgFile,weightsFile):
    netRead = cv2.dnn.readNetFromDarknet(cfgFile, weightsFile)
    ln = netRead.getLayerNames()
    ln = [ln[i[0] - 1] for i in netRead.getUnconnectedOutLayers()]
    return netRead, ln

def predict(image,net,layer,label,default_colors):

    (H, W) = image.shape[:2]
    #Detect object
    blob = cv2.dnn.blobFromImage(image, 0.00392,(416,416),(0,0,0),True,crop=False)
    net.setInput(blob)
    layerOutputs = net.forward(layer)
    # Box dimensions
    boxes = []
    confidences = []
    classIDs = []
    for output in layerOutputs:
        for detection in output:
            scores = detection[5:]
            classID = np.argmax(scores)
            confidence = scores[classID]

            if confidence > confthres:
                box = detection[0:4] * np.array([W, H, W, H])
                (centerX, centerY, width, height) = box.astype("int")
                x = int(centerX - (width / 2))
                y = int(centerY - (height / 2))
                boxes.append([x, y, int(width), int(height)])
                confidences.append(float(confidence))
                classIDs.append(classID)

    # Draw labels
    idxs = cv2.dnn.NMSBoxes(boxes, confidences, confthres,nmsthres)
    if len(idxs) > 0:
        # loop over the indexes we are keeping
        for i in idxs.flatten():
            # extract the bounding box coordinates
            (x, y) = (boxes[i][0], boxes[i][1])
            (w, h) = (boxes[i][2], boxes[i][3])
            text = "{}: {:.4f}".format(label[classIDs[i]], confidences[i])
            bb.add(image,x,y,x+w,y+h,text,default_colors[classIDs[i]])

    listClassne =','.join([str(n) for n in classIDs])
    print((listClassne))
    return image, listClassne

##### Call functions above
default_labels=readLabelFromFile("./coco.names")
default_colors=generateColor(default_labels)
default_nets,default_layer=loadModel("./yolov3.cfg","./yolov3.weights")

###### My custom model
custom_labels=readLabelFromFile("./obj-2.names")
custom_colors=generateColor(custom_labels)
custom_nets,custom_layer=loadModel("./yolov3_bird.cfg","./yolov3_bird_21000.weights")

def handle_image_and_predict(img,net,layer, labels,colors):
    np_img=np.array(img)    
    image=np_img.copy()
    image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
    res, listIndex=predict(image,net,layer,labels,colors)
    image=cv2.cvtColor(res,cv2.COLOR_BGR2RGB)
    np_img=Image.fromarray(image)
    buffered = BytesIO()
    np_img.save(buffered, format="JPEG")
    return buffered, listIndex

def create_response_from_image(img,net,layer,labels,colors):
    buffered, listIndex = handle_image_and_predict(img,net,layer,labels,colors)
    my_encoded_img = buffered.getvalue()
    response =Response(response=my_encoded_img, status=200,mimetype="image/jpeg")
    response.headers["listIndex"]= listIndex
    response.headers['connection']='keep-alive'
    return response

# Initialize the Flask application  
app = Flask(__name__)

# route http posts to this method
@app.route('/detection', methods=['POST'])
def main():
    print('Detection')
    img = request.files["image"].read();
    img = Image.open(io.BytesIO(img))
    return create_response_from_image(img,default_nets,default_layer,default_labels,default_colors)
@app.route('/detection/url', methods=['POST'])
def mainUrlDetection():
    imgUrl= request.headers['url']
    img = Image.open(urllib.request.urlopen(imgUrl))
    return create_response_from_image(img,default_nets,default_layer,default_labels,default_colors)

@app.route('/custom', methods=['POST'])
def main2():
    print('Custom')
    # Get file from post request
    img = request.files["image"].read();
    img = Image.open(io.BytesIO(img))
    # predict
    return create_response_from_image(img,custom_nets,custom_layer,custom_labels,custom_colors)

@app.route('/custom/url', methods=['POST'])
def main2UrlDetection():
    print('Custom request url')
    # read url from request
    imgUrl= request.headers['url']
    # Retrive data image from url
    img = Image.open(urllib.request.urlopen(imgUrl))
    return create_response_from_image(img,custom_nets,custom_layer,custom_labels,custom_colors)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port=8558)