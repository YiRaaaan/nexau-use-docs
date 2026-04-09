#!/usr/bin/env bash
# 把要发布的文件挑出来,放进 dist/
set -euo pipefail

DIST="dist"
rm -rf "$DIST"
mkdir -p "$DIST"

# 必须的:docsify 入口 + 侧边栏 + 中文章节
cp index.html "$DIST/"
cp _sidebar.md "$DIST/"
cp -R zh "$DIST/"
cp -R screenshots "$DIST/"

# 教程示例数据库:让读者直接从站点下载
# 同时拷一份到 zh/ 下,这样 markdown 里相对链接 enterprise.sqlite 在
# docsify 路由(/zh/xxx.md 视图)下也能命中。
cp enterprise.sqlite "$DIST/"
cp enterprise.sqlite "$DIST/zh/"

# 教程 Skills 文件:打包成 zip 供读者下载
(cd enterprise_data_agent && zip -r "../$DIST/skills.zip" skills/)
cp "$DIST/skills.zip" "$DIST/zh/"

# 可选:首页/README(docsify 没用到可以删掉这一行)
cp README.md "$DIST/" 2>/dev/null || true

echo "Built into ./$DIST"
ls -la "$DIST"
