FROM alpine:3.21
RUN apk add --no-cache python3 openssl py3-pillow tzdata font-dejavu
WORKDIR /app
COPY server.py components.py schedule.py weather.py weatherman.py LICENSE NOTICE.md ./
COPY assets/ ./assets/
ENV PYTHONUNBUFFERED=1
EXPOSE 8443
CMD ["python3", "server.py"]
