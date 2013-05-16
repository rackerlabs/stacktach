ALTER TABLE stacktach_instanceexists ADD `tenant` varchar(50);
CREATE INDEX `stacktach_instanceexists_988c9678` ON `stacktach_instanceexists` (`tenant`);
