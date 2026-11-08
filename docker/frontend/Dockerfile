# Copyright (C) 2026 CenkorMES Project
# SPDX-License-Identifier: AGPL-3.0
# CenkorMES 前端生产镜像（管理后台 / H5 通用）。
#
# 构建上下文必须为仓库根目录；通过 --build-arg FRONTEND 选择前端源码目录：
#   FRONTEND=frontend-admin-pro   -> 管理后台
#   FRONTEND=frontend-h5          -> 员工 H5
# 构建产物（dist）由 nginx 托管，/api 就地反代到 backend:8000 容器内部端口。
#
# 构建：docker compose build web-admin web-h5    （参见 docker-compose.yml）

# ---- 阶段一：依赖安装与生产构建 ----
FROM node:20-alpine AS build
ARG FRONTEND
WORKDIR /app

COPY ${FRONTEND}/package.json ${FRONTEND}/package-lock.json ./
RUN npm ci --prefer-offline --no-audit --no-fund

COPY ${FRONTEND}/ ./

# npm run build 会先跑 i18n 门禁，package.json 里用的是 ../scripts/check-i18n.mjs。
# 镜像 WORKDIR=/app，所以把仓库根的 scripts/ 映射到 /scripts，保持相对路径一致；
# 白名单与脚本同目录，门禁会自动加载。
COPY scripts/check-i18n.mjs scripts/i18n-allowlist.json /scripts/
RUN npm run build

# ---- 阶段二：nginx 运行时 ----
FROM nginx:1.27-alpine
ARG FRONTEND
COPY docker/nginx/${FRONTEND}.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
STOPSIGNAL SIGTERM