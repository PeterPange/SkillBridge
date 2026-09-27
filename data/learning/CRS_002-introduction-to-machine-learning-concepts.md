# Introduction to machine learning concepts

## Introduction

Machine learning is in many ways the intersection of two disciplines - data science and software engineering. The goal of machine learning is to use data to create a predictive model that can be incorporated into a software application or service. To achieve this goal requires collaboration between data scientists who explore and prepare the data before using it to train a machine learning model, and software developers who integrate the models into applications where they're used to predict new data values (a process known as inferencing ).

Machine learning has its origins in statistics and mathematical modeling of data. The fundamental idea of machine learning is to use data from past observations to predict unknown outcomes or values. For example:

We recognize that different people like to learn in different ways. You can choose to complete this module in video-based format or you can read the content as text and images. The text contains greater detail than the videos, so in some cases you might want to refer to it as supplemental material to the video presentation.

Want to try using Ask Learn to clarify or guide you through this topic?

## Machine learning models

See the Text and images tab for more details!

Because machine learning is based on mathematics and statistics, it's common to think about machine learning models in mathematical terms. Fundamentally, a machine learning model is a software application that encapsulates a function to calculate an output value based on one or more input values. The process of defining that function is known as training . After the function has been defined, you can use it to predict new values in a process called inferencing .

Let's explore the steps involved in training and inferencing.

The training data consists of past observations. In most cases, the observations include the observed attributes or features of the thing being observed, and the known value of the thing you want to train a model to predict (known as the label ).

In mathematical terms, you'll often see the features referred to using the shorthand variable name x , and the label referred to as y . Usually, an observation consists of multiple feature values, so x is actually a vector (an array with multiple values), like this: [x 1 ,x 2 ,x 3 ,...] .

To make this clearer, let's consider the examples described previously:

An algorithm is applied to the data to try to determine a relationship between the features and the label, and generalize that relationship as a calculation that can be performed on x to calculate y . The specific algorithm used depends on the kind of predictive problem you're trying to solve (more about this later), but the basic principle is to try to fit the data to a function in which the values of the features can be used to calculate the label.

The result of the algorithm is a model that encapsulates the calculation derived by the algorithm as a function - let's call it f . In mathematical notation:

Now that the training phase is complete, the trained model can be used for inferencing . The model is essentially a software program that encapsulates the function produced by the training process. You can input a set of feature values, and receive as an output a prediction of the corresponding label. Because the output from the model is a prediction that was calculated by the function, and not an observed value, you'll often see the output from the function shown as ŷ (which is rather delightfully verbalized as "y-hat").

Want to try using Ask Learn to clarify or guide you through this topic?

## Types of machine learning model

See the Text and images tab for more details!

There are multiple types of machine learning, and you must apply the appropriate type depending on what you're trying to predict. A breakdown of common types of machine learning is shown in the following diagram.

Supervised machine learning is a general term for machine learning algorithms in which the training data includes both feature values and known label values. Supervised machine learning is used to train models by determining a relationship between the features and labels in past observations, so that unknown labels can be predicted for features in future cases.

Regression is a form of supervised machine learning in which the label predicted by the model is a numeric value. For example:

Classification is a form of supervised machine learning in which the label represents a categorization, or class . There are two common classification scenarios.

