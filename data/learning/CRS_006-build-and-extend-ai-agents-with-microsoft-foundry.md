# Build and extend AI agents with Microsoft Foundry

## Introduction

A chat model can generate a response. Add trusted knowledge, live information, and tools that take action, and it becomes an agent you can build with Microsoft Foundry.

You work at Caldova , a pharmaceutical manufacturer that needs to make more of a product than its factories can produce. You build an assistant that helps the planning team decide whether to move work between factories or use an approved partner.

A chat model and an agent both use a large language model (LLM). On its own, the model predicts the next most likely word from patterns in its training data. It has no access to Caldova policies or live systems. An AI agent is a software service that adds knowledge and tools . These capabilities ground answers in business data, retrieve current information, and support actions.

For Caldova, this combination lets the assistant understand a supply chain request, choose the appropriate capability, and return a grounded answer or business action.

Microsoft Foundry Agent Service provides the managed environment for the Caldova assistant. Each task adds the capability needed for the next supply chain request, progressing from grounded answers to live lookups, analysis, and business actions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Configure agent behavior in Microsoft Foundry

Caldova's assistant must choose the right capability for each request and behave reliably when planners use it. How do you shape those decisions, run the configured agent, and check that it behaves as intended?

Instructions define the agent's role, goals, boundaries, and response style. The model provides the reasoning and tool-use capabilities needed for the task. Tools connect the agent to knowledge, live data, computation, or actions. Controls determine how the agent handles unsafe content and accesses protected resources.

These choices work together for every request. Caldova's instructions tell the assistant to answer from company evidence rather than guess. When a planner asks about approved partners, the agent selects File search because the answer comes from policy. When the planner asks whether a material is available, it selects check_stock because the answer requires live inventory. Clear tool descriptions help the agent make that choice.

Security controls apply across those interactions. Content filters block harmful content, Prompt Shields detect attacks in prompts and retrieved documents, and managed identity authenticates the agent without stored credentials. Least-privilege access limits what each tool can do.

Once you've configured the agent, how does Foundry run and manage it? Microsoft Foundry Agent Service hosts and scales the agent. When a planner sends a request, the agent runtime applies your configuration, manages the conversation, and coordinates the model and any tool calls needed to produce a response.

Foundry also helps you check what happens during and after each run. Tracing records inputs, outputs, tool calls, and latency so you can investigate the agent's decisions. Evaluations measure qualities such as response accuracy, safety, and tool use before you release a change. Monitoring then tracks the deployed agent's performance and reliability.

You define how the agent should behave. Foundry runs that configuration and gives you evidence that it behaves as intended.

Want to try using Ask Learn to clarify or guide you through this topic?

## Choose a development approach

The right development approach changes as an agent matures. The Foundry portal helps you test an idea quickly, while code supports source control, automation, and application integration.

The Foundry portal provides forms for creating and configuring agents without writing code. For example, you set instructions, add tools, upload grounding files, and test responses from one interface.

This approach fits an early prototype because it requires little development setup. Caldova uses the portal to ground the assistant in policy documents and confirm that its responses meet supply chain needs.

Code-based development fits an agent that becomes part of an application or automated process. The Microsoft Foundry SDK is the library that your application uses to create, configure, and call the agent.

The Microsoft Foundry extension for Visual Studio Code supports this path in your editor. If you already manage application code in Git, the agent follows the same review and version-control workflow. The resources view organizes models, agents, connections, and vector stores. Agent Designer helps you configure an agent visually and generate SDK code. You also use the same code in a deployment pipeline.

The portal and code paths share the same Foundry project and model deployments. As a result, the choice depends on the task rather than a permanent commitment. For example, you validate instructions in the portal, then open the agent in Visual Studio Code when it needs source control or application integration.

Consider your current project. Choose the portal for a quick prototype or the code path for an agent integrated with an application. Caldova starts in the portal, then uses code as the assistant gains custom tools.

With the development path clear, you next examine how custom tools let the assistant work with business data and take action.

Want to try using Ask Learn to clarify or guide you through this topic?

## Extend an agent with custom tools

An agent can retrieve information, but what happens when a request requires business logic that no built-in tool provides?

Caldova's assistant can search policy content and analyze production data with built-in tools. It can't draft an external capacity request, because that task depends on Caldova's own rules and application logic. To close that gap, you expose the capability as a custom tool .

The most direct option is function calling . You write a Python function such as draft_capacity_request , then register a matching tool definition . The definition describes the function's purpose and the product, quantity, and date parameters it accepts.

