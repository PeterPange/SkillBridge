# Build a containerized web application with Docker

## Introduction

Rapid deployment is key to business agility. Modern organizations must be able to release apps quickly to attract and retain business. Containerization saves time and reduces costs. You don't have to configure hardware and spend time installing operating systems and software to host a deployment. Multiple apps can run in their isolated containers on the same hardware. You can scale out quickly by starting more instances of containers. The images that run in containers are extensible; you can start with a working base image and layer more functionality on top to create a new image.

Suppose you work for an online clothing retailer that's planning to deploy a handful of internal apps, but it hasn't yet decided how to host them. You're looking for maximum compatibility, and the apps could be hosted on-premises, in Azure, or in another cloud provider. Some of the apps might share infrastructure as a service (IaaS) infrastructure. In these cases, the company requires the apps to be isolated from each other. Apps can share the hardware resources, but an app shouldn't be able to interfere with the files, memory space, or other resources the other apps use. The company values the efficiency of its resources and wants something with a compelling app-development story. Docker seems an ideal solution to these requirements. With Docker, you can quickly build and deploy an app and run it in its tailored environment, either locally or in the cloud.

In this module, you'll take an existing application and package it as a Docker image. You'll automate the image-build process by defining the build steps in a Dockerfile. You'll test the app locally by using Docker for Windows. Finally, you'll upload the image to Azure Container Registry and run the application using the Azure Container Instance service.

By the end of this module, you'll be able to build Docker images and run them from Azure.

The exercises in this module require local installations of Docker and Git .

Want to try using Ask Learn to clarify or guide you through this topic?

## Retrieve an existing Docker image and deploy it locally

Docker is a technology that allows you to deploy applications and services quickly and easily. A Docker app runs using a Docker image. A Docker image is a prepackaged environment containing the application code and the environment in which the code executes.

In the corporate scenario we described earlier, you want to investigate the feasibility of packaging and running an app with Docker. You decide to build and deploy a Docker image running a test web app.

In this unit, you'll learn about the key concepts and processes involved in running a containerized app stored in a Docker image.

Docker is a tool for running containerized apps. A containerized app includes the app and the filesystem that makes up the environment in which it runs. For example, a containerized app could consist of a database and other associated software and configuration information needed to run the app.

A containerized app typically has a much smaller footprint than a virtual machine configured to run the same app. This smaller footprint is because a virtual machine has to supply the entire operating system and associated supporting environment. A Docker container doesn't have this overhead, because Docker uses the host computer's operating-system kernel to power the container. Downloading and starting a Docker image is faster and more space-efficient than downloading and running a virtual machine that provides similar functionality.

You create a containerized app by building an image that contains a set of files and a section of configuration information Docker uses. You run the app by asking Docker to start a container based on the image. When the container starts, Docker uses the image configuration to determine what application to run inside the container. Docker provides the operating system resources and the necessary security. It ensures that containers are running concurrently and remain relatively isolated.

Docker doesn't provide the level of isolation available with virtual machines. A virtual machine implements isolation at the hardware level. Docker containers share underlying operating system resources and libraries. However, Docker ensures that one container can't access another's resources unless the containers are configured to do so.

You can run Docker on your desktop or laptop if you're developing and testing locally. For production systems, Docker is available for server environments, including many variants of Linux and Microsoft Windows Server 2016. Many vendors also support Docker in the cloud. For example, you can store Docker images in Azure Container Registry and run containers with Azure Container Instances.

In this module, you'll use Docker locally to build and run an image. Then, you'll upload the image to Azure Container Registry and run it in an Azure Container Instance. This version of Docker is suitable for developing and testing Docker images locally.

Docker was initially developed for Linux and has since expanded to support Windows. Individual Docker images are either Windows-based or Linux-based, but can't be both at the same time. The image's operating system determines what kind of operating system environment is used inside the container.

Docker image authors who wish to offer similar functionality in both Linux-based and Windows-based images can build those images separately. For example, Microsoft offers Windows and Linux Docker images containing an ASP.NET Core environment that you can use as the basis for containerized ASP.NET Core applications.

Linux computers with Docker installed can only run Linux containers. Windows computers with Docker installed can run both kinds of containers. Windows runs both by using a virtual machine to run a Linux system, and uses the virtual Linux system to run Linux containers.

## Exercise - Retrieve an existing Docker image and deploy it locally

A good starting point for building and running your own Docker images is to take an existing image from Docker Hub and run it locally on your computer.

As a proof of concept for the company's applications, you decide to try running a sample image from Docker Hub. The image you selected implements a basic .NET Core ASP.NET web app. Once you establish a process for deploying a Docker image, you're able to run one of your company's own web apps using Docker.

In this exercise, you pull an image from Docker Hub and run it. You examine the local state of Docker to help understand the elements that are deployed. Finally, you remove the container and image from your computer.

