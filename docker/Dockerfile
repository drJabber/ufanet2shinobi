FROM python:3.9-slim-buster

RUN mkdir -p /opt/app /opt/app/logs /opt/app/config
ENV PATH="/opt/app:${PATH}"


ADD ./app/requirements.txt /opt/app/

RUN pip install -r /opt/app/requirements.txt

ADD ./docker/entrypoint.sh /
ADD ./app/* /opt/app/
ADD ./app/config/u2s-template.json /opt/app/config/u2s-template.json

ARG PUID=1000
ARG PGID=1000

RUN chmod +x /entrypoint.sh \
    && addgroup --gid ${PGID} u2sa \
    && adduser --uid ${PUID} --ingroup u2sa --home /home/u2sa --disabled-login --disabled-password  --gecos "" u2sa \
    && chown -R u2sa:u2sa /opt/app /opt/app/logs /opt/app/config

USER u2sa

ENTRYPOINT [ "/entrypoint.sh" ]

VOLUME ["/opt/app/config", "/opt/app/logs"]