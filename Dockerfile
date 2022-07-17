FROM python:3.10.5-slim-buster as deps

RUN mkdir -p /audioviz
WORKDIR /audioviz/

RUN apt-get update && apt-get install -y \
    gcc \
    libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --target=/poetry 'poetry==1.1.12'

COPY poetry.lock pyproject.toml ./

ENV PYTHONPATH="${PYTHONPATH}:/poetry"
RUN echo ${PYTHONPATH}
RUN python -m poetry config virtualenvs.create false \
  && python -m poetry install --no-dev --no-interaction --no-ansi --no-root

COPY audioviz ./

RUN python -m poetry config virtualenvs.create false \
  && python -m  poetry install --no-dev --no-interaction --no-ansi


FROM python:3.10.5-slim-buster as prod

RUN mkdir -p /audioviz
WORKDIR /audioviz/

COPY --from=deps /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages/
ENV PYTHONUSERBASE=/deps

COPY airpixel.yaml .

COPY audioviz ./

ENTRYPOINT ["python", "-m", "airpixel.framework"]
