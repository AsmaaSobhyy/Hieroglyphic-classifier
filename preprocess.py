import matplotlib.pyplot as plt
from skimage import io, transform, color
import cv2
import numpy as np
from skimage.exposure import adjust_sigmoid


def preprocess(img):
    gray =cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    new=adjust_sigmoid(gray, cutoff=0.45, gain=5, inv=False)
    stacked_img = np.stack((new,)*3, axis=-1)
    return stacked_img

##----------main test----

img=io.imread('test/pretest.JPG')
preprocessed=preprocess(img)
# plt.imshow(preprocessed)
cv2.imwrite('test/prep.jpg',preprocessed)