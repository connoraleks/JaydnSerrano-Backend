CREATE TABLE `Dirents` (
  `id` int PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(255) UNIQUE,
  `parent_dirent` int,
  `isDir` boolean,
  `created_at` timestamp,
  `path` varchar(512),
  `url` varchar(255),
  `priority` int
);

ALTER TABLE `Dirents` ADD FOREIGN KEY (`parent_dirent`) REFERENCES `Dirents` (`id`);
