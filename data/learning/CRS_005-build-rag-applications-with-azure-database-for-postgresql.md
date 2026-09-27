# Build RAG applications with Azure Database for PostgreSQL

## Introduction

Retrieval Augmented Generation (RAG) applications combine information retrieval and generative AI to provide accurate, context-aware answers by using large datasets and advanced search techniques.

Imagine you're a solution architect at a mid-sized enterprise tasked with building an internal knowledge assistant for employees to query company policies. The current system struggles with slow response times and often retrieves irrelevant or outdated information, frustrating users. Your team decides to implement a Retrieval Augmented Generation (RAG) application using Azure Database for PostgreSQL and Azure OpenAI . However, as the dataset grows to millions of rows, challenges like ensuring fast retrieval, maintaining accuracy, and avoiding AI-generated responses that might be incorrect. Additionally, complex queries involving multiple concepts, such as 'What are the vacation policies for HR in Europe?' require precise filtering and ranking. To address these issues, you need to optimize retrieval speed, improve accuracy through advanced indexing and chunking strategies, and explore innovative solutions like lightweight knowledge graphs. This module guides you through building and refining a scalable RAG pipeline tailored to such real world challenges.

Want to try using Ask Learn to clarify or guide you through this topic?

## Understand RAG pattern with Azure Database for PostgreSQL

Imagine you’re building an internal assistant that answers employee questions about company policies. A large language model (LLM) can generate fluent responses. However, if it doesn’t have access to your latest company data, the LLM gives outdated or incorrect answers. Retrieval Augmented Generation (RAG) solves this issue by combining the reasoning power of an LLM with the accuracy of your own data.

LLMs are trained on vast quantities of text but don’t know your organization’s data or proprietary content. To address this problem, RAG retrieves relevant information from trusted sources you provide, grounding the LLM model’s response. This approach improves accuracy, reduces AI-generated responses that might be incorrect, and ensures answers are based on facts you control.

A RAG pipeline consists of several key components that work together to provide accurate and relevant responses. Think of RAG as a sequence of steps working together:

So, if, for example, you store your company policies in the database, the RAG pipeline can help retrieve the most relevant policy for your own company instead of generic data that an LLM by itself might provide.

Azure Database for PostgreSQL can handle the retrieval layer of this pipeline. Azure Database for PostgreSQL includes built-in support for vector embeddings and similarity search. What this means is that you can use the database's capabilities to efficiently manage and query your embeddings. Azure Database for PostgreSQL provides two key extensions that make this process possible:

So, there's no need for a separate vector database. You can keep everything together, your structured data, metadata, and embeddings—inside your PostgreSQL instance, which also simplifies governance and security.

Azure Database for PostgreSQL can, for example, be used to implement a RAG pipeline for your company's internal knowledge base. An application uses Azure Database for PostgreSQL to query the database for relevant documents and use them as context for generating answers. You then feed that context into the language model to produce a natural language response.

For example, let’s say you have a table of the company policies called company_policies . You can use the azure_ai extension to generate embeddings for each policy and store them alongside the text on the same table. That way, when employees ask a question, that question is turned into an embedding, and you can pull up the matching policies right away. The following SQL commands illustrate how to set this up:

Before you can run the CREATE EXTENSION commands to enable these extensions, you must add azure_ai and vector to the azure.extensions Server parameter on the Azure Database for PostgreSQL server either through the Azure portal or through CLI commands.

