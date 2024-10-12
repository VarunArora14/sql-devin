from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, inspect

def initSqliteDBLangchain(dbName = "mydb.db"):
    try:
        print("connecting to DB...")
        dbUri = f"sqlite:///{dbName}"
        db = SQLDatabase.from_uri(dbUri)
        print("Connection established! Url:", dbUri)
        return db
    except Exception as e:
        print("Cannot establish connection to DB\nError:", str(e))
        return None

db = initSqliteDBLangchain()
if db:
    print(db.dialect)
    print(db.get_usable_table_names())
    print(db.run("SELECT * FROM Employee LIMIT 10;"))

def initSqliteDB(dbName = "mydb.db"):
    try:
        print("connecting to DB...")
        dbUri = f"sqlite:///{dbName}"
        engine = create_engine(url=dbUri)
        conn = engine.connect()
        inspector = inspect(engine)
        print("Connection established! Url:", dbUri)
        return conn, inspector
    except Exception as e:
        print("Cannot establish connection to DB\nError:", str(e))
        return None, None
    
conn, inspector = initSqliteDB()
print(inspector.get_table_names())

table_names = inspector.get_table_names()
print("Tables:", table_names)

# Loop over each table to get detailed information like schema, columns, etc.
for table_name in table_names:
    print(f"Information for table: {table_name}")
    
    # Get the columns and their attributes for each table
    columns = inspector.get_columns(table_name)
    for column in columns:
        print(f"Column: {column['name']} Type: {column['type']}")
    
    # Additionally, you can use get_pk_constraint and get_foreign_keys 
    # methods to retrieve information about primary and foreign keys respectively
    pk_constraint = inspector.get_pk_constraint(table_name)
    print(f"Primary Key Constraint: {pk_constraint}")

    foreign_keys = inspector.get_foreign_keys(table_name)
    print(f"Foreign Keys: {foreign_keys}")

# Do not forget to close the connection when done
# connection.close()

conn.close()