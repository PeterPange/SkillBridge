# Introduction to DevOps

## Introduction

"DevOps is the union of people, process, and products to enable continuous delivery of value to our end users." - Donovan Brown in What is DevOps?

Consider Netflix's journey: they transformed from a DVD-by-mail service to a global streaming platform by adopting DevOps practices. They dramatically reduced deployment times and achieved multiple daily deployments while maintaining high system availability. This transformation enabled them to respond rapidly to market demands and customer feedback.

Similarly, Microsoft's own transformation journey demonstrates the power of DevOps. Microsoft moved from traditional waterfall development with multi-year release cycles to continuous deployment, now releasing updates to Azure services multiple times per day. This cultural and technical transformation enabled Microsoft to become one of the world's leading cloud providers.

The DevOps learning paths will help you prepare for a comprehensive DevOps transformation. You'll learn the main characteristics of the DevOps process, tools, and people involved during the lifecycle. This module also prepares you for the Microsoft DevOps Solution certification exam (AZ-400). The content includes real-world scenarios, hands-on exercises, reference links, interactive assessments, and practical templates you can use in your organization.

By completing this module, you'll master the foundational concepts needed to lead or participate in a DevOps transformation:

Before starting your DevOps journey, evaluate your current state:

If you answered "yes" to most questions, you're ready to begin. If not, consider addressing these areas first.

Plan before you act. This module will help you understand what DevOps is and how to plan for a DevOps transformation journey with practical, actionable guidance.

The DevOps transformation journey is a comprehensive series of 8 learning paths that will take you from intermediate DevOps practices to advanced implementation. This journey familiarizes you with both Azure DevOps and GitHub platforms, their services, features, and integrations with third-party tools to support your complete DevOps process.

DevOps skills are highly valued in the technology industry as organizations increasingly adopt cloud-native practices and continuous delivery models. The skills you'll develop are in high demand across industries as organizations seek to:

People in these modules are interested in designing and implementing DevOps processes. Also, they're preparing for the AZ-400 - Design and Implement Microsoft DevOps Solutions certification exam.

The certification exam is for DevOps professionals. Combine people, processes, and technologies to continuously deliver valuable products and services that meet end-user needs and business goals. DevOps professionals streamline delivery by optimizing practices, improving communications and collaboration, and creating automation.

## What is DevOps?

The contraction of "Dev" and "Ops" refers to replacing siloed Development and Operations teams. The idea is to create multidisciplinary teams that work together with shared practices, tools, and accountability for outcomes. Essential DevOps practices include agile planning, continuous integration, continuous delivery, and comprehensive monitoring of applications. DevOps is a continuous journey of improvement, not a destination.

Organizations implementing DevOps practices typically see measurable improvements across key operational metrics:

Let's start with a fundamental concept about software development using the OODA (Observe, Orient, Decide, Act) loop. Originally designed to keep fighter pilots from being shot out of the sky, the OODA loop is an excellent framework for staying ahead of your competitors in the business world.

Cycle Time Calculation Exercise: Think about your current development process. How long does it take to go from:

Example: If it takes 2 weeks to deploy a one-line configuration change, your cycle time is 2 weeks. This becomes your velocity constraint.

We recommend using data to inform decisions in your next cycle, but avoid becoming paralyzed by analysis. Experience from many organizations suggests that deployments often have varied outcomes:

The key principle : Fail fast on initiatives that don't advance the business and double down on outcomes that support business goals. This approach is often called "pivot or persevere."

How quickly you can fail fast or double down depends on your cycle time - how long that feedback loop takes to complete. The feedback you collect with each cycle should be:

This evidence-based approach is called validated learning - making decisions based on empirical evidence rather than assumptions or opinions.

The more frequently you deploy, the more you can experiment. The more opportunity you have to pivot or persevere and gain validated learning each cycle. This acceleration in validated learning is the value of the improvement. Think of it as the sum of progress that you achieve and the failures that you avoid.

Want to try using Ask Learn to clarify or guide you through this topic?

## Explore the DevOps journey

Remember, the goal is to shorten cycle time. Start with the release pipeline - this is often the biggest constraint. Ask yourself: How long does it take to deploy a change of one line of code or configuration? This deployment time ultimately becomes the brake on your velocity and ability to respond to market changes.

Drives the ongoing merging and testing of code, leading to early defect discovery. Benefits include:

Implementation tip : Start with automated builds on every commit, then gradually add testing layers.

Enables rapid deployment of software solutions to production and testing environments, helping organizations quickly fix bugs and respond to ever-changing business requirements.

Usually implemented with a Git-based repository, version control enables teams worldwide to communicate effectively during daily development activities and integrate with software development tools for monitoring activities such as deployments.

Use agile planning and lean project management techniques to maximize value delivery:

Monitor running applications including production environments for application health and customer usage. This helps organizations create hypotheses and quickly validate or disprove strategies. Rich data is captured and stored in various logging formats.

