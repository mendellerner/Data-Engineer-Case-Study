import schedule
import time
import snowflake.connector
import sqlalchemy
from sqlalchemy import create_engine
from snowflake.sqlalchemy import URL
import psycopg2
from datetime import date
from typing import List, Set, Dict, Tuple, Optional, Callable, Any
import pandas as pd
import os

# Class for table objects
class Pipe:
    def __init__(self, pull_table: str, push_table: str, not_null:Optional[List[str]] = [], transformations: Optional[List[Tuple[List[str], Callable[[Any],Any]]]] = [], validations: Optional[List[Tuple[List[str], Callable[[Any],Any]]]] = [], dimensions: Optional[List[Tuple[str, Tuple[str,str], List[str]]]] = []):
        self.pull_table = pull_table
        self.push_table = push_table
        self.transformations = transformations
        self.not_null = not_null
        self.validations = validations
        self.dimensions = dimensions
    
    # Runs all the validation routines
    def validate(self, df):
        df = df[df[self.not_null].notnull().all(axis=1)]
        for cols,val in self.validations:
            for col in cols:
                df = val(df,col)
        return df
    
    # Runs the transformation routines
    def transform(self, df):
        for cols,t in self.transformations:
            for col in cols:
                df[col] = t(df[col])
        return df
    
    # Divide dataframe into dimension tables
    def dimensionize(self, df):
        df_arr = [[self.push_table, 'id', df]]
        for target, id_col, cols in self.dimensions:
            # Pulls out columns, links foreign keys, renames foreign key column and drops empty rows in linked tables
            df_arr.append([target, id_col, df_arr[0][1][[id_col[0]] + cols].rename({id_col[0]: id_col[1]}, axis = 1).dropna(axis = 0, how='all', subset = cols)])
            df_arr[0][1] = df.drop(columns = cols, axis = 1)
        return df_arr
    
    # Runs entire routine
    def prepare(self, df):
        return self.dimensionize(self.transform(self.validate(df)))
    
    def __repr__(self):  
        return f"Pulling from: {self.pull_table}\nPushing to: {self.push_table}\nTransformations: {self.transformations}\nNon-Null Columns: {self.not_null}\nValidations: {self.validations}"

not_null = ['id', 'member_id', 'loan_amnt', 'funded_amnt', 'funded_amnt_inv', 'term', 'int_rate', 'installment', 'grade', 'sub_grade', 'home_ownership', 'annual_inc', 'verification_status', 'issue_d', 'loan_status', 'purpose', 'zip_code', 'addr_state', 'dti', 'earliest_cr_line', 'fico_range_low', 'fico_range_high', 'total_pymnt', 'total_pymnt_inv', 'total_rec_prncp', 'total_rec_int', 'total_rec_late_fee', 'recoveries', 'collection_recovery_fee', 'last_pymnt_d', 'last_pymnt_amnt', 'application_type' , 'hardship_flag']
transformations = [
    (['emp_length'], lambda series: series.fillna(value = '0 years').replace({'< 1 year': '0 years', '10+ years': '10 years'}).str.extract('(\d+)',expand=False).astype(int)),
    (['term'], lambda series: series.str.extract('(\d+)',expand=False).astype(int)),
    (['hardship_flag'], lambda series: series.str.lower().replace({"n": False, "y": True}).astype(bool)),
    (['debt_settlement_flag'], lambda series: series.str.lower().replace({"n": False, "y": True}).astype(bool)),
    (["issue_d", "earliest_cr_line", "last_pymnt_d", "sec_app_earliest_cr_line", "hardship_start_date","hardship_end_date", "payment_plan_start_date","debt_settlement_flag_date","settlement_date","created_on","last_updated"], lambda series: pd.to_datetime(series, errors = 'coerce', infer_datetime_format = True))
]
validations = [
    (['loan_amnt', 'funded_amnt', 'funded_amnt_inv', 'term', 'int_rate', 'installment', 'annual_inc', 'zip_code', 'dti', 'fico_range_low', 'fico_range_high', 'total_pymnt', 'total_pymnt_inv', 'total_rec_prncp', 'total_rec_int', 'total_rec_late_fee', 'recoveries', 'collection_recovery_fee', 'last_pymnt_amnt'], lambda df,col: df[(df[cols] >= 0).all(axis = 1)]),
]
dimensions = [
    ('HARDSHIP', ('id', 'loan_id'), ['hardship_type', 'hardship_reason', 'hardship_status', 'deferral_term', 'hardship_amount', 'hardship_start_date', 'hardship_end_date', 'payment_plan_start_date', 'hardship_length', 'hardship_dpd', 'hardship_loan_status', 'orig_projected_additional_accrued_interest', 'hardship_payoff_balance_amount', 'hardship_last_payment_amount']),
    ('SETTLEMENT', ('id', 'loan_id'), ['debt_settlement_flag_date', 'settlement_status', 'settlement_date', 'settlement_amount', 'settlement_percentage', 'settlement_term'])
]
pipes = [Pipe('ACCEPTED', 'TARGET', transformations = transformations, not_null = not_null, validations = [], dimensions = dimensions)]

