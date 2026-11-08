#!/usr/bin/env bash
# CenkorMES 主站 nginx 加固自检
#
# 为什么需要这个脚本：宝塔面板在「切换 SSL / 保存伪静态 / 改反向代理 / 改网站目录」
# 时会重新生成 vhost 与 rewrite 文件，手工加上去的安全头、限流、超时会被冲掉，
# 而且不会有任何报错——站点照常运行，只是悄悄变回加固前的状态。
# 每次动过面板里这个站的设置，跑一遍这个脚本确认没丢。
#
# 用法：bash scripts/check-nginx-hardening.sh
# 退出码：0 全部通过，1 有缺项

set -uo pipefail

VHOST=/www/server/panel/vhost/nginx/ck.mes.cenkor.cn.conf
REWRITE=/www/server/panel/vhost/rewrite/ck.mes.cenkor.cn.conf
DOMAIN=ck.mes.cenkor.cn
LOGROTATE=/etc/logrotate.d/cenkormes-nginx

pass=0
fail=0

ok() { printf '  ✅ %s\n' "$1"; pass=$((pass + 1)); }
ng() { printf '  ❌ %s\n' "$1"; fail=$((fail + 1)); }

has() {  # has <文件> <描述> <字面量>
    if grep -qF -- "$3" "$1" 2>/dev/null; then ok "$2"; else ng "$2（缺：$3）"; fi
}

echo "== 1. vhost 加固项 =="
has "$VHOST" "限流 zone 已定义"            'zone=cenkormes_api'
has "$VHOST" "TLSv1.1 已关闭"              'ssl_protocols TLSv1.2 TLSv1.3'
has "$VHOST" "X-Content-Type-Options"      'X-Content-Type-Options "nosniff"'
has "$VHOST" "X-Frame-Options"             'X-Frame-Options "SAMEORIGIN"'
has "$VHOST" "Referrer-Policy"             'Referrer-Policy "strict-origin-when-cross-origin"'
has "$VHOST" "HSTS"                        'Strict-Transport-Security "max-age=31536000"'

if grep -qF 'TLSv1.1 TLSv1.2' "$VHOST" 2>/dev/null; then
    ng "ssl_protocols 又带上 TLSv1.1 了"
fi

echo "== 2. rewrite 加固项 =="
has "$REWRITE" "API 读超时 120s"           'proxy_read_timeout 120s'
has "$REWRITE" "API 限流已启用"            'limit_req zone=cenkormes_api'
has "$REWRITE" "限流状态码 429"            'limit_req_status 429'
has "$REWRITE" "限流日志降级 warn"         'limit_req_log_level warn'
# /assets/ 与 /index.html 有自己的 add_header，会断开 server 级继承，必须各自带安全头
if grep -qF 'X-Frame-Options "SAMEORIGIN" always' "$REWRITE" 2>/dev/null; then
    ok "location 级安全头已补（add_header 不继承）"
else
    ng "location 级安全头缺失，/index.html 会丢掉 X-Frame-Options"
fi

echo "== 3. 日志轮转 =="
if [ -f "$LOGROTATE" ]; then ok "logrotate 配置存在"; else ng "logrotate 配置丢失"; fi

echo "== 4. 线上实测响应头 =="
hdr=$(curl -sI --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/" -k 2>/dev/null)
for h in strict-transport-security x-content-type-options x-frame-options referrer-policy; do
    if printf '%s' "$hdr" | grep -qi "^$h:"; then ok "响应头 $h"; else ng "响应头 $h 缺失"; fi
done

code=$(curl -s -o /dev/null -w '%{http_code}' --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/health" -k 2>/dev/null)
[ "$code" = "200" ] && ok "API 代理可用（/api/health 200）" || ng "API 代理异常（/api/health $code）"

echo
echo "通过 $pass 项，失败 $fail 项"
[ "$fail" -eq 0 ] || exit 1
