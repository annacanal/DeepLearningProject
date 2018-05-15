import tensorflow as tf
import time
from datetime import timedelta
import math
import random
import numpy as np
import load_dataset

#Adding Seed so that random initialization is consistent
from numpy.random import seed
seed(1)
from tensorflow import set_random_seed
set_random_seed(2)


##################################   INIT     ################################
batch_size = 100
learning_rate = 1e-3 #1e-4
# 20% of the data will automatically be used for validation
validation_size = 0.2
img_size = 150
num_channels = 3 #RGB (if grey scale, num_channels=1)
#num_classes = 2 #len(target_names) - 1
classes = ['not_smiling','smiling'] # 0 = no smiling, 1=smiling
# classes = ['female','male'] # 0 = no smiling, 1=smiling
num_classes = len(classes)
train_path='../dataset/dataset_smile/'
model_dir= '/smile-model/smile.ckpt'
# train_path='../dataset/dataset_gender/'
# model_dir= '/gender-model/gender.ckpt'
#load all the training and validation images and labels into memory
data = load_dataset.read_train_sets(train_path, img_size, classes, validation_size=validation_size)
print("Complete reading input data.")
print("Number of files in Training-set:\t\t{}".format(len(data.train.labels)))
print("Number of files in Validation-set:\t{}".format(len(data.valid.labels)))
session = tf.Session()
# Define the graph
x = tf.placeholder(tf.float32, shape=[None, img_size,img_size,num_channels], name='x')
## labels
y_true = tf.placeholder(tf.float32, shape=[None, num_classes], name='y_true')
y_true_cls = tf.argmax(y_true, dimension=1)
W = tf.Variable(tf.zeros([150 * 150, num_classes]))
b = tf.Variable(tf.zeros([num_classes]))

# Network parameters
filter_size_conv1 = 5
num_filters_conv1 = 20
filter_size_conv2 = 3
num_filters_conv2 = 40
filter_size_conv3 = 3
num_filters_conv3 = 60
filter_size_conv4 = 2
num_filters_conv4 = 80
num_filters_conv5 = 100 #inception layer
fc_layer_size = 160


################################ FUNCTIONS ######################3
def create_weights(shape):
    return tf.Variable(tf.truncated_normal(shape, stddev=0.05))

def create_biases(size):
    return tf.Variable(tf.constant(0.05, shape=[size]))

def create_convolutional_layer(input,num_input_channels,conv_filter_size,num_filters):
    weights = create_weights(shape=[conv_filter_size, conv_filter_size, num_input_channels, num_filters])
    biases = create_biases(num_filters)
    ## Create the convolutional layer
    layer = tf.nn.conv2d(input=input,  filter=weights, strides=[1, 1, 1, 1],  padding="VALID")
    #layer += biases
    layer = tf.nn.bias_add(layer, biases)
    ## Output of pooling is fed to Relu which is the activation function for us.
    layer = tf.nn.relu(layer)
    return layer


def create_localconvolutional_layer(input,num_input_channels,conv_filter_size,num_filters):
    weights = create_weights(shape=[conv_filter_size, conv_filter_size, num_input_channels, num_filters])
    biases = create_biases(num_filters)
    ## Create the convolutional layer
    layer = tf.keras.layers.LocallyConnected2D(filters=num_filters, kernel_size =[conv_filter_size,conv_filter_size],
                                               strides=[1, 1, 1, 1], padding = "valid", activation=tf.nn.relu,
                                               use_bias= True, kernel_initializer= input, bias_initializer= biases)
    #layer += biases
    ## Output of pooling is fed to Relu which is the activation function for us.
    #layer = tf.nn.relu(layer)
    return layer


def create_pool_layer(layer):
    ##max-pooling.
    layer = tf.nn.max_pool(value=layer, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="SAME")
    return layer

def create_inception2d(input, num_input_channels, num_filters):
    # bias dimension = 3*filter_count and then the extra in_channels for the avg pooling
    biases1 = create_biases(num_filters)
    biasespre1 = create_biases(num_input_channels)
    biasespre2 = create_biases(num_input_channels)
    biases3 = create_biases(num_filters)
    biases5 = create_biases(num_filters)
    biasespost = create_biases(num_filters)

    # 1x1
    weights1 = create_weights(shape=[1, 1, num_input_channels, num_filters])
    one_by_one_layer = tf.nn.conv2d(input=input, filter=weights1, strides=[1, 1, 1, 1], padding="SAME")
    one_by_one_layer = tf.nn.bias_add(one_by_one_layer, biases1)
    weights_pre1 = create_weights(shape=[1, 1, num_input_channels, num_input_channels])
    pre_conv1= tf.nn.conv2d(input=input, filter=weights_pre1, strides=[1, 1, 1, 1], padding="SAME")
    pre_conv1 =tf.nn.relu ( tf.nn.bias_add(pre_conv1, biasespre1))
    weights_pre2 = create_weights(shape=[1, 1, num_input_channels, num_input_channels])
    pre_conv2= tf.nn.conv2d(input=input, filter=weights_pre2, strides=[1, 1, 1, 1], padding="SAME")
    pre_conv2 = tf.nn.relu((tf.nn.bias_add(pre_conv2, biasespre2)))
    # 3x3
    weights3 = create_weights(shape=[3, 3, num_input_channels, num_filters])
    three_by_three_layer = tf.nn.conv2d(input=pre_conv1, filter= weights3, strides=[1, 1, 1, 1], padding="SAME")
    three_by_three_layer = (tf.nn.bias_add(three_by_three_layer, biases3))
    # 5x5
    weights5 = create_weights(shape=[5, 5, num_input_channels, num_filters])
    five_by_five_layer = tf.nn.conv2d(input=pre_conv2, filter= weights5, strides=[1, 1, 1, 1], padding="SAME")
    five_by_five_layer = (tf.nn.bias_add(five_by_five_layer, biases5))

    # avg pooling
    pooling = tf.nn.max_pool(value= input, ksize=[1, 3, 3, 1], strides=[1, 1, 1, 1], padding="SAME")
    post_conv1 = tf.nn.conv2d(input=pooling, filter=weights1, strides=[1, 1, 1, 1], padding="SAME")
    post_conv1 = (tf.nn.bias_add(post_conv1, biasespost))

    inception1 = tf.nn.relu(tf.concat([one_by_one_layer, three_by_three_layer, five_by_five_layer, post_conv1], axis=3))
    return inception1

