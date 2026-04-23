# SWE-bench 镜像传输方案

## 脚本说明

### 本地脚本

1. **batch-download.sh** - 下载镜像
   - 从数据集读取前5个镜像
   - 自动拉取、导出、压缩
   - 生成清单文件

2. **upload-from-local.sh** - 从本地上传到服务器
   - 通过堡垒机跳转
   - 自动打包、上传、清理
   - **需要配置**: 堡垒机和目标服务器信息

### 服务器脚本

3. **server-import.sh** - 在服务器导入镜像
   - 自动解压和导入
   - 显示进度和统计
   - 交互式确认

4. **download-from-relay.sh** - 从堡垒机拉取(备用)
   - 适用于已上传到堡垒机的情况

---

## 使用流程

### 方案1: 本地直接传输到服务器(推荐)

```bash
# 步骤1: 在本地下载镜像
cd /Users/yuhaitao01/dev/baidu/explore/test/docker
./batch-download.sh

# 步骤2: 配置上传脚本
vim upload-from-local.sh
# 修改以下配置:
#   RELAY_USER="your_username"
#   RELAY_HOST="relay.example.com"
#   TARGET_USER="your_username"
#   TARGET_HOST="target.example.com"

# 步骤3: 上传到服务器
./upload-from-local.sh

# 步骤4: SSH到服务器
ssh -J relay_user@relay_host:port target_user@target_host

# 步骤5: 导入镜像
cd /ssd1/Dejavu/docker_images
chmod +x server-import.sh
./server-import.sh
```

### 方案2: 通过堡垒机中转

```bash
# 步骤1: 在本地下载镜像
./batch-download.sh

# 步骤2: 先上传到堡垒机
scp swebench-images-export/*.tar.gz relay_user@relay_host:/tmp/

# 步骤3: 在服务器上拉取
# (在服务器上运行)
./download-from-relay.sh
```

---

## 配置说明

### upload-from-local.sh 需要配置的参数:

```bash
RELAY_USER="your_username"              # 堡垒机用户名
RELAY_HOST="relay.example.com"          # 堡垒机地址
RELAY_PORT="22"                         # 堡垒机SSH端口

TARGET_USER="your_username"             # 目标服务器用户名
TARGET_HOST="target.example.com"        # 目标服务器地址
TARGET_DIR="/ssd1/Dejavu/docker_images" # 目标路径(已配置好)
```

### SSH配置简化(可选)

在 `~/.ssh/config` 添加:

```
Host relay
    HostName relay.example.com
    User your_username
    Port 22

Host target
    HostName target.example.com
    User your_username
    ProxyJump relay
```

配置后可以简化命令:
```bash
ssh target  # 直接连接
scp file target:/path/  # 直接传输
```

---

## 文件结构

### 本地
```
/Users/yuhaitao01/dev/baidu/explore/test/docker/
├── batch-download.sh           # 下载脚本
├── upload-from-local.sh        # 上传脚本
├── server-import.sh            # 服务器导入脚本
├── download-from-relay.sh      # 从堡垒机拉取脚本
└── swebench-images-export/     # 下载的镜像
    ├── manifest.txt
    ├── image1.tar.gz
    └── ...
```

### 服务器
```
/ssd1/Dejavu/docker_images/
├── swebench-images-20250123_143000.tar.gz  # 上传的压缩包
├── image1.tar.gz                           # 解压后的镜像
├── image2.tar.gz
└── ...
```

---

## 常见问题

### Q: 上传很慢怎么办?
A: 
1. 确保堡垒机网络正常
2. 可以分批上传,修改 `BATCH_SIZE=2` 每次只传2个
3. 使用 `rsync` 代替 `scp` (支持断点续传)

### Q: 导入失败怎么办?
A: 
1. 检查磁盘空间: `df -h /ssd1`
2. 检查Docker服务: `docker ps`
3. 手动导入单个文件: `gunzip -c file.tar.gz | docker load`

### Q: 如何清理文件?
A:
```bash
# 服务器上
cd /ssd1/Dejavu/docker_images
rm *.tar.gz  # 导入后可删除

# 本地
rm -rf swebench-images-export/  # 上传后可删除
```

---

## 预计时间和空间

| 步骤 | 时间 | 空间占用 |
|------|------|---------|
| 下载5个镜像 | 30-60分钟 | 5-15GB |
| 打包 | 5-10分钟 | 临时占用同等空间 |
| 上传 | 10-60分钟 | 取决于网络 |
| 解压导入 | 10-20分钟 | 镜像原始大小 |

**建议**: 确保本地和服务器都有 **20GB+** 可用空间
