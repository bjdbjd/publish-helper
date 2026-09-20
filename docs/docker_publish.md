# 镜像发布

> 1.本文档指导研发人员发布镜像  
> 2.推送到镜像仓库

## 1.编译镜像

> 此步骤将从 git 仓库拉取最新代码，构建镜像并推送到镜像仓库。

登录服务器，在可用目录下执行以下命令：

```shell
# 此变量为版本，后续将此shell改为build.sh脚本，版本从项目配置文件获取
git clone git@github.com:bjdbjd/publish-helper.git
PROJECT_VERSION=2.0.0
cd publish-helper
docker build --no-cache --progress=plain -t bdjbjd/publish-helper:${PROJECT_VERSION} -f deploy/Dockerfile .
```

## 2.推送镜像

```shell
# 当前不推送到公共仓库，正式发布补充，合并到上面build.sh脚本中
```

## 启动
> 正式发布docker版本后，启动部分迁移到用户使用部署  
> 使用此目录下`publish-helper.yml`启动，需要修改其中镜像版本

```shell
# 在编译服务器上直接可以启动，正式发布后需要拉取镜像
# 停止
docker-compose -f publish-helper.yml down
# 启动
docker-compose -f publish-helper.yml up -d
```

