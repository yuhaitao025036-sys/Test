#!/bin/bash
# 快速导入Docker镜像

cd /ssd1/Dejavu/docker_images || exit 1

echo "开始导入镜像..."
count=0

for f in *.tar.gz; do
    # 跳过主压缩包
    [[ "$f" == swebench-images-*.tar.gz ]] && continue
    [[ ! -f "$f" ]] && continue
    
    echo "[$((++count))] 导入: $f"
    if gunzip -c "$f" | docker load; then
        echo "  ✓ 成功"
    else
        echo "  ✗ 失败"
    fi
done

echo ""
echo "导入完成! 已导入 $count 个镜像"
echo ""
echo "查看已导入的镜像:"
docker images | grep sweap-images