If it hurts, do it more often. Adopting new practices like going to the gym is likely to hurt first. The more you exercise the new techniques, the easier they'll become.

Like training at the gym, where you first exercise large muscles before small muscles, adopt practices that have the most significant impact first. Cross-train to develop synergy between practices.

Tool-first approach : Don't start by buying tools. Start with understanding your current state and desired outcomes.

Big bang transformation : Avoid trying to change everything at once. Start small and expand gradually.

DevOps team silo : Don't create a separate "DevOps team." DevOps is a practice, not a role.

## Identify transformation teams

Unless you're building an entirely new organization, one of the significant challenges of any DevOps transformation project is dealing with competing priorities that conflict with ongoing business operations.

Availability Challenge : If the staff members leading the transformation are also involved in existing day-to-day work, it will be challenging for them to focus on the transformation when their current role directly impacts customer outcomes. Desperate customer situations will always take priority over long-term transformation projects.

Organizational Inertia : Implementing existing processes and procedures to support current business outcomes can make it difficult to disrupt the status quo required for true DevOps transformation.

Research by Dr. Vijay Govindarajan and Dr. Chris Trimble in "Beyond the Idea: How to Execute Innovation" shows that successful innovation often occurs despite existing organizational processes. They concluded that it only works by creating a separate team to pursue the transformation.

Invest in Training and Skills Development

The separate team should be composed of staff members who are:

Consider including external experts who can:

Want to try using Ask Learn to clarify or guide you through this topic?

## Define organization structure for agile practices

For most organizations, reorganizing to be agile is challenging. It requires a fundamental mindset shift and cultural transformation that challenges many existing policies, processes, and power structures within the organization.

Good governance in organizations, particularly large enterprises, often leads to:

While most large organizations haven't fully moved to agile structures, most are experimenting with hybrid approaches because:

Traditional approach : Top-down decision making with multiple approval layers Agile approach : Distributed decision making with clear accountability

Traditional approach : Following defined processes regardless of results Agile approach : Optimizing for outcomes while adapting processes

Horizontal team structures divide teams according to technical layers or software architecture components. Teams are organized by technical specialty rather than business capability.

Vertical team structures span the entire technology stack and are aligned with business capabilities or customer value streams.

Vertical teams scale more effectively because you can add entire teams rather than trying to coordinate across multiple horizontal teams. Instead of project teams, create feature teams with long-term ownership.

Want to try using Ask Learn to clarify or guide you through this topic?

## Explore shared goals and define timelines

Effective DevOps transformation requires goals that are Specific, Measurable, Achievable, Relevant, and Time-bound (SMART) . These outcomes should have specific, measurable targets that directly relate to customer value and business objectives.

DevOps aims to provide excellent customer value, so outcomes should maintain a customer value focus:

Measurable goals need realistic timelines and regular checkpoints. Use the Objectives and Key Results (OKRs) framework to structure your DevOps transformation goals.

Objective : Qualitative, inspirational goal Key Results : Quantitative measures of progress toward the objective

Weekly reviews : Track progress on immediate goals and remove blockers Monthly reviews : Assess medium-term goal progress and adjust tactics Quarterly reviews : Evaluate long-term objectives and strategic alignment

Want to try using Ask Learn to clarify or guide you through this topic?

## What is Azure DevOps?

Azure DevOps is a Software as a service (SaaS) platform from Microsoft that provides an end-to-end DevOps toolchain for developing and deploying software.

It also integrates with the most-leading tools on the market and is an excellent option for orchestrating a DevOps toolchain.

Azure DevOps includes a range of services covering the complete development life cycle.

Also, you can use Azure DevOps to orchestrate third-party tools.

Azure DevOps is not focused on organizations that are end-to-end Microsoft or Windows.

Azure DevOps provides a platform that is:

Want to try using Ask Learn to clarify or guide you through this topic?

## What is GitHub?

GitHub is a Software as a service (SaaS) platform from Microsoft that provides Git-based repositories and DevOps tooling for developing and deploying software.

It has a wide range of integrations with other leading tools.

GitHub provides a range of services for software development and deployment.

Want to try using Ask Learn to clarify or guide you through this topic?

## Design a license management strategy

When designing a license management strategy, you first need to understand your progress in the DevOps implementation phase.

If you have a draft of the architecture, you're planning for the DevOps implementation; you already know part of the resources to consume.

For example, you started with a version control-implementing Git and created some pipelines to build and release your code.

If you have multiple teams building their solutions, you don't want to wait in the queue to start building yours.

Probably, you want to pay for parallel jobs and make your builds run in parallel without depending on the queue availability.

For the latest, most up-to-date Azure DevOps pricing information, visit Azure DevOps Pricing .

For the latest, most up-to-date GitHub pricing information, visit GitHub Pricing .

Want to try using Ask Learn to clarify or guide you through this topic?

## What is source control?

