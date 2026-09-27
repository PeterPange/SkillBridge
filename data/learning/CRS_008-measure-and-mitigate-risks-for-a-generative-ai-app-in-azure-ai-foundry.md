# Measure and mitigate risks for a generative AI app in Azure AI Foundry

## Introduction

Contoso Camping Store would like to launch a new chatbot to enhance their customer support. The proposed chatbot should be designed to provide instant, accurate information about the store's wide range of camping products. Your goal is to create a chatbot in Azure AI Foundry that can generate responses about Contoso Camping Store product features and provide recommendations based on customer preferences. As you build it, you also apply layered mitigations so the chatbot stays grounded, relevant, and safe.

By completing this module, you're able to:

Want to try using Ask Learn to clarify or guide you through this topic?

## Prepare

The first step in this guided project is to create a project and the supporting resources in Azure AI Foundry. This module intentionally uses a hub-based project in the Foundry (classic) experience because the later units rely on classic navigation such as Data + indexes , Guardrails + controls , and Evaluation .

Use the East US 2 region for this exercise. Current evaluation guidance lists East US 2 as supporting the full risk-and-safety evaluator set used later in this module, including Protected material , Indirect attack , and Groundedness Pro . Feature availability still changes over time, so verify both model and feature support before you create resources. For more information, see Microsoft Foundry feature availability across cloud regions , Rate limits, region support, and enterprise features for evaluation , and Azure AI Content Safety region availability .

If your UI doesn't match the screenshots, first confirm that you're in Foundry (classic) . The current portal uses different menu names, such as Discover > Model catalog , Build > Evaluations , and Operate > Compliance . If you're already in the classic experience and still don't see Data + indexes , Guardrails + controls , or Evaluation , select ... More to customize the left pane. For background, see What is Microsoft Foundry (classic) portal? , Create a hub project for Microsoft Foundry (classic) , and Migrate from the Foundry (classic) portal .

If Create new resource or AI hub resource isn't available, confirm that you have the required permissions on the hub or resource group. Official hub-project guidance calls out Owner or Contributor permissions for creating or using hub resources in the portal.

You also need an Azure AI Search resource before you create the product index later in this module. If your project doesn't already have one connected, you can create or connect one during the index-creation workflow.

Sample files for this guided project are available in the Measure and Mitigate Workshop folder. Download the repository to access the files required for this module. To download the repository, select Code > Download ZIP .

After extracting the ZIP file, note the location of the Products folder and the evaluation .jsonl files because you use them in later units. Keep the extracted file and folder names unchanged so they match the steps in this module.

Want to try using Ask Learn to clarify or guide you through this topic?

## Choose and deploy a model

Selecting a model from the Model Catalog is the first step toward creating the Contoso Camping Store chatbot. The model catalog in Azure AI Foundry is the central place to discover, compare, and deploy models for generative AI applications. Exact collection labels and available models can change over time, so focus on the model card, deployment options, benchmark data when published, and regional availability when you make your choice.

The model catalog includes Azure OpenAI models together with a wide range of partner and community models. Some models support serverless deployment, some support managed compute, and some support both. For more information, see Microsoft Foundry Models overview .

There are various factors to consider when choosing a model, such as performance, relevance, cost, deployment options, and regional availability. You can learn more about each model by reviewing its model card. Let's look at the model cards for both gpt-4o and a Meta Llama chat model.

The model card for gpt-4o helps you confirm that the model supports chat completion and gives you the information you need before deployment.

Let's now look at a model provided as a serverless deployment offering to compare the difference in information available on a model card.

The model card for Llama-3.3-70B-Instruct has more information about the model, including its license, deployment options, training data, and benchmark comparisons across related models.

Model availability in the catalog changes over time. If a specific model isn't listed, choose another model from the same provider that's currently available in your region.

While the model card provides detailed information about each model, comparing candidate models helps you weigh tradeoffs such as quality, safety, cost, and throughput before you deploy. You're using an Azure OpenAI chat completion model to create the Contoso Camping Store chatbot, so let's compare two current Azure OpenAI chat models.

Not every model has published benchmark data. If a model doesn't have a Benchmarks tab, Microsoft hasn't published benchmark results for that model yet. Public benchmarks are useful for narrowing down options, but you should still test with your own prompts and data. For more information, see Compare models using the model leaderboard .

Across most common chat scenarios, gpt-4o is a strong choice for this guided project, so let's deploy it.

You can deploy a model from either the model card or your project’s deployment page.

