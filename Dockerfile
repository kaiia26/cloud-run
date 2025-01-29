FROM python:3.12
WORKDIR /app


COPY requirements.txt /app/
RUN pip install -r requirements.txt


COPY . /app
RUN mkdir -p /app/files

CMD ["gunicorn", "-b", "0.0.0.0:5000", "main:app"]


