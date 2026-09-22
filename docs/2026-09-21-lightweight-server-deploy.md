# 轻量应用服务器手动部署

适用环境：阿里云轻量应用服务器，系统为 Alibaba Cloud Linux 或 CentOS 系（包管理器是 `dnf`，没有 `apt`）。机器按 2 核 2G 准备。

部署形态：

- 前端是 Vite 静态产物（`dist/`），由 Nginx 托管。
- 后端是 **wheel 发布包**：本机构建，服务器 `pip install`，用 systemd 跑 `snsn-api start`（无 reload）。
- Nginx 把 `/api` 反代到 `127.0.0.1:8000`。8000 不对公网开放。

| 路径 | 用途 |
|------|------|
| `/opt/snsn/.venv` | 运行时虚拟环境（装 wheel） |
| `/opt/snsn/.env` | 密钥与配置（不进发布包） |
| `/opt/snsn/data/tmp` | 上传和抽音的临时文件 |
| `/opt/snsn/releases/<ver>/` | 后端发布包（wheel + unit） |
| `/opt/snsn/frontend/` | 前端静态产物（`frontend/dist`） |

轻量控制台防火墙只放行 **22、80、443**。

## 1. 系统依赖

```bash
cat /etc/os-release
sudo dnf update -y
sudo dnf install -y nginx git python3.11 python3.11-pip
python3.11 --version
```

`python3.11 --version` 需要是 3.11 或更高。不要用系统自带的 `python3` 建虚拟环境，它经常是 3.6，装不了当前依赖。

`ffmpeg` 和 `ffprobe` 必须同时在 PATH 里。先试软件源：

```bash
sudo dnf install -y epel-release
sudo dnf install -y ffmpeg
ffmpeg -version
ffprobe -version
```

软件源里没有 `ffmpeg` 时，用静态包：

```bash
cd /tmp
curl -L -o ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar -xf ffmpeg.tar.xz
sudo cp ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe /usr/local/bin/
ffmpeg -version
ffprobe -version
```

2G 内存跑转码容易被系统杀掉，加 2G 交换空间：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. 后端（发布包）

### 2.1 本机构建

在开发机 `backend/` 下：

```powershell
cd backend
.\release.ps1
# 或: python scripts\build_release.py
```

产物在 `backend/dist/`：

- `snsn_api-0.1.0-py3-none-any.whl`
- `snsn-api-0.1.0-release.tar.gz`（推荐上传这个）

不要上传 Windows 的 `.venv`、`.env`、源码整树。

### 2.2 服务器安装

```bash
sudo mkdir -p /opt/snsn /opt/snsn/data/tmp /opt/snsn/releases /opt/snsn/frontend

# 把 snsn-api-0.1.0-release.tar.gz 传到服务器后：
# 用 tar 直接解到目标目录（会带上 .env.example；不要用 cp dir/*，会漏掉点文件）
sudo mkdir -p /opt/snsn/releases/0.1.0
sudo tar -xzf /path/to/snsn-api-0.1.0-release.tar.gz \
  -C /opt/snsn/releases/0.1.0 --strip-components=1
# 确认含有 .env.example：
# ls -la /opt/snsn/releases/0.1.0

cd /opt/snsn
sudo python3.11 -m venv .venv
sudo .venv/bin/pip install -U pip
sudo .venv/bin/pip install /opt/snsn/releases/0.1.0/snsn_api-*-py3-none-any.whl

sudo cp -n /opt/snsn/releases/0.1.0/.env.example /opt/snsn/.env
sudo chmod 600 /opt/snsn/.env
```

`cp -n` 在 `.env` 已存在时不会覆盖。编辑 `/opt/snsn/.env`，至少填这些项：

```bash
SNSN_HOST=127.0.0.1
SNSN_PORT=8000
SNSN_WORKERS=1
SNSN_TMP_DIR=/opt/snsn/data/tmp
SNSN_MAX_UPLOAD_MB=200
SNSN_API_TOKEN=换成一长串随机口令

SNSN_OSS_ACCESS_KEY_ID=
SNSN_OSS_ACCESS_KEY_SECRET=
SNSN_OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
SNSN_OSS_BUCKET=
SNSN_OSS_PREFIX=tmp/snsn/

SNSN_DASHSCOPE_API_KEY=
SNSN_ASR_MODEL=paraformer-v2
SNSN_TRANSLATE_MODEL=qwen-plus
SNSN_ENABLE_TRANSLATE=true
```

`SNSN_API_TOKEN` 留空则上传接口不校验。填了的话，构建前端时要用同一个值。

OSS Bucket 建在华北2（北京），和百炼 Paraformer 同区。轻量机不在北京时，继续用公网地址 `oss-cn-beijing.aliyuncs.com`。机器也在北京时，把 `SNSN_OSS_ENDPOINT` 改成 `https://oss-cn-beijing-internal.aliyuncs.com`。给 `tmp/snsn/` 加一条生命周期规则，例如 1 天后删除。

```bash
sudo chmod 600 /opt/snsn/.env
sudo cp /opt/snsn/releases/0.1.0/snsn-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now snsn-api
sudo systemctl status snsn-api
curl -s http://127.0.0.1:8000/api/health
```

