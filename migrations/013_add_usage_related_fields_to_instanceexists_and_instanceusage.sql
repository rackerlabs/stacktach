ALTER TABLE stacktach_instanceexists ADD `os_architecture` varchar(50);
ALTER TABLE stacktach_instanceexists ADD `os_distro` varchar(50);
ALTER TABLE stacktach_instanceexists ADD `os_version` varchar(50);
ALTER TABLE stacktach_instanceexists ADD `rax_options` varchar(50);

ALTER TABLE stacktach_instanceusage ADD `os_architecture` varchar(50);
ALTER TABLE stacktach_instanceusage ADD `os_distro` varchar(50);
ALTER TABLE stacktach_instanceusage ADD `os_version` varchar(50);
ALTER TABLE stacktach_instanceusage ADD `rax_options` varchar(50);
