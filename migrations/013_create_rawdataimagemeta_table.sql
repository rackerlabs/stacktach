CREATE TABLE `stacktach_rawdataimagemeta` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `raw_id` integer NOT NULL,
    `os_architecture` varchar(50),
    `os_distro` varchar(50),
    `os_version` varchar(50),
    `rax_options` varchar(50)
);
ALTER TABLE `stacktach_rawdataimagemeta` ADD CONSTRAINT `raw_id_refs_id_97b56a49` FOREIGN KEY (`raw_id`) REFERENCES `stacktach_rawdata` (`id`);
CREATE INDEX `stacktach_rawdataimagemeta_fbc597a7` ON `stacktach_rawdataimagemeta` (`raw_id`);
