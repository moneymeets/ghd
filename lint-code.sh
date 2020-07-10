#!/usr/bin/env bash

set -e

cd docker
poetry run black .
poetry run flake8