-- Enable required extensions (to enable, only need to be run once per database) CREATE EXTENSION IF NOT EXISTS azure_ai; CREATE EXTENSION IF NOT EXISTS vector; -- Configure Azure OpenAI endpoint and key (requires azure_ai_settings_manager role) SELECT azure_ai.set_setting('azure_openai.endpoint', '<your-endpoint>'); SELECT azure_ai.set_setting('azure_openai.subscription_key', '<your-key>'); -- Create a table to store documents and embeddings CREATE TABLE IF NOT EXISTS company_policies ( id bigserial PRIMARY KEY, title text, policy_text text NOT NULL, embedding vector(1536) -- set to your model's dimension ); -- Insert a sample row and generate its embedding in one step. -- Obviously your table will have hundreds, thousands or millions of rows. INSERT INTO company_policies (title, policy_text, embedding) VALUES ( 'vacation policy', 'Employees receive 15 vacation days per year. Unused days can roll over to the next year.', azure_openai.create_embeddings('<embedding-deployment-name>', 'Employees receive 15 vacation days per year. Unused days can roll over to the next year.') ); -- Run a quick test to retrieve the most similar chunk to a sample question. -- Notice how you are converting the question into an embedding for the search, -- then using that embedding to find the closest match in the database. SELECT id, title, policy_text FROM company_policies ORDER BY embedding <-> azure_openai.create_embeddings('<embedding-deployment-name>', 'How many vacation days do employees get?')::vector LIMIT 1; -- This query returns the most relevant row that matches the query. -- The final step on a RAG is to pass 'both' the returned row(s) and the question back -- to your application. Your application then passes that context to the LLM -- to generate a natural language answer. In this example, the table is now ready to store policies and their embeddings. You can insert policies into the table using SQL commands, and the embeddings are generated using the Azure AI services. You cover indexing and querying these embeddings in later sections.

Regardless of the complexity of your own solutions, you use a similar approach to set up your own environment. First, you enable the required extensions, then create your tables with their respective vector columns, and then start inserting and embedding your content together. You then ask your questions whose embeddings are then compared to the table's embeddings. Finally, the rows returned from the database are used to provide context to the LLM to generate a natural language answer. These steps allow you to easily build a RAG application on top of your PostgreSQL database.

Azure Database for PostgreSQL can effectively implement RAG patterns by applying its builtin AI and vector search capabilities. The azure_ai extension enables seamless integration with Azure OpenAI and Azure AI Services for generating embeddings, creating chat completions, and using semantic operators for tasks such as text generation, information extraction, truth evaluation, and ranking—directly within SQL queries. The vector (pgvector) extension facilitates efficient storage and retrieval of embeddings, making it possible to perform similarity searches without the need for a separate vector database. Start small when applying these methods to new scenarios, gradually expanding the scope as you refine your approach in your own environment.

## Explore information retrieval challenges - scale and accuracy

Retrieval augmented generation (RAG) depends on pulling the right passages from your data before the model answers. Two issues show up as your content grows: scale and accuracy . Scale is about how your data size and access patterns grow, and how fast results come back. Accuracy is about whether those results actually answer the question. If retrieval is slow or off target, the experience suffers regardless of the model's strength.

In a RAG, every user question triggers a nearest neighbor search over vectors. As more rows are added and more users query the data at once, data access patterns slow down and concurrency pressure increases the delay.

Keep retrieval inside Azure Database for PostgreSQL and decide how results are searched and ranked in the database. Start with pgvector for vector similarity search. When data sets grow, use an approximate index so queries avoid comparing against every row. To improve performance, pgvector provides index options like IVFFlat or HNSW . For very large data sets, consider DiskANN through the pg_diskann extension, which is designed for high recall, high QPS (queries per second), and low latency at large scale .

Fast queries don't help if they return the wrong passages. Missing relevant rows or ranking them poorly forces the model to guess.

Treat accuracy as a two-step concern in the database. First, generate good candidates with pgvector using a distance function that matches your embeddings and an index that balances recall and latency for your size. Second, improve ordering when needed. You can rerank results directly in SQL by using the semantic operators in the azure_ai extension—such as azure_ai.rank for LLM-based relevance ranking.

There's also a Semantic Ranker solution accelerator for Azure Database for PostgreSQL if you want a full pipeline example built around this pattern. Both approaches are designed to run with PostgreSQL as the single data tier.

Some domains benefit from modeling how things connect. A graph step can improve retrieval by using relationships and prominence signals. Graph queries are available in Azure Database for PostgreSQL through the Apache AGE extension. GraphRAG is a Microsoft Research approach that combines vector search with graph queries to improve retrieval accuracy . It extracts a knowledge graph from your data and uses that structure to supply better context to the Large Language Model.

You need to establish a monitoring strategy that captures key metrics and provides insights into query performance.

Create a baseline of your RAG query performance using:

These tools help you identify bottlenecks and areas for improvement in your RAG pipeline. They help you make determinations about performance ( scale ), but you need other strategies to ensure retrieval accuracy .

While measuring accuracy isn't as straightforward as measuring for scale , you can use some of the lessons from the Architecture Center article on the evaluation phase.

As your application grows, reevaluate your application's performance and adjust your RAG pipeline as needed. It's important to monitor both retrieval speed and accuracy over time.

## Enhance scale with vector indexes

As your data set grows from hundreds to millions of rows, fast retrieval becomes a hard requirement. Without optimization, a similarity search scans the entire table, which raises latency and hurts the user experience. A vector index reduces the work by directing the database to the most promising rows first, so queries return faster. Azure Database for PostgreSQL supports vector indexes through the pgvector and pg_diskann extensions. In a Retrieval Augmentation Generation (RAG) solution, store each item's embedding in a vector column on the same row as its related fields, then index that column. That index is the vector index .

To be able to use pgvector or pg_diskann on a Flexible Server, you must first add the vector extension on the Server parameters azure.extensions parameter.

Speed is the name of the game. You want your queries to return results as quickly as possible. Think of an HR assistant that answers questions about policies. With 500 rows, a full scan might be fine. With 5 million rows, it isn't. Indexes reduce the amount of data scanned at query time. Indexes trade a bit of storage and build time for faster queries as data grows. Vector indexes quickly narrow down the search space, allowing for rapid retrieval of relevant rows.

PostgreSQL supports several approximate nearest neighbor index types for vector search. Each has its own strengths and weaknesses. Two are provided by the pgvector extension, and a third is available via the pg_diskann extension:

IVFFlat (Inverted File with Flat Compression) - Provided by the pgvector extension. Groups vectors into many lists . At query time, it picks the closest lists and compares the query only to items in those lists. The ivfflat.probes setting controls how many lists to check per query; more probes usually improve recall but add time. If you set probes equal to the number of lists, the search checks every list (an exact search over the index) and loses the speed benefit. Begin with the defaults and adjust ivfflat.probes at query time if obvious matches are missing.

HNSW (Hierarchical Navigable Small Worlds) - Provided by the pgvector extension. Builds a multilayer neighbor graph. Search begins in the top layer and narrows as it moves down to denser layers near the closest neighbors. Compared to IVFFlat , it can deliver better query speed at similar recall, but it uses more memory and takes longer to build. There's no training step, so you can create the index even on an empty table. The key settings are m and ef_construction when you build, and hnsw.ef_search when you query. The m parameter sets the maximum number of connections per node in each layer (default 16). The ef_construction parameter sets the size of the candidate list while the index is built (default 64). At query time, hnsw.ef_search controls the candidate list the search keeps (default 40). Larger values generally improve recall, with more memory or longer build/query time. Start with defaults, then adjust hnsw.ef_search when speed matters more and results are already solid.

DiskANN (Disk Approximate Nearest Neighbor) - Provided by the pg_diskann extension. This extension adds a separate DiskANN index access method. Keeps most of the structure on disk with a small working set in memory; designed for very large data. It offers high recall, high queries per second, and low query latency, even for tables with billions of rows. DiskANN’s Azure implementation stores full vectors on SSD while compressing working sets in RAM, which trims memory use and limits SSD reads during queries. The built-in vector compression and quantization preserve accuracy as data evolves, making DiskANN a strong fit for large semantic search and RAG scenarios. The defaults aim for strong results at large scale. If searches skip good neighbors, raise diskann.l_value_is to consider more candidates, then check latency. If memory is tight on very large tables, create the index with product_quantized = true to reduce memory use, noting there can be a small quality trade-off.

Creating an index in Azure Database for PostgreSQL is simple, first enable the respective extension, and then run the respective CREATE INDEX statement for the index type you want to use. Let's assume you're creating a vector index for a table named company_policies . The table embeddings are stored in a vector column named embedding .

Create the extension in PostgreSQL (you only need to enable the extension once per database):

CREATE EXTENSION IF NOT EXISTS vector; Create an IVFFlat index:

CREATE INDEX company_policies_vec_ivf ON company_policies USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100); ANALYZE company_policies; This statement creates an IVFFlat index on the embedding column of the company_policies table. The lists parameter specifies how many lists to create in the index. You can adjust this value based on your data size and query performance needs.