A Source control system (or version control system) allows developers to collaborate on code and track changes. Use version control to save your work and coordinate code changes across your team. Source control is an essential tool for multi-developer projects.

The version control system saves a snapshot of your files (history) so that you can review and even roll back to any version of your code with ease. Also, it helps to resolve conflicts when merging contributions from multiple sources.

For most software teams, the source code is a repository of invaluable knowledge and understanding about the problem domain that the developers have collected and refined through careful effort.

Source control protects source code from catastrophe and the casual degradation of human error and unintended consequences.

Without version control, you're tempted to keep multiple copies of code on your computer. It could be dangerous. Easy to change or delete a file in the wrong code copy, potentially losing work.

Version control systems solve this problem by managing all versions of your code but presenting you with a single version at a time.

Tools and processes alone aren't enough to accomplish the above, such as adopting Agile, Continuous Integration, and DevOps. Believe it or not, all rely on a solid version control practice.

Version control is about keeping track of every change to software assets—tracking and managing the who, what, and when. Version control is the first step needed to assure quality at the source, ensure flow and pull value, and focus on the process. All of these create value not just for the software teams but ultimately for the customer.

Version control is a solution for managing and saving changes made to any manually created assets. If changes are made to the source code, you can go back in time and easily roll back to previous-working versions.

Version control tools will enable you to see who made changes, when, and what exactly was changed.

Version control also makes experimenting easy and, most importantly, makes collaboration possible. Without version control, collaborating over source code would be a painful operation.

There are several perspectives on version control.

## Describe working with Git locally

Git and Continuous Delivery is one of those delicious chocolate and peanut butter combinations. We occasionally find two great tastes that taste great together in the software world!

Continuous Delivery of software demands a significant level of automation. It's hard to deliver continuously if you don't have a quality codebase.

Git provides you with the building blocks to take charge of quality in your codebase. It allows you to automate most of the checks in your codebase. Also, it works before committing the code into your repository.

To fully appreciate the effectiveness of Git, you must first understand how to carry out basic operations on Git. For example, clone, commit, push, and pull.

The natural question is, how do we get started with Git?

One option is to go native with the command line or look for a code editor that supports Git natively.

Visual Studio Code is a cross-platform, open-source code editor that provides powerful developer tooling for hundreds of languages.

To work in open-source, you need to embrace open-source tools.

This tutorial teaches us how to initialize a Git repository locally.

Then we use the ASP.NET Core MVC project template to create a new project and version it in the local Git repository.

We'll then use Visual Studio Code to interact with the Git repository to do basic commit, pull, and push operations.

You need to set up your working environment with the following:

## Introduction to Azure Repos

Azure Repos is a set of version control tools that you can use to manage your code.

Using version control is a good idea whether your software project is large or small.

Azure Repos provides two types of version control:

For further reference on using git in Azure Repos, refer to Microsoft Learn .

Want to try using Ask Learn to clarify or guide you through this topic?

## Introduction to GitHub

GitHub is the largest open-source community in the world. Microsoft owns GitHub. GitHub is a development platform inspired by the way you work.

You can host and review code, manage projects, and build software alongside 40 million developers from open source to business.

GitHub is a Git repository hosting service that adds many of its features.

While Git is a command-line tool, GitHub provides a Web-based graphical interface.

It also provides access control and several collaboration features, such as wikis and essential task management tools for every project.

So what are the main benefits of using GitHub? Nearly every open-source project uses GitHub to manage its project.

Using GitHub is free if your project is open source and includes a wiki and issue tracker, making it easy to have more in-depth documentation and get feedback about your project.

Automate from code to cloud: Cycle your production code faster and simplify your workflow with GitHub Packages and built-in CI/CD using GitHub Actions.

Securing software together: GitHub plays a role in securing the world's code—developers, maintainers, researchers, and security teams. On GitHub, development teams everywhere can work together to secure the world's software supply chain, from fork to finish.

Seamless code review: Code review is the surest path to better code and is fundamental to how GitHub works. Built-in review tools make code review an essential part of your team's process.

All your code and documentation in one place: Hundreds of millions of private, public, and open-source repositories are hosted on GitHub. Every repository has tools to help your host, version, and release code and documentation.

Manage your ideas: Coordinate early, stay aligned, and get more done with GitHub's project management tools.

## Module assessment

Choose the best response for each question.

Which of the following choices best describes DevOps?

DevOps is the role of who manages source control, pipelines, and monitor environments to continue delivering value to the software project.

DevOps is the union of people, process, and products to enable continuous delivery of value to our end users.

DevOps is the new process of creating continuous delivery and continuous integration for software projects.

Which of the following choices drives the ongoing merging and testing of code that leads to finding defects early?

Which of the following choices is a practice that enables the automated creation of environments?

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

This module explored the key areas that organizations must apply to start their DevOps transformation Journey, change the team's mindset, and define timelines and goals.

You learned how to describe the benefits and usage of:

Want to try using Ask Learn to clarify or guide you through this topic?
