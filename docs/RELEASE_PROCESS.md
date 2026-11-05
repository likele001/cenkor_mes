# CenkorMES 发版与升级说明

> 适用版本：v2.2.2 及以后
> 本文分两半：**上半是维护者怎么发版**，**下半是客户机怎么升级**。
> 部署细节见 [DEPLOYMENT.md](./DEPLOYMENT.md)，本文只讲「版本怎么产生、怎么流到客户机」。

---

## 1. 两条链路，一张图

```
维护者侧（发版）
  改代码 ──► VERSION + backend/CHANGELOG.json ──► git tag vX.Y.Z ──► 推送
                                                                     │
                                                                     ▼
                                                          GitHub Actions
                                          ┌──────────┬─────────────┴──────┐
                                          │preflight │ github-release     │package + attach
                                          │三处一致  │ 建 Release + 正文  │ 建 dist、打包、挂附件
                                          └──────────┴────────────────────┘
                                                                     │
                                                                     ▼
                                                      Release: cenkormes-vX.Y.Z.tar.gz
                                                               + .tar.gz.sha256
                                                                     │
客户机侧（升级）                                                       ▼
   后台「立即升级」 ──► 查 Releases API ──► 下载包 ──► 校验 SHA256 ──► 覆盖代码
   或 scripts/upgrade.sh                                                   │
                                                              alembic upgrade head
                                                                          │
                                                                  重启后端（人工/守护）
```

一句话：**代码只往一个方向流——tag 触发 CI 出包，客户机只认包**。
客户机不需要 git、不需要 SSH key、不需要 node（包内已带预构建 `dist`）。

---

## 2. 版本号真源：只有一个

`VERSION`（仓库根目录）是**唯一**真源。所有其他地方都是它的影子：

| 位置 | 谁写 | 作用 |
|---|---|---|
| `VERSION` | 人 / `release-all.sh` | 唯一真源 |
| `backend/CHANGELOG.json` 的 `description` | `release-all.sh` | GitHub Release **正文**来源 |
| git tag `vX.Y.Z` | `release-all.sh` | 触发 CI 的**唯一开关** |
| `system_versions` 表 | 后端启动时同步 | 「关于」页显示的版本 |

**这三者必须一致**：`tag == VERSION == CHANGELOG.json 里的 version`。

不一致会发生什么：tag 照样推得上去、Release 照样建得出来，但正文退化成
`Release v2.2.1` 这种空壳，而「关于」页显示的是新版本号。只有翻 GitHub 才发现。

所以有 `scripts/release-check.sh`（只读，不改任何文件）：

```bash
bash scripts/release-check.sh                 # 校验当前目录
bash scripts/release-check.sh --tag v2.2.2     # 额外校验 tag 与 VERSION 一致
bash scripts/release-check.sh --root /path/repo  # 校验指定目录（CI 回填旧版本用）
```

校验四项：VERSION 格式是否为 `vX.Y.Z`、CHANGELOG 是否有该条目、说明是否短于 8 字、
传入的 tag 是否与 VERSION 一致。顺带提示工作区脏文件和「tag 已存在指向哪里」。

---

## 3. 发版 SOP

### 3.1 前置检查

```bash
cd /www/wwwroot/cenkormes
git status --short          # 必须干净（未提交的改动不会被 git archive 打进包）
git log --oneline -5        # 确认这批提交就是要发的
bash scripts/release-check.sh --tag v2.2.2   # 版本号还没涨，失败是正常的，看的是现有状态
```

> **工作区脏 = 改动不会进包**。打包用的是 `git archive HEAD`，只取被 git 跟踪且已提交的文件。

### 3.2 试跑（不写文件、不提交、不推送）

```bash
bash scripts/release-all.sh --dry-run "本次发版说明"
```

确认打印的 `版本号: v2.2.1 → v2.2.2` 和递增位数符合预期。
默认 `patch`；要 minor / major 就加环境变量：

```bash
VERSION_BUMP=minor bash scripts/release-all.sh "说明"
VERSION_BUMP=major bash scripts/release-all.sh "说明"
```

### 3.3 正式发版

```bash
bash scripts/release-all.sh "一句话说清这版干了什么；多条用分号隔开"
```

脚本按序做六件事：

