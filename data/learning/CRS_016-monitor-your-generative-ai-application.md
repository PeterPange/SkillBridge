# Monitor your generative AI application

## Introduction

In the early stages of working with generative AI, it's common to focus on getting something that works. Whether it's a demo, a prototype, or a proof-of-concept, these milestones can all feel significant. However, making something production-ready is a different challenge.

Without proper monitoring, even seemingly stable generative AI applications can face issues in real-world conditions:

Many teams fall into the trap of deploying without fully understanding how their system performs under real conditions. Monitoring transforms guesswork into engineering.

Imagine you work for Lakeshore Retail, which sells outdoor gear. The customer support team fields hundreds of inquiries daily about your extensive product lineup, ranging from camping gear to specialized hiking equipment. To enhance response speed and accuracy, they deployed an AI assistant named Trail Guide.

However, deploying a generative AI solution is just the beginning. As an AI engineer, you're asked to implement ongoing monitoring to maintain quality, mitigate risk and safety, and ensure customer satisfaction.

In this module, you learn best practices for monitoring generative AI applications with Azure AI and Azure Monitor. By the end, you're able to proactively monitor AI agents and assistants like Trail Guide and optimize their real-world effectiveness.

Want to try using Ask Learn to clarify or guide you through this topic?

## Why do you need to monitor?

When you move from experimentation to production with a generative AI solution, one of the earliest and most important decisions you face is choosing the optimal deployment configuration . Specifically, what kind of compute should you allocate to your model? This decision directly affects performance, cost, and scalability.

In Microsoft Foundry, like many cloud platforms, deploying a generative AI application means binding it to a compute resource . That resource defines the horsepower behind your app: how fast it can respond, how many requests it can handle at once, and ultimately how much it costs to operate.

A small VM (for example, Standard_F2s) might be low-cost and sufficient for light usage. But it could struggle with:

A larger VM (for example, Standard_F4s or F8s) might offer faster performance and better concurrency, but:

The problem is: you can't know what’s right for your use case until you see it in action.

Generative AI workloads are different from traditional web apps:

So when you deploy a generative AI solution like a summarization app or a chatbot, you're not just asking "Will it run?" You’re asking:

In production, these questions become even more urgent. Product managers and business stakeholders want fast response times to keep users engaged, cost predictability to maintain return on investment (ROI), and stable performance as the user base grows.

But as an engineer, you’re making choices with incomplete information unless you’ve measured how your deployment behaves.

To measure, is to monitor . Monitoring isn't just a technical tool, but also a critical input to business and engineering decisions.

Through monitoring, you iteratively improve the performance of your generative AI solution:

Monitoring and adjusting iteratively is the same process production teams use to tune their infrastructure, plan for scale, and minimize wasted spend.

## Understand key metrics to monitor

Before you can optimize performance or make informed decisions about deployment, you need to know what to look at. In generative AI applications, especially those built using Microsoft Foundry, monitoring isn’t about measuring everything, it’s about measuring the right things .

Let's explore the key performance signals you should monitor in your generative AI system and how they connect to real-world outcomes like user experience, reliability, and cost.

Traditional monitoring for web services focuses on uptime, memory use, and API failure rates. While some of those still matter here, generative AI systems have unique dynamics. Each request can vary drastically in how much compute it uses depending on factors like:

That means monitoring needs to focus on behavioral metrics tied directly to how the language model performs under different conditions.

Here are the four most important things you should monitor when deploying a generative AI app:

Latency refers to the time it takes for a request to travel from the client to the system and for the system to start processing it. Essentially, it's the delay before any response begins .

Response time is the total time it takes from the moment a request is sent by the client until the complete response is received. The response time includes the latency, the time taken to process the request on the system, and the time taken to send the response back to the client.

Slow responses can feel broken or unreliable, directly affecting how users perceive your service. The response time is often the first indication that your deployment might be underpowered or overloaded.

The full request-response cycle of a generative AI system can be illustrated as follows:

Where a user sends the first request, which then travels across the network . The system receives the request and begins processing, sending input to the language model and waiting for the generated output. The system finalizes the output and sends the response back through the network to the user.

By monitoring and optimizing each of these components, you can ensure a smoother and more reliable user experience.

Throughput refers to the number of requests your app can process within a given time frame. It reflects how well your system scales with demand.

## Explore how to monitor with Azure

Now that you understand what to monitor, it’s time to explore how Azure supports performance monitoring in practice. Azure gives you lightweight, code-first tools to inspect and reason about the behavior of your generative AI deployments, without needing to build out full observability stacks.

Effective monitoring requires a multi-faceted approach that includes, tracing , online evaluation , and observability through Azure Monitor Application Insights .

Let's explore each of these components in more detail.

To continuously monitor your generative AI application, start by capturing and storing detailed telemetry data . You can store telemetry data by instrumenting your application with the Azure AI Tracing package . This package logs trace data to an Azure Monitor Application Insights resource.

The trace data follows the OpenTelemetry standard, ensuring structured and comprehensive observability. Once you have tracing set up, you can analyze your application's request flow, track latency, and monitor resource consumption.

You can trace any AI model supporting the Azure AI model inference API .

By default, tracing allows you to monitor metrics like token usage, API calls, and response times. To add metrics that reflect the model's performance, you can add continuous evaluation.

Continuous evaluation helps you assess the quality, security, and safety of AI-generated outputs in real-time. With Azure AI Online Evaluation , you can automatically evaluate your application's responses .

You can use built-in evaluators that align with the Azure AI Evaluation SDK (like groundedness or coherence) or define custom evaluators to track domain-specific performance metrics. When you consistently run evaluations on collected trace data, your team can proactively detect and mitigate emerging issues in both preproduction and live deployments.

