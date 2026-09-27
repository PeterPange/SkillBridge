# Write your first Python code

## Introduction

See the Text and images tab for more details!

Python is one of the world's most popular programming languages. It's known for its clear, readable syntax and broad versatility—used in everything from web development and data analysis to automation and artificial intelligence. Best of all, getting started with Python is straightforward, even if you've never written code before.

In this module, you take your first steps with Python. You learn how to display output to the console, how to get input from a user, and how to work with text. By the end of this module, you'll have built a small Python program that creates a personalized greeting.

Want to try using Ask Learn to clarify or guide you through this topic?

## Display output with print

See the Text and images tab for more details!

The most fundamental thing a program can do is communicate with you. In Python, you display output to the screen using the built-in print() function.

The print() function outputs text to the console. You call it by passing the text you want to display inside parentheses, enclosed in quotes:

Hello, world! You can try running this code yourself in an online python interpreter at https://aka.ms/python-coder .

Python doesn't care if you use single quotes ( ' ) or double quotes ( " ), as long as you match them up. For example, `print('Hello, world!') works the exact same way.

If you want to print words, you must use quotes. Omitting them tells Python to look for a variable instead of text. A variable acts as a container for a value. For example:

# This code is missing quotes around the text print(Hello) This code results in an error NameError: name 'Hello' is not defined . Don't panic if you see this; it just means Python is looking for a container that doesn't exist yet!

The # symbol is used to add comments to your code. Comments are notes for humans reading the code, and Python ignores them when running the program.

You can pass multiple values to print() by separating them with commas. Python automatically inserts a space between each item for you, which is great for combining text:

Hello world! Using escape characters Adding a space between items is helpful, but sometimes you need more control over how your text is formatted, like starting a new line, adding a tab space, or including quotation marks inside your text. You can't just press Enter or Tab inside your quotes to do this. Instead, Python uses escape characters , which act as secret commands inside your text. They always start with a backslash ( \ ) :

Make sure to use the backslash ( \ ) and not the forward slash ( / ). Typing /n will just print /n on your screen.

Want to try using Ask Learn to clarify or guide you through this topic?

## Accept user input

See the Text and images tab for more details!

Programs become truly powerful when they can interact with the people using them. Python's built-in input() function lets you pause your program, wait for the user to type something, and capture that information.

Think of the input() function as a question prompt. When Python hits this line, it waits until the user types their answer and presses the Enter key before continuing with the rest of the code.

To save their answer, you must "catch" it using a variable:

favorite_color = input("What is your favorite color? ") print("Oh, I love", favorite_color, "too!") In this code, favorite_color is a variable that catches the user's response. If the user types Blue and presses Enter , the output is:

What is your favorite color? Blue Oh, I love Blue too! You can try running this code yourself in an online python interpreter at https://aka.ms/python-coder .

Notice the blank space at the end of the prompt: "What is your favorite color? " . When accepting user input, add a space or new line before closing your quotes. If you don't, the user's typing will be glued directly to your text, looking messy like this: What is your favorite color?Blue

Before you go further, it helps to know that every value in Python has a data type , which is a label that tells Python what kind of value it's working with. For example, some common data types are:

Why does this matter? Python treats these two types very differently. You can add numbers together ( 25 + 1 equals 26 ), but you can't add a number to text ( "25" + 1 causes an error).

An essential rule to remember is that the input() function always returns text, even if the user types a number. For example:

age = input("How old are you? ") print("Next year you will be", age + 1) If you run this code and type 25 , you might expect it to print 26 . Instead, Python crashes and displays an error message in your console:

TypeError: can only concatenate str (not "int") to str Because the age is locked as text, you can't perform math operations on it just yet.

## Manipulate strings

See the Text and images tab for more details!

Text is one of the most common types of data in programming. In Python, text is represented as a string —a sequence of characters enclosed in single or double quotes. Python provides many built-in ways to manipulate and format strings.

You can join two or more strings together into a single string using the + operator:

first = "Hello" last = "world" message = first + ", " + last + "!" print(message) Output:

Hello, world! While concatenation works great for simple combinations, it can become complicated when you try to mix variables, punctuation, and spaces together.

A cleaner, modern way to combine strings and variables is with an f-string (short for formatted string). To create this kind of string, place the letter f directly outside your opening quotes, and place any variable names inside curly braces {} :

name = "Alex" print(f"Hello, {name}!") Output:

Hello, Alex! You can try running this code yourself in an online python interpreter at https://aka.ms/python-coder .

In the previous unit, we saw how input() + 1 resulted in a TypeError because Python can't mix text and numbers. F-strings solve this problem. In an f-string, Python automatically formats numbers inside curly braces into text:

age = input("How old are you? ") print(f"Next year you will be {age + 1}") # Works perfectly! Note

If you forget the f prefix (e.g., print("Hello, {name}") ), Python won't look inside the braces—it will literally print {name} on the screen.

Python strings have many built-in methods for common operations:

## Exercise - Create a personalized greeting

In this exercise, you write a Python program that asks the user for their name and displays a personalized greeting.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

Which function is used to display text output in Python?

What data type does the input() function always return?

Which Python feature lets you embed variable values directly inside a string?

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

See the Text and images tab for more details!

In this module, you wrote your first Python code.

You used the print() function to display output to the console, the input() function to accept input from a user, and common string operations to format and manipulate text. You combined these skills to build a Python program that creates a personalized greeting.

Want to try using Ask Learn to clarify or guide you through this topic?
