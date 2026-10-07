-- 报价单（演示扩展）建表脚本
-- 要求幂等（可重复执行）；宿主按文件指纹只执行一次，内容变更后会重跑
-- 注意：本样例为 MySQL 语法；SQLite 开发环境请按需调整（如去掉 AUTO_INCREMENT）
CREATE TABLE IF NOT EXISTS ext_quotation_demo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer VARCHAR(128) NOT NULL,
    amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO ext_quotation_demo (customer, amount, status)
SELECT '示例客户', 12800.00, 'draft' FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM ext_quotation_demo);
