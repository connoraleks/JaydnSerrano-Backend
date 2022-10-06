CREATE TABLE `Dirents` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(255) UNIQUE,
  `parent` int,
  `isDir` boolean,
  `created_at` timestamp,
  `path` varchar(512),
  `src` varchar(255),
  `priority` int DEFAULT 0,
  `width` int,
  `height` int
);
ALTER TABLE `Dirents` ADD FOREIGN KEY (`parent`) REFERENCES `Dirents` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