CREATE INDEX company_policies_vec_hnsw ON company_policies USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64); This statement creates an HNSW index on the embedding column of the company_policies table. The m parameter sets the maximum number of connections per node, and ef_construction controls the size of the candidate list during index construction.

## Build RAG Applications with Azure Database for PostgreSQL and Python

Now that the database is ready with embeddings and vector indexes, it’s time to turn retrieval into a working application. The goal is simple: take a user question, retrieve the most relevant chunks from PostgreSQL, and generate an answer grounded in those chunks using Azure OpenAI through LangChain .

In this unit, you learn the basics of building a RAG application in Python . The application connects to the database, runs a similarity search on the database, and passes the search results to a model with clear instructions to avoid hallucinations. Since the model receives a well defined context based on the database data, it can generate more accurate and relevant answers grounded in that context.

Remember from our previous units, the RAG flow is a set of steps that combines retrieval and generation. Let’s break it down:

LangChain provides a framework for building applications with language models. It simplifies the process of connecting to various data sources, managing prompts, and handling responses. By combining Azure Database for PostgreSQL with Python and LangChain , you can create a powerful RAG application that retrieves relevant information and generates accurate responses. While your RAG application might evolve, these core principles guide its development.

In this application, you use the LangChain AzureChatOpenAI wrapper to interact with the Azure OpenAI service.

