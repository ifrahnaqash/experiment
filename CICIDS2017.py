import numpy as np

my_seed = 12
np.random.seed(my_seed)
import random

random.seed(my_seed)


import tensorflow

tensorflow.random.set_seed(my_seed)

import pandas as pd  # data processing, CSV file I/O (e.g. pd.read_csv)
from Preprocessing import Preprocessing as prep
from DatasetsConfig import Datasets
from Plot import Plot
from keras import callbacks
from keras.utils import np_utils

from sklearn.metrics import confusion_matrix
from keras.models import Model

from keras.models import load_model
from keras import backend as K
from keras.utils import plot_model
np.set_printoptions(suppress=True)
from sklearn.model_selection import train_test_split



def getResult(cm, N_CLASSES):
    tp = cm[0][0]  # attacks true
    fn = cm[0][1]  # attacs predict normal
    fp = cm[1][0]  # normal predict attacks
    tn = cm[1][1]  # normal as normal
    attacks = tp + fn
    normals = fp + tn
    OA = (tp + tn) / (attacks + normals)
    AA = ((tp / attacks) + (tn / normals)) / N_CLASSES
    P = tp / (tp + fp)
    R = tp / (tp + fn)
    F1 = 2 * ((P * R) / (P + R))
    FAR = fp / (fp + tn)
    TPR = tp / (tp + fn)
    r = (tp, fn, fp, tn, OA, AA, P, R, F1, FAR, TPR)
    return r