Who decides when to run it? With an imperative workflow, your application chooses and calls each function. Function calling uses a declarative pattern: you describe the capability once, and the agent chooses it when a request matches that description. Your application then runs the requested function and returns its result to the agent.

A description such as "get data" doesn't tell the agent when to choose the tool. Use a specific purpose and clear parameters so the agent can distinguish draft_capacity_request from its other capabilities.

The next question is where the business logic should run. Choose the tool type that matches how the capability already exists:

The hosting option changes, but the agent's decision stays declarative. In each case, you describe what the tool does and the information it needs. The agent then matches a request to the appropriate tool.

Want to try using Ask Learn to clarify or guide you through this topic?

## Connect an agent to MCP servers

Every hardcoded integration makes an agent more difficult to extend and maintain. A Model Context Protocol (MCP) server provides a tool catalog that the agent can discover at runtime instead.

The Model Context Protocol (MCP) breaks this cycle. Instead of baking each integration into the agent, you put tools on a server that acts as a live catalog. Your agent, through a lightweight client , asks the server what tools are available at runtime. It calls whichever tool the request needs, and the server handles the rest. Add a tool on the server, and every connected agent finds it automatically — no agent redeployment required.

The separation is the key insight: the server hosts tools, the client discovers and calls them, and the agent stays focused on deciding what to do. The same server can serve multiple agents, and the same agent can connect to multiple servers with a single consistent authentication approach.

Foundry Agent Service supports remote MCP servers directly, so you don't have to manage a client session or wrap functions yourself. You configure an MCPTool with a label that identifies the server, the server's endpoint URL, and an optional list of which tools the agent can call. The require_approval setting controls whether the agent pauses for confirmation before each call — always by default, or never for tools that run automatically.

Approval is where reasoning matters. When require_approval="always" , the agent returns an mcp_approval_request that names the tool it wants to call. Your code inspects the request and responds with an mcp_approval_response containing the request ID and an approve Boolean value. The agent then proceeds.

Why default to always ? Consider a tool that submits an external capacity request. Requiring approval means a person or your validation logic reviews the request before submission. For read-only lookups, such as searching documentation or checking material stock, you might switch to never . The setting represents a deliberate tradeoff between control and convenience.

The same MCP pattern exposes Caldova's material inventory through a stock-checking server. The assistant discovers the stock tool at runtime, calls it for a material request, and returns the current quantity. This final capability completes the progression from grounded policy answers to live information and business actions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Exercise - Build and extend an AI agent

Now you put the pieces together by building and extending an AI agent.

In this exercise, you build a Caldova supply chain assistant and extend it with knowledge, tools, and an MCP server. The lab is modular: the shortest task takes about 15 minutes, while the two core tasks take about 35 minutes.

If you don't have an Azure subscription, and you want to explore Microsoft Foundry, you can sign up for an account , which includes credits for the first 30 days.

Launch the exercise and follow the instructions.

After completing the exercise, if you're finished exploring Azure AI agents, delete the Azure resources that you created during the exercise.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

Caldova planners need answers from the company's supply chain policy instead of the model's training data. Which capability should you add to the agent?

Grounding, by attaching the supply chain policy with a File search tool.

A second model deployment in a different region.

You add a draft_capacity_request function to the Caldova assistant. Which statement best describes the declarative nature of this custom tool?

You must write code that explicitly calls each tool function in sequence.

The agent decides when and how to call a tool based on the prompt and the tool's description.

Tools run automatically on a fixed schedule regardless of the prompt.

Caldova exposes material stock through a remote MCP server. What is the main advantage of this approach instead of hardcoding the stock tool?

It removes the need for the agent to use a model.

Tools can be discovered dynamically at runtime, so they can be added or updated centrally without changing agent code.

It guarantees the agent never needs approval to call a tool.

A capacity-request tool is configured with require_approval="always" . What does the agent return before submitting the request?

## Summary

You started with a language model and added the elements that make an agent useful. Trusted knowledge helps it answer accurately, while tools let it retrieve information, analyze data, and take action.

You applied these skills by building a supply chain assistant for Caldova. You first grounded the assistant in Caldova's supply chain policy so it answers from trusted data. Next, you connected it to live documentation and used Code interpreter to analyze production output. You then added a custom function that drafts capacity requests. Finally, you connected an MCP server so the assistant discovers a tool and checks current material stock.

Along the way, you compared the Foundry portal, Visual Studio Code, and code-first approaches. You also applied the declarative tool pattern, where the agent decides when to call a described tool, and handled approval requests for sensitive actions.

The through-line: grounding supplies the right knowledge , and tools supply the right capabilities . Together they turn a chat model into an agent that can act.

Want to try using Ask Learn to clarify or guide you through this topic?
