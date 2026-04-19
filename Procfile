web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
release: alembic -c backend/alembic.ini upgrade head
