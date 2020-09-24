# Pipe
## `Pipe`
### Usage
```python
Pipe(pull_table, push_table, transformations = [], not_null = [], validations = [], dimensions = [])]
```
### Parameters

#### pull_table: `str`

Name of table to pull from.

#### push_table: `str`

Name of table to push to.

#### not_null: `Optional[List[str]]`

List of columns that must not be null. Drops rows with null values in these columns.

#### transformations: `Optional[List[Tuple[List[str], Callable[[Any],Any]]]]`

List of tuples in the following structure:
```python
transformation = (['hardship_flag'], lambda series: series.str.lower().replace({"n": False, "y": True}).astype(bool))
```
where `transformation[0]` is an array of column names and `transformation[1]` is a lambda function that takes in a series and returns the modified series by column.

#### validations: `Optional[List[Tuple[List[str], Callable[[Any],Any]]]]`

List of tuples in the following structure:
```python
validation = (['loan_amnt', 'funded_amnt'], lambda df,col: df[df[col] >= 0])
```
where `validation[0]` is an array of column names and `validation[1]` is a lambda function to operate on each column. Returns a dataframe less the columns that don't validate.

#### dimensions: `Optional[List[Tuple[str, Tuple[str,str], List[str]]]] = [])`
List of tuples in the following structure:
```python
dimension = ('HARDSHIP', ('id', 'loan_id'), ['hardship_type', 'hardship_reason'])
```
where `dimension[0]` is the name of the target dimension table, `dimension[1]` is a tuple pair matching the dataframe PRIMARY KEY to the dimension table FOREIGN KEY and `dimension[2]` is the list of columns to include in the dimension table.

#### *Pipe*.validate(self, df) -> df
Processes `not_null` and `validations` and removes non-fitting rows from dataframe.

#### *Pipe*.transform(self, df) -> df
Processes `transformations` and returns transformed dataframe.

#### *Pipe*.dimensionize(self, df) -> [[target, id_col, df]]
Processes `dimensions` by splitting out dimension columns from main fact table, renaming FOREIGN KEY columns in  dimension tables and returning an array of lists in the form `[['target', 'id', df_fact], ['dimension1', 'id_col', df_dimension1]]`.

#### *Pipe*.prepare(self, df) -> [[target,id_col, df]]
Passes dataframe through `transform` -> `validate` -> `dimensionize`.