1. 递增 `VERSION`
2. 追加/覆盖 `backend/CHANGELOG.json` 中该版本条目（按版本号幂等）
3. `git commit`（`chore(release): bump version to vX.Y.Z`）
4. 跑 `release-check.sh --tag <新版本>` 做**推 tag 前的最后一道闸门**——失败即中止，此时还没打 tag，修好重跑即可
5. 打附注 tag 并推 `main` + tag
6. 提示你去宝塔重启后端

> `--no-push` 只本地提交 + 打 tag，不推送。
> `VERSION` 一旦写入就不会回退，中止后重跑脚本会**再涨一个补丁号**；
> 想保持号段就手动改回 `VERSION` 再跑。

### 3.4 等 CI（约 5～8 分钟）

```bash
gh run list --limit 3
gh run watch
```

四个 job 按顺序：`preflight` → `github-release`（秒级）→ `package`（前端构建，数分钟）→ `attach`。

### 3.5 验收（必做）

```bash
TAG=v2.2.2
curl -s https://api.github.com/repos/likele001/cenkor_mes/releases/tags/$TAG \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["name"]); print([a["name"] for a in d["assets"]])'
```

必须看到**两个附件**：`cenkormes-$TAG.tar.gz` 与 `cenkormes-$TAG.tar.gz.sha256`。
只有 `Source code (zip/tar.gz)` 说明 `package` 或 `attach` 挂了——客户点升级会得到
「该版本没有产物包」。

再抽验包内容：

```bash
curl -fsSL -o /tmp/p.tgz https://github.com/likele001/cenkor_mes/releases/download/$TAG/cenkormes-$TAG.tar.gz
tar tzf /tmp/p.tgz | head -5
tar xzOf /tmp/p.tgz cenkormes-$TAG/VERSION            # 应等于 $TAG
tar tzf /tmp/p.tgz | grep -c 'frontend-admin-pro/dist/index.html'   # 应为 1
```

### 3.6 本机（生产）同步

本机是**开发机即部署机**，发完 tag 后本机代码已经是最新的，但**部署目录的运行时不会自己变**：

- 后端：到宝塔面板重启 `cenkormes`（`system_versions` 在启动时同步，「关于」页才会显示新版本）
- 前端：`dist` 由 CI 构建，本机要重建；或直接用产物包覆盖：

```bash
bash scripts/upgrade.sh --version v2.2.2      # 走正式通道，顺带验证包可用
```

> 本机自己升级自己时，`frontend-*/dist` 由 `_promote_frontend` 原子换入，
> 不会出现「nginx 读到半个 dist」的中间态。

### 3.7 失败处置

| 失败点 | 现象 | 处置 |
|---|---|---|
| `release-check` | 本地报「校验未通过」，未打 tag | 补 CHANGELOG 说明或改 `VERSION`，重跑 |
| `preflight` | CI 第一个 job 红 | 同上；注意闸门校验的是**被推送的 tag** |
| `package` | 前端构建失败 | 看 CI 日志，`npm ci` 或 tsc 报错；修完重打 tag |
| `attach` | Release 建了但没附件 | 手动触发 workflow 补挂：`gh workflow run release.yml -f tag=$TAG` |
| 历史 tag 没 Release | 只有 tag | 同上，`workflow_dispatch` 回填（脚本会从主干取，不依赖 tag 内有没有脚本） |

---

## 4. CI 四道 job 各干什么

`.github/workflows/release.yml`，由 `push tag v*` 或手动 `workflow_dispatch` 触发。

| job | 依赖 | 职责 | 没有它会怎样 |
|---|---|---|---|
| `preflight` | — | 双检出（tag → `target/`，主干 → `tooling/`），跑 `release-check.sh --root target --tag <tag>` | 版本不一致的 Release 会被静默创建，正文空壳 |
| `github-release` | preflight | 从 CHANGELOG.json 取该版本 `description` 作正文，建/更新 Release | 只有 tag，没有 Release 页 |
| `package` | preflight | `npm ci && build` 两个前端 → `git archive` 取跟踪文件 → 灌入 dist → 双保险删 `.env`/`backend/data` → 包内自检 → 打 tar.gz + sha256 | 客户只能拿到不含 dist 的源码快照，装上去前端空白 |
| `attach` | 上面两个 | `gh release upload --clobber` 把两个附件挂到 Release | Release 存在但「立即升级」不可用 |

