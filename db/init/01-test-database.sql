-- Runs once, when the MySQL volume is first created: a separate database for the tests.
CREATE DATABASE IF NOT EXISTS unison_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON unison_test.* TO 'unison'@'%';
