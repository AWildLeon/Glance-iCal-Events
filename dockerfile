FROM python:alpine

RUN pip install flask pytz icalevents

USER app
WORKDIR /app

COPY app.py .


CMD ["python", "app.py"]
