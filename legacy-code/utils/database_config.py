from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from sqlalchemy.orm import declarative_base

load_dotenv()

# Build database URL from environment variables
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

Base = declarative_base()

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
Session = sessionmaker(bind=engine)

def init_db():
    from database import models
    from database.models import Base
    Base.metadata.create_all(engine)


#for debuggingpurposes (commented out- delete before committing)
# from sqlalchemy import inspect

# def list_tables():
#     inspector = inspect(engine)
#     tables = inspector.get_table_names()
#     print(f"Database tables: {tables}")

# def print_config():
#     print(f"Database host: {os.getenv('POSTGRES_HOST')}")
#     print(f"Database name: {os.getenv('POSTGRES_DB')}")
#     print(f"Database user: {os.getenv('POSTGRES_USER')}")

# list_tables()
# print_config()