三个刻意的设计，别动：

1. **`preflight` 用两个 checkout**。回填历史 tag 时，那个 tag 里可能根本没有
   `release-check.sh`（脚本是后加的），直接 checkout 到 tag 再跑会 `exit 127`。
   所以脚本从主干取（`tooling/`），用 `--root` 指向目标 tag 的检出目录。
   **校验逻辑不能放在被检查对象里**。
2. **`attach` 必须显式 `--repo`**。该 job 没有 checkout，`gh` 无法从 `.git` 推断仓库，
   会报 `fatal: not a git repository`。
3. **`package` 与 `attach` 分开**。Release 创建是秒级，前端构建是分钟级；
   合并会让「Release 已建但附件迟到」，客户在窗口期点升级拿到的是「没有产物包」。

---

## 5. 产物包规格

**命名**：`cenkormes-vX.Y.Z.tar.gz`
**摘要**：`cenkormes-vX.Y.Z.tar.gz.sha256`（`sha256sum` 格式）
**体积**：约 8 MB（主要是两份 dist）
**顶层目录**：`cenkormes-vX.Y.Z/`（解包后带一层，`tar xzf` 不会污染部署目录）

**内容来源**：

```bash
git archive --format=tar HEAD | tar -x -C "$ROOTDIR"   # 只取被跟踪的文件
cp -a frontend-admin-pro/dist "$ROOTDIR/frontend-admin-pro/dist"
cp -a frontend-h5/dist        "$ROOTDIR/frontend-h5/dist"
rm -rf "$ROOTDIR/backend/data"
find "$ROOTDIR" \( -name ".env" -o -name ".env.*" \) -delete
```

**必然不在包里**（打包后还会二次删除 + 断言）：

- `backend/.env`、任何 `.env.*`（客户配置与密钥）——`find ... -delete` 后还有一条
  `if find ... | grep -q .` 硬断言，宁可失败也不发出去
- `backend/data/`（上传件、备份、扩展、模型、升级缓存）
- `node_modules/`、`.git/`、`logs/`

**包自检**：`VERSION`、`backend/app/main.py`、`backend/requirements.txt` 三样缺一样就中止；
并打印包内 `VERSION` 供人工核对。

---

## 6. 客户机升级通道 A：后台「立即升级」

「关于/版本」页 → 检查更新 → 立即升级 / 回滚。后端代跑同样一套产物包。

| 环节 | 依赖 | 说明 |
|---|---|---|
| 查最新版本 | 能访问 `api.github.com` | 公开仓库匿名读，**不需要任何令牌** |
| 下载产物包 | 能访问 `github.com` | Release 附件直链 |
| 校验 | 无额外依赖 | 优先 Release 接口自带 digest，其次 `.sha256` 附件；**两者都没有直接拒绝安装** |
| 前端换入 | 不需要 node | 包内已带 `dist`，整体原子换入 |
| 数据库备份 | `mysqldump` | 失败即中止，绝不带病继续 |
| 磁盘 | — | 开工前剩余 < 2 GiB 直接拒绝（历史上有一次就是 `disk full` 失败在半路） |

**阶段与超时**（`STAGE_TIMEOUTS`，秒）：

| 阶段 | 超时 | 为什么给这么长 |
|---|---|---|
| `backup` | 5400（90 分钟） | 大库 `mysqldump` 真的要跑这么久，给短了会误杀 |
| `fetch` / `checkout` | 900 | 下载 + 解包 |
| `deps` | 2400 | `pip install`，内网源慢 |
| `build` | 3600 | git 模式下的前端构建 |
| `migrate` | 1800 | `alembic upgrade head` |
| `restart` | 900 | 杀进程后等面板守护拉起（约 60s 一轮）+ 应用启动，健康检查最多等 180s |

**僵尸任务收尸**：进程被强杀 / 断电后，`upgrade_jobs` 里会留下永久 `running` 的任务，
前端永远转圈。`reconcile_jobs` 用三重判据判断是否已死，然后标 `failed` 并释放锁：

1. 该 id 不在本进程的执行集合里；
2. 锁文件持有者 pid 已不存在（`backup` 阶段跳过这条，避免误杀还在跑的 `mysqldump`）；
3. 或当前阶段已超过上表超时。

