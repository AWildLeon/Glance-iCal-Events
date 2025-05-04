FROM python:alpine

RUN addgroup app && adduser -G app -D app

WORKDIR /app

COPY --chown=app:app requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app.py .

USER app

EXPOSE 8076

ENV FLASK_ENV=production
ENTRYPOINT ["gunicorn", "app:app", "--bind", "0.0.0.0:8076"]
