-- 事件钩子（演示扩展）建表脚本
-- 要求幂等（可重复执行）；宿主按文件指纹只执行一次，内容变更后会重跑
-- 注意：本样例为 MySQL 语法；SQLite 开发环境请按需调整（如去掉 AUTO_INCREMENT）
CREATE TABLE IF NOT EXISTS ext_hook_demo_report_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_code VARCHAR(64) NOT NULL DEFAULT '',
    report_id INT NOT NULL DEFAULT 0,
    good_qty INT NOT NULL DEFAULT 0,
    bad_qty INT NOT NULL DEFAULT 0,
    logged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