Model availability and quota vary by model and region. Before deployment, verify that your chosen model is available in your target region and that you have enough quota to deploy it. If gpt-4o isn't available to you, use another Azure OpenAI chat completion model such as gpt-4o-mini , and then use that same deployment throughout the rest of the module. For more information, see Create and deploy an Azure OpenAI in Microsoft Foundry Models resource (classic) and Manage Azure OpenAI in Microsoft Foundry Models quota (classic) .

## Upload data and create an index

While it’s useful to see how the model handles general questions, the chatbot should ground product-specific answers in the Contoso Camping Store catalog. That means you need a retrieval-augmented generation (RAG) pattern and a searchable index.

RAG is a pattern used in AI that uses a large language model (LLM) to generate answers with your own data. When a user asks a question, the data store is searched based on user input. The user question is then combined with the matching results and sent to the LLM using a prompt (explicit instructions to an AI or machine learning model) to generate the desired answer.

For RAG to work well, we need to find a way to search and send your data to the LLM in an efficient and cost-effective manner. This process is achieved by using an index. An index is a data store that allows you to search data efficiently. An index can be optimized for LLMs by creating vectors (text data converted to number sequences using an embedding model). A good index usually has efficient search capabilities like keyword searches, semantic searches, vector searches, or a combination of these examples. This optimized RAG pattern can be illustrated as follows.

Azure AI Foundry supports project data assets and vector indexes for RAG workflows. In hub-based projects, those assets appear under Data + indexes . The exact wizard pages can vary slightly over time, but the goal is the same: upload the product files, create a vector index backed by Azure AI Search, and then attach that project index in the chat playground.

An index asset contains important information such as:

Azure AI Search is the recommended backing store for the index in this project. The classic portal documentation often shows this workflow starting from the Chat playground , but in this guided project you create the same project assets from Data + indexes so you can inspect them directly. For more information, see Hub resources overview (classic) , Build and consume vector indexes in Microsoft Foundry portal (classic) , and Retrieval augmented generation (RAG) and indexes .

Let’s now upload the data and then create an index.

Data can come from an existing Azure Storage path, a URL, or an upload from your local machine. In this exercise, you upload the Products folder into the project as a data asset.

Let’s add the Contoso Camping Store product data via an upload of the products folder.

Uploading a folder creates a project data asset backed by the project's workspace storage. For more information, see How to add and manage data in your Microsoft Foundry hub-based project (classic) .

Now that the product data is uploaded, create a project index named products-index .

Index creation can take several minutes. Wait until the index status shows Completed before you continue.

## Create a system message

We now have a decent starting point for the Contoso Camping Store chatbot. We can ask questions about Contoso Camping Store products, but what happens if you enter a prompt that's irrelevant to the chatbot’s purpose or asks for general product recommendations?

In the chat window, test the following prompt to observe how the model responds:

Generative AI models are unpredictable, and without the proper guardrails in place, the Contoso Camping Store chatbot might not stay on course to only generate responses about Contoso Camping Store products. It can also help to make the chatbot's responses more customer-friendly by redirecting off-topic questions instead of exposing raw retrieval wording. Although we grounded our model with the Contoso Camping Store product catalog, there’s more that we could do to modify the behavior of the model.

Let’s start by defining the system message. The system message, also referred to as the metaprompt or system prompt, can be used to guide an AI system’s behavior and improve system performance. The system message should:

The system message is included in the prompt that's passed to the model, so it affects token usage. Use it to define the assistant's role, scope, tone, and fallback behavior - not to store conversation state, which belongs in chat history or retrieved data. System messages work best when they're specific, concise, and testable. For guidance on writing effective system messages, see Safety system messages .

Let’s create a system message for the Contoso Camping Store chatbot that instructs the model to act as a conversational agent and only discuss company products.

On the Chat playground page, within the System message box, enter:

You are the Contoso Camping Store chatbot. Help customers learn about and buy Contoso Camping Store products. - Only answer questions that are related to Contoso Camping Store products, product care, product compatibility, or purchase decisions. - For product-specific answers, use only the retrieved Contoso product data. - If the retrieved sources don't contain the answer, say you can't find it in the product catalog. Do not guess or invent details. - If a user asks about an unrelated topic, politely refuse and redirect them to Contoso Camping Store products. - Respond in the same language the user uses. - Bold each product name in the response. - If source references are provided with the retrieved content, use those references instead of inventing your own. Select Apply changes .

If a notification appears warning that updating the system message will start a new chat session, select Continue .

When defining more safety and behavioral guardrails, it’s helpful to first identify and prioritize the harms you want to address. Azure AI Foundry provides built-in Safety system messages that you can adapt for your scenario. Treat them as starting templates: add only the components that are relevant to this chatbot, replace generic placeholders with Contoso-specific wording, and remove any instructions that conflict with your main system message.

