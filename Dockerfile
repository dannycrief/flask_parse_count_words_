FROM python:3.8-alpine

WORKDIR .

COPY requirements.txt .

ENV FLASK_APP app.py

ENV FLASK_RUN_HOST 0.0.0.0

RUN \
 apk add --no-cache python3 postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc python3-dev musl-dev postgresql-dev && \
 python3 -m pip install -r requirements.txt --no-cache-dir && \
 apk --purge del .build-deps

COPY . .

EXPOSE 5000

CMD ["flask", "run"]