手工兜底：`POST /api/admin/system/upgrade/jobs/{id}/force-fail`。

**相关环境变量**：

| 变量 | 默认 | 作用 |
|---|---|---|
| `CENKORMES_UPGRADE_MODE` | `artifact` | `artifact` 产物包；`git` 开发机用；`auto` 按有无 `.git` 自动选 |
| `CENKORMES_REPO` | `likele001/cenkor_mes` | 私有化部署指向自己的仓库 / 私有镜像 |
| `CENKORMES_GITHUB_API` | `https://api.github.com` | 内网镜像或 GitHub Enterprise |
| `CENKORMES_ALLOW_UNVERIFIED` | 空 | `1` 才允许装无摘要的包（不建议） |
| `CENKORMES_RESTART_CMD` | 空 | 自定义重启命令；不配则杀监听进程等面板守护拉起 |
| `CENKORMES_CELERY_UNITS` | `cenkormes-celery cenkormes-beat` | 升级后一并重启的 worker 单元名 |
| `CENKORMES_HEALTH_URL` | `http://127.0.0.1:8500/api/health` | 升级后健康检查地址 |
| `CENKORMES_RELEASE_CACHE_TTL` | `300` | Releases 列表缓存秒数（匿名 API 每小时只有 60 次） |

> `CENKORMES_CELERY_UNITS` 存在的原因：守护脚本里的服务名是全局的。同机再跑一套预发
> 实例时，如果两套共用同一组单元名，升级预发会把**生产 worker**也重启掉。

---

## 7. 客户机升级通道 B：命令行

```bash
bash scripts/upgrade.sh --list                  # 列出远端可安装版本
bash scripts/upgrade.sh                         # 装最新正式版
bash scripts/upgrade.sh --version v2.2.2        # 装指定版本（也可用于修复被改坏的文件）
bash scripts/upgrade.sh --dry-run               # 只打印将执行的动作
bash scripts/upgrade.sh --skip-backup           # 跳过数据库备份（不推荐）
bash scripts/upgrade.sh --skip-frontend         # 不换入 dist（正常不需要）
bash scripts/upgrade.sh --repo owner/name       # 指定仓库
bash scripts/upgrade.sh --git                   # 开发机：改回 git fetch/checkout
```

流程：备份数据库 → 下载包 → **校验 SHA256** → 解包 → 覆盖代码 → `pip install -r requirements.txt`
→ `alembic upgrade head` → 提示重启。

**脚本绝不启停任何服务**。跑完必须手动重启后端（uvicorn / celery）才生效。
完全无外网的机器：把包和 `.sha256` 拷进内网，按 [DEPLOYMENT.md 第 8.3 节](./DEPLOYMENT.md) 手动覆盖。

---

## 8. 覆盖规则：什么会被覆盖，什么永远不会

覆盖是**逐文件 `copy2`**，不用 `rsync`，因此不要求客户机装 rsync。

**永不覆盖、永不删除**（`PROTECTED_PREFIXES` / `_is_protected`）：

| 路径 | 原因 |
|---|---|
| `backend/.env`、任何 `.env` / `.env.*` | 现场配置与密钥 |
| `backend/data/` 整个目录 | 客户数据：上传件、备份、扩展、模型、升级缓存 |
| `.git/`、`node_modules/`、`backend/node_modules/` | 与产物无关，且体积大 |
| `backend/.venv/`、`venv/` 等虚拟环境 | 宝塔 / 客户自建环境 |
| `logs/` | 运行日志 |
| `frontend-*/dist/` | 由 `_promote_frontend` 整体原子换入，不走逐文件覆盖 |
| `.release-manifest.txt` | 安装清单本身 |
| `dist.__bak/`、`.dist-build-*`、`.dist-new-*` | 前端换入的临时与回滚产物 |

**废弃文件清理**：靠 `.release-manifest.txt`（上一版装过哪些文件的清单）。
按「旧清单 − 新清单」精确删除，所以升级不会在客户机上留下已废弃的旧代码。
**首次以产物包升级时没有清单，此时一份都不删**——宁可留垃圾，不能删客户文件。

**前端原子换入**：`dist` 先解到 `.dist-new-*`，再改名换入，旧的留成 `dist.__bak`；
换入失败会把 `dist.__bak` 还原回去，不会出现「前端目录空着」。

