FROM alpine:3.18.6

ENV TELEGRAM_TOKEN abc
ENV TELEGRAM_ADMIN abc
ENV TELEGRAM_GROUP abc
ENV TELEGRAM_NOTIFICATION_CHANNEL abc
ENV TELEGRAM_THREAD 1
ENV HOURS_BETWEEN_SCANS 1
ENV IP_RANGE abc
ENV LANGUAGE ES
ENV TZ UTC

ARG VERSION=1.0.0

WORKDIR /app
RUN wget https://github.com/dgongut/intrubot/archive/refs/tags/v${VERSION}.tar.gz -P /tmp
RUN tar -xf /tmp/v${VERSION}.tar.gz
RUN mv intrubot-${VERSION}/* /app
RUN rm /tmp/v${VERSION}.tar.gz
RUN rm -rf intrubot-${VERSION}/
RUN apk add --no-cache python3 py3-pip tzdata
RUN pip3 install pyTelegramBotAPI==4.22.1
RUN pip3 install scapy==2.5.0

WORKDIR /app
COPY . .

ENTRYPOINT ["python3", "intrubot.py"]
