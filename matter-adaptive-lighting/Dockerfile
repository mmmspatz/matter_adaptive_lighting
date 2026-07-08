ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

COPY pyproject.toml /opt/app/
COPY src /opt/app/src
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir /opt/app

CMD ["/opt/venv/bin/python", "-u", "-m", "matter_adaptive_lighting", "run"]
