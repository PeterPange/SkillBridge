# Introduction to Transact-SQL

## Introduction

SQL is an acronym for Structured Query Language. SQL is used to communicate with relational databases. SQL statements are used to perform tasks such as update data in a database, or retrieve data from a database. For example, the SQL SELECT statement is used to query the database and return a set of data rows. Some common relational database management systems that use SQL include Microsoft SQL Server, MySQL, PostgreSQL, MariaDB, and Oracle.

There is a SQL language standard defined by the American National Standards Institute (ANSI). Each vendor adds their own variations and extensions.

Basic SQL statements, such as SELECT , INSERT , UPDATE , and DELETE are available no matter what relational database system you're working with. Although these SQL statements are part of the ANSI SQL standard, many database management systems also have their own extensions. These extensions provide functionality not covered by the SQL standard, and include areas such as security management and programmability. Microsoft database systems such as SQL Server, Azure SQL Database, Microsoft Fabric, and others use a dialect of SQL called Transact-SQL, or T-SQL . T-SQL includes language extensions for writing stored procedures and functions, which are application code that is stored in the database, and managing user accounts.

Programming languages can be categorized as procedural or declarative . Procedural languages enable you to define a sequence of instructions that the computer follows to perform a task. Declarative languages enable you to describe the output you want, and leave the details of the steps required to produce the output to the execution engine.

SQL supports some procedural syntax, but querying data with SQL usually follows declarative semantics. You use SQL to describe the results you want, and the database engine's query processor develops a query plan to retrieve it. The query processor uses statistics about the data in the database and indexes that are defined on the tables to come up with a good query plan.

