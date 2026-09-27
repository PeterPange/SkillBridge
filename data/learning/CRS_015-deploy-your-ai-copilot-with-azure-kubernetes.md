# Deploy your AI Copilot with Azure Kubernetes

## Introduction

Discover the advantages of deploying your applications on Azure Kubernetes Service (AKS), which offers streamlined scalability, robust orchestration, and integration with other Azure services for modern cloud-native applications.

Imagine you’re part of a fast-growing development team building a microservices-based application. Your team needs a reliable solution to manage and scale containerized workloads across multiple environments without compromising on efficiency or control. You want to use Kubernetes for container orchestration while taking advantage of Azure’s comprehensive ecosystem to optimize your deployments.

The topics covered in this module include:

By the end of this module, you can understand how Azure Kubernetes Service simplifies deploying and managing containerized applications, enabling you to confidently orchestrate your workloads in a scalable and efficient way.

Want to try using Ask Learn to clarify or guide you through this topic?

## Deploy applications with Azure Kubernetes Service

Azure Kubernetes Service (AKS) is a fully managed Kubernetes container orchestration service that simplifies deployment, scaling, and management of containerized applications. AKS integrates seamlessly with the Azure ecosystem, providing developers with a powerful platform to build and manage cloud-native applications with minimal infrastructure overhead.

With AKS, developers can focus on their applications instead of managing infrastructure. AKS handles the complexities of Kubernetes, such as cluster provisioning, upgrades, and scaling, while still allowing developers to have granular control over the configuration when needed. The service is designed to reduce operational burden while providing the flexibility to run any container-based workload.

Deploying applications on AKS is made easy with its integration into the Azure DevOps ecosystem. Whether you're using GitHub Actions or Azure Pipelines, AKS supports seamless continuous integration and continuous delivery (CI/CD) workflows. This integration allows teams to automatically build, test, and deploy applications at scale while ensuring quick updates to production environments with minimal downtime.

Azure Kubernetes Service provides built-in support for autoscaling, allowing your applications to handle increased traffic effortlessly. AKS integrates with Azure Load Balancer and Azure Application Gateway, ensuring that your services remain available and responsive under various workloads. Whether scaling horizontally with more pods or vertically with larger VMs, AKS offers flexible scaling options that adapt to your application’s needs.

AKS is designed to optimize resource allocation, allowing you to scale your infrastructure efficiently. With its pay-as-you-go pricing model, you only pay for the virtual machines (VMs) you use, reducing overall operational costs. Additionally, AKS supports multi node pools, enabling developers to run different workloads on optimized resources for cost efficiency and performance.

AKS provides a secure environment for your applications with features like Microsoft Entra ID (formerly Azure Active Directory) integration, role-based access control (RBAC), and network security policies. It also supports private clusters and integration with Azure Policy to ensure compliance with your organization’s security standards. AKS enables you to manage and secure containerized workloads while using the extensive compliance offerings in Azure.

Azure Kubernetes Service seamlessly integrates with Azure Monitor, Azure Log Analytics, and other monitoring tools to provide real-time insights into your cluster’s performance and health. With AKS, developers can easily track resource usage, application performance, and troubleshoot issues, ensuring optimal uptime and reliability for their applications.

Deploying applications on AKS combines the scalability of Kubernetes with the ease of Azure’s management tools, offering a powerful, cost-efficient, and secure solution for running containerized applications in the cloud.

Want to try using Ask Learn to clarify or guide you through this topic?

## Create containerized apps with Azure Kubernetes Service clusters

Azure Kubernetes Service (AKS) clusters provide a robust platform for managing containerized applications in the cloud. With Kubernetes, AKS simplifies the deployment, scaling, and management of applications, allowing developers to focus on building innovative solutions without getting bogged down in infrastructure details.

AKS clusters are collections of virtual machines (VMs) configured to run containerized applications using Kubernetes. Each cluster consists of a master node that manages the Kubernetes environment and one or more worker nodes that run your applications in containers. With AKS, you can create, scale, and manage your Kubernetes clusters effortlessly, enjoying all the benefits of Kubernetes without the operational overhead.

Fully Managed Service : Azure takes care of the complexities of Kubernetes management, including updates, scaling, and monitoring, enabling you to focus on application development.

Integration with Azure Services : AKS integrates seamlessly with other Azure services, providing a cohesive development and deployment experience.

Auto-Scaling Capabilities : AKS supports horizontal and vertical scaling, automatically adjusting the number of pods or the size of VMs based on traffic and demand, ensuring your applications remain responsive under varying loads.

Built-in Load Balancing : AKS includes Azure Load Balancer and Application Gateway to distribute incoming traffic across multiple pods, ensuring high availability and reliability of your applications.

Enhanced Security Features : With Microsoft Entra ID integration, role-based access control (RBAC), and network security policies, AKS clusters provide a secure environment for your applications, protecting against unauthorized access and ensuring compliance.

