import os
import cv2
import numpy as np
from matplotlib import pyplot as plt
from os import listdir
from os.path import isfile, join

from assesSEM.IO import deal_with_folder_availability
from assesSEM.unet import build_unet
import matplotlib as mpl
import time
import pandas as pd
from assesSEM.smooth_tiled_predictions import predict_img_with_smooth_windowing
from importlib.resources import files  # used to access models included in the package



im_h = 512 #height
im_w  = 512 #width
im_ch = 2 #no of channels (1 for BSE and 1 for CL)
nb_classes = 5
input_shape = (im_h, im_w, im_ch)

model = build_unet(input_shape, n_classes=5);
model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy']);

#Load previously saved model
model_path = files('assesSEM.models').joinpath("model_mlo_512_512_2.h5")
model.load_weights(model_path)


def save_image(data, cm, fn):
   
    sizes = np.shape(data)
    height = float(sizes[0])
    width = float(sizes[1])
     
    fig = plt.figure()
    fig.set_size_inches(width/height, 1, forward=False)
    ax = plt.Axes(fig, [0., 0., 1., 1.])
    ax.set_axis_off()
    fig.add_axes(ax)
 
    ax.imshow(data, cmap=cm,  vmin= -1, vmax=4)
    plt.savefig(fn, dpi = height) 
    plt.close()
    
    
    

cmap_segmentation =(mpl.colors.ListedColormap(['white','white','#000000', '#ff0000', '#00ff00', '#ffff00']))
#ffff00 yellow
#000000 black
#00ff00 green
#ff0000 red
# original colors


x = ['dataset1','dataset2','dataset3', 'dataset4']



value = input("Please enter # of images loaded per dataset folder:\n") 
print(f'You entered {value}')
no_samples = int(value)



for folder in x:
    
    print('Opening folder', folder , '..')
    path_folder_cl = folder + '/CL/'
    path_folder_bse = folder + '/BSE/'

    onlyfiles_cl = [f for f in listdir(path_folder_cl) if isfile(join(path_folder_cl, f))]
    onlyfiles_bse = [f for f in listdir( path_folder_bse) if isfile(join(path_folder_bse, f))]
    print('Found' , len(onlyfiles_cl), 'files in CL folder:')
    print('Found' , len(onlyfiles_bse), 'files in BSE folder:')

    im_dummy  = cv2.imread(path_folder_cl + onlyfiles_cl[0] , 0)

    #Create 'CL segmented' folder
    directory = 'CL_segmented'
    path = os.path.join(folder, directory) 
    deal_with_folder_availability(path)

    # CSV array dummy
    dummy_array = np.zeros([len(onlyfiles_cl),5])
    df = pd.DataFrame(data=dummy_array, columns=['path', 'quartz_rel_area', 'overgrowth_rel_area' , 'otherminerals_rel_area', 'pores_rel_area'] )
    
    #Start segmenting images...
    for i in range(no_samples):
        check1 = os.path.isfile(path_folder_cl + onlyfiles_cl[i])
        if check1 == True:
            im_name = onlyfiles_cl[i]
            print('Segmenting', im_name, '..')
            cl_im  = cv2.imread(path_folder_cl + im_name , 0)
            cl_im = cl_im / 255 #Normalize
            bse_im = cv2.imread(path_folder_bse + im_name , 0)
            bse_im = bse_im / 255 #Normalize
            
            # Create input for UNet
            X = np.zeros([cl_im.shape[0], cl_im.shape[1], 2])
            X[:,:,0] = cl_im
            X[:,:,1] = bse_im
        
            # Start segmentation (+moving window w. patch size + smoothing)
            start = time.time()
            predictions_smooth = predict_img_with_smooth_windowing(
                X,
                window_size=im_h,
                subdivisions=2,  # Minimal amount of overlap for windowing. Must be an even number.
                nb_classes=nb_classes,
                pred_func=(
                    lambda img_batch_subdiv: model.predict(img_batch_subdiv)
                )
            )
            end = time.time()
            print('execution time:',end-start)

            # Save &/ plot image
            test_argmax=np.argmax(predictions_smooth, axis=2)
            
            save_image(test_argmax, cmap_segmentation, path + '/' + im_name)
            
            total_area = test_argmax.shape[0] * test_argmax.shape[1]
            df['path'][i] = path + '/' + im_name
            df['quartz_rel_area'][i] =  np.round(np.count_nonzero(test_argmax == 4) / total_area * 100,2)
            df['otherminerals_rel_area'][i] =  np.round(np.count_nonzero(test_argmax == 3) / total_area * 100,2)
            df['overgrowth_rel_area'][i] = np.round(np.count_nonzero(test_argmax == 2) / total_area * 100,2)
            df['pores_rel_area'][i] = np.round(np.count_nonzero(test_argmax == 1) / total_area * 100,2)
            print('Done and saved!')

    df.to_csv(path + '/' + 'results_' + folder +'.csv' , index=False)
    print('.csv-file saved!')
           