For a comprehensive view of your AI application's health, Azure Monitor Application Insights offers advanced observability tools. These tools include:

This integration ensures that all critical insights, such as token usage, latency, and request volume, are readily accessible, empowering your team to make data-driven optimizations.

Alerts notify you of critical conditions and can take corrective action.

## Integrate monitoring into your app

To generate monitoring data that is captured by Application Insights and visualized in Azure Monitor, you need to run a service you deployed through the Microsoft Foundry.

A service can simply be a deployed language model, or a deployed generative AI app like an AI assistant or agent.

To integrate monitoring into your code, you need to:

The code snippets provided here are just to highlight what parts of the code would do. A complete working example is provided in the exercise.

To begin monitoring your generative AI application, you need to use the Microsoft Foundry SDK to run model inference. Model inference could be anything from a single language model completion to a full multi-turn assistant.

The Microsoft Foundry SDK allows you to connect with a specific Azure AI hub and project. With Python, this may look like the following code sample:

connection_string = os.getenv('PROJECT_CONNECTION_STRING') credential = DefaultAzureCredential() project = AIProjectClient.from_connection_string( conn_str=connection_string, credential=credential ) After, you can use the Azure AI model inference package (part of the Microsoft Foundry SDK) to interact with a deployed service. For example:

chat_client = project.inference.get_chat_completions_client() model_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o") response = chat_client.complete( model=model_name, messages=[ SystemMessage("You are an AI assistant that acts as a travel guide."), UserMessage(content=( "What are some recommended supplies for a camping trip in the mountains?" ))] Capture spans with a tracer To easily trace the path of an inference request through your application, Azure integrates with the OpenTelemetry standard.

The OpenTelemetry standard uses spans and a tracer to organize your monitoring data:

In your application, for example, you start by getting a tracer instance and generating unique identifiers for spans:

# Get the tracer instance tracer = trace.get_tracer(__name__) # Generate a session ID for this script execution SESSION_ID = str(uuid.uuid4()) # Configure the tracer to include session ID in all spans os.environ['AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED'] = 'true' Then, you can use the tracer to create a span named generate_completion to represent the process of generating a response from the AI model. The span is used before you interact with the deployed service, so you update the code with:

# Generate a chat completion about camping supplies with tracer.start_as_current_span("generate_completion") as span: try: span.set_attribute("session.id", SESSION_ID) response = chat_client.complete( model=model_name, messages=[ SystemMessage("You are an AI assistant that acts as a travel guide."), UserMessage(content=( "What are some recommended supplies for a camping trip in the mountains?" ))] ) except Exception as e: span.set_status(Status(StatusCode.ERROR, str(e))) span.record_exception(e) raise Export data automatically Finally, you need to ensure you're connecting with your Applications Insights resource to automatically export the generated monitoring data. When you connect an Application Insights resource with your Microsoft Foundry project, you can get the resource through the project:

## Interpret monitoring results

By now, you understand what to monitor and how Azure Monitor supports lightweight monitoring out-of-the-box. The final step before going hands-on is to explore how to make sense of monitoring data , and more importantly, how it can guide practical decisions.

This unit focuses on interpretation, not prescribing specific actions, but helping you think critically about what the data means and how to apply it to solution development.

Monitoring should never be a passive activity. Instead, it forms a feedback loop. After you deploy a service, you observe how it behaves, compare it to your objectives, and adjust as needed.

This feedback loop can be repeated when needed, where each round helps you narrow in on the right balance between performance and cost.

Workbooks provide a flexible canvas for analyzing data and creating rich visual reports in the Azure portal. Workbooks can query data from multiple data sources and combine and correlate data from multiple data sets in one visualization, giving you visual representation of your system. Workbooks are interactive, with data updating in real time, and can be shared across teams.

You can use the workbooks that Azure Monitor Insights provide, use the workbook template library, or create your own workbooks.

When you connect an Application Insights instance to your Microsoft Foundry project, important metrics are already visualized for you in the Insights for Generative AI applications dashboard .

When selecting the dashboard, you're linked to a prebuilt Azure Workbook in Azure Monitor that provides real-time insights into the performance metrics, usage patterns, and operational efficiency of your AI applications. You can track data such as execution times, token consumption, and error rates across sessions. You can use these detailed logs and visualizations to identify bottlenecks and optimize workflows.

Token counts reveal how your prompt and output design affect cost and performance.

By monitoring token patterns, you can fine-tune your app to be more efficient—sometimes without changing deployment infrastructure at all.

Errors tell you when your deployment is hitting a limit. For example:

If your error rate increases with usage, that’s a sign your app needs optimization—either in compute capacity or flow design.

## Exercise - Enable monitoring for a generative AI application

If you have an Azure subscription, you can explore monitoring with Microsoft Foundry for yourself.

If you don't have an Azure subscription, and you want to explore Microsoft Foundry, you can sign up for an account , which includes credits for the first 30 days.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Knowledge check

What serves as the foundation of continuous monitoring for generative AI applications?

What does Azure AI Online Evaluation help assess in real time?

Which component provides advanced observability tools including custom dashboards and configurable alerting mechanisms?

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

Monitoring generative AI applications is crucial for maintaining their reliability, performance, and cost-effectiveness in production environments.

This module has outlined the importance of continuous monitoring through tracing, online evaluation, and the use of Azure Monitor Application Insights. By implementing these best practices, businesses can proactively manage AI agents like Trail Guide, optimize their real-world effectiveness, and ensure customer satisfaction. The insights provided by Azure Monitor's dashboards and alerts enable teams to detect anomalies, optimize performance, and align AI systems with business objectives and user expectations.

As generative AI continues to evolve, ongoing monitoring will remain a key component in harnessing its full potential.

Want to try using Ask Learn to clarify or guide you through this topic?