For the following Python examples, you use the following table structure:

CREATE TABLE company_policies ( id SERIAL PRIMARY KEY, title TEXT, policy_text TEXT, embedding VECTOR(1536) ); In this table, you assume a vector index is created on the embedding column to enable efficient similarity searches.

Let's review the Python code snippets for each step. Most RAG applications follow a similar structure.

Keep connections short-lived and secure. In this example, secrets are in environment variables and passed to the connection.

import os, psycopg2 from contextlib import contextmanager @contextmanager def get_conn(): conn = psycopg2.connect( host=os.getenv("PGHOST"), user=os.getenv("PGUSER"), password=os.getenv("PGPASSWORD"), dbname=os.getenv("PGDATABASE"), connect_timeout=10 ) try: yield conn finally: conn.close() This script sets up a context manager for database connections, ensuring they're properly closed after use. Time to move to the actual retrieval.

Since the user is asking a question, you need a function to query the database with that question. That function should return the relevant chunks based on the question. This example assumes that the vector index is ranked using cosine distance , so you use the respective operator class (<=>) for querying.

def retrieve_chunks(question, top_k=5): sql = """ WITH q AS ( SELECT azure_openai.create_embeddings(%s, %s)::vector AS qvec ) SELECT id, title, policy_text FROM company_policies, q ORDER BY embedding <=> q.qvec LIMIT %s; """ params = (os.getenv("OPENAI_EMBED_DEPLOYMENT"), question, top_k) with get_conn() as conn, conn.cursor() as cur: cur.execute(sql, params) rows = cur.fetchall() return [{"id": r[0], "title": r[1], "text": r[2]} for r in rows] So this function retrieves relevant chunks from the database based on the user's question. These chunks are then used to generate a context-aware answer in a subsequent step.

## Exercise: Build RAG applications with Azure Database for PostgreSQL and Python

In this exercise, you build a simple RAG (Retrieval-Augmented Generation) application using Python and Azure Database for PostgreSQL. The application retrieves relevant policy chunks from the database based on user questions and generates context-aware answers using a language model.

To complete this exercise, you will need an Azure subscription and be approved for Azure OpenAI access. If you need Azure OpenAI access, apply at the Azure OpenAI limited access page.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Improve accuracy with advanced RAG architectures

So far, the pipeline retrieves relevant chunks and answers based on them. But accuracy can still suffer when queries are ambiguous, chunks are too large, or ranking is weak. This unit explores strategies to improve precision and recall without sacrificing speed. These techniques build on the foundation from earlier units and prepare you for more advanced RAG patterns.

