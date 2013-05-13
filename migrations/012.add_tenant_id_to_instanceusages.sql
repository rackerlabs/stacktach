ALTER TABLE stacktach_instanceusage ADD `tenant` varchar(50);
CREATE INDEX `stacktach_instanceusage_987c9676` ON `stacktach_instanceusage` (`tenant`);