Select the + Add section drop-down and select Safety system messages .

On the Select safety system message(s) to insert screen, choose the templates that address harmful content , ungrounded content , and protected material (text) . These are the three categories Microsoft publishes ready-made templates for. Jailbreak and indirect-attack mitigations are handled later in this module by Prompt shields in your custom content filter, not by a system message template.

## Create a content filter

So far, the model has generated responses to neutral input. You should also test adversarial input to observe how the model behaves when harmful input is provided. In the chat window, submit the following prompt:

Given the harmful nature of this input, it’s best to block it altogether rather than let the model generate a product recommendation. To do that, create a custom content filter and attach it to the deployment.

Azure OpenAI deployments start with the default content filter, which blocks the four core harm categories at the medium threshold for both prompts and completions. Prompt shields for direct attacks and protected material detectors are also on by default, but Prompt shields for indirect attacks are off by default. Because this chatbot uses retrieved product documents, it's a good candidate for enabling indirect-attack protection in a custom content filter. The content filtering system is powered by Azure AI Content Safety .

All customers can configure low , medium , or high thresholds for the core harm categories. Approval is required only if you want to partially or fully disable those filters or use annotate-only behavior for them. For more information, see Configure content filters and Content filter configurability .

Create the content filter from the Guardrails + controls page in your project. For more information, see Configure content filters (classic) .

On the Input filter page, you can configure the filter for the user prompt. Content is annotated by category and blocked according to the threshold you set.

If your portal also shows Spotlighting for document attacks, leave it off for this exercise unless you specifically want the extra protection and understand that it increases token usage and can push large documents closer to model input limits.

On the Output filter page, you can configure the filter for model output. Content is annotated by category and blocked according to the threshold you set.

You can add the content filter to a deployment as part of the creation workflow. Alternatively, you can add the content filter later via the Models + endpoints page in your project.

In the classic experience, content filtering configurations are created at the Azure OpenAI resource level and can be reused across deployments within that resource.

Now that the content filter is created and attached to the deployment, return to the Chat playground and test whether the filter blocks the harmful input.

Now that the model blocks harmful input, we can move forward with evaluating the model's responses methodically.

## Run a manual evaluation

Given the recent improvements you made to the model’s behavior, it’s best that we evaluate the model’s output more methodically. In hub-based projects, Azure AI Foundry supports both manual and automated evaluations. Start with a manual evaluation so you can inspect outputs row by row before you move on to batch scoring.

Manual evaluation in Azure AI Foundry enables you to iteratively test your prompt configuration (system message, grounding, model, and parameters) against a test set in a single interface. With each response generation, you can manually rate the outputs to build confidence in your prompt and identify where more mitigation is needed.

After completing an evaluation, you can save the results. Reference the results as needed to make decisions on how to potentially improve the model’s responses and/or to compare to future manual evaluations.

A test set of data is provided for you that includes a set of prompts consisting of both relevant Contoso Camping Store queries and a few adversarial prompts. Let's run a manual evaluation to observe how the model performs.

This module uses the classic hub-based evaluation experience. The exact location of some controls can vary slightly as the portal evolves, but the workflow is the same: use the same assistant configuration you tested in the chat playground, run it against test data, inspect each output, and record whether it met your expectation. Because manual evaluations keep their own assistant setup, reapply your changes there and rerun the affected rows whenever you update the system message. For more information about evaluation concepts, see Hub resources overview (classic) and Run evaluations from the Microsoft Foundry portal .

In the left navigation, within the Assess and improve section, select Evaluation .

In the Assistant setup section, for System message , enter the following baseline version. It reflects the chatbot configuration you've built so far before you add the new recommendation-formatting instruction later in this unit:

You are the Contoso Camping Store chatbot. Help customers learn about and buy Contoso Camping Store products. - Only answer questions that are related to Contoso Camping Store products, product care, product compatibility, or purchase decisions. - For product-specific answers, use only the retrieved Contoso Camping Store product data. - If the retrieved sources don't contain the answer, say you can't find it in the product catalog. Do not guess or invent details. - If a user asks about an unrelated topic, politely refuse and redirect them to Contoso Camping Store products. - Respond in the same language the user uses. - Bold each product name in the response. - If source references are provided with the retrieved content, use those references instead of inventing your own. ## Safety guidance - You must not generate content that may be harmful to someone physically or emotionally even if a user requests or creates a condition to rationalize that harmful content. - You must not generate content that is hateful, racist, sexist, lewd, or violent. - If the user requests copyrighted content such as books, lyrics, recipes, or news articles, politely refuse and give a short summary instead. Select the Add your data tab.

