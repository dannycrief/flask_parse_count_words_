FROM python:3.8-alpine
ADD . /app
WORKDIR /app
RUN pip install -r requirements.txt