def create_flatten_layer(layer):
    layer_shape = layer.get_shape()
    num_features = layer_shape[1:4].num_elements()
    layer = tf.reshape(layer, [-1, num_features])
    return layer

def create_fc_layer(input, num_inputs, num_outputs, use_relu=True):
    weights = create_weights(shape=[num_inputs, num_outputs])
    biases = create_biases(num_outputs)

    layer = tf.matmul(input, weights) + biases
    if use_relu:
        layer = tf.nn.relu(layer)
    return layer


def show_progress(epoch, feed_dict_train, feed_dict_validate, val_loss):
    acc = session.run(accuracy, feed_dict=feed_dict_train)
    val_acc = session.run(accuracy, feed_dict=feed_dict_validate)
    msg = "Training Epoch {0} --- Training Accuracy: {1:>6.1%}, Validation Accuracy: {2:>6.1%},  Validation Loss: {3:.3f}"
    print(msg.format(epoch + 1, acc, val_acc, val_loss))


def train(num_iteration):
    global total_iterations

    for i in range(total_iterations,
                   total_iterations + num_iteration):

        x_batch, y_true_batch, _, cls_batch = data.train.next_batch(batch_size)
        x_valid_batch, y_valid_batch, _, valid_cls_batch = data.valid.next_batch(batch_size)

        feed_dict_tr = {x: x_batch,
                        y_true: y_true_batch}
        feed_dict_val = {x: x_valid_batch,
                         y_true: y_valid_batch}

        session.run(optimizer, feed_dict=feed_dict_tr)

        if i % int(data.train.num_examples / batch_size) == 0:
            val_loss = session.run(cost, feed_dict=feed_dict_val)
            epoch = int(i / int(data.train.num_examples / batch_size))
            show_progress(epoch, feed_dict_tr, feed_dict_val, val_loss)
            saver.save(session, model_dir)

    total_iterations += num_iteration


################################## NETWORK ####################################

layer_conv1 = create_convolutional_layer(input=x, num_input_channels=num_channels, conv_filter_size=filter_size_conv1,
                                         num_filters=num_filters_conv1)
layer_pool1 = create_pool_layer(layer_conv1)

layer_conv2 = create_convolutional_layer(input=layer_pool1, num_input_channels=num_filters_conv1,
                                         conv_filter_size=filter_size_conv2, num_filters=num_filters_conv2)
layer_pool2 = create_pool_layer(layer_conv2)

layer_conv3 = create_convolutional_layer(input=layer_pool2, num_input_channels=num_filters_conv2,
                                         conv_filter_size=filter_size_conv3, num_filters=num_filters_conv3)
# layer_conv3 = create_localconvolutional_layer(input=layer_pool2, num_input_channels=num_filters_conv2,
#                                          conv_filter_size=filter_size_conv3, num_filters=num_filters_conv3)

layer_pool3 = create_pool_layer(layer_conv3)

layer_conv4 = create_convolutional_layer(input=layer_pool3, num_input_channels=num_filters_conv3,
                                         conv_filter_size=filter_size_conv4, num_filters=num_filters_conv4)
layer_pool4 = create_pool_layer(layer_conv4)

#inception layer:
layer_inception_5 = create_inception2d(input=layer_pool4, num_input_channels=num_filters_conv4, num_filters=num_filters_conv5)
layer_pool5 = create_pool_layer(layer_inception_5)

layer_flat = create_flatten_layer(layer_pool5)

layer_fc1 = create_fc_layer(input=layer_flat, num_inputs=layer_flat.get_shape()[1:4].num_elements(),
                            num_outputs=fc_layer_size,  use_relu=True)

layer_fc2 = create_fc_layer(input=layer_fc1, num_inputs=fc_layer_size, num_outputs=num_classes, use_relu=False)

y_pred = tf.nn.softmax(layer_fc2, name='y_pred')

y_pred_cls = tf.argmax(y_pred, dimension=1)
session.run(tf.global_variables_initializer())
cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits=layer_fc2,
                                                        labels=y_true)
cost = tf.reduce_mean(cross_entropy)
optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(cost)
correct_prediction = tf.equal(y_pred_cls, y_true_cls)
accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

session.run(tf.global_variables_initializer())
total_iterations = 0
saver = tf.train.Saver()

#train(num_iteration=3000)
train(num_iteration=3000)
