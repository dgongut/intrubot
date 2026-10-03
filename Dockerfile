FROM alpine:3.24.2

ARG VERSION=2.0.2

# Without it Python buffers stdout when there is no tty and docker logs stays empty
ENV TZ=UTC \
    PYTHONUNBUFFERED=1

WORKDIR /app

# py3-aiohttp comes prebuilt from Alpine: pyTelegramBotAPI requires it and on
# platforms without a wheel (linux/386) pip would try to compile it
RUN apk add --no-cache python3 py3-pip py3-aiohttp tzdata

# ADD (not curl) so BuildKit checks the remote file on every build: a cached
# layer keyed on the command text alone would keep shipping the old code if
# the tag is ever moved
ADD https://github.com/dgongut/intrubot/archive/refs/tags/v${VERSION}.zip /tmp/app.zip

# Unpack the source and install the dependencies
RUN unzip -q /tmp/app.zip -d /tmp && \
    mv /tmp/intrubot-${VERSION}/intrubot.py /app && \
    mv /tmp/intrubot-${VERSION}/config.py /app && \
    mv /tmp/intrubot-${VERSION}/devices.py /app && \
    mv /tmp/intrubot-${VERSION}/scanner.py /app && \
    mv /tmp/intrubot-${VERSION}/logger.py /app && \
    mv /tmp/intrubot-${VERSION}/message_queue.py /app && \
    mv /tmp/intrubot-${VERSION}/locale /app && \
    mv /tmp/intrubot-${VERSION}/requirements.txt /app && \
    rm -rf /tmp/app.zip /tmp/intrubot-${VERSION}/ && \
    export PIP_BREAK_SYSTEM_PACKAGES=1 && \
    pip3 install --no-cache-dir -r /app/requirements.txt

# Health check: unhealthy when Telegram has not answered a poll for 2 minutes
# (the bot touches the file on every poll, see HEARTBEAT_PATH in config.py)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import os, sys, time; sys.exit(time.time() - os.path.getmtime('/tmp/intrubot.heartbeat') > 120)"

ENTRYPOINT ["python3", "intrubot.py"]
