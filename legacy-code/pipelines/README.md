# Multi-Stage Pipeline for Planning Application Data

This directory contains a modular, multi-stage pipeline for processing planning application data with strong separation of concerns.

## Pipeline Structure

The pipeline is divided into four main stages:

1. **Data Transformation** (`data_transformation.py`): Initial data cleaning with Pandas
2. **Validation** (`validation.py`): Data validation using Pydantic models
3. **Relational DataFrame** (`relational_dataframe.py`): Creating structured DataFrames with relationships
4. **Database** (`database.py`): Database operations with SQLAlchemy

Each stage has a single responsibility and communicates with the next stage through metadata attached to the items.

## Common Components

- **Base Pipeline** (`base.py`): Common functionality for all pipeline stages
- **Pipeline Manager** (`manager.py`): Optional utility for monitoring pipeline flow

## Data Flow

1. Items are collected in batches in the Data Transformation stage
2. Transformed data is validated using Pydantic models
3. Valid items are organized into relational DataFrames
4. DataFrames are saved to the database using SQLAlchemy

## Error Handling

- **Validation Errors**: Rejected items are saved to a JSON Lines file
- **Database Errors**: Failed batches are saved for later processing
- **Logging**: Comprehensive logging at each stage

## Configuration

Pipeline settings are configured in `settings.py`:

```python
# Pipeline-specific settings
BATCH_SIZE = 100
REJECTED_ITEMS_PATH = 'data/rejected_items.jsonl'
FAILED_DB_BATCHES_PATH = 'data/failed_db_batches.jsonl'

# Database settings
DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'planning_applications'
DB_USER = 'postgres'
DB_PASSWORD = 'postgres'
```

## Usage

The pipeline is automatically applied to all `PlanningApplicationItem` objects. No additional configuration is needed beyond setting up the database connection.

## Dependencies

- pandas
- pydantic
- sqlalchemy
- psycopg2 (for PostgreSQL)

## Backward Compatibility

The original pipeline classes from `pipelines.py` are still available and can be used alongside the new pipeline structure. 