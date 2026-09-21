# 轻量应用服务器手动部署

适用环境：阿里云轻量应用服务器，系统为 Alibaba Cloud Linux 或 CentOS 系（包管理器是 `dnf`，没有 `apt`）。机器按 2 核 2G 准备。

部署形态：

- 前端是 Vite 静态产物，由 Nginx 托管。
- 后端是 FastAPI 源码，不打包。在服务器上建虚拟环境后用 `uvicorn` 跑。
- Nginx 把 `/api` 反代到 `127.0.0.1:8000`。8000 不对公网开放。

| 路径 | 用途 |
|------|------|
| `/opt/snsn/backend` | 后端源码、虚拟环境、`.env` |
| `/opt/snsn/backend/data/tmp` | 上传和抽音的临时文件 |
| `/var/www/snsn` | 前端 `dist` |

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

## 2. 后端

后端不需要构建。把源码放到服务器，在 Linux 上新建虚拟环境。不要上传本机 Windows 的 `.venv`，也不要上传 `.env`、`__pycache__`、`data/tmp`。

服务器能访问私有仓库时：

```bash
sudo mkdir -p /opt/snsn /var/www/snsn
sudo git clone <仓库地址> /opt/snsn
```

不能在服务器上克隆时，从本机上传 `backend` 目录（排除上面那些文件）到 `/opt/snsn/backend`。

然后在服务器上：

```bash
sudo useradd -r -s /sbin/nologin snsn || true
cd /opt/snsn/backend
sudo python3.11 -m venv .venv
sudo .venv/bin/pip install -U pip
sudo .venv/bin/pip install -r requirements.txt
sudo cp -n .env.example .env
sudo mkdir -p /opt/snsn/backend/data/tmp
```

`cp -n` 在 `.env` 已存在时不会覆盖。编辑 `/opt/snsn/backend/.env`，至少填这些项：

```bash
SNSN_HOST=127.0.0.1
SNSN_PORT=8000
SNSN_TMP_DIR=/opt/snsn/backend/data/tmp
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
sudo chown -R snsn:snsn /opt/snsn
sudo chmod 600 /opt/snsn/backend/.env
```

新建 `/etc/systemd/system/snsn-api.service`：

```ini
[Unit]
Description=SnSn API
After=network.target

[Service]
User=snsn
Group=snsn
WorkingDirectory=/opt/snsn/backend
EnvironmentFile=/opt/snsn/backend/.env
ExecStart=/opt/snsn/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

工作目录必须是 `backend`，进程才会读到同目录的 `.env`。任务状态在内存里，重启服务会丢掉进行中的转写。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now snsn-api
sudo systemctl status snsn-api
curl -s http://127.0.0.1:8000/api/health
```

`ffmpeg`、`oss_configured`、`asr_configured` 都应为 `true`。

## 3. 前端

在自己的电脑上构建，不要在 2G 服务器上跑 `npm run build`。

PowerShell：

```powershell
cd frontend
npm install
$env:VITE_SNSN_API_TOKEN="和服务器 SNSN_API_TOKEN 相同"
npm run build
```

后端没设 `SNSN_API_TOKEN` 时，不要设置 `VITE_SNSN_API_TOKEN`。这个值会写进静态文件，口令改了就要重新构建并上传。

把 `frontend/dist` 里的全部内容上传到服务器的 `/var/www/snsn/`：

```powershell
scp -r dist/* root@服务器IP:/var/www/snsn/
```

服务器上：

```bash
sudo chown -R nginx:nginx /var/www/snsn
sudo find /var/www/snsn -type d -exec chmod 755 {} \;
sudo find /var/www/snsn -type f -exec chmod 644 {} \;
```

## 4. Nginx

这台系统没有 `sites-available`。配置写到 `/etc/nginx/conf.d/snsn.conf`，把 `server_name` 换成域名或公网 IP：

```nginx
server {
    listen 80;
    server_name 你的域名或IP;

    client_max_body_size 220m;
    root /var/www/snsn;
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

`client_max_body_size` 要大于后端的 200MB 上传上限，否则大文件会在 Nginx 被拒绝。

```bash
sudo rm -f /etc/nginx/conf.d/default.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

SELinux 若是 Enforcing，允许 Nginx 反代本机接口，并让它能读静态目录：

```bash
getenforce
sudo setsebool -P httpd_can_network_connect 1
sudo dnf install -y policycoreutils-python-utils
sudo semanage fcontext -a -t httpd_sys_content_t "/var/www/snsn(/.*)?"
sudo restorecon -Rv /var/www/snsn
```

`getenforce` 输出 `Disabled` 或 `Permissive` 时，上面这组可以跳过。

本机若装了 firewalld，再放行网页端口。命令不存在就说明没装，只靠轻量控制台防火墙：

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

浏览器打开 `http://服务器IP/api/health`，应返回和本机 `curl` 一样的 JSON。再打开首页，导入一段短音频，确认能排队、转写、出字幕。

## 5. HTTPS

域名已经解析到这台机器之后：

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

之后用 `https://你的域名` 访问。

## 6. 更新

后端：上传新的源码（或在服务器上 `git pull`），然后：

```bash
cd /opt/snsn/backend
sudo .venv/bin/pip install -r requirements.txt
sudo chown -R snsn:snsn /opt/snsn
sudo systemctl restart snsn-api
```

前端：本机重新 `npm run build`，把 `dist` 覆盖到 `/var/www/snsn/`。静态文件不用重启 Nginx。

日志：

```bash
sudo journalctl -u snsn-api -f
```

确认没有正在跑的任务后，可以清理 `/opt/snsn/backend/data/tmp` 里的残留文件。