Cost Efficiency : With a pay-as-you-go pricing model, you only pay for the resources you use. AKS helps optimize resource allocation, allowing for cost-effective management of your containerized workloads.

Simplified Deployment and Management : The ease of deploying applications on AKS allows teams to implement continuous integration and delivery (CI/CD) practices efficiently, reducing deployment times, and minimizing errors.

Robust Monitoring and Diagnostics : AKS clusters offer integrated monitoring tools that provide insights into application performance and resource utilization, allowing for proactive management and troubleshooting.

Build and Push the Container Image : First, you create a Dockerfile that defines the application environment and dependencies. Then you build a Docker image of your application. Once the image is built, you push it to a container registry such as Azure Container Registry (ACR) or Docker Hub, where it is accessed by AKS.

Create an AKS Cluster : Use the Azure portal, CLI, or Azure Resource Manager templates to create a Kubernetes cluster in AKS. This cluster serves as the environment for your containerized application, where you can define and manage Kubernetes resources.

## Exercise - Prepare your copilot application

Previously in this learning path, you implemented AI vector search functionality within your MongoDB project. Now this project is extended to include a web application interface. In this exercise, you’ll add code to expose key functions and create endpoints, enabling external interactions with the application. You’ll also create a Dockerfile to containerize your app, then run the Docker image locally to verify everything is working as expected. By the end of this exercise, you create a web application ready for deployment, complete with accessible endpoints, and containerized for easy distribution.

You need your own Azure subscription to run this exercise, and you might incur charges. If you don't already have an Azure subscription, create a free account before you begin.

Before you begin developing and deploying your application, you need to set up your local coding environment if you haven't already. Follow the steps to ensure you have the necessary tools installed and configured.

If you've already cloned the repository and created the Azure resources, then you only need to copy and paste the .env file from 04-vector-search/.env to 05-deploy-with-aks/node.js . Then right-click on the 05-deploy-with-aks folder and select Open in integrated Terminal and run npm install . Now you're ready to begin!

Node.js is required to run and manage JavaScript dependencies for the application you're deploying. You can download the latest version of Node here . You can verify the installation by opening the terminal in Visual Studio Code and running the command node -v

You can install the Azure CLI by following the instructions on this page . You can verify the installation by opening the terminal in Visual Studio Code and running the command az -v

Install the Docker extension for Visual Studio Code.

You can find the extension by navigating to View > Extensions and enter "Docker" in the search bar.

Clone the following repository in Visual Studio Code:

https://github.com/MicrosoftLearning/mslearn-cosmosdb-mongodb-vcore

Once the repository is cloned, navigate to the project directory 05-deploy-with-aks .

Right-click on the 05-deploy-with-aks folder and select Open in integrated Terminal .

## Exercise - Create an Azure Kubernetes Service cluster

In this exercise, you create an Azure Kubernetes Service (AKS) cluster and deploy an image to the Azure Container Registry (ACR). Afterwards, you can access your app through an external IP address.

In this task, you create an Azure Container Registry. An Azure Container Registry (ACR) is a secure, managed registry that stores container images, making it easy to deploy those images to Azure services like AKS.

Open the Visual Studio Code project from the previous exercise.

In the terminal, log in to Azure using az login

In the terminal, create the ACR with the following command:

az acr create --resource-group myResourceGroup --name myACRName --sku Basic Be sure to replace myResourceGroup and myACRName with the desired names of your resources. You can use an existing resource group, or create a new one using the command:

az group create --name myResourceGroup --location eastus Log in to your ACR resource with the following command:

az acr login --name myACRName Be sure to replace myACRName with the name of your registry. Next, you need to tag your local Docker image with your ACR login server address.

Before you can create an AKS cluster, you must make sure the Microsoft.Compute resource provider is registered for your subscription. Afterwards, you can create your cluster and deploy your image.

Navigate to portal.azure.com and select your subscription.

In the left hand menu, select Resource providers under Settings .

In the name filter, enter "Microsoft.Compute".

## Module assessment

Choose the best response for each of the questions below.

Which tool is used to deploy a Kubernetes manifest file to an AKS cluster?

What is the primary role of a Kubernetes master node in an AKS cluster?

To run containerized applications in pods.

To manage the Kubernetes environment and coordinate worker nodes.

To handle role-based access control (RBAC) within the cluster.

What happens during a rolling update of an AKS deployment?

All existing pods are stopped and replaced simultaneously.

The container image is deleted and rebuilt automatically.

New pods are created and replace old ones gradually, minimizing downtime.

You must answer all questions before checking your work.

You must answer all questions before checking your work.

## Summary

In this module, you learned how to develop, containerize, and deploy an AI-powered vector search application on Azure. Starting with implementing vector search capabilities for your app, you then created and configured an Azure Container Registry (ACR) to securely store your container images. Finally, you deployed your application to Azure Kubernetes Service (AKS). Throughout the module, you gained hands-on experience in building cloud-native applications, preparing you to deploy robust AI solutions with efficiency and reliability.

Want to try using Ask Learn to clarify or guide you through this topic?