Even when a vector search is used, wrong, or incomplete context leads to fluent but incorrect answers. Users lose trust if the assistant sounds confident but is wrong. Improving accuracy means:

There are many strategies to improve accuracy in retrieval-augmented generation (RAG) systems. Let's explore some of the core techniques.

Chunking and embeddings - Start with moderate chunk sizes for embeddings, about 512 tokens, and use small overlaps of roughly 10 to 15 percent. Tune these values for your data. If you change how you chunk, recompute the embeddings so the index matches the new boundaries. Azure guidance recommends around 512 tokens per chunk with 10 to 15 percent overlap as a starting point.

Query rewriting - Normalize and expand queries before embedding by fixing spelling, resolving acronyms, and adding missing context. When a question is ambiguous, apply lightweight rules or use a Large Language Model (LLM) to rewrite it into a clearer form. For example, turn "vacation policy" into "How many vacation days do employees get?"

Hybrid search - Combine vector similarity with keyword or metadata filters, such as WHERE department = 'HR' . When you need both keyword and vector signals, merge results with a reranker like Reciprocal Rank Fusion to improve recall and ordering.

Metadata filtering - Tag chunks with attributes such as department, date, or document type. Filter on these fields at query time to cut noise and speed up the search.

Semantic ranking - After the initial retrieval, rerank with a cross-encoder or an LLM scoring step to tighten the ordering when similarity alone isn't enough.

Querying for relevant chunks isn't enough. Context matters as well, and these strategies help ensure the model has the right context for each query.

While those strategies improve accuracy, they can still struggle with complex queries or large document sets. Advanced architectures build on these foundations to unlock new capabilities. Let's explore a few key approaches.

Build a knowledge graph from your content and retrieve along relationships, for example policy → benefits → vacation. Azure provides a GraphRAG framework that runs on Azure Database for PostgreSQL .

Use summary or higher-level indexes to narrow candidates first, then drill down to exact chunks. This method is useful for long documents at scale.

## Explore GraphRAG with Azure Database for PostgreSQL

As your data grows, many documents or rows start to sound alike. This unit shows how to keep the full retrieval flow inside Azure Database for PostgreSQL while also taking relationships into account. Documents stay in tables. Relationships live in a property graph with Apache AGE (A Graph Extension) and are queried with openCypher . When the question is evaluated, you combine meaning-based matches from pgvector (with optional reranking) and a relationship score from the graph. Because the whole flow runs in SQL, the system is easier to operate and easier to understand.

Apache AGE adds graph features to Azure Database for PostgreSQL . You model entities as nodes and relationships as edges , with properties on both. This method lets you run graph queries alongside your regular SQL, so you can mix structured tables and graph structure in one place. It fits use cases like social networks, recommendation systems, and knowledge graphs. You get the strengths of both relational and graph models without running a second database.

Text similarity is good at "this looks like that" answers, but large sets of similar or near duplicate text can hide the best answers. Reranking improves ordering, yet it still scores passages one by one. Many questions depend on connections like citations, comembership, repeated references, and neighborhood patterns. In the company policy database example, you might have two sections about taxi reimbursement. One lives in the 2025 Travel Policy and several current rules point to it. The other is a 2023 section kept for historic purposes with no current links to it. A plain similarity search treats them the same. But when you also look at how rules connect to policies using the graph, the 2025 section rises to the top. That result is the one you return.

When similarity alone isn't enough, GraphRAG is a method from Microsoft Research that improves RAG by extracting a knowledge graph from your source data and using that structure to supply better context to the Large Language Model (LLM). It has three main steps:

In the company policy database example, use the company_policies table as the source. Each row becomes a Policy node with policy_id , title , policy_text , department , and category as properties. Create Entity nodes from values you already have (one per department and one per category). Optionally add Entity nodes for important terms found in policy_text (such as "taxi reimbursement" or "airport"). Connect them with edges:

Store this graph in the same Postgres instance with Apache AGE so you can join graph results back to company_policies without the need for a separate graph database.

