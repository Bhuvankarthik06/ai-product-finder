-- Optional: create the MySQL database. Tables are created automatically by seed.py.
CREATE DATABASE IF NOT EXISTS product_finder CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE product_finder;

-- Reference of what SQLAlchemy creates:
-- CREATE TABLE products (
--   id INT AUTO_INCREMENT PRIMARY KEY,
--   name VARCHAR(160) NOT NULL,
--   brand VARCHAR(60) NOT NULL,
--   category VARCHAR(60) NOT NULL,
--   price INT NOT NULL,
--   rating FLOAT NOT NULL DEFAULT 4.0,
--   description TEXT NOT NULL,
--   specs TEXT NOT NULL,
--   in_stock BOOLEAN NOT NULL DEFAULT TRUE,
--   INDEX (brand), INDEX (category), INDEX (price)
-- );
