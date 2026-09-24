# syntax=docker/dockerfile:1
#
# Publish Helper 统一镜像：Vue 前端 + Flask API + nginx 同一个容器。
#
# 构建（context 必须是**两个仓库的公共父目录**，即 GitHub/）：
#   cd ..
#   docker build -f publish-helper/deploy/Dockerfile -t publish-helper:local .
#
# 之所以 context 要抬到父目录：前端 publish-helper-vue 是**独立仓库**（与后端平级），
# 本 Dockerfile 需要在 node 阶段 COPY 它的源码。用 `context: ..` 也是因此——
# 直接从后端根目录构建会拿不到前端源码。
#
# CI 里同样用父目录作 context：checkout 两个仓库到同级子目录即可（见
# .github/workflows/docker.yml），不需要把前端做成 submodule。

# ---------------------------------------------------------------------------
# 阶段一：构建 Vue 前端
# ---------------------------------------------------------------------------
# 用 bookworm（Debian 12）：前端 engines.node 要求 ^22.18.0 || >=24.12.0，
#          且下面运行时阶段也用 bookworm，便于统一 glibc 版本。
FROM node:22-bookworm-slim AS web

WORKDIR /build

# 先只拷依赖清单，让 npm ci 这层可缓存（源码改动不会触发重装依赖）
COPY publish-helper-vue/package.json publish-helper-vue/package-lock.json ./

# npm ci 严格按 lockfile 安装，构建可复现。
# 默认 registry 用 npmmirror：package-lock.json 里 515 条 resolved 全部指向
# registry.npmmirror.com，npm ci 会**按 resolved 直接下载**，所以这里换源并不能
# 改变 tarball 来源——默认值只影响少数按 registry 解析的请求（如 peer 依赖补装）。
# 设成与 lockfile 同源可避免"配置与锁文件两套源"的困惑。
ARG NPM_REGISTRY=https://registry.npmmirror.com/
RUN npm config set registry "$NPM_REGISTRY" \
    && npm ci --no-audit --no-fund

COPY publish-helper-vue/ ./

# VITE_API_AUTH_TOKEN 会被 Vite **内联进产物**（构建期生效，运行期改无用）。
# 后端默认不开启鉴权，留空即可。
ARG VITE_API_AUTH_TOKEN=
ENV VITE_API_AUTH_TOKEN=$VITE_API_AUTH_TOKEN

# 用 build:docker（只跑 vite build，不跑 vue-tsc 类型检查）——
# 镜像构建不该因类型告警而失败；类型检查在 CI 的 lint 步骤单独把关。
RUN npm run build:docker

# ---------------------------------------------------------------------------
# 阶段二：运行时（Python + Flask + nginx）
# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

ENV API_PORT=15372 \
    NGINX_PORT=15373 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    PYTHONPATH=/app

WORKDIR /app

# --- 系统依赖 -------------------------------------------------------------
# MediaInfo 用**官方仓库的 .deb 本地安装**，不用 apt 装 Debian 源里的版本：
#   libs/deb/ 里的 .deb 是 Debian 12(bookworm) 构建、要求 glibc >= 2.34，
#   与 bookworm 基础镜像匹配。**不要**换回 bullseye 基础镜像或 buster apt 源——
#   那正是旧 Dockerfile 的三方版本错配（buster 源 / bullseye 镜像 / bookworm deb）。
#   curl 仅用于容器 healthcheck（slim 镜像不自带）。
COPY publish-helper/libs/deb/libzen0v5_0.4.41-1_amd64.Debian_12.deb \
     publish-helper/libs/deb/libmediainfo0v5_24.04-1_amd64.Debian_12.deb \
     /tmp/debs/
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx gettext-base curl \
    && apt-get install -y --no-install-recommends /tmp/debs/libzen0v5_0.4.41-1_amd64.Debian_12.deb \
                                                 /tmp/debs/libmediainfo0v5_24.04-1_amd64.Debian_12.deb \
    && rm -rf /tmp/debs /var/lib/apt/lists/*

# --- 应用代码 -------------------------------------------------------------
COPY publish-helper/src src
COPY publish-helper/static static
# 注意：**不拷** libs/pinyin/Mandarin.dat。xpinyin 是用
# `Path(__file__).with_name('Mandarin.dat')` 从**自己包目录**读数据表的，
# wheel 里已自带同名文件；仓库里那份是给 PyInstaller 打包用的（见
# packaging/publish_helper.spec），容器里拷进来也不会被读到。
COPY publish-helper/deploy/requirements_api.txt requirements_api.txt
COPY publish-helper/libs/deb/entrypoint entrypoint
COPY publish-helper/libs/deb/nginx.conf /etc/nginx/nginx.template.conf
RUN chmod +x entrypoint

# 只读的静态资源母本。compose 会把宿主目录挂到 /app/static，那会**遮住**镜像自带的
# static/ —— 而 abbreviation.json / combo-box-data.json / picture-bed-data.json /
# ph-bjd.ico 是程序运行必需的数据文件。故在这里留一份母本，由 entrypoint 在启动时
# 把「缺失」的文件补进 /app/static（只补缺失，绝不覆盖用户改过的 settings.json）。
RUN cp -r static /opt/static-default

# --- 前端产物 -------------------------------------------------------------
COPY --from=web /build/dist/web /public

RUN pip install --no-cache-dir -r requirements_api.txt \
        -i https://mirrors.aliyun.com/pypi/simple/ \
        --trusted-host mirrors.aliyun.com --default-timeout=600

# media/temp/logs 由 config 在启动时按需创建；static 已随镜像携带默认配置，
# 用户配置通过 compose 的 volume 覆盖（见 deploy/docker-compose.yml）。
EXPOSE 15372 15373

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:${API_PORT}/api/settings || exit 1

# entrypoint 用 exec 起 Flask，使 PID 1 能收到 SIGTERM（见 libs/deb/entrypoint）
ENTRYPOINT ["/app/entrypoint"]
