FROM python:3.12
WORKDIR /app

COPY . /app
RUN mkdir -p /app/files

RUN pip install -r requirements.txt
CMD ["gunicorn", "-b", "0.0.0.0:5000", "main:app"]