This exercise takes place on your computer, not in Azure. You need a local installation of Docker to proceed with the exercise. Download: https://docs.docker.com/desktop/install/windows-install/

Open a command prompt window on your local computer.

Enter the following code to pull the ASP.NET Sample app image from the Docker Hub registry. This image contains a sample web app developed by Microsoft, and is based on the default ASP.NET template available in Visual Studio.

docker pull mcr.microsoft.com/dotnet/samples:aspnetapp Enter the following code to verify that the image was stored locally.

docker image ls You should see a repository named mcr.microsoft.com/dotnet/samples with a tag of aspnetapp .

Enter the following code to start the sample app. The -d flag is to run it as a background, non-interactive app. The p flag is to map port 8080 in the container that's created to port 8080 locally. This setting is intended to avoid conflicts with any web apps already running on your computer. The command responds with a lengthy hexadecimal identifier for the instance.

docker run -d -p 8080:8080 mcr.microsoft.com/dotnet/samples:aspnetapp Open a web browser and go to the URL for the sample web app: http://localhost:8080 . You should get a page that looks like the following screenshot:

At the command prompt, run the following command to view the running containers in the local registry.

docker ps The output should look similar to the following example:

## Customize a Docker image to run your own web app

Docker Hub is an excellent source of images to get you started building your own containerized apps. You can download an image that provides the basic functionality you require, then layer your own application on top of it to create a new custom image. You can automate the steps for this process by writing a Dockerfile.

In the online clothing store scenario, the company decided that Docker is the way forward. The next step is to determine the best way to containerize your web applications. The company plans to build many of the apps using ASP.NET Core. You've noticed that Docker Hub contains a base image that includes this framework. As a proof of concept, you want to start with this base image and add the code for one of the web apps to create a new custom image. You also want this process to be easily repeatable, so it can be automated whenever you release a new version of the web app.

In this unit, you'll learn how to create a custom Docker image and how you can automate the process by writing a Dockerfile.

To create a Docker image containing your application, you typically begin by identifying a base image , to which you add files and configuration information. The process of identifying a suitable base image usually starts with an image search on Docker Hub. You want an image that already contains an application framework and all the utilities and tools of a Linux distribution, like Ubuntu or Alpine. For example, if you have an ASP.NET Core application that you want to package into a container, Microsoft publishes an image called mcr.microsoft.com/dotnet/core/aspnet that already contains the ASP.NET Core runtime.

You can customize an image by starting a container with the base image and making changes to it. Changes usually involve activities such as copying files into the container from the local filesystem and running various tools and utilities to compile code. When you're finished, you can use the docker commit command to save the changes to a new image.

Manually completing the above process is time consuming and error prone. You could script it with a script language like Bash, but Docker provides a more effective way of automating image creation via a Dockerfile .

A Dockerfile is a plain-text file containing all the commands needed to build an image. Dockerfiles are written in a minimal scripting language designed for building and configuring images. They document the operations required to build an image, starting with a base image.

The following example shows a Dockerfile that builds a .NET 6.0 application and packages it into a new image.

FROM mcr.microsoft.com/dotnet/sdk:6.0 WORKDIR /app COPY myapp_code . RUN dotnet build -c Release -o /rel EXPOSE 80 WORKDIR /rel ENTRYPOINT ["dotnet", "myapp.dll"] In this file, the following operations take place:

By convention, applications meant to be packaged as Docker images typically have a Dockerfile located in the root of their source code, and it's almost always named Dockerfile .

The docker build command creates a new image by running a Dockerfile. This command's syntax has several parameters:

docker build -t myapp:v1 . Behind the scenes, the docker build command creates a container, runs commands in it, then commits the changes to a new image.

## Exercise - Customize a Docker image to run your own web app

A Dockerfile contains the steps for building a custom Docker image.

You decide to deploy one of your organization's web apps using Docker. You select a simple web app that implements a web API for a hotel reservations website. The web API exposes HTTP POST and GET operations that create and retrieve customers' bookings.

In this version of the web app, the bookings aren't actually persisted, and queries return dummy data.

In this exercise, you'll create a Dockerfile for an app that doesn't have one. Then, you'll build the image and run it locally.

If it's not already running, start Docker on your computer.

In a command prompt window on your local computer, run the following command to download the source code for the web app.

git clone https://github.com/MicrosoftDocs/mslearn-hotel-reservation-system.git Enter the following command to open the src directory.

cd mslearn-hotel-reservation-system/src In the src directory, enter the following commands to create a new file named Dockerfile and open it in Notepad:

copy NUL Dockerfile notepad Dockerfile Note

By default the notepad command opens a text file. Make sure that you save it as file type All Files with no file extension. To verify, open the src folder in File Explorer, select View > Show> File name extensions. If necessary, rename the file and remove .txt from the file name.

Add the following code to the Dockerfile:

