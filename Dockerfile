FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt folder2rss.py config.json /app/

EXPOSE 8000

RUN pip install --no-cache-dir -r requirements.txt && \
    mkdir /app/podcasts

CMD ["python3", "folder2rss.py"]

