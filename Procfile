web: python -m openoutreach.cli runserver --host 0.0.0.0 --port ${PORT:-8001}
daemon: ./bin/start-daemon.sh
postdeploy: python -m openoutreach.cli ensure-indexes
