import pandas as pd
import cv2
import numpy as np
import matplotlib.pyplot as plt
from skimage import io, transform, color

from skimage.feature import canny
from skimage.transform import hough_line, hough_line_peaks

import pickle
from sklearn.utils import shuffle
from collections import Counter, defaultdict


def crop_vertical(image):
    gray =cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges=canny(gray, sigma=3, low_threshold=10, high_threshold=50)
    tested_angles = np.linspace(-np.pi / 2, np.pi / 2, 360)
    h, theta, d = hough_line(edges, theta=tested_angles)
    _, angles, dist=hough_line_peaks(h, theta, d,25)
    dist= np.append(dist,[0,gray.shape[1]])
    sub_images=[]
    dist= sorted(dist)
    for i in range(len(dist)-1):
        sub_images.append(gray[:,int(dist[i]):int(dist[i+1])])
    return sub_images,dist

def move_coord(coordinates,dist):
    new_coordinates=[]
    for d in range(len(dist)-1):
        new_coordinates.append([])

    for cor in coordinates:
        for i in range(len(dist)-1):
            if cor[0] >= dist[i] and cor[0] <= dist[i+1]:
                new_cor = cor.copy()
                new_cor[0]=new_cor[0]-dist[i]
                new_coordinates[i].append(new_cor)
    ordered_coor=[]
    for coor in new_coordinates:
        new_coordinates_df=pd.DataFrame(coor,columns=['X', 'Y','L','W'])
        new_coordinates_df=new_coordinates_df.sort_values(by=['Y','X'])
        ordered_coordinates=new_coordinates_df.to_numpy()
        ordered_coor.append(ordered_coordinates)
    return ordered_coor

def get_glyphs(gray_image,coordinates):
    glyphs=[]
    for coordinate in coordinates:
        cor=np.asarray(coordinate).astype(int)
        glyph_img=gray_image[cor[1]:cor[1]+cor[3],cor[0]:cor[0]+cor[2]]
        glyphs.append(glyph_img)
    return glyphs
def add_padding(img,new_shape=(75,50)):
#     img=np.asarray(img)
    h,w=img.shape
    exp_h,exp_w=new_shape
    addedh=0
    addedw=0
    
    if w <= exp_w and h <= exp_h:
        addedh = exp_h - h
        addedw = exp_w - w
    else:
        h0=h*exp_w
        w0=w*exp_h
        if h0 >= w0:
            addedw = (h0-w0)/exp_h
        else:
            addedh =(w0-h0)/exp_w
    
    addedh=int(addedh/2)
    addedw = int(addedw/2)
    
    bordered=cv2.copyMakeBorder(img,addedh,addedh,addedw,addedw,cv2.BORDER_REPLICATE)
#     bordered=cv2.copyMakeBorder(img,addedh,addedh,addedw,addedw,cv2.BORDER_CONSTANT, None, value = 255)
    bordered = cv2.GaussianBlur(bordered,(15,15),0)
    bordered[addedh:addedh+h, addedw:addedw+w] = img
#     bordered =cv2.GaussianBlur(bordered,(3,3),0)
    resized = cv2.resize(bordered, (exp_w,exp_h))
    return resized


def pad_images(sentence_images):
    padded_images=[]
    for img in sentence_images:
        padded_images.append(add_padding(img))
    return padded_images
        
def lm_next(model,prev):
    pred = dict( eval('model'+ str(prev)))
    next_scores = sorted(pred.items(), key=lambda item: item[1],reverse=True)
    out = dict(next_scores)
    if len(list(out.keys()))==0:
        out ={'None':0}
    return out

def whichGlyph_pair(image,anchor_img,anchor_label):
    N,w,h,_=anchor_img.shape
#     pairs=[np.zeros((N, w, h,1)) for i in range(2)]
#     image=np.asarray(image)
    test_image= np.asarray([image]*N).reshape(N, w, h,1)
    
    anchor_label, test_image, anchor_img = shuffle(anchor_label, test_image, anchor_img)
#     pairs = [test_image,anchor_img]
    
    return test_image, anchor_img, anchor_label