In binary classification , the label determines whether the observed item is (or isn't ) an instance of a specific class. Or put another way, binary classification models predict one of two mutually exclusive outcomes. For example:

In all of these examples, the model predicts a binary true / false or positive/negative prediction for a single possible class.

Multiclass classification extends binary classification to predict a label that represents one of multiple possible classes. For example,

In most scenarios that involve a known set of multiple classes, multiclass classification is used to predict mutually exclusive labels. For example, a penguin can't be both a Gentoo and an Adelie . However, there are also some algorithms that you can use to train multilabel classification models, in which there may be more than one valid label for a single observation. For example, a movie could potentially be categorized as both science fiction and comedy .

Unsupervised machine learning involves training models using data that consists only of feature values without any known labels. Unsupervised machine learning algorithms determine relationships between the features of the observations in the training data.

The most common form of unsupervised machine learning is clustering . A clustering algorithm identifies similarities between observations based on their features, and groups them into discrete clusters. For example:

In some ways, clustering is similar to multiclass classification; in that it categorizes observations into discrete groups. The difference is that when using classification, you already know the classes to which the observations in the training data belong; so the algorithm works by determining the relationship between the features and the known classification label. In clustering, there's no previously known cluster label and the algorithm groups the data observations based purely on similarity of features.

## Regression

See the Text and images tab for more details!

Regression models are trained to predict numeric label values based on training data that includes both features and known labels. The process for training a regression model (or indeed, any supervised machine learning model) involves multiple iterations in which you use an appropriate algorithm (usually with some parameterized settings) to train a model, evaluate the model's predictive performance, and refine the model by repeating the training process with different algorithms and parameters until you achieve an acceptable level of predictive accuracy.

The diagram shows four key elements of the training process for supervised machine learning models:

After each train, validate, and evaluate iteration, you can repeat the process with different algorithms and parameters until an acceptable evaluation metric is achieved.

Let's explore regression with a simplified example in which we'll train a model to predict a numeric label ( y ) based on a single feature value ( x ). Most real scenarios involve multiple feature values, which adds some complexity; but the principle is the same.

For our example, let's stick with the ice cream sales scenario we discussed previously. For our feature, we'll consider the temperature (let's assume the value is the maximum temperature on a given day), and the label we want to train a model to predict is the number of ice creams sold that day. We'll start with some historic data that includes records of daily temperatures ( x ) and ice cream sales ( y ):

We'll start by splitting the data and using a subset of it to train a model. Here's the training dataset:

To get an insight of how these x and y values might relate to one another, we can plot them as coordinates along two axes, like this:

Now we're ready to apply an algorithm to our training data and fit it to a function that applies an operation to x to calculate y . One such algorithm is linear regression , which works by deriving a function that produces a straight line through the intersections of the x and y values while minimizing the average distance between the line and the plotted points, like this:

The line is a visual representation of the function in which the slope of the line describes how to calculate the value of y for a given value of x . The line intercepts the x axis at 50, so when x is 50, y is 0. As you can see from the axis markers in the plot, the line slopes so that every increase of 5 along the x axis results in an increase of 5 up the y axis; so when x is 55, y is 5; when x is 60, y is 10, and so on. To calculate a value of y for a given value of x , the function simply subtracts 50; in other words, the function can be expressed like this:

You can use this function to predict the number of ice creams sold on a day with any given temperature. For example, suppose the weather forecast tells us that tomorrow it will be 77 degrees. We can apply our model to calculate 77-50 and predict that we'll sell 27 ice creams tomorrow.

To validate the model and evaluate how well it predicts, we held back some data for which we know the label ( y ) value. Here's the data we held back:

## Binary classification

See the Text and images tab for more details!

Classification, like regression, is a supervised machine learning technique; and therefore follows the same iterative process of training, validating, and evaluating models. Instead of calculating numeric values like a regression model, the algorithms used to train classification models calculate probability values for class assignment and the evaluation metrics used to assess model performance compare the predicted classes to the actual classes.

Binary classification algorithms are used to train a model that predicts one of two possible labels for a single class. Essentially, predicting true or false . In most real scenarios, the data observations used to train and validate the model consist of multiple feature ( x ) values and a y value that is either 1 or 0 .

To understand how binary classification works, let's look at a simplified example that uses a single feature ( x ) to predict whether the label y is 1 or 0. In this example, we'll use the blood glucose level of a patient to predict whether or not the patient has diabetes. Here's the data with which we'll train the model:

To train the model, we'll use an algorithm to fit the training data to a function that calculates the probability of the class label being true (in other words, that the patient has diabetes). Probability is measured as a value between 0.0 and 1.0, such that the total probability for all possible classes is 1.0. So for example, if the probability of a patient having diabetes is 0.7, then there's a corresponding probability of 0.3 that the patient isn't diabetic.

There are many algorithms that can be used for binary classification, such as logistic regression , which derives a sigmoid (S-shaped) function with values between 0.0 and 1.0, like this:

Despite its name, in machine learning logistic regression is used for classification, not regression. The important point is the logistic nature of the function it produces, which describes an S-shaped curve between a lower and upper value (0.0 and 1.0 when used for binary classification).

The function produced by the algorithm describes the probability of y being true ( y =1) for a given value of x . Mathematically, you can express the function like this:

For three of the six observations in the training data, we know that y is definitely true , so the probability for those observations that y =1 is 1.0 and for the other three, we know that y is definitely false , so the probability that y =1 is 0.0 . The S-shaped curve describes the probability distribution so that plotting a value of x on the line identifies the corresponding probability that y is 1 .

The diagram also includes a horizontal line to indicate the threshold at which a model based on this function will predict true ( 1 ) or false ( 0 ). The threshold lies at the mid-point for y ( P(y) = 0.5 ). For any values at this point or above, the model will predict true ( 1 ); while for any values below this point it will predict false ( 0 ). For example, for a patient with a blood glucose level of 90, the function would result in a probability value of 0.9. Since 0.9 is higher than the threshold of 0.5, the model would predict true ( 1 ) - in other words, the patient is predicted to have diabetes.

As with regression, when training a binary classification model you hold back a random subset of data with which to validate the trained model. Let's assume we held back the following data to validate our diabetes classifier:

Applying the logistic function we derived previously to the x values results in the following plot.

## Multiclass classification

See the Text and images tab for more details!

Multiclass classification is used to predict to which of multiple possible classes an observation belongs. As a supervised machine learning technique, it follows the same iterative train, validate, and evaluate process as regression and binary classification in which a subset of the training data is held back to validate the trained model.

Multiclass classification algorithms are used to calculate probability values for multiple class labels, enabling a model to predict the most probable class for a given observation.

Let's explore an example in which we have some observations of penguins, in which the flipper length ( x ) of each penguin is recorded. For each observation, the data includes the penguin species ( y ), which is encoded as follows:

As with previous examples in this module, a real scenario would include multiple feature ( x ) values. We'll use a single feature to keep things simple.

To train a multiclass classification model, we need to use an algorithm to fit the training data to a function that calculates a probability value for each possible class. There are two kinds of algorithm you can use to do this:

One-vs-Rest algorithms train a binary classification function for each class, each calculating the probability that the observation is an example of the target class. Each function calculates the probability of the observation being a specific class compared to any other class. For our penguin species classification model, the algorithm would essentially create three binary classification functions:

Each algorithm produces a sigmoid function that calculates a probability value between 0.0 and 1.0. A model trained using this kind of algorithm predicts the class for the function that produces the highest probability output.

As an alternative approach is to use a multinomial algorithm, which creates a single function that returns a multi-valued output. The output is a vector (an array of values) that contains the probability distribution for all possible classes - with a probability score for each class which when totaled add up to 1.0:

An example of this kind of function is a softmax function, which could produce an output like the following example:

The elements in the vector represent the probabilities for classes 0, 1, and 2 respectively; so in this case, the class with the highest probability is 2 .

Regardless of which type of algorithm is used, the model uses the resulting function to determine the most probable class for a given set of features ( x ) and predicts the corresponding class label ( y ).

## Clustering

See the Text and images tab for more details!

Clustering is a form of unsupervised machine learning in which observations are grouped into clusters based on similarities in their data values, or features. This kind of machine learning is considered unsupervised because it doesn't make use of previously known label values to train a model. In a clustering model, the label is the cluster to which the observation is assigned, based only on its features.

For example, suppose a botanist observes a sample of flowers and records the number of leaves and petals on each flower:

There are no known labels in the dataset, just two features . The goal is not to identify the different types (species) of flower; just to group similar flowers together based on the number of leaves and petals.

There are multiple algorithms you can use for clustering. One of the most commonly used algorithms is K-Means clustering, which consists of the following steps:

The following animation shows this process:

Since there's no known label with which to compare the predicted cluster assignments, evaluation of a clustering model is based on how well the resulting clusters are separated from one another.

There are multiple metrics that you can use to evaluate cluster separation, including:

Want to try using Ask Learn to clarify or guide you through this topic?

## Deep learning

See the Text and images tab for more details!

Deep learning is an advanced form of machine learning that tries to emulate the way the human brain learns. The key to deep learning is the creation of an artificial neural network that simulates electrochemical activity in biological neurons by using mathematical functions, as shown here.

Artificial neural networks are made up of multiple layers of neurons - essentially defining a deeply nested function. This architecture is the reason the technique is referred to as deep learning and the models produced by it are often referred to as deep neural networks (DNNs). You can use deep neural networks for many kinds of machine learning problem, including regression and classification, as well as more specialized models for natural language processing and computer vision.

Just like other machine learning techniques discussed in this module, deep learning involves fitting training data to a function that can predict a label ( y ) based on the value of one or more features ( x ). The function ( f(x) ) is the outer layer of a nested function in which each layer of the neural network encapsulates functions that operate on x and the weight ( w ) values associated with them. The algorithm used to train the model involves iteratively feeding the feature values ( x ) in the training data forward through the layers to calculate output values for ŷ , validating the model to evaluate how far off the calculated ŷ values are from the known y values (which quantifies the level of error, or loss , in the model), and then modifying the weights ( w ) to reduce the loss. The trained model includes the final weight values that result in the most accurate predictions.

To better understand how a deep neural network model works, let's explore an example in which a neural network is used to define a classification model for penguin species.

The feature data ( x ) consists of some measurements of a penguin. Specifically, the measurements are:

In this case, x is a vector of four values, or mathematically, x=[x1,x2,x3,x4] .

The label we're trying to predict ( y ) is the species of the penguin, and that there are three possible species it could be:

This is an example of a classification problem, in which the machine learning model must predict the most probable class to which an observation belongs. A classification model accomplishes this by predicting a label that consists of the probability for each class. In other words, y is a vector of three probability values; one for each of the possible classes: [P(y=0|x), P(y=1|x), P(y=2|x)] .

The process for inferencing a predicted penguin class using this network is:

The weights in a neural network are central to how it calculates predicted values for labels. During the training process, the model learns the weights that will result in the most accurate predictions. Let's explore the training process in a little more detail to understand how this learning takes place.

While it's easier to think of each case in the training data being passed through the network one at a time, in reality the data is batched into matrices and processed using linear algebraic calculations. For this reason, neural network training is best performed on computers with graphical processing units (GPUs) that are optimized for vector and matrix manipulation.

## Exercise - Explore machine learning scenarios

Now it's your chance to train and test machine learning models.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

You want to create a model to predict the cost of heating an office building based on its size in square feet and the number of employees working there. What kind of machine learning problem is this?

You need to evaluate a classification model. Which metric can you use? ​​

The difference between predicted and actual label values

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

Machine learning is the foundation on which artificial intelligence is built. In this module, you've learned about some of the core principles and concepts on which machine learning is based, and about the different kinds of model you can train and evaluate.

To learn more about how machine learning can help organizations get predictive insights from their data, see What is machine learning?

Want to try using Ask Learn to clarify or guide you through this topic?
