#!/bin/bash
# CenkorMES 启动脚本
set -e

echo "=== CenkorMES 启动 ==="

# 检查 Python 环境
if [ ! -d "backend/venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv backend/venv
    source backend/venv/bin/activate
    pip install -r backend/requirements.txt
else
    source backend/venv/bin/activate
fi

# 启动后端
echo "启动后端服务 (端口 8500)..."
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8500 --reload &
BACKEND_PID=$!
cd ..

# 启动前端(admin)
echo "启动管理后台前端 (端口 5174)..."
cd frontend-admin-pro
npm install --silent 2>/dev/null
npm run dev -- --port 5174 &
ADMIN_PID=$!
cd ..

# 启动前端(H5)
echo "启动 H5 移动端 (端口 5173)..."
cd frontend-h5
npm install --silent 2>/dev/null
npm run dev -- --port 5173 &
H5_PID=$!
cd ..

echo ""
echo "=== 服务启动完成 ==="
echo "管理后台: http://localhost:5174"
echo "H5 移动端: http://localhost:5173"
echo "API:        http://localhost:8500/api"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $ADMIN_PID $H5_PID 2>/dev/null" EXIT
wait
