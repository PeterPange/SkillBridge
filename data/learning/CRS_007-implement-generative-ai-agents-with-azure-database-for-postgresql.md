# Implement generative AI agents with Azure Database for PostgreSQL

## Introduction

Organizations today need applications that can handle complex, multi-step tasks autonomously while delivering personalized, context-aware responses. AI agents are transforming how businesses interact with customers by orchestrating workflows, retrieving relevant information, and maintaining conversational context across interactions.

Consider Margie's Travel, a vacation rental platform with thousands of properties and continuous guest inquiries. They need intelligent systems to recommend personalized stays, analyze guest feedback, and coordinate specialized tasks like inventory checks and sentiment analysis. With AI agents powered by Azure Database for PostgreSQL, the company can build scalable solutions that combine vector search for semantic understanding, persistent memory for context retention, and multi-agent orchestration for complex workflows.

This module shows you how to build and deploy AI agents using Azure Database for PostgreSQL and orchestration frameworks.

After completing this module, you'll be able to:

Want to try using Ask Learn to clarify or guide you through this topic?

## Understand AI agents with Azure Database for PostgreSQL

Many modern applications use AI agents to automate tasks, answer questions, and create personalized experiences. Before looking at a specific example, it’s helpful to understand how agentic architectures work and why Azure Database for PostgreSQL is a strong fit for these systems.

At the core of an agentic architecture are three capabilities: information retrieval, reasoning, and memory. Azure Database for PostgreSQL supports all three through its native extensions and scalable infrastructure.

Consider Margie’s Travel, a company that manages thousands of vacation rentals and guest interactions. They use Azure Database for PostgreSQL to support retrieval, reasoning, and memory, enabling agents to respond with relevant, personalized information.

Some tasks are too complex for a single agent. Multi-agent systems let agents specialize and coordinate, improving accuracy and scale. Think of multi-agent architectures as a team of experts, each handling a specific part of the workflow. Azure Database for PostgreSQL provides a unified data layer that all agents can access for information retrieval and memory. Orchestration frameworks manage how these agents interact, share context, and combine their outputs.

Let’s look at how Margie’s Travel orchestrates multiple agents to deliver personalized property recommendations.

Multi-agent architecture showing how a planning agent orchestrates specialized agents that access Azure Database for PostgreSQL and Azure OpenAI to deliver personalized results.

When a guest requests a personalized property recommendation, Margie's Travel orchestrates several agents:

Each agent interacts with Azure Database for PostgreSQL to access structured data, vector embeddings, and historical context. This orchestration ensures modularity and responsiveness at scale.

Azure Database for PostgreSQL has several features that make it a strong choice for agentic architectures. Azure Database for PostgreSQL is fully managed, scalable, and AI-ready. It supports large data volumes and complex queries without requiring manual intervention. Native vector search and semantic operators support advanced information retrieval and reasoning directly within SQL workflows. The platform also integrates with frameworks such as Microsoft Agent Framework , LangGraph , LlamaIndex , and Microsoft Foundry , making it easier to design and orchestrate agents.

AI agents rely on data retrieval and memory to work effectively. Azure Database for PostgreSQL supports both, giving agents a place to find information and keep track of context. These capabilities make it a practical choice for building systems that can manage complex tasks and continue to perform well as they scale.

Want to try using Ask Learn to clarify or guide you through this topic?

## Apply information retrieval for agents

AI agents depend on reliable information retrieval to give useful answers, recommendations, and support. As data grows, they need search methods that move beyond simple keyword matching. When semantic understanding is combined with scalable indexing, agents can deliver results that reflect both the query and the data behind it. Azure Database for PostgreSQL enables these capabilities through features such as vector search, semantic operators, and graph-based retrieval.

AI agent architecture showing how agents use tools to retrieve information from Azure Database for PostgreSQL through vector search and SQL queries.

Vector search matches information by meaning instead of exact wording. Text, reviews, or documents are stored as numeric embeddings in the database. When a query arrives, the system compares the meaning of the query to these embeddings and returns the closest matches.

The azure_ai extension adds built-in AI functions for PostgreSQL. You can generate embeddings, apply semantic analysis, and even call large language models directly from SQL. These features enable better search results, content summaries, and fact extraction without leaving the database.

For example, at Margie’s Travel, when a guest asks "Which properties are quiet and close to the city center?" , the agent uses vector search to connect the intent of the question with property descriptions and guest reviews. It retrieves the most relevant listings even when the same words aren't used.

Large knowledge bases require efficient indexing to keep searches fast. Azure Database for PostgreSQL supports methods such as DiskANN , which performs similarity search across millions of vectors while keeping memory use low. This feature ensures the agent responds quickly, even with a large dataset.

Accuracy is as important as speed. Semantic operators in the azure_ai extension let agents better rank results and surface more relevant results higher in the list. GraphRAG can then connect related facts across documents to provide a fuller answer.

Take another Margie’s Travel scenario: when a guest asks for "family-friendly apartments with great reviews about cleanliness," the agent uses semantic operators to filter and rank properties, then applies GraphRAG to link reviews and property data. The result is a recommendation that is both precise and trustworthy.

Suppose a guest asks: "I’m looking for a pet-friendly apartment near the city center with positive reviews about cleanliness." The agent:

With vector search, semantic operators, and scalable indexing, agents can respond with answers that are both fast and relevant. These tools help users find what they need while keeping results grounded in the underlying data.

Want to try using Ask Learn to clarify or guide you through this topic?

## Evaluate agentic frameworks for integration with PostgreSQL

