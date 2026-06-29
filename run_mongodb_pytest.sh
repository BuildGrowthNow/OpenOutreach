#!/bin/bash
export DJANGO_SETTINGS_MODULE="openoutreach.settings.development"
python3 -m pytest "$@"