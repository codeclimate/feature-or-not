#!/usr/bin/env python3

import math

from matplotlib import cm
from matplotlib import gridspec
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from sklearn import metrics
import tensorflow as tf
from tensorflow.python.data import Dataset


tf.logging.set_verbosity(tf.logging.ERROR)
pd.options.display.max_rows = 10
pd.options.display.float_format = '{:.1f}'.format

pull_requests_dataframe = pd.read_csv("/pull_requests.csv")

pull_requests_dataframe = pull_requests_dataframe.reindex(
        np.random.permutation(pull_requests_dataframe.index))
pull_requests_dataframe

"""
To get started with ML, first predict one label from one feature
We will predict time-to-review based on the size of the PR
"""
def my_input_fn(features, targets, batch_size=1, shuffle=True, num_epochs=None):
    """Trains a linear regression model of one feature.
    See: https://developers.google.com/machine-learning/crash-course/first-steps-with-tensorflow/programming-exercises

    Args:
      features: pandas DataFrame of features
      targets: pandas DataFrame of targets
      batch_size: Size of batches to be passed to the model
      shuffle: True or False. Whether to shuffle the data.
      num_epochs: Number of epochs for which data should be repeated. None = repeat indefinitely
    Returns:
      Tuple of (features, labels) for next data batch
    """

    # Convert pandas data into a dict of np arrays.
    features = {key:np.array(value) for key,value in dict(features).items()}

    # Construct a dataset, and configure batching/repeating.
    ds = Dataset.from_tensor_slices((features,targets)) # warning: 2GB limit
    ds = ds.batch(batch_size).repeat(num_epochs)

    # Shuffle the data, if specified.
    if shuffle:
      ds = ds.shuffle(buffer_size=10000)

    # Return the next batch of data.
    features, labels = ds.make_one_shot_iterator().get_next()
    return features, labels

# Filter out rows where time to review is null
filtered_pull_requests_dataframe = pull_requests_dataframe[pull_requests_dataframe['time_to_review_in_minutes'].notnull()]

# Define the input feature: size (additions + deletions).
my_feature = filtered_pull_requests_dataframe[["time_to_review_in_minutes"]]

# Configure a numeric feature column for time_to_review_in_minutes.
feature_columns = [tf.feature_column.numeric_column("time_to_review_in_minutes")]

# Define the label.
targets = filtered_pull_requests_dataframe["time_to_review_in_minutes"]

# Use gradient descent as the optimizer for training the model.
my_optimizer=tf.train.GradientDescentOptimizer(learning_rate=0.00002)
my_optimizer = tf.contrib.estimator.clip_gradients_by_norm(my_optimizer, 5.0)

# Configure the linear regression model with our feature columns and optimizer.
# Set a learning rate of 0.0000001 for Gradient Descent.
linear_regressor = tf.estimator.LinearRegressor(
    feature_columns=feature_columns,
    optimizer=my_optimizer
)

_ = linear_regressor.train(
    input_fn = lambda:my_input_fn(my_feature, targets, batch_size=5),
    steps=500
)

def serving_input_fn():
    feature = tf.convert_to_tensor(my_feature)
    inputs = {'time_to_review_in_minutes': feature}
    return tf.estimator.export.ServingInputReceiver(inputs, inputs)

# linear_regressor.export_savedmodel("/tmp", serving_input_fn, as_text=True)

# Create an input function for predictions.
# Note: Since we're making just one prediction for each example, we don't
# need to repeat or shuffle the data here.
prediction_input_fn =lambda: my_input_fn(my_feature, targets, num_epochs=1, shuffle=False)

# Call predict() on the linear_regressor to make predictions.
predictions = linear_regressor.predict(input_fn=prediction_input_fn)

# Format predictions as a NumPy array, so we can calculate error metrics.
predictions = np.array([item['predictions'][0] for item in predictions])

# Print Mean Squared Error and Root Mean Squared Error.
mean_squared_error = metrics.mean_squared_error(predictions, targets)
root_mean_squared_error = math.sqrt(mean_squared_error)
print("Mean Squared Error (on training data): %0.3f" % mean_squared_error)
print("Root Mean Squared Error (on training data): %0.3f" % root_mean_squared_error)

calibration_data = pd.DataFrame()
calibration_data["predictions"] = pd.Series(predictions)
calibration_data["targets"] = pd.Series(targets)
print(calibration_data.describe())

sample = filtered_pull_requests_dataframe.sample(n=500)
# Get the min and max total_rooms values.
x_0 = sample["size"].min()
x_1 = sample["size"].max()

# Retrieve the final weight and bias generated during training.
weight = linear_regressor.get_variable_value('linear/linear_model/size/weights')[0]
bias = linear_regressor.get_variable_value('linear/linear_model/bias_weights')

# Get the predicted median_house_values for the min and max total_rooms values.
y_0 = weight * x_0 + bias
y_1 = weight * x_1 + bias

# Plot our regression line from (x_0, y_0) to (x_1, y_1).
plt.plot([x_0, x_1], [y_0, y_1], c='r')

# Label the graph axes.
plt.ylabel("time_to_review_in_minutes")
plt.xlabel("size")

# Plot a scatter plot from our data sample.
plt.scatter(sample["size"], sample["time_to_review_in_minutes"])

# Save graph.
plt.savefig("/tmp/fig.png")
