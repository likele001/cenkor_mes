cd "$(dirname "$0")" || exit 1
npm install
npm run dev -- --host 0.0.0.0 --port 5173

