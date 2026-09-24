# 镜像发布

> 面向维护者：构建并发布**统一镜像**（Vue 前端 + Flask API + nginx 同容器）到 GHCR。

镜像地址：`ghcr.io/bjdbjd/publish-helper:<版本>`

## 1. 自动发布（推荐）

推 tag 即触发 `.github/workflows/docker.yml` 构建并推送，同时打上版本号与 `latest`：

```shell
git tag v2.0.2
git push origin v2.0.2
```

工作流会 checkout **两个仓库**（`publish-helper` 与 `publish-helper-vue`）到同级目录，
再以父目录为 context 构建——与本地布局一致。也可在 Actions → Docker Image → Run workflow 手动触发。

## 2. 本地构建

统一镜像需要前端源码，因此 **context 必须是两个仓库的公共父目录**，且两个仓库须同级：

```shell
# 目录结构：/<parent>/publish-helper 与 /<parent>/publish-helper-vue
cd /<parent>
docker build -f publish-helper/deploy/Dockerfile -t publish-helper:local .
```

或直接用 Makefile（会自动 cd 到父目录）：

```shell
cd publish-helper
make docker-build
```

> 前端是**独立仓库**（不做成 submodule），所以不能只在后端根目录下构建。
> npm 默认源是 `registry.npmmirror.com`（与 package-lock.json 的 resolved 同源）。
> 需要改源时用 `--build-arg NPM_REGISTRY=https://registry.npmjs.org/`。

## 3. 手动推送到 GHCR

```shell
echo $GITHUB_TOKEN | docker login ghcr.io -u <用户名> --password-stdin
docker tag publish-helper:local ghcr.io/bjdbjd/publish-helper:2.0.2
docker tag publish-helper:local ghcr.io/bjdbjd/publish-helper:latest
docker push ghcr.io/bjdbjd/publish-helper:2.0.2
docker push ghcr.io/bjdbjd/publish-helper:latest
```

## 4. 用户侧启动

见 `deploy/docker-compose.yml`。用户只需拉取镜像，把 `static/`（配置）与 `media/`
（资源）挂上即可；界面在 **15373** 端口（nginx 同时提供界面与 `/api` 反代），
15372 是容器内的 Flask，默认不对宿主暴露。

```shell
docker compose -f deploy/docker-compose.yml up -d
```

首次启动时，entrypoint 会把镜像内自带的静态数据文件（`abbreviation.json`、
`combo-box-data.json`、`picture-bed-data.json`、`ph-bjd.ico`）**按缺失补种**到挂载出来的
`static/`，并生成默认 `settings.json`；此后用户改动不会被覆盖。
