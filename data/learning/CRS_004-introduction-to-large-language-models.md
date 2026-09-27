# Introduction to large language models

## Introduction

You might be familiar with AI models that can analyze text, images, or audio. Each of these tasks requires a dedicated model. Large language models (LLMs) provide a new way to approach AI. LLMs are "general purpose" AI models, which means they're good at many things. LLM usage has the potential to improve workflows for people in many different professions.

Imagine you're a student thinking about creating a product that uses AI. You heard about LLMs and you might have experience using a feature like ChatGPT. To determine if this type of AI is right for your product, you need to learn the core concepts of LLMs and understand what scenarios LLMs are good for.

Understand LLMs and which one to use for what purpose.

Thank you to Gold Student Ambassador John Aziz for your help in writing this module

Want to try using Ask Learn to clarify or guide you through this topic?

## Understand LLMs

A large language model (LLM) is a type of AI that can process and produce natural language text. It learns from a massive amount of data gathered from sources like books, articles, webpages, and images to discover patterns and rules of language.

An LLM is built by using a neural network architecture. It takes an input, has several hidden layers that break down different aspects of language, and produces at the output layer.

People often report how the latest foundational model is bigger than the last, but what does this mean? In short, the more parameters a model has, the more data it can process, learn from, and generate.

For each connection between two neurons of the neural network architecture, there's a function: weight * input + bias. This network produces numerical values that determine how the model processes language.

LLMs are indeed large, and growing quickly. Some models could calculate millions of parameters in 2018. But today GPT-4 can calculate trillions of parameters.

A foundation model refers to a specific instance or version of an LLM. For example, GPT-3, GPT-4, or Codex.

Foundational models are trained and fine-tuned on a large corpus of text, or code if it's a Codex model instance.

A foundational model takes in training data in all different formats and uses a transformer architecture to build a general model. Adaptions and specializations can be created to achieve certain tasks via prompts or fine-tuning.

There are a few things that separate traditional NLPs from LLMs.

As important as it is to understand what an LLM can do, it's equally important to understand what it can't do so you choose the right tool for the job.

Understand language : An LLM is a predictive engine that pulls patterns together based on pre-existing text to produce more text. It doesn't understand language or math.

Understand facts : An LLM doesn't have separate modes for information retrieval and creative writing; it simply predicts the next most probable token.

## Core concepts of LLMs

There are a few core concepts that are important to understand to effectively use LLMs, namely tokens and prompts .

A text prompt is a sentence. An LLM understands several different languages. You can write prompts in your own language without the need to learn a specific language to work with the LLM. See the following examples of prompts:

Generate an image of a pink parrot with a pirate hat.

Create a web app in Python that handles customers.

The more specific you are about what you’re asking for, the better the result is.

A token is a basic unit text or code that an LLM can understand and process.

OpenAI natural language models don't operate on words or characters as units of text, but on something in-between: tokens.

OpenAI provides a useful tokenizer website that can help you understand how it tokenizes your requests. For more information, see OpenAI tokenizer .

After you start typing inside the OpenAI tokenizer prompt box, a counter appears to count the total number of tokens in the box.

If you're actively typing, the counter might take a few seconds to update.

Let's try to determine the number of tokens for the following words apple , blueberries , and Skarsgård .

Because the word apple is a common word, it requires one token to be represented. On the other hand, the word blueberries requires two tokens ( blue and berries ) to be represented. Unless the word is common, proper names like Skarsgård require multiple tokens to be represented.

## When to use LLMs

Overall, we recommend that you use large language models when you need to generate text, images, or even code.

There are three different categories of generative AI models:

Large language models can perform multiple natural language tasks, including:

Large language models are proficient in over a dozen programming languages, such as C#, JavaScript, Perl, PHP, and Python. By using LLMs to code, you can solve the following challenges:

For example, given the input "Write a for loop counting from 1 to 10 in Python," the following answer is provided:

for i in range(1,11): print(i) Image processing Large language models can create both realistic and artistic images, change the layout or style of an image, and create variations on a provided image. For example:

Image generation : LLMs can generate original images by using input text of what you would like the image to be. The more detailed you are, the more likely it is that the model produces the desired image.

Editing an image : LLMs can edit an image by using input text of what you would like changed about the image. You can change the style of an image, add or remove items, or generate new content to add.

Image variations : LLMs can generate variations of an image by using the image itself and input text specifying how many variations of the image to produce. The original image stays the same, but the color, background scene, and where the objects are located might change in variations.

Want to try using Ask Learn to clarify or guide you through this topic?

## Which model to use

There are many factors, including cost, availability, performance, and capability, to consider when choosing which LLM to use. Generally, we recommend the following guides:

gpt-35-turbo : This model is economical, performs well, and, despite the ChatGPT name, can be used for a wide range of tasks beyond chat and conversation.

gpt-35-turbo-16k , gpt-4 or gpt-4-32k : These models are a good choice if you need to generate more than 4,096 tokens or need to support larger prompts. However, these models are more expensive, can be slower, and might have limited availability.

Embedding models : If your tasks include search, clustering, recommendations, and anomaly detection, you should use an embedding model. Computers can easily utilize a vector of numbers that form the embedding. The embedding is an information-dense representation of the semantic meaning of a piece of text. The distance between two embeddings in the vector space is correlated with semantic similarity. For example, if two texts are similar, then their vector representations are also similar.

DALL-E : This model generates images from text prompts. DALL-E differs from other language models because its output is an image, not text.

Whisper : This model is trained on a large dataset of English audio and text. Whisper is optimized for speech-to-text capabilities like transcribing audio files. It can be used to transcribe audio files that contain speech in languages other than English, but the output of the model is English text. Use Whisper to quickly transcribe audio files one at a time, translate audio from other languages into English, or provide your prompt to the model to guide the output.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

Check your knowledge by answering the following questions.

What is the purpose of a Large language model (LLM)?

To process and produce natural language text by learning from a massive amount of text data to discover patterns and rules of language.

To exhibit anthropomorphism and understand emotions.

What is the difference between traditional Natural language processing (NLP) and Large language models (LLMs)?

Traditional NLP uses many terabytes of unlabeled data in the foundation model, while LLMs provide a set of labeled data to train the machine-learning model.

Traditional NLP is highly optimized for specific use cases, while LLMs describe in natural language what you want the model to do.

Traditional NLP requires one model per capability, while LLMs use a single model for many natural language use cases.

What is the purpose of tokenization in natural language models?

To represent text in a manner that's meaningful for machines without losing its context, so that algorithms can more easily identify patterns.

To generate text on a letter-by-letter basis.

To represent common words with a single token.

## Summary

In this module, you learned what large language models are and how they're more “general purpose” than traditional AI models. LLMs are great to use for various tasks including chat, conversation, image modification, coding, and anomaly detection.

You also learned core concepts like prompts, tokens, and completions.

Finally, you were introduced to different models like gpt-35-turbo, embedding models, and DALL-E. You learned which model to use for what purpose and how to choose the right model for your needs.

Want to try using Ask Learn to clarify or guide you through this topic?
