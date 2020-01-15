FROM python:3.8-alpine

WORKDIR /ghd
COPY . .

RUN set -ex \
    && apk add --update --no-cache build-base libffi-dev openssl-dev \
    && pip install poetry \
    && poetry config virtualenvs.in-project true \
    && poetry install \
    && apk del build-base libffi-dev openssl-dev \
    && rm -r ~/.cache


ENTRYPOINT ["/ghd/entrypoint.sh"]
