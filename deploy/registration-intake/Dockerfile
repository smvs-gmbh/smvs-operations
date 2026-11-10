FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/intake
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home intake
COPY --chown=intake:intake app ./app
USER intake
EXPOSE 8080
# nginx terminates TLS and preserves Host. Forwarded headers are not trusted.
CMD ["uvicorn", "app.registration.gateway:from_environment", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-proxy-headers"]
