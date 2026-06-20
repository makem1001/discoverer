# 发现者（Discoverer）生产部署手册

> 环境：**大陆云服务器 + Ubuntu/Debian + Docker** ｜ 域名：`zlzlzf.cn`（`.cn`，需备案）
> 目标：HTTPS 域名访问 → `https://zlzlzf.cn`

---

## 🗺️ 全景路线图

```
当前卡点 ↓
[A] ICP备案(7-20天) ──┐
                      ├─→ [E] DNS解析 → [F] Nginx反代 → [G] HTTPS → [H] 安全收尾 → 🎉上线
[B] 服务器环境 ───────┤        (备案通过后做)
[C] 部署discoverer ───┤
[D] IP验证 ───────────┘
   (备案期间并行做，不用等)
```

**关键认知**：A（备案）是唯一阻塞域名访问的关卡，只能你本人去云控制台做，约 7–20 天。但 B/C/D 不用等备案，**现在就能并行做**，先用 `服务器IP:3000` 把服务跑起来。备案一过，E/F/G 半小时收尾。

---

## 阶段 A — 立即提交 ICP 备案（阻塞项）

1. 登录你的云服务商控制台（阿里云/腾讯云），搜索「**备案**」入口
2. 新增备案 → 选择这台服务器对应的**云服务器实例**（备案号绑定服务器）
3. 填写：主体信息（个人/企业）、网站信息（域名 `zlzlzf.cn`、网站名称、服务内容）
4. 上传：身份证、人脸核验（按引导走）
5. 提交后进入管局审核，**7–20 天**，期间手机保持畅通
6. ⚠️ 备案通过前，域名指向大陆服务器的 80/443 会被运营商拦截，**这是正常现象**

> 备案是免费的。提交完就往下走阶段 B，别干等。

---

## 阶段 B — 服务器环境准备（备案期间并行）

SSH 登录服务器后依次执行：

```bash
# 1) 更新系统
sudo apt update && sudo apt upgrade -y

# 2) 安装 Docker + Compose 插件
#    ⚠️ 大陆服务器访问 docker.com 常被 reset，用阿里云镜像源：
curl -fsSL https://get.docker.com | sudo sh -s -- --mirror Aliyun
sudo usermod -aG docker $USER          # 让当前用户免 sudo 用 docker
newgrp docker                          # 立即生效（或重新登录）
docker --version && docker compose version

# 2.5) ⚠️ 配 Docker 镜像加速器（大陆服务器拉 Docker Hub 基础镜像极慢/卡死，必配）
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
JSON
sudo systemctl daemon-reload && sudo systemctl restart docker

# 3) 安装系统级 Nginx（对外网关）+ certbot（HTTPS证书）
sudo apt install -y nginx certbot python3-certbot-nginx git rsync

# 4) 防火墙：阿里云推荐直接用「安全组」放行端口（控制台操作，更安全）
#    ⚠️ 不建议在服务器上开 ufw —— 若忘了先放行 22 会把自己 SSH 锁在门外！
#    如确需 ufw，务必先 allow 22 再 enable：
# sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable
```

> ⚠️ 云服务商的**安全组**也要在控制台放行 **80、443、22**。8000/3000 端口**不要**对公网开放（仅本机用）。

---

## 阶段 C — 部署 discoverer

### C1. 拉代码

```bash
cd ~
git clone https://github.com/makem1001/discoverer.git
cd discoverer
```

### C2. 创建后端 .env（git 里没有，需手建）

```bash
# 生成一个强随机 JWT 密钥
JWT=$(openssl rand -hex 32)

cat > backend/.env <<EOF
LLM_API_KEY=sk-你的DeepSeek新key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
JWT_SECRET_KEY=$JWT
EOF
```

> 🔑 `LLM_API_KEY` 填你刚换的新 key；`JWT_SECRET_KEY` 必须改成随机值（默认值 `discoverer-prod-change-me` 绝不能上生产）。

### C3. ⚠️ 传行情数据（关键坑！921MB 不在 git 里）

在**你本地 Mac** 上执行（不是服务器），把 921MB 行情数据同步到服务器：

```bash
cd /Users/zhanfei/WorkBuddy/2026-06-07-15-23-57/discoverer
rsync -avz --progress data/ <你的用户名>@<服务器公网IP>:~/discoverer/data/
```