# Continuously running routine
def updateTables(pipe, today):
    ## Pulls new data from data lake
    try:
        connection = psycopg2.connect(user = "puller", password = "****", host = "10.0.0.1", port = "5432", database = "DATA_LAKE")

        cursor = connection.cursor()
        # Query new data
        df_pulled = pd.read_sql_query(f'SELECT * FROM {pipe.pull_table} WHERE last_updated BETWEEN {today} AND {pipe.last_updated};',connection)
    except (Exception, psycopg2.Error) as error:
        print (error)
    finally: # closing database connection.
        if(connection):
            cursor.close()
            connection.close()
            print("PostgreSQL connection is closed")
    
    ## Transform and validate
    df_arr = pipe.prepare(df_pulled)

    ## Send to warehouse for each dimension table
    for target, id_col, df in df_arr:
        if len(df):
            try:
                # Upload to temp table in warehouse in order to construct merge
                engine = create_engine(URL(
                        account=os.getenv("SNOWFLAKE_ACCOUNT"),
                        user=os.getenv("SNOWFLAKE_USER"),
                        password=os.getenv("SNOWFLAKE_PASSWORD"),
                        role="ETL",
                        warehouse='DATA_WAREHOUSE',
                        database="LENDING_CLUB",
                        schema="PUBLIC",
                    ))
                df.to_sql('TEMP', con=engine, schema = 'PUBLIC', index = False, if_exists = 'replace')

                connection = snowflake.connector.connect(
                        account=os.getenv("SNOWFLAKE_ACCOUNT"),
                        user=os.getenv("SNOWFLAKE_USER"),
                        password=os.getenv("SNOWFLAKE_PASSWORD"),
                        warehouse='DATA_WAREHOUSE',
                        database="LENDING_CLUB",
                        schema="PUBLIC",
                        session_parameters={
                            'QUERY_TAG': 'ETL',
                        }
                    )
                cursor = connection.cursor()
                # Send to warehouse
                columns = ",".join(df.columns.tolist())
                values = ",".join([f"TEMP.{col}" for col in df.columns.tolist()])
                excluded = ",".join([f'a.{col} = TEMP.{col}' for col in df.drop('id', axis = 1).columns.tolist()])
                # Construct MERGE
                query = f'MERGE INTO {target} AS a USING TEMP ON a.{id_col} = TEMP.{id_col} WHEN MATCHED THEN UPDATE SET {excluded},"warehouse_last_updated" = current_timestamp() WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values})'
                cursor.execute(query)
                cursor.commit()
                cursor.execute("DROP TABLE TEMP;")
                # Atomic update to last_updated. Only increased if entire routine completes
                pipe.last_updated = today
            except (Exception, psycopg2.Error) as error :
                print (error)
            finally: # closing database connection.
                if(connection):
                    cursor.close()
                    connection.close()

def job(pipes):
    for pipe in pipes:
        updateTables(pipe,date.today())
    return

schedule.every().day.at("00:00").do(job,pipes)

# Run once on init
job((pipes,date.today()))
while True:
    schedule.run_pending()
    time.sleep(60) # wait one minute