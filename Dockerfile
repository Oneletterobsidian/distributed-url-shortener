FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app
COPY ./tests ./tests
COPY pytest.ini .
COPY locustfile.py .
COPY locustfile_read_only.py .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]