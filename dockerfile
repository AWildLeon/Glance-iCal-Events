FROM python:alpine

RUN pip install flask requests pytz ics

USER app
WORKDIR /app

COPY app.py .


CMD ["python", "app.py"]