> `rsync` 支持断点续传，中断了重跑同一条命令即可。921MB 视带宽约几分钟到几十分钟。
> 不传的话：回测/选股会 fallback 到 mock 随机数据，**结果无意义**。

### C4. 起服务

```bash
# 回到服务器的 discoverer 目录
cd ~/discoverer
docker compose up -d --build      # 首次构建较慢，耐心等
docker compose ps                 # 两个服务都 healthy/running 即成功
docker compose logs -f backend    # 看后端日志，Ctrl+C 退出
```

---

## 阶段 D — 用 IP 验证（备案前就能测）

浏览器访问：`http://<服务器公网IP>:3000`

> 大陆服务器**未备案时，用 IP + 非标准端口访问通常不被拦**，所以这步能提前验证服务是否正常。能正常注册/登录/跑回测 = 部署成功，只等备案接域名。

---

## 阶段 E — DNS 解析（备案通过后）

去你的**域名服务商**（注册 zlzlzf.cn 的地方）控制台 → 解析设置 → 添加两条 A 记录：

| 主机记录 | 类型 | 记录值 | 说明 |
|---------|------|--------|------|
| `@` | A | `<服务器公网IP>` | 裸域 zlzlzf.cn |
| `www` | A | `<服务器公网IP>` | www.zlzlzf.cn |

> 生效一般几分钟到几小时。验证：`ping zlzlzf.cn` 解析到你的 IP 即成功。

---

## 阶段 F — 系统 Nginx 反向代理（备案通过后）

前端容器内部已有 nginx 处理静态文件 + `/api` 代理（跑在宿主 3000 端口）。系统 Nginx 只需把域名流量转发到 3000：

```bash
sudo tee /etc/nginx/sites-available/discoverer.conf > /dev/null <<'EOF'
server {
    listen 80;
    server_name zlzlzf.cn www.zlzlzf.cn;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/discoverer.conf /etc/nginx/sites-enabled/
sudo nginx -t          # 测试配置语法
sudo systemctl reload nginx
```

此时 `http://zlzlzf.cn` 应该能打开了。

---

## 阶段 G — 上 HTTPS（Let's Encrypt 免费证书）

```bash
sudo certbot --nginx -d zlzlzf.cn -d www.zlzlzf.cn
# 按提示填邮箱、同意条款，选择 "重定向 HTTP→HTTPS"(选 2)
```

certbot 会自动改写 Nginx 配置、装证书、配 80→443 跳转。证书 90 天有效，**自动续期**已内置：

```bash
sudo certbot renew --dry-run    # 验证自动续期正常
```

完成后访问 `https://zlzlzf.cn` 🎉

---

## 阶段 H — 安全收尾（必做）

- [ ] **安全组**：仅放行 22/80/443；关闭 8000/3000 的公网入站
- [ ] **JWT_SECRET_KEY**：确认已用 `openssl rand -hex 32` 生成的强密钥（见 C2）
- [ ] **SSH 安全**：禁用 root 密码登录，改用密钥；可改默认 22 端口
- [ ] **DeepSeek key**：确认旧 key 已在控制台删除（✅ 你已完成）
- [ ] **定期备份**：`data/` 和 SQLite `discoverer.db` 定期 rsync 到别处

---

## 🔧 常见问题排查

| 现象 | 原因 / 解决 |
|------|------------|
| 域名打不开，IP 能开 | 备案没过 / DNS 没生效 / 安全组没放行 80,443 |
| 回测结果全是乱数 | `data/` 行情数据没传上去（见 C3） |
| `docker compose up` 报端口占用 | `sudo lsof -i:3000` 查占用，或改 compose 端口映射 |
| LLM 功能报 401 | `backend/.env` 的 `LLM_API_KEY` 没填对，改完 `docker compose restart backend` |
| certbot 报错域名无法验证 | DNS 还没生效 / 80 端口没通，等 DNS 生效后重试 |
| 改了代码想更新 | `git pull && docker compose up -d --build` |

---

## 📌 你现在的下一步

1. **今天就做**：阶段 A 提交 ICP 备案（去云控制台）
2. **同时做**：阶段 B → C → D，把服务在服务器上用 IP 跑起来
3. **备案通过后**：阶段 E → F → G，半小时接上域名 + HTTPS

备案那 7-20 天别浪费，把 B/C/D 跑通，等批复一下来就能上线。哪一步卡住把报错发我。
