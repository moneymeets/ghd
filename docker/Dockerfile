FROM python:3.9-alpine

WORKDIR /ghd
COPY . .

RUN set -ex \
    && apk add --update --no-cache build-base libffi-dev openssl-dev \
    && pip install poetry \
    && poetry config virtualenvs.in-project true \
    && poetry install \
    && poetry run nosetests \
    && apk del build-base libffi-dev openssl-dev \
    && rm -r ~/.cache


ENTRYPOINT ["/ghd/entrypoint.sh"]
