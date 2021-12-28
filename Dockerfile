ARG PYTHON_VERSION
FROM python:$PYTHON_VERSION-slim-buster

WORKDIR /ghd
COPY . .

RUN set -ex \
    && apt update \
    && apt install -y libffi-dev \
    && pip install poetry \
    && poetry config virtualenvs.in-project true \
    && poetry install \
    && poetry run pytest \
    && apt remove libffi-dev -y \
    && apt clean autoclean autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && rm -r ~/.cache

ENTRYPOINT ["/ghd/entrypoint.sh"]
