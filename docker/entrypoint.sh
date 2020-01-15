#!/usr/bin/env sh

cd /ghd || exit 1
eval "poetry run ./ghd.py $*"
