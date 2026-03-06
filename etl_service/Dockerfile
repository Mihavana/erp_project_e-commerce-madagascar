FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Changement ici : On lance l'API au lieu du script seul
CMD ["uvicorn", "etl:app", "--host", "0.0.0.0", "--port", "8002"]