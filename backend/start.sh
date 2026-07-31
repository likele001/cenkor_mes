cd "$(dirname "$0")" || exit 1
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
