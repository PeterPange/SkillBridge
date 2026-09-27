# Explore and analyze data with Python

## Introduction

Unsurprisingly, the role of a data scientist primarily involves exploring and analyzing data. Although the end result of data analysis might be a report or a machine learning model, data scientists begin their work with data, with Python being the most popular programming language data scientists use for working with data.

After decades of open-source development, Python provides extensive functionality with powerful statistical and numerical libraries:

Usually, a data-analysis project is designed to establish insights around a particular scenario or to test a hypothesis.

For example, suppose a university professor collects data about their students, including the number of lectures attended, the hours spent studying, and the final grade achieved on the end of term exam. The professor could analyze the data to determine if there is a relationship between the amount of studying a student undertakes and the final grade they achieve. The professor might use the data to test a hypothesis that only students who study for a minimum number of hours can expect to achieve a passing grade.

In this training module, we'll explore and analyze grade data for a fictitious university class from a professor's point of view. We'll use Jupyter notebooks and several Python tools and libraries to clean the data set, apply statistical techniques to test several hypotheses about the data, and visualize the data to determine the relationships between variables.

Want to try using Ask Learn to clarify or guide you through this topic?

## Explore data with NumPy and Pandas

Data scientists can use various tools and techniques to explore, visualize, and manipulate data. One of the most common ways in which data scientists work with data is to use the Python language and some specific packages for data processing.

NumPy is a Python library that provides functionality comparable to mathematical tools such as MATLAB and R. While NumPy significantly simplifies the user experience, it also offers comprehensive mathematical functions.

Pandas is an extremely popular Python library for data analysis and manipulation. Pandas is like a spreadsheet application for Python, providing easy-to-use functionality for data tables.

Notebooks are a popular way of running basic scripts using your web browser. Typically, these notebooks are a single webpage, broken up into text sections and code sections that can be run individually.

Data exploration and analysis is typically an iterative process, in which the data scientist takes a sample of data and performs the following kinds of tasks to analyze it and test hypotheses:

Want to try using Ask Learn to clarify or guide you through this topic?

## Exercise - Explore data with NumPy and Pandas

Now it's your opportunity to explore some data for yourself.

In this exercise, you'll use a lightweight Python notebook tool that's been developed specifically for this training. The notebook tool runs in your browser, so there's no need to install anything or sign into a cloud service. You just need a modern browser, like Microsoft Edge, with JavaScript enabled.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Visualize data

Data scientists visualize data to understand it better. They might scan the raw data, examine summary measures such as averages, or graph the data. Graphs are a powerful means of visualizing data, and data scientists often use graphs to discern moderately complex patterns quickly.

Graphing is done to provide a fast qualitative assessment of our data, which can be useful for understanding results, finding outlier values, examining how numbers are distributed, and so on.

While sometimes we know ahead of time what kind of graph will be most useful, other times we use graphs in an exploratory way. To understand the power of data visualization, consider the following data: the location (x,y) of a self-driving car. In the data's raw form, it's hard to see any real patterns. The mean or average tells us that the car's path was centred around x=0.2 and y=0.3, and the range of numbers appears to be between about -2 and 2.

If we now plot Location-X over time, we can see that we appear to have some missing values between times 7 and 12.

If we graph X versus Y, we end up with a map of where the car has driven. It’s instantly obvious that the car has been driving in a circle and at some point drove to the center of that circle.

Graphs aren't limited to 2D scatter plots like those above. They can be used to explore other aspects of your data; for example, proportions (pie charts and stacked bar graphs) and how the data are spread (histograms and box-and-whisker plots). Often, when we're trying to understand raw data or results, we might experiment with different types of graphs until we come across one that explains the data in a visually intuitive way.

Want to try using Ask Learn to clarify or guide you through this topic?

## Exercise - Visualize data with Matplotlib

In this exercise, you'll use a lightweight Python notebook tool that's been developed specifically for this training. The notebook tool runs in your browser, so there's no need to install anything or sign into a cloud service. You just need a modern browser, like Microsoft Edge, with JavaScript enabled.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Examine real world data

Data presented in educational material is often remarkably perfect, designed to show students how to find clear relationships between variables. "Real-world" data is a bit less simple.

Because of the complexity of "real-world" data, we have to inspect raw data for issues before we use it.

As such, the best practice is to inspect the raw data and process it before use, which reduces errors or issues typically by removing erroneous data points or modifying the data into a more useful form.

Real-world data can contain many different issues that can affect the utility of the data and our interpretation of the results.

It's important to realize that most real-world data are influenced by factors that weren't recorded at the time. For example, we might have a table of race-car track times alongside engine sizes; but various other factors that weren't written down, such as the weather, probably also played a role. If problematic, we can often reduce the influence of these factors by increasing the size of the dataset.

In other situations, data points that are clearly outside of what's expected—also known as " outliers "—can sometimes be safely removed from analyses, although we must take care to not remove data points that provide real insights.

Another common issue in real-world data is bias. Bias refers to a tendency to select certain types of values more frequently than others in a way that misrepresents the underlying population, or "real world". Bias can sometimes be identified by exploring data while keeping in mind basic knowledge about where the data came from.

Real-world data will always have issues, but data scientists can often overcome these issues by:

Want to try using Ask Learn to clarify or guide you through this topic?

## Exercise - Examine real world data

Now let's take a look at some more complex analysis techniques that reflect real-world data distributions.

In this exercise, you'll use a lightweight Python notebook tool that's been developed specifically for this training. The notebook tool runs in your browser, so there's no need to install anything or sign into a cloud service. You just need a modern browser, like Microsoft Edge, with JavaScript enabled.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

Answer the following questions to check your learning.

You have a NumPy array with the shape (2,20). What does this tell you about the elements in the array?

The array is two dimensional, consisting of two arrays each with 20 elements

The array contains 2 elements, with the values 2 and 20

The array contains 20 elements, all with the value 2

You have a Pandas DataFrame named df_sales containing daily sales data. The DataFrame contains the following columns: year, month, day_of_month, sales_total. You want to find the average sales_total value. Which code should you use?

You have a DataFrame containing data about daily ice cream sales. You use the corr method to compare the avg_temp and units_sold columns, and get a result of 0.97. What does this result indicate?

On the day with the maximum units_sold value, the avg_temp value was 0.97

Days with high avg_temp values tend to coincide with days that have high units_sold values

The units_sold value is, on average, 97% of the avg_temp value

You must answer all questions before checking your work.

You must answer all questions before checking your work.

## Summary

In this module, you learned how to use Python to explore, visualize, and manipulate data. Data exploration is at the core of data science and is a key element in data analysis and machine learning.

Machine learning is a subset of data science that deals with predictive modeling. In other words, machine learning uses data to create predictive models in order to predict unknown values. You might use machine learning to predict how much food a supermarket needs to order or to identify plants in photographs.

Machine learning works by identifying relationships between data values that describe the characteristics of something (its features , such as the height and color of a plant) and the value we want to predict (the label , such as the species of plant). These relationships are built into a model through a training process.

Want to try using Ask Learn to clarify or guide you through this topic?
