# Data Engineering Case Study

## Prompt
### Download Data
We will be exploring Lending Club’s loan origination data from 2007-2018. [Download from Kaggle](https://www.kaggle.com/wordsforthewise/lending-club#)

### Part 1: Data Exploration and Evaluation
*Create an exploratory data analysis project. Load the data and perform any necessary cleaning and aggregations to explore and better understand the dataset. Based on your exploration, please describe your high level findings in a few sentences. Please include two data visualizations and two summary statistics to support these findings.*

### Part 2: Data Pipeline Engineering
*Build a prototype of a production data pipeline that will feed an analysis system (data warehouse) based on this dataset. This system will allow data scientists and data analysts to interactively query and explore the data, and will also be used for machine learning model training and evaluation. Assume that the system will receive periodic updates of this dataset over time, and that these updates will need to be processed in a robust, efficient way. For this section, please:*
- *Create a data model / schema in a database or storage engine of your choice.*
- *Develop code that will persist the dataset into this storage system in a fully automated way.*
- *Include any data validation routines that you think may be necessary.*

*Prioritize simplicity in your data model and processing code. Explain your thought process and document any alternate data models you considered along the way. Finally, wrap up with a discussion of system improvements that could be addressed in the future.*

---

## Case Study
### Part 1: Data Exploration and Evaluation
#### Findings
<div style="margin-bottom:15px;padding-left:0px">
<figure style='display:block;padding-left:20px;padding-bottom:10px;float:right; margin: 0' >
        <img src="Images/Summary Statistics by Grade.png" />
        <figcaption style='text-align:center; padding-bottom: 5px'>Summary by Grade with Simple Rate of Return</figcaption>
        
</figure>
As one would expect, the mean interest rate and default rate rise as the grade decreases. Many who look at the Lending Club data are particularly interested in the platform as an alternative investment. Using a simple rate of return, it is clear that the mean rate of return decreases dramatically with lower grade loans, much of which is attributable to low-grade loans that quickly default.
<figure style='display:block;margin:0px' >
       <img src="Images/Distribution of Simple Annualized Rate of Return by Loan Grade.png" />
 <figcaption style='text-align:center'>Distribution of Simple Annualized Rate of Return by Loan Grade</figcaption>
        
</figure>
</div>

<div style="margin-bottom:15px;padding-left:0px">
<figure style='display:block;padding-left:20px;padding-bottom:10px;float:right; margin: 0' >
        <img src="Images/Summary Statistics by Year.png" />
        <figcaption style='text-align:center; padding-bottom: 5px'>Summary Statistics of Loan Issuance and Default Rate </figcaption>
        
</figure>
It is also important to understand how the loan statistics change year to year to give insight into the strictness of Lending Club's underwriting process. Clearly, the Mean Debt-to-Income ratio is increasing across all grades while Lending Club is also inconsistent about verifiying borrowers income. This can imply that Lending Club is issuing riskier loans. Excluding 2017 and 2018 (as those years are too recent for the loans to play out) the default rate has increased every year from 2010 to 2016.
<figure style='display:block;margin:0px' >
       <img src="Images/Debt to Income by Year.png" />
 <figcaption style='text-align:center'>Debt-to-Income Ratio by Year</figcaption>
        
</figure>
</div>

---

### Part 2: Data Pipeline Engineering
#### The Storage Engine
We will be using [Snowflake](https://www.snowflake.com) for the storage engine as it is a fully managed cloud-based data warehouse which supports infinite scaling in both compute and storage and is highly optimized for analytics tasks. Although our Lending Club dataset is only ~400MB, Snowflake would be an excellent choice for larger systems to any size. 

Though PostGres provides excellent storage capabilities, it does not scale for analytics workloads. Microsoft SQL Server is much better as it offers columnar database options but still requires the company to manage it themselves. Going with Spotify's take on Business Intelligence, that a company should focus as little as possible on supporting its infrastructure technologies. Snowflake fulfills all these requirements.

#### The Data Model
The data model follows a semi-normalized structure with a central fact table ("ACCEPTED") and dimension tables in order for the database to contain the entire dataset from Lending Club. The data is semi-normalized as most columns that would be analyzed are found in the "ACCEPTED" table and therefore don't require any joins. A view is included to reconstruct the original Lending Club table. The additional dimensions are features that may be analyzed on their own but not usually with the fact table.
<div style="margin:20px">
    <div align='center'>
        <img src="Images/Data%20Model.png" />
        <div>Data Model. <i>Designed using <a href="dbdiagrams.io">dbdiagrams.io</a></i></div>
    </div>
</div>
I considered moving the member profile information to another dimension (using `member_id` as the foreign key) but ultimately decided against it. My reasoning twofold: Much of the profile information is very useful for analytics, and therefore should be accessed without joins. Additionally, unlike a user profile which is constantly updated with the most current information, the member information here is a snapshot in time as of the acceptance of the loan.

#### Automated Pipeline Between Data Lake and Warehouse
The entire ETL pipeline is constructed in Python from start to finish. I considered using SQL but decided on Python for its flexibility and CPython based table/matrix operations. Automatic periodic updates are acheived through the `schedule` module, set to update every day at `00:00`. Alternatively, this could be handled through CRON.

The module extracts the data from the application (in this case assumed to be PostGres) and loading into the Snowflake data warehouse through the `Pipe` class which is initialized with all the information for transforming, validating, and dimensioning the table. See [README-Pipe.md](README-Pipe.md) for details on the class.

The order of operations is as follows:
1. Initialize the pipes that the module will schedule.
   - This includes requesting the most recent update date from the Snowflake database.
2. Schedule the table updates job.
3. Run table updates once upon initializing.
4. Pull new data from application.
5. Transform -> validate -> dimensionize.
6. Upload data to each table in Snowflake warehouse.
   1. This uses a `MERGE` on the table's `id` column to upsert by inserting if no match and updating if the `id` already exists in the database. This is important because we are generally only increasing the number of records and updating loans as details change.
7. Update the pipe's `last_updated` property to the `today` variable.

#### Discussion of Future System Improvements

|System Improvement|Value|
|-|-|
|Full support for catching drop rows to notify the upstream application about invalid rows.|This may allow the upstream application to attempt to recover some data.|
|Create transformation, validation and dimensioning processes that are fully integrated into the data warehouse.|Reduces need for third-party software and code. Provides purpose-built tools for connecting to data lake including optimization for ingesting new data. Enables creation of truly temporary table for MERGE so will not incur costs of fail-safe data storage.|
|Support for raw file storage, whether structured or semi-structured.|Allows for raw data to be stored in the warehouse for access if necessary. Also allows for ETL processes to happen on the warehouse rather than within scripts or connectors. The data warehouse also does not need to rely on the producing application or data lake for any structure in the data.|
|Processes to keep up-to-date with data lake schema so that changes are automatically propogated into the ETL pipeline.|Massively reduces man-hours required for maintenance of connector.|
|ETL pipeline using a message-broker system such as Kafka.|Allows for real-time streaming to data warehouse. Even when not running in real-time, the ETL pipeline always knows which data has been ingested and when there is new data to ingest.|
|Further communication with the data science and analytics team to determine important fields.|Possibility of cold-storage of unused fields with pipelines for reintegration. This will allow moving certain fields offline to reduce Snowflake storage costs.|
|If raw data is already stored in the cloud, it can be made accessible to Snowflake through staging the raw or JSON files and then use pipes to ETL the data in near real-time.|Efficient way to store both raw and processed data together. This also allows for the data warehouse to only warehouse the data that is necessary while simultaneously allowing access to all the data.|
|Alternatively, use a fully-managed data pipeline service such as [Striim](https://www.striim.com/integrations/postgresql-snowflake/) or [Stitch](https://www.stitchdata.com/integrations/postgresql/snowflake/) to oversee the transfer of data between the applications and Snowflake including incremental updates and logging. |This would allow the team to leverage the expertise of the managed solution, similar to leveraging the cloud data storage expertise of Snowflake.|