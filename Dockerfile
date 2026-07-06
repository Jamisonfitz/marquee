FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REPO_DIR=/app \
    DATA_DIR=/config

WORKDIR /app
RUN apk add --no-cache su-exec
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY cast ./cast
COPY output ./output
COPY CHANGELOG.md ./CHANGELOG.md
COPY VERSION ./VERSION
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN addgroup -S marquee && adduser -S -G marquee marquee \
    && mkdir -p /config && chown -R marquee:marquee /app /config \
    && chmod +x /docker-entrypoint.sh
# Start as root so the entrypoint can chown a host-owned /config, then it drops
# to the marquee user via su-exec before running the app.

EXPOSE 8084
VOLUME ["/config"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8084/healthz', timeout=3)" || exit 1
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "cast/cast.py"]