Entity summarization Create short summaries for each policy and, if helpful, for small groups (for example, by category or department). The GraphRAG library can build multi-level summaries. Keep these summaries as node properties so they're easy to fetch during ranking and when preparing model context.

Graph query generation at query time At question time, run vector search over company_policies.embedding to get an initial set of candidates by semantic similarity. In parallel, run an openCypher query that scores how well each candidate is connected to what the question is about. For the "taxi reimbursement from the airport" example, the graph score can reward policies that belong to the Travel category, sit under the Finance department (or another relevant one), and mention entities like taxi reimbursement and airport .

Similarity alone often ties near duplicate sections. The graph step promotes sections that both match the question and sit in the right part of the network. The final context you send to the model is smaller, clearer, and easier to justify. The full pipeline, vector search, optional semantic reranking, openCypher graph query, and RRF (Reciprocal Rank Fusion), runs inside Postgres.

With similarity only, look-alike text can crowd out the right passage. In the taxi reimbursement example, relationship signals push items that match the question and live in the most relevant category, department, or topic to the top. The context you pass to the model is tighter and easier to defend, and you can point to exact paths and scores to explain each rank.

Use GraphRAG in Azure Database for PostgreSQL to keep data and relationships in one place, rank results by both meaning and connections, and cite the exact source for each answer. The GraphRAG solution accelerator shows the full pipeline. It includes vector search, semantic reranking, openCypher graph scoring, and rank fusion. It runs inside Postgres and is written in SQL, and it delivers clear gains over vector-only retrieval.

You can keep reranking inside the database with SQL semantic operators. The rank() operator from the azure_ai semantic operators lets you rerank top candidates with state of the art models directly in a query, so you can combine semantic ranking with graph scoring without leaving Postgres. As your data grows, pair the graph step with the right vector index. DiskANN in Azure Database for PostgreSQL supports high dimensional embeddings (up to 16,000 dimensions), faster index builds, and a Product Quantization that can reduce memory and cost while maintaining high accuracy. Reported gains include up to 10× faster performance and about 4× cost savings versus an HNSW (Hierarchical Navigable Small Worlds) index.

## Exercise: Implement GraphRAG with Azure Database for PostgreSQL

GraphRAG combines text similarity with graph-based connections to improve retrieval accuracy in RAG applications. In this exercise, you implement a GraphRAG pipeline using Azure Database for PostgreSQL with the Apache AGE extension and pgvector for vector similarity search. You extract a lightweight knowledge graph from your data and use it to enhance retrieval for complex queries.

To complete this exercise, you will need an Azure subscription and be approved for Azure OpenAI access. If you need Azure OpenAI access, apply at the Azure OpenAI limited access page.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

What does GraphRAG add to a standard RAG pipeline?

A replacement for vector search that removes embeddings

A knowledge graph so retrieval can follow relationships before ranking with embeddings

A new fine-tuned model trained on policies

When results are combined from vector and keyword searches, what simple method helps merge rankings?

What SQL statement is useful to check timing and confirm a vector index is used?

EXPLAIN (ANALYZE, BUFFERS) followed by the query

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

In this module, you learn how to build a scalable RAG application on Azure Database for PostgreSQL using the azure_ai and pgvector extensions. You set up efficient embedding storage and similarity search, apply vector indexing with IVFFlat , HNSW , and DiskANN , and tune the retrieval pipeline with hybrid search. You also integrate a lightweight knowledge graph through GraphRAG to pull in relationship context, then apply Semantic Ranking to refine results so answers stay precise and relevant. The full RAG application runs with Azure Database for PostgreSQL , Python , and LangChain to keep the workflow straightforward.

These skills translate to faster query execution, improved retrieval accuracy, and an architecture that scales to millions of rows with low latency and high recall. The knowledge graph layer improves domain understanding and helps resolve unclear questions for complex, real world use cases. Semantic Ranking tightens ordering when similarity alone isn't enough. The outcome is reliable, context-aware responses that support decision making and automation.

After completing this module, you learn:

Want to try using Ask Learn to clarify or guide you through this topic?
