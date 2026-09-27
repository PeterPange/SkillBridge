# Introduction to DevOps principles for machine learning

## Introduction

There's an increase in machine learning projects across organizations due to more data being available, the democratization of compute power, and the advancement in algorithms used to train models.

However, one of the main obstacles when adopting and scaling machine learning projects is a lack of a clear strategy and organizational silos.

Machine learning operations or MLOps aims to more efficiently scale from a proof of concept or pilot project to a machine learning workload in production.

Implementing MLOps helps you to make your machine learning workloads robust and reproducible. For example, you'll be able to monitor, retrain, and redeploy a model whenever needed while always keeping a model in production.

The purpose of MLOps is to make the machine learning lifecycle scalable:

MLOps requires multiple roles and multiple tools. Data scientists often focus on all tasks related to training the model, also referred to as the inner loop .

To package and deploy the model, data scientists may need the help of machine learning engineers who apply DevOps practices to scale the machine learning models.

Taking a trained model and deploying it to production is often referred to as the outer loop . In the outer loop, the model is packaged, validated, deployed, and monitored. When you decide the model needs to be retrained, you go back to the inner loop to make changes to the model.

Using DevOps principles like agile planning can help your team organize your work and produce deliverables more quickly. With source control , you can facilitate the collaboration on projects. And with automation you can accelerate the machine learning lifecycle.

This module will introduce you to these DevOps principles and highlight two tools commonly used: Azure DevOps and GitHub .

Want to try using Ask Learn to clarify or guide you through this topic?

## DevOps for machine learning

DevOps is described as the union of people, process, and products to enable continuous delivery of value to our end users , by Donovan Brown in What is DevOps? .

To understand how it is of use when working with machine learning models, let's explore some essential DevOps principles further.

DevOps is a combination of tools and practices guiding developers in creating robust and reproducible applications. The goal of using DevOps principles is to quickly deliver value to the end user.

If you want to more easily deliver value by integrating machine learning models in data transformation pipelines or real-time applications, you'll benefit from implementing DevOps principles. Learning about DevOps will help you to organize and automate your work.

Creating, deploying, and monitoring robust and reproducible models to deliver value to the end user is the goal of machine learning operations ( MLOps ).

There are three processes that we want to combine whenever we talk about machine learning operations (MLOps):

ML includes all the machine learning workloads for which a data scientist is responsible. A data scientist will do:

DEV refers to the software development, which includes:

Let's go over some DevOps principles that are essential for MLOps.

One of the core principles of DevOps is automation . By automating tasks, we aspire to get new models deployed to production faster. Through automating, you'll also create reproducible models that are reliable and consistent across environments.

Especially when you want to improve your model regularly over time, automation allows you to do all necessary activities quickly to ensure the model in production is always the best performing model.

A key concept to achieve automation is CI/CD , which stands for continuous integration and continuous delivery .

## DevOps tools

Azure DevOps is a platform created by Microsoft, which includes several services to help you with many of the DevOps activities.

Some tools offered by the cloud-hosted Azure DevOps include:

In addition to these three, Azure DevOps offers more tools to help organizations with their DevOps journey. Azure DevOps is designed as a platform, which means that you choose which of the tools you want to use. You aren't required to use all that Azure DevOps has to offer.

Many of the Azure DevOps tools work with a large variety of languages and are cross-platform. As we're exploring the relevance of DevOps principles and tools for machine learning projects, we'll focus on working with Python and Linux as they're most commonly used.

GitHub is an open-source development platform owned by Microsoft, which includes several DevOps tools like:

GitHub and Git are often used together but aren't the same. Git focuses on source control and can be accessed from various tools. GitHub is a specific code-hosting provider that offers the Git system through a web-based graphical interface and combines Git repositories with other DevOps tools.

Git is a distributed source control system. Although there are other source control systems, Git is the most popular system available today and widely used for both open-source frameworks and machine learning projects.

The essential idea with Git is distributing the source control, meaning that every team member works on their own copy of the complete repository.

To work on a project simultaneously, Git offers trunk-based development with branching capabilities. By creating branches for your code project, you can edit the code without touching the main copy of the project. Once you complete your changes to the code, you can merge it with the main copy, for example via a pull request.

Learn more about source control systems with Microsoft Learn

Want to try using Ask Learn to clarify or guide you through this topic?

## Integrate Azure Machine Learning with DevOps tools

Imagine you work with a data science team on a machine learning project. Your team can choose to use Azure DevOps or GitHub to plan work, store the code repository, and automate workflows.

With either sets of tools, there are generally two roles:

The administrator is responsible for connecting Azure Machine Learning with either Azure DevOps or GitHub. To understand how the integration with Azure Machine Learning is set up, let's explore how an administrator would securely connect Azure DevOps and GitHub with Azure Machine Learning.

To connect Azure DevOps with Azure Machine Learning, you'll first need to create an organization and a project. You'll use the organization to group and manage projects.

Start by signing in to Azure DevOps with a Microsoft or GitHub account.

Once signed in, you can create an organization .

Within an organization, you can create multiple projects .

For each project, you'll have access to tools like Boards , Repos , and Pipelines to apply DevOps principles in your project.

To securely access your Azure Machine Learning workspace from Azure DevOps, you'll have to create a service connection .

When you create a service connection, you define how Azure DevOps will be authenticated to connect to another service. When you work with Azure Machine Learning, the recommended option is to let Azure DevOps create a service principal for you.

A service principal is created as an identity in the Microsoft Entra ID . Instead of using a team member's credentials to connect with Azure Machine Learning, Azure DevOps uses the service principal's credentials.

When an Azure DevOps project is created, you can connect to an existing Azure Machine Learning workspace:

## Module assessment

Which tool can be used for agile planning when working with Azure DevOps?

Which activity may be a part of continuous integration?

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

Want to try using Ask Learn to clarify or guide you through this topic?