FROM mcr.microsoft.com/dotnet/core/sdk:2.2 WORKDIR /src COPY ["/HotelReservationSystem/HotelReservationSystem.csproj", "HotelReservationSystem/"] COPY ["/HotelReservationSystemTypes/HotelReservationSystemTypes.csproj", "HotelReservationSystemTypes/"] RUN dotnet restore "HotelReservationSystem/HotelReservationSystem.csproj" This code has commands to fetch an image containing the .NET Core Framework SDK. The project files for the web app ( HotelReservationSystem.csproj ) and the library project ( HotelReservationSystemTypes.csproj ) are copied to the /src folder in the container. The dotnet restore command downloads the dependencies required by these projects from NuGet.

## Deploy a Docker image to an Azure Container Instance

Azure Container Instance is a service that loads and runs Docker images on demand. The Azure Container Instance service can retrieve an image from a registry, such as Docker Hub or Azure Container Registry.

Your organization wants to use Azure to run its web apps. For this reason, it makes sense to store the images in Azure Container Registry and run them using the Azure Container Instance service.

In this unit, you'll learn how to upload a Docker image to Azure Container Registry. Then, you'll run the image using the Azure Container Instance service.

Azure Container Registry is a registry-hosting service provided by Azure. Each Azure Container Registry resource you create is a separate registry with a unique URL. These registries are private , meaning they require authentication to push or pull images. Azure Container Registry runs in the cloud and provides similar levels of scalability and availability to other Azure services.

You can create a registry using the Azure portal or the Azure Command Line Interface (CLI). You can use the Cloud Shell in the Azure portal or a local install of the Azure CLI. Keep in mind that you need to create a resource group before you can create the registry. When creating a resource group, we recommend choosing the nearest region. In this example, our resource group's name is mygroup , and the location is US West.

You don't need to run any of the following commands. We'll do that in the next exercise.

You need a unique name for your container. You can check to see if a name is already in use here .

az group create --name mygroup --location westus az acr create --name <unique name> --resource-group mygroup --sku standard --admin-enabled true Different SKUs provide varying scalability and storage levels.

Azure Container Registry repositories are private, meaning they don't support unauthenticated access. To pull images from an Azure Container Registry repository, use the docker login command and specify the URL of the login server for the registry. The login server URL for a registry in Azure Container Registry has the form < registry_name >.azurecr.io.

docker login myregistry.azurecr.io Docker login will prompt you for a username and password. To find this information, go to the Azure portal and look up the access keys for the registry or run the following command.

az acr credential show --name myregistry --resource-group mygroup You can push an image from your local computer to a Docker registry by using the docker push command. Before you push an image, you must create an alias for the image that specifies the repository and tag that the Docker registry creates. The repository name must be of the form *<login_server>/< image_name >:< tag />. Use the docker tag command to perform this operation. The following example creates an alias for the reservationsystem image.

docker tag reservationsystem myregistry.azurecr.io/reservationsystem:v2 If you run docker image ls , you'll get two entries for the image: one with the original name and the second with the new alias.

## Exercise - Deploy a Docker image to an Azure Container Instance

Azure Container Instance enables you to run a Docker image in Azure.

In the previous exercise, you packaged and tested your web app as a local Docker image. Now, you want to use the output of that exercise and make the web application available globally. To accomplish this availability, you can run the image as an Azure Container Instance.

In this exercise, you'll learn how to rebuild the image for the web app and upload it to Azure Container Registry. You'll use the Azure Container Instance service to run the image.

You need your own Azure subscription to complete this exercise, and you might incur charges. If you don't already have an Azure subscription, create a free account before you begin.

Sign in to the Azure portal with your Azure subscription.

On the resource menu or from the Home page, select Create a resource . The Create a resource pane appears.

In the menu, search for Container Registry . In the Container Registry search result, select Create > Container Registry .

The Create container registry pane appears.

On the Basics tab, enter the following values for each setting.

Leave all other options as their defaults, then select Review + create . When the Validation passed notification appears, select Create . Wait until the container registry has been deployed before continuing.

Select Go to resource . The Container registry pane displays essentials about your container registry.

In the resource menu, under Settings , select Access keys . The Access keys pane for your container registry appears.

## Summary

Packaging an app in a Docker image gives you a convenient way to deploy and run the app. You can automate the process of building a Docker image by defining the steps in a Dockerfile. After you've created an image, you can upload it to a registry such as the Azure Container Registry. From there, you can create a container instance that runs the application.

In this module, you created resources by using your Azure subscription. You want to clean up these resources so that you won't continue to be charged for them.

In the Azure portal, select Home , and then select Resource groups .

Find the learn-deploy-container-aci-rg resource group, or whatever resource group name you used, and select it.

In the command bar, select Delete resource group . A dialog pane appears asking you to type the resource group name.

Enter the name of the resource group ( learn-deploy-container-aci-rg or whatever name you used), then select Delete . Select Delete again to confirm deletion. All of the resources that you created in this module are deleted along with the resource group.

Want to try using Ask Learn to clarify or guide you through this topic?
