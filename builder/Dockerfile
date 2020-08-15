FROM arm64v8/python@sha256:9ced67c06852b84c047a38374865b523c909095a0dbef2c871a859e43f0ac5eb


RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

RUN apt-get update && apt-get install -y \
        libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.poetry/bin:${PATH}"

RUN mkdir -p /out
RUN mkdir -p /app

COPY poetry.lock /app/poetry.lock
COPY pyproject.toml /app/pyproject.toml
COPY builder/poetry.toml /app/poetry.toml

WORKDIR /app
RUN poetry install --no-dev --no-root

ENTRYPOINT [ "python" ]