SQL is most often (though not always) used to query data in relational databases. A relational database is one in which the data has been organized in multiple tables (technically referred to as relations ), each representing a particular type of entity (such as a customer, product, or sales order). The attributes of these entities (for example, a customer's name, a product's price, or a sales order's order date) are defined as the columns, or attributes, of the table, and each row in the table represents an instance of the entity type (for example, a specific customer, product, or sales order).

The tables in the database are related to one another using key columns that uniquely identify the particular entity represented. A primary key is defined for each table, and a reference to this key is defined as a foreign key in any related table. This is easier to understand by looking at an example:

The diagram shows a relational database that contains four tables:

Each customer is identified by a unique CustomerID field - this field is the primary key for the Customer table. The SalesOrderHeader table has a primary key named OrderID to identify each order, and it also includes a CustomerID foreign key that references the primary key in the Customer table so it identifies which customer is associated with each order. Data about the individual items in an order are stored in the SalesOrderDetail table, which has a composite primary key that combines the OrderID in the SalesOrderHeader table with a LineItemNo value. The combination of these values uniquely identifies a line item. The OrderID field is also used as a foreign key to indicate which order the line item belongs to, a ProductID field is used as a foreign key to the ProductID primary key of the Product table to indicate which product was ordered.

Set theory is one of the mathematical foundations of the relational model of data management and is fundamental to working with relational databases. While you might be able to write queries in T-SQL without a thorough understanding of sets, you may eventually have difficulty writing some of the more complex types of statements that may be needed for optimum performance.

Without diving into the mathematics of set theory, you can think of a set as "a collection of definite, distinct objects considered as a whole." In terms applied to SQL Server databases, you can think of a set as a collection of distinct objects containing zero or more members of the same type. For example, the Customer table represents a set: specifically, the set of all customers. You will see that the results of a SELECT statement also form a set.

As you learn more about T-SQL query statements, it is important to always think of the entire set, instead of individual members. This mindset will better equip you to write set-based code, instead of thinking one row at a time. Working with sets requires thinking in terms of operations that occur "all at once" instead of one at a time.

## Work with schemas

In SQL Server database systems, tables are defined within schemas to create logical namespaces in the database. For example, a Customer table might be defined in a Sales schema, while a Product table is defined in a Production schema. The database might track details of orders that customers have placed in an Order table in the Sales schema. You then might also need to track orders from suppliers for product components in an Order table in the Production schema.

Database systems such as SQL Server use a hierarchical naming system. This multi-level naming helps to disambiguate tables with the same name in different schemas. The fully qualified name of an object includes the name of a database server instance in which the database is stored, the name of the database, the schema name, and the table name. For example: Server1.StoreDB.Sales.Order .

When working with tables within the context of a single database, it's common to refer to tables (and other objects) by including the schema name. For example, Sales.Order .

Want to try using Ask Learn to clarify or guide you through this topic?

## Explore the structure of SQL statements

In any SQL dialect, the SQL statements are grouped together into several different types of statements. These different types are:

Sometimes you may also see TCL listed as a type of statement, to refer to Transaction Control Language . In addition, some lists may redefine DML as Data Modification Language , which wouldn't include SELECT statements, but then they add DQL as Data Query Language for SELECT statements.

In this module, we'll focus on DML statements. These statements are commonly used by data analysts to retrieve data for reports and analysis. DML statements are also used by application developers to perform "CRUD" operations to create, read, update, or delete application data.

Want to try using Ask Learn to clarify or guide you through this topic?

## Examine the SELECT statement

Transact-SQL or T-SQL, is a dialect of the ANSI standard SQL language used by Microsoft SQL products and services. It is similar to standard SQL. Most of our focus will be on the SELECT statement, which has by far the most options and variations of any DML statement.

Let's start by taking a high-level look at how a SELECT statement is processed. The order in which a SELECT statement is written is not the order in which it is evaluated and processed by the SQL Server database engine.

SELECT OrderDate, COUNT(OrderID) AS Orders FROM Sales.SalesOrder WHERE Status = 'Shipped' GROUP BY OrderDate HAVING COUNT(OrderID) > 1 ORDER BY OrderDate DESC; The query consists of a SELECT statement, which is composed of multiple clauses , each of which defines a specific operation that must be applied to the data being retrieved. Before we examine the run-time order of operations, let's briefly take a look at what this query does, although the details of the various clauses will not be covered in this module.

The SELECT clause returns the OrderDate column, and the count of OrderID values, to which it assigns the name (or alias ) Orders :

SELECT OrderDate, COUNT(OrderID) AS Orders The FROM clause identifies which table is the source of the rows for the query; in this case it's the Sales.SalesOrder table:

FROM Sales.SalesOrder The WHERE clause filters rows out of the results, keeping only those rows that satisfy the specified condition; in this case, orders that have a status of "shipped":

WHERE Status = 'Shipped' The GROUP BY clause takes the rows that met the filter condition and groups them by OrderDate , so that all the rows with the same OrderDate are considered as a single group and one row will be returned for each group:

GROUP BY OrderDate After the groups are formed, the HAVING clause filters the groups based on its own predicate. Only dates with more than one order will be included in the results:

HAVING COUNT(OrderID) > 1 For the purposes of previewing this query, the final clause is the ORDER BY, which sorts the output into descending order of OrderDate :

ORDER BY OrderDate DESC; Now that you've seen what each clause does, let's look at the order in which SQL Server actually evaluates them:

To apply this understanding to our example query, here is the logical order at run time of the SELECT statement above:

FROM Sales.SalesOrder WHERE Status = 'Shipped' GROUP BY OrderDate HAVING COUNT(OrderID) > 1 SELECT OrderDate, COUNT(OrderID) AS Orders ORDER BY OrderDate DESC; Not all the possible clauses are required in every SELECT statement that you write. The only required clause is the SELECT clause, which can be used on its own in some cases. Usually a FROM clause is also included to identify the table being queried. In addition, Transact-SQL has other clauses that can be added.

## Work with data types

Columns and variables used in Transact-SQL each have a data type . The behavior of values in expressions depends on the data type of the column or variable being referenced. For example, as you saw previously, you can use the + operator to concatenate two string values, or to add two numeric values.

The following table shows common data types supported in a SQL Server database.

For more details on the different data types and their attributes, visit the Transact-SQL reference documentation .

Compatible data type values can be implicitly converted as required. For example, suppose you can use the + operator to add an integer number to a decimal number, or to concatenate a fixed-length char value and a variable length varchar value. However, in some cases you may need to explicitly convert values from one data type to another - for example, trying to use + to concatenate a varchar value and a decimal value will result in an error, unless you first convert the numeric value to a compatible string data type.

Implicit and explicit conversions apply to certain data types, and some conversions aren't possible. For more information, use the chart in the Transact-SQL reference documentation .

The CAST function converts a value to a specified data type if the value is compatible with the target data type. An error is returned if incompatible.

For example, the following query uses CAST to convert the integer values in the ProductID column to varchar values (with a maximum of 4 characters) in order to concatenate them with another character-based value:

SELECT CAST(ProductID AS varchar(4)) + ': ' + Name AS ProductName FROM Production.Product; Possible result from this query might look something like this:

However, let's suppose the Size column in the Production.Product table is a nvarchar (variable length, Unicode text data) column that contains some numeric sizes (like 58) and some text-based sizes (like "S", "M", or "L"). The following query tries to convert values from this column to an integer data type:

SELECT CAST(Size AS integer) As NumericSize FROM Production.Product; This query results in the following error message:

Error: Conversion failed when converting the nvarchar value 'M' to data type int.

Given that at least some of the values in the column are numeric, you might want to convert those values and ignore the others. You can use the TRY_CAST function to convert data types.

## Handle NULLs

A NULL value means no value or unknown . It does not mean zero or blank, or even an empty string. Those values are not unknown. A NULL value can be used for values that haven’t been supplied yet, for example, when a customer has not yet supplied an email address. As you've seen previously, a NULL value can also be returned by some conversion functions if a value is not compatible with the target data type.

You'll often need to take special steps to deal with NULL. NULL is really a non-value. It is unknown. It isn't equal to anything, and it’s not unequal to anything. NULL isn't greater or less than anything. We can’t say anything about what it is, but sometimes we need to work with NULL values. Thankfully, T-SQL provides functions for conversion or replacement of NULL values.

The ISNULL function takes two arguments. The first is an expression we are testing. If the value of that first argument is NULL, the function returns the second argument. If the first expression is not null, it is returned unchanged.

For example, suppose the Sales.Customer table in a database includes a MiddleName column that allows NULL values. When querying this table, rather than returning NULL in the result, you may choose to return a specific value, such as "None".

SELECT FirstName, ISNULL(MiddleName, 'None') AS MiddleIfAny, LastName FROM Sales.Customer; The results from this query might look something like this:

The value substituted for NULL must be the same datatype as the expression being evaluated. In the above example, MiddleName is a varchar , so the replacement value could not be numeric. In addition, you'll need to choose a value that will not appear in the data as a regular value. It can sometimes be difficult to find a value that will never appear in your data.

The previous example handled a NULL value in the source table, but you can use ISNULL with any expression that might return a NULL, including nesting a TRY_CONVERT function within an ISNULL function.

The ISNULL function is not ANSI standard, so you may wish to use the COALESCE function instead. COALESCE is a little more flexible in that it can take a variable number of arguments, each of which is an expression. It will return the first expression in the list that is not NULL.

If there are only two arguments, COALESCE behaves like ISNULL. However, with more than two arguments, COALESCE can be used as an alternative to a multipart CASE expression using ISNULL.

If all arguments are NULL, COALESCE returns NULL. All the expressions must return the same or compatible data types.

SELECT COALESCE ( expression1, expression2, [ ,...n ] ) The following example uses a fictitious table called HR.Wages , which includes three columns that contain information about the weekly earnings of the employees: the hourly rate, the weekly salary, and a commission per unit sold. However, an employee receives only one type of pay. For each employee, one of those three columns will have a value, the other two will be NULL. To determine the total amount paid to each employee, you can use COALESCE to return only the non-null value found in those three columns.

SELECT EmployeeID, COALESCE(HourlyRate * 40, WeeklySalary, Commission * SalesQty) AS WeeklyEarnings FROM HR.Wages; The results might look something like this:

## Exercise - Work with SELECT statements

Now it's your chance to try the Transact-SQL techniques you've learned about for yourself.

To use Azure SQL Database, you will need a Microsoft Azure subscription in which you have administrative access.

To set up a database for this exercise, sign into your Azure subscription and follow the setup instructions to provision Azure SQL Database.

To complete the exercise using Microsoft SQL Server, you'll need to follow these setup instructions to install Microsoft SQL Server and the required tools and database.

You need access to a Microsoft Fabric capacity in which you have sufficient permission to create a Fabric SQL Database. See Getting started with Fabric .

To complete the exercise using Microsoft Fabric SQL Database, you'll need to follow these setup instructions to create a Fabric SQL Database for the lab.

Launch the exercise and follow the instructions.

Want to try using Ask Learn to clarify or guide you through this topic?

## Module assessment

You must return the Name and Price columns from a table named Product in the Production schema. In the resulting rowset, you want the Name column to be named ProductName. Which of the following Transact-SQL statements should you use?

SELECT * FROM Product AS Production.Product;

SELECT Name AS ProductName, Price FROM Production.Product;

SELECT ProductName, Price FROM Production.Product;

You must retrieve data from a column that is defined as char(1). If the value in the column is a digit between 0 and 9, the query should return it as an integer value. Otherwise, the query should return NULL. Which function should you use?

You must return the Cellphone column from the Sales.Customer table. Cellphone is a varchar column that permits NULL values. For rows where the Cellphone value is NULL, your query should return the text 'None'. What query should you use?

SELECT ISNULL(Cellphone, 'None') AS Cellphone FROM Sales.Customer;

SELECT NULLIF(Cellphone, 'None') AS Cellphone FROM Sales.Customer;

SELECT CONVERT(varchar, Cellphone) AS None FROM Sales.Customer;

You must answer all questions before checking your work.

You must answer all questions before checking your work.

Want to try using Ask Learn to clarify or guide you through this topic?

## Summary

Here is a video tutorial accompanying this training module to enhance your learning experience.

For more detailed information about Transact-SQL syntax, refer to the Transact-SQL reference documentation .

If you're ready to get started with Azure SQL Database, try Azure SQL Database free of charge for the life of your subscription.

Want to try using Ask Learn to clarify or guide you through this topic?
