FROM arm64v8/python@sha256:9ced67c06852b84c047a38374865b523c909095a0dbef2c871a859e43f0ac5eb

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python

RUN apt-get update && apt-get install -y \
        libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.poetry/bin:${PATH}"
RUN poetry config virtualenvs.create false

COPY pyproject.toml /pyproject.toml
COPY poetry.lock /poetry.lock
RUN poetry install --no-dev --no-root

COPY dist /dist
RUN pip install dist/*.tar.gz

COPY airpixel.yaml /airpixel.yaml

ENTRYPOINT [ "python", "-m", "airpixel" ]