class RunCNN1DCICIDS():
    def __init__(self, dsConfig, config):
        self.config = config
        self.ds = dsConfig



    def createImage(self, train_X, trainA, trainN):
        rows = [train_X, trainA, trainN]
        rows = [list(i) for i in zip(*rows)]

        train_X = np.array(rows)

        if K.image_data_format() == 'channels_first':
            x_train = train_X.reshape(train_X.shape[0], train_X.shape[1], train_X.shape[2])
            input_shape = (train_X.shape[1], train_X.shape[2])
        else:
            x_train = train_X.reshape(train_X.shape[0], train_X.shape[2], train_X.shape[1])
            input_shape = (train_X.shape[2], train_X.shape[1])
        return x_train, input_shape



    def run(self):

        print('MINDFUL EXECUTION')

        dsConf = self.ds
        pathModels = dsConf.get('pathModels')
        pathPlot = dsConf.get('pathPlot')
        configuration = self.config


        VALIDATION_SPLIT = float(configuration.get('VALIDATION_SPLIT'))
        N_CLASSES = int(configuration.get('N_CLASSES'))
        pd.set_option('display.expand_frame_repr', False)

        # contains path of dataset and model and preprocessing phases
        ds = Datasets(dsConf)
        ds.preprocessing1()
        train, test = ds.getTrain_TestCIDIS()
        prp = prep(train, test)

        # Preprocessing phase from original to numerical dataset
        PREPROCESSING1 = int(configuration.get('PREPROCESSING1'))
        if (PREPROCESSING1 == 1):

            train, test = ds.preprocessing2(prp)
        else:
            train, test = ds.getNumericDatasets()


        clsT, clsTest = prp.getCls()
        train_normal = train[(train[clsT] == 1)]


        train_anormal = train[(train[clsT] == 0)]


        train_XN, train_YN = prp.getXYTrain(train_normal)

        train_XA, train_YA = prp.getXYTrain(train_anormal)


        train_X, train_Y, test_X, test_Y = prp.getXYCICIDS(train, test)



        print('Train data shape normal', train_XN.shape)
        print('Train target shape normal', train_YN.shape)
        print('Train data shape anormal', train_XA.shape)
        print('Train target shape anormal', train_YA.shape)


        # convert class vectors to binary class matrices fo softmax
        train_Y2 = np_utils.to_categorical(train_Y, int(configuration.get('N_CLASSES')))
        print("Target train shape after", train_Y2.shape)
        test_Y2 = list()
        for t in test_Y:
            t_Y2 = np_utils.to_categorical(t, int(configuration.get('N_CLASSES')))
            test_Y2.append(t_Y2)
        print("Train all", train_X.shape)

        # create pandas for results
        columns = ['TP', 'FN', 'FP', 'TN', 'OA', 'AA', 'P', 'R', 'F1', 'FAR(FPR)', 'TPR']
        results = pd.DataFrame(columns=columns)

        callbacks_list = [
            callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0001, patience=20, restore_best_weights=True),
        ]

        if (int(configuration.get('LOAD_AUTOENCODER_NORMAL')) == 0):


            autoencoderN, p = ds.getAutoencoder_Normal(train_XN, N_CLASSES)

            encoderN = Model(inputs=autoencoderN.input, outputs=autoencoderN.get_layer('encoder3').output)
            encoderN.summary()

            history = autoencoderN.fit(train_XN, train_XN,
                                       validation_split=VALIDATION_SPLIT,
                                       batch_size=p['batch_size'],
                                       epochs=p['epochs'], shuffle=True,
                                       callbacks=callbacks_list,
                                       verbose=1)
            autoencoderN.save(pathModels + 'autoencoderNormal.h5')
            Plot.printPlotLoss(history, 'autoencoderN', pathPlot)
        else:
            print("Load autoencoder Normal from disk")
            autoencoderN = load_model(pathModels + 'autoencoderNormal.h5')
            autoencoderN.summary()


        train_RE = autoencoderN.predict(train_X)
        # test
        test_RE = []
        for t in test_X:
            t_N = autoencoderN.predict(t)
            testX = t_N
            test_RE.append(testX)



        if (int(configuration.get('LOAD_AUTOENCODER_ADV')) == 0):


            autoencoderA, p = ds.getAutoencoder_Attacks(+train_XA, N_CLASSES)

            encoderA = Model(inputs=autoencoderA.input, outputs=autoencoderA.get_layer('encoder3').output)
            encoderA.summary()

            history = autoencoderA.fit(train_XA, train_XA,
                                       validation_split=VALIDATION_SPLIT,
                                       batch_size=p['batch_size'],
                                       epochs=p['epochs'], shuffle=True,
                                       callbacks=callbacks_list,
                                       verbose=1)
            autoencoderA.save(pathModels + 'autoencoderAttacks.h5')
            Plot.printPlotLoss(history, 'autoencoderA', pathPlot)
        else:
            print("Load autoencoder Attacks from disk")
            autoencoderA = load_model(pathModels + 'autoencoderAttacks.h5')
            autoencoderA.summary()

        train_REA = autoencoderA.predict(train_X)
        # test predictions
        test_REA = []
        for t in test_X:
            testXA = autoencoderA.predict(t)
            testR = testXA
            test_REA.append(testR)



        train_X_image, input_Shape = self.createImage(train_X, train_RE, train_REA)  # XS UNSW
        test_X_image = list()

        for t, tN, tA in zip(test_X, test_RE, test_REA):
            test_XIm, input_shape = self.createImage(t, tN, tA)
            test_X_image.append(test_XIm)




        if (int(configuration.get('LOAD_CNN')) == 0):
            callbacks_list = [
                callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0001, patience=10,
                                        restore_best_weights=True),
            ]

            model, p = ds.getMINDFUL(input_shape, N_CLASSES)
            XTraining, XValidation, YTraining, YValidation = train_test_split(train_X_image, train_Y2, stratify=train_Y2,
                                                                              test_size=0.2)  # before model building


            history3 = model.fit(XTraining, YTraining,
                                 # validation_data=(test_X, test_Y2),
                                 validation_data=(XValidation, YValidation),
                                 batch_size=p['batch_size'],
                                 epochs=p['epochs'], shuffle=True,
                                 callbacks=callbacks_list,
                                 verbose=1)

            Plot.printPlotAccuracy(history3, 'finalModel1', pathPlot)
            Plot.printPlotLoss(history3, 'finalModel1', pathPlot)
            model.save(pathModels + 'MINDFUL.h5')
        else:
            print("Load softmax from disk")
            model = load_model(pathModels + 'MINDFUL.h5')
            model.summary()



        predictionsL = model.predict(train_X_image)
        y_pred = np.argmax(predictionsL, axis=1)
        cmC = confusion_matrix(train_Y, y_pred)
        print('Prediction Training')
        print(cmC)

        r_list = []
        i = 0
        for t, Y in zip(test_X_image, test_Y):
            i += 1
            predictionsC = model.predict(t)
            print('Softmax on test set')
            y_pred = np.argmax(predictionsC, axis=1)
            cm = confusion_matrix(Y, y_pred)
            print(cm)
            r = getResult(cm, N_CLASSES)
            r_list.append(tuple(r))



        dfResults_temp = pd.DataFrame(r_list, columns=columns)
        drMean = dfResults_temp.mean(axis=0)
        drmeanList = pd.Series(drMean).values
        r_mean = []
        for i in drmeanList:
            r_mean.append(i)

        dfResults = pd.DataFrame([r], columns=columns)
        print(dfResults)


        results = results.append(dfResults, ignore_index=True)


        results.to_csv(ds._testpath + '_results.csv', index=False)