AI agents rely on orchestration frameworks to manage tasks, coordinate tools, and maintain context. These frameworks provide the structure needed to build agents that can reason, retrieve information, and interact with external systems. Azure Database for PostgreSQL integrates with several of these frameworks, making it easier to build applications that combine data, logic, and language models.

Several open-source and Microsoft-supported frameworks help developers build and manage AI agents. For example, at Margie's Travel these frameworks play different roles in supporting guest interactions and property recommendations:

Although all frameworks support agent orchestration, they differ in focus:

Each framework can connect to Azure Database for PostgreSQL to support agent memory, retrieval, and context management:

For example, at Margie's Travel, LangGraph orchestrates multi-agent workflows, LlamaIndex handles retrieval from PostgreSQL's vector store, and Microsoft Agent Framework manages conversation memory and agent collaboration—all using the same PostgreSQL database. Foundry Agent Service deploys the agents in production, ensuring scalability and reliability.

Azure Database for PostgreSQL pairs with any of these frameworks to support agent memory, retrieval, and context management. Developers can select the framework that best fits their application needs and connect it to PostgreSQL through native extensions, framework-specific connectors, or custom integrations.

Want to try using Ask Learn to clarify or guide you through this topic?

## Implement AI agents with Foundry Agent Service

Foundry Agent Service provides a hosted orchestration layer for building and deploying intelligent agents. These agents can interact with tools, retrieve data, and maintain context across workflows. When integrated with Azure Database for PostgreSQL , agents gain access to scalable vector search, persistent memory, and structured data—essential for delivering relevant, context-aware responses.

Microsoft Foundry Agent Service lets developers define agents that use tools, maintain memory, and interact with users through natural language. PostgreSQL acts as both a structured data source and a vector store, enabling agents to retrieve facts and semantic matches from enterprise content.

For example, at Margie’s Travel, agents built with Foundry Agent Service answer guest questions, recommend properties, and automate support workflows. The integration allows agents to choose between vector search and SQL queries depending on the request.

To support intelligent behavior, agents combine embeddings, vector search, and structured queries. Together, these components help agents interpret user intent, retrieve relevant data, and provide responses with context.

Developers follow a series of steps to set up and configure an AI agent that integrates with Azure Database for PostgreSQL :

Margie’s Travel builds an AI agent to help guests find vacation rentals. The agent uses Foundry Agent Service to manage its workflow and Azure Database for PostgreSQL to store and retrieve property data.

When a guest asks, "Show me pet-friendly apartments near the beach with great reviews," the agent:

This setup enables Margie’s Travel to provide personalized recommendations quickly, while ensuring security and performance at scale.

Foundry Agent Service simplifies the process of building intelligent agents that integrate with Azure Database for PostgreSQL . By combining embeddings, vector search, and orchestration, developers can create agents that retrieve information, maintain context, and respond intelligently to user needs.

Want to try using Ask Learn to clarify or guide you through this topic?

## Exercise - Build an AI agent with Foundry Agent Service and Azure Database for PostgreSQL

Agent Foundry is a powerful framework for building AI agents that can interact with various data sources and services. In this exercise, you build an AI agent using Agent Foundry that connects to an Azure Database for PostgreSQL instance. The agent is capable of retrieving information from the database and generating responses based on user queries.

To complete this exercise, you will need an Azure subscription and be approved for Azure OpenAI access. If you need Azure OpenAI access, apply at the Azure OpenAI limited access page.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Integrate AI agents with MCP and PostgreSQL

Modern AI agents often need to interact with a wide range of tools and data sources. The Model Context Protocol (MCP) provides a standardized way for agents to discover, connect to, and invoke external tools and services. MCP acts as a universal adapter, enabling seamless integration with platforms like GitHub and Azure services .

Together, these components allow agents to dynamically access tools during runtime, improving flexibility and modularity.

Azure MCP Server can be configured to expose tools that interact with Azure Database for PostgreSQL . For example, agents can use MCP-wrapped tools to:

With this setup, agents use PostgreSQL to store information and retrieve it when needed. MCP connects the agent and the database so they can work together.

In a typical agentic architecture, MCP fits between the orchestration layer and the tool layer. Agents use orchestration frameworks like Azure AI Agent Service to manage workflows and reasoning. When a task requires external data or computation, the agent calls tools hosted on the MCP Server.

MCP architecture showing how agents use Azure MCP Server to access Azure Database for PostgreSQL and other Azure services.

For example, at Margie’s Travel, agents use MCP to access tools that query property databases, analyze guest reviews, and generate summaries. This modular approach allows the team to update tools independently and scale agent capabilities without rewriting core logic.

MCP and Azure MCP Server give AI agents a reliable way to connect with external tools and data sources. When used with Azure Database for PostgreSQL , they allow agents to query structured and semantic data as part of their workflow. This combination helps create systems that are flexible, consistent, and easier to scale.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

What are the two core capabilities that Azure Database for PostgreSQL provides for agentic architectures?

Which framework is specifically designed for complex workflows and multi-agent coordination with branching logic?

In an agentic architecture, where does Model Context Protocol (MCP) fit?

The architecture fits between the user interface and the database.

The architecture fits between the database and storage systems.

The architecture fits between the orchestration layer and the tool layer.

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

In this module, you explored how to implement AI agents using Azure Database for PostgreSQL. You learned about agentic architectures, information retrieval with vector search, multi-agent orchestration frameworks, and integration with Foundry Agent Service and Model Context Protocol.

By combining these capabilities, you can build intelligent systems that understand context, retrieve relevant information, and coordinate complex workflows. Azure Database for PostgreSQL provides the foundation for agent memory, semantic search, and scalable data access, enabling you to create responsive, personalized applications.

Want to try using Ask Learn to clarify or guide you through this topic?
