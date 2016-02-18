-- Copyright 2009 FriendFeed
--
-- Licensed under the Apache License, Version 2.0 (the "License"); you may
-- not use this file except in compliance with the License. You may obtain
-- a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
-- WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
-- License for the specific language governing permissions and limitations
-- under the License.

-- To create the database:
--   CREATE DATABASE blog;
--   GRANT ALL PRIVILEGES ON blog.* TO 'blog'@'localhost' IDENTIFIED BY 'blog';
--
-- To reload the tables:
--   mysql --user=blog --password=blog --database=blog < schema.sql

-- SET SESSION storage_engine = "InnoDB";
-- SET SESSION time_zone = "+0:00";
-- ALTER DATABASE CHARACTER SET "utf8";
SET client_encoding = 'UTF8';

SET client_encoding = 'UTF8';

DROP TABLE IF EXISTS authors;
CREATE TABLE authors (
    id SERIAL PRIMARY KEY,
    level INT NOT NULL,
    credits INT NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(100) NOT NULL,
    intro TEXT
);

DROP TABLE IF EXISTS entries;
CREATE TABLE entries (
    id SERIAL PRIMARY KEY,
    hide BOOLEAN,
    link TEXT,
    thumbnail TEXT,
    excerpt TEXT,
    topicId INT NOT NULL,
    author_id INT NOT NULL REFERENCES authors(id),
    author VARCHAR(100),
    feedback INT,
    slug VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(512),
    terms VARCHAR(100),
    markdown TEXT,
    html TEXT,
    tags VARCHAR(100),
    published TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL,
);

DROP TABLE IF EXISTS tags;
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(100) NOT NULL,
    tag VARCHAR(100) NOT NULL
);
--DROP TABLE IF EXISTS topics;s
--CREATE TABLE topics (
--    id SERIAL PRIMARY KEY,
--    topicId INT NOT NULL,
--    author_id INT NOT NULL REFERENCES authors(id),
--    slug VARCHAR(100) NOT NULL UNIQUE,
--    title VARCHAR(512) NOT NULL,
--    markdown TEXT NOT NULL,
--    html TEXT NOT NULL,
--    published TIMESTAMP NOT NULL,
--    updated TIMESTAMP NOT NULL
--);
