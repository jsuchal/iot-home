FROM alpine:3.21
RUN apk add --no-cache python3 openssl py3-pillow
WORKDIR /app
COPY server.py LICENSE NOTICE.md ./
ENV PYTHONUNBUFFERED=1
EXPOSE 8443
CMD ["python3", "server.py"]