工作目录是 `/opt/snsn`（读同目录 `.env`）。代码在 venv 的 site-packages 里，不靠服务器上的源码树。任务状态在内存里，重启服务会丢掉进行中的转写。

`ffmpeg`、`oss_configured`、`asr_configured` 都应为 `true`。

## 3. 前端

在自己的电脑上构建并打成 tar.gz，不要在 2G 服务器上跑 `npm run build`。

PowerShell：

```powershell
cd frontend
# 确认 .env 里已有 VITE_SNSN_API_TOKEN（与服务器 SNSN_API_TOKEN 一致）
.\release.ps1
```

产物：`frontend/release/snsn-www-YYYYMMDD-HHMM.tar.gz`。

后端没设 `SNSN_API_TOKEN` 时，不要设置 `VITE_SNSN_API_TOKEN`。这个值会写进静态文件，口令改了就要重新构建并上传。

上传到服务器后解压到 `/opt/snsn/frontend/`：

```powershell
scp .\release\snsn-www-*.tar.gz root@服务器IP:/tmp/
```

```bash
sudo mkdir -p /opt/snsn/frontend
sudo tar -xzf /tmp/snsn-www-YYYYMMDD-HHMM.tar.gz -C /opt/snsn/frontend
sudo chown -R nginx:nginx /opt/snsn/frontend
sudo find /opt/snsn/frontend -type d -exec chmod 755 {} \;
sudo find /opt/snsn/frontend -type f -exec chmod 644 {} \;
```

## 4. Nginx

### 4.1 写配置

```bash
sudo vi /etc/nginx/conf.d/snsn.conf
```

按 `i` 进入编辑，粘贴下面内容（`server_name` 改成你的域名或公网 IP），然后 `Esc`，输入 `:wq` 回车保存退出：

```nginx
server {
    listen 80;
    server_name 你的域名或IP;

    client_max_body_size 220m;
    root /opt/snsn/frontend;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

（更习惯图形化编辑可用 `sudo nano /etc/nginx/conf.d/snsn.conf`，`Ctrl+O` 保存，`Ctrl+X` 退出。）

### 4.2 生效

```bash
sudo rm -f /etc/nginx/conf.d/default.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

### 4.3 验收

```bash
curl -s http://127.0.0.1/api/health
```

浏览器打开 `http://服务器IP`，能进首页；`/api/health` 应返回 JSON。

### 4.4 可选（多数情况可跳过）

SELinux 是 Enforcing 时：

```bash
sudo setsebool -P httpd_can_network_connect 1
sudo dnf install -y policycoreutils-python-utils
sudo semanage fcontext -a -t httpd_sys_content_t "/opt/snsn/frontend(/.*)?"
sudo restorecon -Rv /opt/snsn/frontend
```

装了 firewalld 时：

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 5. HTTPS

域名已经解析到这台机器之后：

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

之后用 `https://你的域名` 访问。

## 6. 更新

后端：本机改版本号（`pyproject.toml` 的 `version`）后重新 `.\release.ps1`，上传新的 `snsn-api-<ver>-release.tar.gz`，然后：

```bash
# 例：升级到 0.1.1
sudo mkdir -p /opt/snsn/releases/0.1.1
sudo tar -xzf /tmp/snsn-api-0.1.1-release.tar.gz \
  -C /opt/snsn/releases/0.1.1 --strip-components=1
cd /opt/snsn
sudo .venv/bin/pip install --upgrade /opt/snsn/releases/0.1.1/snsn_api-*-py3-none-any.whl
sudo systemctl restart snsn-api
curl -s http://127.0.0.1:8000/api/health
```

前端：本机重新 `.\release.ps1`，上传 `snsn-www-*.tar.gz`，解压覆盖 `/opt/snsn/frontend/`。静态文件不用重启 Nginx。

日志：

```bash
sudo journalctl -u snsn-api -f
```

确认没有正在跑的任务后，可以清理 `/opt/snsn/data/tmp` 里的残留文件。

## 7. GitHub Actions 自动部署（私有库可用）

私有仓库一样能用 Actions，不需要把仓库改成公开。在 GitHub → **Settings → Secrets and variables → Actions** 添加：

| Secret | 含义 |
|--------|------|
| `DEPLOY_HOST` | 服务器公网 IP 或域名 |
| `DEPLOY_USER` | SSH 用户，一般是 `root` |
| `DEPLOY_SSH_KEY` | 部署用私钥全文（建议单独一对密钥） |
| `VITE_SNSN_API_TOKEN` | 与服务器 `SNSN_API_TOKEN` 相同 |
| `DEPLOY_WWW_DIR` | 可选，默认 `/opt/snsn/frontend` |
| `DEPLOY_SSH_PORT` | 可选，默认 `22` |

服务器上把对应**公钥**写进 `~/.ssh/authorized_keys`。`.env` 仍只放在服务器，不会进 CI。

发版：仓库 **Actions → Deploy → Run workflow**，勾选要发后端/前端。

流程：`build` 产物 → `scp` → 服务器执行 `deploy/remote_install.sh`（装 wheel、解压静态、`systemctl restart snsn-api`）。