If the products-index isn't selected, select the Select available project index drop-down and select products-index .

In the manual evaluation results table, select Import test data . If the portal asks whether to save the dataset as a reusable asset first, you can continue without saving for this exercise.

On the Select dataset page, select Upload file and upload the e2e-manual-evaluation.jsonl file and select Next .

On the Map data page, select the following within the Dataset mapping section:

## Run and compare automated evaluations

Automated evaluations in Azure AI Foundry use built-in evaluators to score model or dataset outputs at scale. AI-assisted quality evaluators such as coherence and fluency use a judge model, while similarity compares responses against expected answers when you provide ground-truth data. Risk and safety evaluators inspect content for harmful or insecure behavior. Evaluator availability varies by region, which is one reason this module uses East US 2 .

AI-assisted evaluation is useful when you want a repeatable way to measure both quality and safety across many prompts. It's especially helpful in generative AI scenarios where outputs are open-ended and traditional pass-or-fail checks aren't enough.

In this unit, you use a dataset target. That means Azure AI Foundry scores the responses already stored in the .jsonl file instead of rerunning your live playground configuration. The sample dataset includes prompt, answer, and ground-truth fields so you can evaluate the dataset's quality and safety profile at scale.

The evaluation may take a few minutes to execute. Once the evaluation is complete, open the evaluation run to review the results. If a metric is unavailable or missing, verify your region and model support. For more information, see Run evaluations from the Microsoft Foundry portal and Rate limits, region support, and enterprise features for evaluation .

The results for the automated evaluation vary because the evaluation is influenced by the judge model and the dataset. Therefore, the review of results provided is generalized and based on sample automated evaluation results. Treat the scores as signals for investigation, not proof that the app is production-ready, and analyze your own row-level results to decide what to improve next.

Select the i icon or Learn more about metrics link for evaluator definitions and scoring details. For more information, see View evaluation results in the Microsoft Foundry portal .

Now that you have the results of the automated evaluation, you're equipped with analytical data to influence and support your next course of action. Does the system message need adjustments? Is there another data connection to be made? Or do you suspect that another model might provide better results? These are some of the ideas that might come to mind after analyzing the results.

To facilitate a comprehensive comparison between two or more runs, select the runs you want to compare and open the comparison view. In this exercise, you use a second pregenerated dataset so you can practice the comparison experience without having to regenerate outputs yourself first.

The e2e-automated-evaluation-2.jsonl file is a pregenerated sample that simulates improved outputs after changes such as refining the system message, adjusting content filters, and improving the grounded data. In a real workflow, you would make those changes in your app and then regenerate or capture a fresh dataset before running the second evaluation.

There's now a clearer picture of how the scored outputs differ between runs. In a production workflow, pair automated evaluations with human review and compare fresh runs each time you change prompts, grounding data, models, or guardrails. For more information about evaluator categories, region support, and results interpretation, see Run evaluations from the Microsoft Foundry portal , Rate limits, region support, and enterprise features for evaluation , and View evaluation results in the Microsoft Foundry portal .

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

Choose the best response for each of the questions.

What should the chatbot do when the retrieved product data doesn't contain the answer?

Say it can't find the answer in the product catalog and avoid guessing.

Use general model knowledge to provide the most likely answer.

Switch to general camping advice even if the question is product-specific.

Invent a reasonable price or feature so the response stays helpful.

For Azure OpenAI model deployments, what is the threshold level for the default content filter?

After you select two or more automated evaluation runs, which action opens the comparison view?

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

In this guided project, you created layered mitigations for the Contoso Camping Store chatbot by grounding the model with product data, refining the system message, applying a content filter, and reviewing the results with manual and automated evaluations.

While manual evaluation enables human reviewers to spot-check output quality, automated evaluation helps you measure quality and safety at scale. Use automated scores together with human review rather than as a replacement for it. Safeguarding your app with Azure AI Content Safety and well-designed system messages helps you reduce harmful or off-topic behavior before deployment.

The next step before deployment is to operationalize the application by creating a rollout and readiness plan. Operationalizing includes planning for phased delivery, defining incident response procedures, monitoring the system in production, and incorporating user feedback into future prompt, data, and guardrail updates.

Although the process applied today might look linear, it's an iterative process. As you introduce new features, monitor usage, and/or implement user feedback, you're encouraged to revisit each step in the generative AI development lifecycle.

After completing this guided project, if you've finished exploring Azure AI Foundry and related Azure resources, delete the resources that you created during the exercise to avoid ongoing charges.

Want to try using Ask Learn to clarify or guide you through this topic?