def whichGlyph(model,image,anchor_img,anchor_label):
    test_image,anchor_img,targets = whichGlyph_pair(image,anchor_img,anchor_label)
    probs = model.predict([test_image,anchor_img])
    return probs,anchor_img,targets

def predict_multi_anchor(image,multi_anchor_img,multi_anchor_label,model):
    multi_N=multi_anchor_img.shape[0]
    final_scores=np.zeros((multi_anchor_label[0].shape[0],1))
    for j in range(multi_N):
      predicted,anchor_imgs,targets=whichGlyph(model,image,multi_anchor_img[j],multi_anchor_label[j])
      zipped_lists = zip(targets,predicted)
      sorted_pairs = sorted(zipped_lists)
      tuples = zip(*sorted_pairs)
      targets,predicted = [ list(tuple) for tuple in  tuples]
      final_scores = np.asarray(final_scores) + np.asarray(predicted)
    return final_scores,np.asarray(targets)
def choose_next(clf_3,score_3,language_model,prev):
    freq=lm_next(language_model,prev)
    freq_3=[]
    for pred in clf_3:
        if pred in freq.keys():
            freq_3.append(freq[pred])
        else:
            freq_3.append(0)
    freq_3=np.array(freq_3)
    score_3 =np.array(score_3).flatten()
    score_3_sum = score_3 / np.sum(score_3)
    freq_3_exp = np.exp(freq_3)/sum(np.exp(freq_3))
    scores = score_3_sum + 2*freq_3_exp
    predicted=clf_3[np.argmax(scores)]
    return predicted

def predict_lm(Xtest,multi_anchor_img,multi_anchor_label,model,language_model):
    preds=[]
    for new in Xtest:
        if len(preds) < 2 :
            predicted,targets=predict_multi_anchor(new,multi_anchor_img,multi_anchor_label,model)
            sort_index = np.argsort(np.asarray(predicted).reshape(len(predicted),))
            targ=targets[sort_index[-1]]
#             print(targ)
            if targ =='UNKNOWN':
                targ=targets[sort_index[-2]] 
            preds.append(targ)
        else:
            predicted,targets=predict_multi_anchor(new,multi_anchor_img,multi_anchor_label,model)
            sort_index = np.argsort(np.asarray(predicted).reshape(len(predicted),))
            predicted = choose_next(targets[sort_index[-3:]],predicted[sort_index[-3:]],language_model,preds[-2:])
            preds.append(predicted)
    return preds

def predict_all(glyphs,model,multi_anchor_img,multi_anchor_label,language_model):
    predictions=[]
    for glyph_list in glyphs:
        
        sentence_padded = pad_images(glyph_list)
        preds=predict_lm(sentence_padded,multi_anchor_img,multi_anchor_label,model,language_model)
        pred_sub="".join(preds)
#         for glyph in glyph_list:
#             padded= add_padding(glyph,(75,50))
#             predicted,anchor_imgs,targets=whichGlyph(model,padded,anchor_img,anchor_label)
#             maxp = np.argmax(predicted)
#             pred_sub+=targets[maxp]
        predictions.append(pred_sub)
    return predictions

def image_to_gardiner(img,coordinates,multi_anchor_img,multi_anchor_label,model,language_model):
    
    sub_images,dist=crop_vertical(img)
    
    new_coordinates=move_coord(coordinates,dist)
    
    glyphs=[]
    for i in range(len(sub_images)):
        glyphs.append(get_glyphs(sub_images[i],new_coordinates[i]))
    
    preds=predict_all(glyphs,model,multi_anchor_img,multi_anchor_label,language_model)
    
    return preds

# read all files needed
with open("fine_tuned_model.pickle", "rb") as f:
    (model) = pickle.load(f)

with open("multi_anchor.pickle", "rb") as f:
    (multi_anchor_img,multi_anchor_label) = pickle.load(f)

import dill as pickle
with open("language_model_sent.pkl", "rb") as f:
    language_model = pickle.load(f)


#----------main ------------
test_img=io.imread('test/0.jpg')
detected=pd.read_json('test/image_0_predictions.txt')
coordinates=detected['bbox']

final_pred=image_to_gardiner(test_img,coordinates,multi_anchor_img,multi_anchor_label,model,language_model)
print(final_pred)