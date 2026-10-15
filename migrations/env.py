python -m alembic revision --autogenerate -m "initial PostgreSQL schema"
# Open the new file and check every table, constraint, index and foreign key.
python -m alembic upgrade head
python -m alembic current
python -m alembic history
