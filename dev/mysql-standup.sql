-- Create the ai-grimoire user and databases on an existing MySQL 8 server.
-- Run as root:
--
--   docker exec -i mysql mysql -uroot -pmysql < dev/mysql-standup.sql
--   mysql -h 127.0.0.1 -uroot -p < dev/mysql-standup.sql
--
-- Idempotent: re-running only resets the password. The password is "localdev";
-- edit both lines below to change it.
--
--   grimoire       real data (point AI_GRIMOIRE_DSN at it)
--   grimoire_test  contract tests - they DELETE every row, so never share it
--
-- Tables are created by the plugin on first use; nothing to migrate here.

CREATE DATABASE IF NOT EXISTS grimoire      CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS grimoire_test CHARACTER SET utf8mb4;

CREATE USER IF NOT EXISTS 'grimoire'@'%' IDENTIFIED BY 'localdev';
ALTER USER 'grimoire'@'%' IDENTIFIED BY 'localdev';

GRANT ALL PRIVILEGES ON grimoire.*      TO 'grimoire'@'%';
GRANT ALL PRIVILEGES ON grimoire_test.* TO 'grimoire'@'%';

SELECT 'Done. export AI_GRIMOIRE_DSN=mysql://grimoire:localdev@127.0.0.1:3306/grimoire' AS next_step
UNION ALL
SELECT 'export AI_GRIMOIRE_TEST_MYSQL_DSN=mysql://grimoire:localdev@127.0.0.1:3306/grimoire_test';
