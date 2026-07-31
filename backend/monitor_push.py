#!/usr/bin/env python3
"""
推送队列监控脚本
用于实时监控飞书、企业微信、钉钉的推送任务队列状态
"""

import sys
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import redis

# 配置数据库连接（从环境变量读取，默认 cenkormes）
import os
DB_URL = os.getenv("MONITOR_DB_URL", "mysql+pymysql://cenkermes:123456abc@127.0.0.1:3306/cenkermes?charset=utf8mb4")


def get_redis_stats():
    """获取Redis队列状态"""
    r = redis.Redis(host='127.0.0.1', port=6379, db=2, decode_responses=True)
    
    stats = {
        'queues': {},
        'total_tasks': 0
    }
    
    # 检查主要队列
    queues = ['celery', 'default', 'ai', 'celery.pidbox', 'celeryev']
    for queue in queues:
        try:
            length = r.llen(queue)
            stats['queues'][queue] = length
            stats['total_tasks'] += length
        except:
            pass
    
    return stats


def get_db_push_stats():
    """获取数据库中的推送统计"""
    engine = create_engine(DB_URL)
    
    stats = {
        'feishu': {},
        'wecom': {},
        'dingtalk': {}
    }
    
    with Session(engine) as db:
        # 飞书统计
        result = db.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM feishu_push_logs 
            WHERE DATE(created_at) = CURDATE()
            GROUP BY status
        """))
        for row in result:
            stats['feishu'][row[0]] = row[1]
        
        # 企业微信统计
        result = db.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM wecom_push_logs 
            WHERE DATE(created_at) = CURDATE()
            GROUP BY status
        """))
        for row in result:
            stats['wecom'][row[0]] = row[1]
        
        # 钉钉统计
        result = db.execute(text("""
            SELECT status, COUNT(*) as count 
            FROM dingtalk_push_logs 
            WHERE DATE(created_at) = CURDATE()
            GROUP BY status
        """))
        for row in result:
            stats['dingtalk'][row[0]] = row[1]
    
    return stats


def format_report():
    """生成监控报告"""
    print("=" * 60)
    print(f"📊 推送队列监控报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Redis队列状态
    redis_stats = get_redis_stats()
    print("\n🐇 Redis 队列状态:")
    print("-" * 40)
    for queue, length in redis_stats['queues'].items():
        emoji = "✅" if length == 0 else "⚠️"
        print(f"  {emoji} {queue}: {length} 个任务")
    print(f"\n  📦 总任务数: {redis_stats['total_tasks']}")
    
    # 数据库推送统计
    db_stats = get_db_push_stats()
    print("\n📱 今日推送统计:")
    print("-" * 40)
    
    for channel, data in db_stats.items():
        total = sum(data.values())
        success = data.get('success', 0)
        failed = data.get('failed', 0)
        pending = data.get('pending', 0)
        deferred = data.get('deferred', 0)
        
        channel_emoji = {'feishu': '🦅', 'wecom': '🐧', 'dingtalk': '📌'}.get(channel, '📱')
        print(f"\n  {channel_emoji} {channel.upper()}:")
        print(f"     总计: {total} | 成功: {success} | 失败: {failed} | 待处理: {pending} | 延迟: {deferred}")
    
    # 建议
    print("\n💡 状态诊断:")
    if redis_stats['total_tasks'] > 100:
        print("  ⚠️ 警告: Redis队列任务过多，可能需要清理")
    elif redis_stats['total_tasks'] > 0:
        print("  ✅ 正常: 队列中有少量任务正在处理")
    else:
        print("  ✅ 健康: 队列为空，所有任务已处理")
    
    # 检查是否有失败推送
    total_failed = sum(d.get('failed', 0) for d in db_stats.values())
    if total_failed > 0:
        print(f"  ⚠️ 警告: 今日有 {total_failed} 条推送失败，请检查日志")
    
    print("\n" + "=" * 60)
    
    return {
        'timestamp': datetime.now().isoformat(),
        'redis': redis_stats,
        'push_stats': db_stats,
        'is_healthy': redis_stats['total_tasks'] < 100 and total_failed == 0
    }


if __name__ == '__main__':
    result = format_report()
    
    # 如果传入 --json 参数，输出JSON格式
    if '--json' in sys.argv:
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))
