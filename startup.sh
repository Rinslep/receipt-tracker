#!/bin/bash
pip install -r requirements.txt --quiet
gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