---

## 9. 回滚

| 层 | 做法 |
|---|---|
| 代码 | `bash scripts/upgrade.sh --version <上一个版本>`，不需要本地保留 git 历史 |
| 数据库 | 用升级前的 dump 恢复（`backend/data/backups/`）；**先停后端再恢复** |
| 前端 | 自动：换入失败会还原 `dist.__bak`；手工：`mv dist.__bak dist` |

注意：回滚数据库后代码也要回到对应版本，否则 `alembic` 版本链会和代码预期不符。

---

## 10. 排错手册（都是真踩过的）

| 现象 | 根因 | 解法 |
|---|---|---|
| `PATCH /releases/tags/vX` 返回 404 | GitHub API 不接受用 tag 直接改 Release | 先 `GET /releases/tags/vX` 拿 **id**，再 `PATCH /releases/{id}` |
| tag 存在但没 Release | 早期 CI 因账单锁定没跑；或忘了补 CHANGELOG | `gh workflow run release.yml -f tag=vX.Y.Z` 回填 |
| 手动触发 workflow 报 `fatal: not a git repository` | `attach` job 没 checkout | 命令显式带 `--repo ${{ github.repository }}` |
| 回填旧 tag 时 CI `exit 127` | 旧 tag 里没有 `release-check.sh` | 脚本从主干检出，用 `--root` 指向目标 tag |
| 脚本推上去后每行都报语法错 | Windows 下写出 CRLF，`#!/usr/bin/env bash\r` 找不到解释器 | 写文件用 `write_bytes` 强制 LF；`bash -n` 先验 |
| `VERSION` 比较永远不相等 | 同上，`VERSION` 里混进 `\r` | `release-check.sh` 已 `tr -d ' \r\n'`，编辑器设 LF |
| 客户装完前端空白 | 拿了 GitHub 的 Source code 快照（不含 `dist`） | 只认 `cenkormes-vX.Y.Z.tar.gz` 附件 |
| 「立即升级」提示该版本没有产物包 | `package`/`attach` 失败 | 看 CI 日志；`workflow_dispatch` 补挂 |
| 升级失败在半路，`disk full` | 磁盘剩余不足 | 后台现在开工前 <2 GiB 直接拒绝；先清 `backend/data/backups/` |
| 升级任务永远「进行中」 | 进程被强杀，任务没写终态 | `reconcile_jobs` 会自动收尸；兜底 `POST .../jobs/{id}/force-fail` |
| 升级后另一套实例的 worker 被重启 | 守护脚本服务名是全局的 | 给每套实例设独立的 `CENKORMES_CELERY_UNITS` |
| 手动起进程后宝塔反复报 `address already in use` | 违反「Python 一律宝塔托管」 | **不手动 `kill`/`nohup`/`setsid`**；要重启就先清端口残留，等守护拉起 |

---

## 11. 发版前检查清单

```
[ ] git status 干净，要发的东西都已提交
[ ] release-all.sh --dry-run 版本号递增符合预期
[ ] 说明写清楚（≥8 字，说清「改了什么/影响谁」）
[ ] CI 四个 job 全绿
[ ] Release 有两个附件（tar.gz + .sha256）
[ ] 包内 VERSION == tag，dist/index.html 存在
[ ] 本机/生产已重启后端，「关于」页版本正确
[ ] 客户可升级路径验证过（至少 upgrade.sh --list 能看到新版本）
```

---

## 附录：命令速查

```bash
# 一致性校验
bash scripts/release-check.sh --tag v2.2.2

# 发版
bash scripts/release-all.sh --dry-run "说明"
bash scripts/release-all.sh "说明"
VERSION_BUMP=minor bash scripts/release-all.sh "说明"

# 看 CI
gh run list --limit 3 && gh run watch

# 回填 Release / 补挂产物
gh workflow run release.yml -f tag=v2.2.2

# 客户机
bash scripts/upgrade.sh --list
bash scripts/upgrade.sh --version v2.2.2

# 验证 Release 附件
curl -s https://api.github.com/repos/likele001/cenkor_mes/releases/latest \
  | python3 -c 'import json,sys; print([a["name"] for a in json.load(sys.stdin)["assets"]])'
```
