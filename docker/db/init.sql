-- MySQL dump 10.13  Distrib 8.0.34, for Win64 (x86_64)
--
-- Host: mysql-367e2d56-mohamed311-06d1.f.aivencloud.com    Database: defaultdb
-- ------------------------------------------------------
-- Server version	8.0.35

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

-- Ensure user exists with correct host
CREATE USER IF NOT EXISTS 'sfcollab'@'%' IDENTIFIED BY 'sfcollab_pass';

-- Always reset privileges
GRANT ALL PRIVILEGES ON sfcollab_db.* TO 'sfcollab'@'%';

FLUSH PRIVILEGES;

--
-- GTID state at the beginning of the backup 
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `email` varchar(255) NOT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `password` varchar(255) NOT NULL,
  `is_email_verified` tinyint(1) DEFAULT NULL,
  `last_login` datetime DEFAULT NULL,
  `last_seen` datetime DEFAULT NULL,
  `last_login_ip` varchar(45) DEFAULT NULL,
  `status` enum('active','deleted', 'banned') DEFAULT NULL,
  `role` enum('founder','contributor', 'influencer', 'content_creator', 'community_manager','hr_specialist','investor','advisor','mentor','partner','admin','moderator','member','technical_lead','engineering_manager','backend_engineer','frontend_engineer','fullstack_engineer','mobile_engineer','software_architect','qa_engineer','test_automation_engineer','devops_engineer','cloud_engineer','sre','infrastructure_engineer','platform_engineer','cybersecurity_engineer','data_scientist','data_engineer','machine_learning_engineer','ai_engineer','mlops_engineer','data_analyst','ai_researcher','product_manager','product_owner','ux_designer','ui_designer','product_designer','ux_researcher','growth_engineer','growth_marketer','seo_specialist','content_strategist') DEFAULT NULL,
  `builder_plan_id` VARCHAR(255) DEFAULT NULL,
  `founder_plan_id` VARCHAR(255) DEFAULT NULL,
  `credits` int DEFAULT 0,
  `xp_points` int DEFAULT NULL,
  `streak_days` int DEFAULT NULL,
  `last_activity_date` date DEFAULT NULL,
  `total_revenue` float DEFAULT NULL,
  `satisfaction_percentage` float DEFAULT NULL,
  `active_startups_count` int DEFAULT NULL,
  `profile_picture` varchar(500) DEFAULT NULL,
  `profile_bio` text,
  `profile_company` varchar(255) DEFAULT NULL,
  `profile_social_links` json DEFAULT NULL,
  `profile_country` varchar(100) DEFAULT NULL,
  `profile_city` varchar(100) DEFAULT NULL,
  `profile_timezone` varchar(50) DEFAULT NULL,
  `pref_email_notifications` tinyint(1) DEFAULT NULL,
  `pref_push_notifications` tinyint(1) DEFAULT NULL,
  `pref_privacy` enum('public','private') DEFAULT NULL,
  `pref_language` varchar(10) DEFAULT NULL,
  `pref_timezone` varchar(50) DEFAULT NULL,
  `pref_theme` enum('light','dark') DEFAULT NULL,
  `pref_builder_preferences` varchar(50) DEFAULT NULL,
  `notif_new_comments` tinyint(1) DEFAULT NULL,
  `notif_new_likes` tinyint(1) DEFAULT NULL,
  `notif_new_suggestions` tinyint(1) DEFAULT NULL,
  `notif_join_requests` tinyint(1) DEFAULT NULL,
  `notif_approvals` tinyint(1) DEFAULT NULL,
  `notif_story_views` tinyint(1) DEFAULT NULL,
  `notif_post_engagement` tinyint(1) DEFAULT NULL,
  `notif_email_digest` enum('daily','weekly','monthly') DEFAULT NULL,
  `notif_quiet_hours_enabled` tinyint(1) DEFAULT NULL,
  `notif_quiet_hours_start` varchar(5) DEFAULT NULL,
  `notif_quiet_hours_end` varchar(5) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `storage_used_mb` float NOT NULL DEFAULT 0.0,
  
  PRIMARY KEY (`id`),

  UNIQUE KEY `ix_users_email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=119 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--


LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
-- INSERT INTO `users` VALUES (119,'Fatima','Abba','abbazarah@gmail.com','++2349027715996','scrypt:32768:8:1$4hjJkbyjmXCucon2$6b7f5be64eb418240d88fdd72aac6b08764ca0afe730623a4ab5af20813d17d3cece672e2b097cd178cdbf3d4b17e54b8c2b14fcbd029016f5cf58024ef7b424',1,'2026-01-14 20:30:18','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'/uploads/20260113_144336_119_cbda08fd2a28df5adc317626622060a3.jpg',NULL,NULL,'{}','Nigeria','Yola',NULL,1,1,'public','en','Africa/Lagos','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 10:51:19','2026-01-14 20:30:18'),(120,'Oskar','Oskar','oskarrro777@gmail.com','++48507351830','scrypt:32768:8:1$RmfUsMGuq3rLMACw$41283c0256be02225775190b014abf76d2f41b86e3c3723a56b840c012794574ca6323c722c7c2e21d67ab35ffd371b1083fc5bba39cafdefa31e6367c2176c7',1,'2026-01-14 15:50:42','active','admin',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocK8xcYC3FE4iyrYTx5LdbVNYUpYuJc3ijkknGYUUus2vKFOHF0=s96-c',NULL,NULL,'{}','Poland','Bochnia',NULL,1,1,'public','en','Europe/Warsaw','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 11:15:41','2026-01-14 15:50:42'),(121,'Chinmaya','Bharadwaj H S','chinmayabharadwajhs@gmail.com','+9194875483','scrypt:32768:8:1$CKwILr17Ji0vIv51$1fef75bb0140652d26933603edef7207d0b8999d98172e8e86e6577fd2362a4c22c898c095db9d5bfdab1ff942034ff7061a3bd3b95de88014b2490c8c30bbed',1,'2026-01-14 17:16:51','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocLvo1crlc_PxQfsYoFkyC77XgYmfoQOcQeyR5PjAj3NZKsP0Q=s96-c',NULL,NULL,'{}','India','Mangaluru',NULL,1,1,'public','en','Asia/Calcutta','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 12:08:43','2026-01-14 17:16:51'),(122,'Oskar','','oskarrro7777@gmail.com','+485073518300','scrypt:32768:8:1$iP38hKBRqMzfrEHe$a74ebc6f369e5aabd97f10abc08f255fef6b773e5150ea978940333d4f7a4efc04d201683daea8145e8f35b5723775a4082a441bf88873e0030e532ef45c70fc',1,'2026-01-13 12:57:28','active','admin',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocL3rDjPBcXnv2HB1AjOzmryAhi4OzlS1c4vGrA33C9ywrSgRw=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 12:57:28','2026-01-13 12:57:47'),(123,'Krystian','Śledziewski','krystian09536@gmail.com','++48690 518 727','scrypt:32768:8:1$zKkSHv1VSzL73FcW$f78f712221113e0e36341a0d79bee780b01ed5084c5032756747c11dc7eeee007390506f9240508787ffa89e057b2ebe00eb0470b33cc045c72e2b05ee3b322a',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 12:57:50','2026-01-13 12:58:46'),(124,'YASH','BHATNAGAR','yb99.official@gmail.com','++918178484774','scrypt:32768:8:1$6NFqNFVqVszOc4OR$0bfc39e7f60f57a45767f8ba35d97325e01e03373b2047f42b4b3797a0bb57c6d87f4367bd5e655c2f3a944d4c3c8b34906d121fde9314ab3e5c3420f3a234aa',1,'2026-01-13 13:09:18','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocLuTzxIAmVLBkggSTO4bLjmC1ImyfnwxtFh0kfKlYJj2VLSXg=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:09:18','2026-01-13 13:10:21'),(125,'Sanskriti','Dhakad','dhakadsanskriti28@gmail.com',NULL,'scrypt:32768:8:1$m4nlhlHVhtrT7ypx$66e648ab64f3d20f5964dd4101b9bd5a54fa58dae4e0e616bf6795a941b50999d2573c97e372ac8c7676b998061e0d900eade6f274cb313564184123daf4370e',1,'2026-01-13 13:10:12','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocL92MdEUpbzW7d8FxV1Kxl9e1GwSdhQfgEqn7kttrMvXEvVH-0z5g=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:10:12','2026-01-13 13:10:12'),(126,'ayush','gupta','ayush160998@gmail.com',NULL,'scrypt:32768:8:1$C0RrB1e3egVnLpUN$9985bbd06c04cd74f31a777582a65f3eeddda1f8fd123741ec569d1be48456e9d88bd315718193dc24378f31fbf3303d5f7a8471d1f82c56066013ec7dd6608e',1,'2026-01-13 13:25:07','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocKuWhpqKCMQIFzZHiVEX8YkYhx0MQHUcyQ-eRab_neXHIiEtg=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:25:07','2026-01-13 13:25:07'),(127,'ayush','Gupta','ayush199816@gmail.com','++917409726481','scrypt:32768:8:1$T2Cwp1HXijKYwcm0$77560746c2da357198da460c29f0220cd6b551d22b33c07ce5ea123fa55b5ac9c8086d5608e70bcb8a773cb19e404e22e10a4572fe009eb781784e3777c0fe96',1,'2026-01-13 15:53:54','active','admin',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocJPm46M7yFLVX8F8RcgiJ_4PAuexyNjOtdRDP5N43MT_tPb-VwO=s96-c',NULL,NULL,'{}','India','Bareilly',NULL,1,1,'public','en','Asia/Calcutta','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:27:29','2026-01-13 15:53:54'),(128,'Ayush','Gupta','ayush16098@gmail.com',NULL,'scrypt:32768:8:1$EyZl3Og5lXsvNjpI$b15646f0dc47fecd1c6be1aa5169b5cc5a5d4232e1d4c92f8930e8660a1c7095965188d66e3a3c0ace8370a38a61432551eef3b7c2a12f0ef0b2ea7eb6e844ee',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:30:03','2026-01-13 13:30:03'),(129,'Ayush','Gupta','itsayushonly@gmail.com',NULL,'scrypt:32768:8:1$8imiDEKpvMpAZ37p$99e01cfce0a11f91345f072fcd95d1cd79de0d7c07aebb0c105b0e0d685f45f5dca2d595c805a56f7207c35e8f7dd7d105905cc96b12d5a441621d9c30895a23',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:30:37','2026-01-13 13:30:37'),(130,'Laurie','Breton','lauriebreton6@gmail.com',NULL,'scrypt:32768:8:1$PceVPBwkhsNpPCS1$154c71ac4e6137a96ddff37a6d0e56768693c560387710f3376483d6d58410d3b7548d7b8dfac467fc1249b3441031eef03b51fd6786f8727299e1f191a8f1fa',1,'2026-01-13 13:36:55','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocJWlyzOCacqLsg6wQtKA-sV-Z9sWKFQtzlCIX6AZW-TTGrRpIiD=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:36:55','2026-01-13 13:36:55'),(131,'Ivan','Gomez','ivandavidgomezsilva@gmail.com','+573024690359','scrypt:32768:8:1$3SwQjtEjsWynJOiW$98239287f43915ee55cf48ea0082401b99118002434b35101ac55b7b995f636401e4e4af21bf0505e9a6a8ef6269729d3ce55c6cf6dc5b00fc2b3c7cfb9a578a',1,'2026-01-14 08:25:22','active','admin',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocLrIBUYVi0eJaYHI_MoIxv-h1LnvLbJ5Z7yZizPC4FCJXUHXqE=s96-c','',NULL,'{}','Colombia','Floridablanca',NULL,1,1,'public','en','America/Bogota','light','marketing',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 13:47:59','2026-01-14 08:25:22'),(132,'NANDAN','SHETTY','nandansshetty456@gmail.com','++919988989898','scrypt:32768:8:1$vdcLdP8g859CBB1g$58bbac2ffac97456663bae8c00755c40b9b5b4b8fd23a5a3a1a43f4f0ab25e292a7a00e1cd41795e64b9ee12ab886cd87455c8518cc7dceca2a857a9132e56fa',1,'2026-01-14 05:02:13','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocIf7AsUjULEuzR1c8CSltAO9LH7gxkEV62ByRGwQwVpYVomtQ=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 14:11:46','2026-01-14 05:02:13'),(133,'Bardawal','Parshuram','bardawalparshuram7@gmail.com','++919949540729','scrypt:32768:8:1$gYsEFhGF70YnNxWL$c0d7164d0a44c451f819b34d96dc20c53f495ca859b931dc62506fe7d0fa05cdf6f2af72fea439768276d46a75eb83edb90edafe89be80f91973f1fa389325ff',1,'2026-01-13 14:34:12','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocL58PdAvqTKDXRjbC79kzEecxK84laezM5yiNysU_Er8FRoVGY=s96-c',NULL,'Codetech IT Solutions','{}','India','Hyderabad, Telangana',NULL,1,1,'public','en','Indian/Chagos','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 14:34:12','2026-01-13 14:44:09'),(134,'Ivan','Marcos','info@meridianlib.com',NULL,'scrypt:32768:8:1$jmXQPMtM85hLPcsx$cb0ac01327a9d9db24023954e351c047bf53ceb04fbf4bc95761d0f257d0b7f8d182fb24c2cb492429f0aee9a906e45351854d84a3e19ef0434a7afc42cf9234',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 14:34:41','2026-01-13 14:34:41'),(135,'Laurie','Breton','laurieetc@gmail.com',NULL,'scrypt:32768:8:1$11ZjjHtP4l86B5En$676c62b84560045d8e5af9997aa27060c7ff7bfafc0a1b6eb7594bd7381c81b8cc740048ea48504c596a33d249947c4d79bc786dff331c52efb6b54ff37fed66',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 14:58:21','2026-01-13 14:58:21'),(136,'Ivan','Gomez','ivandavidgomezsilva@atmail.com',NULL,'scrypt:32768:8:1$y5gilOLrZt7LirsI$e71ccea527d98fbc9437ecff52d879526384f417eacc7721f7ef8d4a73aba31bbf7ba4de0885b982968fb70a6f15fcf379694404d545a70fb6537271fd2b9a00',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 16:07:08','2026-01-13 16:07:08'),(137,'Laurie','Breton','lauriebreton2005@icloud.com',NULL,'scrypt:32768:8:1$v2t2fCeuojhB6GTa$4bbed271ccfd165d1408414f5fb6d0b653bb018f01236fca0cf97c304a1f87b5b371e54767289cd16612054604947c13a96a0d8bf9fd11dbf37888709f2acd7c',0,'2026-01-13 16:30:40','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'/uploads/20260113_170355_137_IMG_9667.jpeg','wakjsnefk',NULL,'{\"linkedin\": \"https://www.linkedin.com/in/laurie-breton-567694353/\", \"instagram\": \"https://www.instagram.com/laurie._.bee/\"}','Canada','Montreal',NULL,1,1,'public','en','America/Toronto','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 16:21:10','2026-01-13 17:44:22'),(138,'vishnu','teja','vishnuteja7055@gmail.com','++919346687054','scrypt:32768:8:1$pPaPZCzUp4HJTVfQ$db788771db3b18794889904f6ac7b0c5cb0e265b1f1499d71dcd5f714898e60fb03dcd44460469e3474a35a321c19d13c238ffc40deceac7feb4d1215d9791b7',1,'2026-01-13 16:24:23','active','member',NULL,0,0,0,'2026-01-13',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocLL6gpnyGLA5IhDovcV3A6Z2lG35_7sbZcDlqkcRov6mN-vrw=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 16:23:15','2026-01-13 16:25:28'),(139,'Ivan','Gomez','i.gomezs2@uniandes.edu.co','+573024690358','scrypt:32768:8:1$WVngtiFsJcAzT9R7$d96e73003fe746ba1f430a6fec7f501391c3e8c5b72571248d9e8be8e60c1c8c8af24b7c88d8761787c9bd2f8d82574512d253efd4c5796b579d68600d4f457c',0,'2026-01-13 20:10:09','active','member',NULL,0,0,0,'2026-01-13',0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 16:24:16','2026-01-13 20:12:22'),(140,'Ivan','Marcos','info@meeridianlib.com',NULL,'scrypt:32768:8:1$oe8KR9d7ahskhAHW$205d400fa036c09f7c71a6404653d4779b6697a15a59e6f6c84ec69384992b8ac3b52fcaeb0f30afd73b741bb176633447ae001e26a13a8b0da3dd7b45831685',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-13 20:09:39','2026-01-13 20:09:39'),(141,'sdgfdfs','dsad','oskarkonstanciakpl@hotmail.com','++485073518300','scrypt:32768:8:1$b4xazf596zgZIUq0$b06701cbe3a3df2a903878113fe898a081f50ed0302957fd5fa46c952ecdf1659aa121895622093670b96574b4af77e8abac1df6b5030429aaf5898807f40dc7',0,'2026-01-14 16:40:54','active','member',NULL,0,0,0,'2026-01-14',0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 00:43:48','2026-01-14 16:40:54'),(142,'Srinilaa','Panneer Selvam ','psmn2013@gmail.com','++919345224499','scrypt:32768:8:1$WmnLj49OG20FRNd2$abaa773391012c946951e94f671d7c45c3178c4c79a8bed8f7449276776cefb5f04296b8f4770becf9cda230aae7cdc36771cf8aa48efe8146f30b2fc29ea50b',0,NULL,'active','member',NULL,0,0,0,NULL,0,100,0,NULL,NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 01:41:18','2026-01-14 01:42:44'),(143,'Thinura','Vithanage','thinu7007@gmail.com',NULL,'scrypt:32768:8:1$Eip6A6IZW5I5Lchm$7c4882187e1b3df0934a74e3d96305c85d1fd219926e46a7e5cfc466abaefcdd8df5909f8ae5e7c05a113434894e9adf7bf3c7a255465e97a22c04a340a2bb12',1,'2026-01-14 03:06:55','active','member',NULL,0,0,0,'2026-01-14',0,100,0,NULL,'Founder @ Aviyora | Building the system that helps Great, US SaaS startups reach their true potential ','Aviyora','{\"twitter\": \"https://x.com/thinuvc?s=21\", \"linkedin\": \"https://www.linkedin.com/in/thinura-vithanage?utm_source=share&utm_campaign=share_via&utm_content=profile&utm_medium=ios_app\"}','United States','San Francisco ',NULL,1,1,'public','en','America/Los_Angeles','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 03:06:55','2026-01-14 03:16:10'),(144,'Hans','Nduwabike','hansnduwabike@gmail.com',NULL,'scrypt:32768:8:1$rEvW2NmI0fBB3Ins$b74ccf2e2182420b8ad6dc6278661838540b2e4b69150f31b3504cb834aef2f0d59657b96053af5a64c736152c1093646224562e1233f71c1a7f419f703b8310',1,'2026-01-14 03:44:35','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocIdNP7H03-bBVVE2G_VGn66JBstOWTyS0BWG7cDHBhH7bWRghs=s96-c',NULL,NULL,'{}','Canada','Montreal',NULL,1,1,'public','en','America/Toronto','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 03:44:35','2026-01-14 03:47:23'),(145,'Ivan','Gomez','ivandavidgomezsilva@hotmail.com',NULL,'scrypt:32768:8:1$r8DYSo77CX02XF4x$15da7cafd8bec78b5e751be6b34c91dc4be7d5bdfe8cb5e335dd7105bc1fd0a228ffb90c00bb8dd933a1a6f5b6a8557b1b40bbf74562f2b470f663a866d67736',1,'2026-01-14 08:25:29','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'https://avatars.githubusercontent.com/u/158605517?v=4',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 08:10:58','2026-01-14 08:25:29'),(146,'Krin','Gl','owlkoconut@gmail.com',NULL,'scrypt:32768:8:1$J0ARsvBSv2OUfF1b$e7986969023ebaef754ed09a369682f039682899df37f0784958e9c3925da9e78b331206ff73b713863aa09e46b4c369e3b2d9be4f4310f48b5692a3206b669a',1,'2026-01-14 20:53:43','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocLoTbecnJ_0w6_e4G7CEHnFmqaqjkOoVWGjsyT00svsMOHvH_hp=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 20:53:43','2026-01-14 20:53:43'),(147,'Sakif','Hussain','shachcha01@gmail.com','+8801781706940','scrypt:32768:8:1$sf9FFJrpYq2YX1lE$28e36445c84d8413d134cd06c1bf795ee89b2bfbec277245eabffae508f122cac10fb3290fe55363ded899c4fe86e80939e54646627a65fe0b44126ecb40fd67',1,'2026-01-14 21:22:32','active','member',NULL,0,0,0,'2026-01-14',0,100,0,'https://lh3.googleusercontent.com/a/ACg8ocJZL2FTB8Ic_Kci5TVRzUFtWjMEX0q2VqYP7QLELhPuYR8F3wJA=s96-c',NULL,NULL,'{}',NULL,NULL,NULL,1,1,'public','en','UTC','light','development',1,1,1,1,1,1,1,'weekly',0,'22:00','08:00','2026-01-14 21:22:32','2026-01-14 21:26:54');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;


CREATE TABLE `activities` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `action` varchar(255) NOT NULL,
  `details` text,
  `ip_address` varchar(45) DEFAULT NULL,
  `user_agent` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `action` (`action`),
  KEY `created_at` (`created_at`),
  CONSTRAINT `activities_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
--
-- Table structure for table `achievements`
--
DROP TABLE IF EXISTS `waitlist`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `waitlist` (
  `id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(255) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `last_activity_at` datetime DEFAULT NULL,
  `referral_points` int DEFAULT 0,
  `contribution_points` int DEFAULT 0,
  `activity_points` int DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  KEY `ix_email` (`email`),
  KEY `ix_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET character_set_client = @saved_cs_client */;
--
-- Dumping data for table `waitlist`
--


LOCK TABLES `waitlist` WRITE;


/*!40000 ALTER TABLE `waitlist` DISABLE KEYS */;
/*!40000 ALTER TABLE `waitlist` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `feedback`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `feedback` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `content` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `created_at` (`created_at`),
  CONSTRAINT `feedback_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `feedback` WRITE;
/*!40000 ALTER TABLE `feedback` DISABLE KEYS */;
/*!40000 ALTER TABLE `feedback` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `achievements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `achievements` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` text,
  `icon` varchar(100) DEFAULT NULL,
  `category` enum('task','social','learning','milestone') DEFAULT NULL,
  `points` int DEFAULT NULL,
  `requirement_type` varchar(50) DEFAULT NULL,
  `requirement_value` int DEFAULT NULL,
  `badge_color` varchar(20) DEFAULT NULL,
  `rarity` enum('common','rare','epic','legendary') DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=235 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `achievements`
--

LOCK TABLES `achievements` WRITE;
/*!40000 ALTER TABLE `achievements` DISABLE KEYS */;
-- INSERT INTO `achievements` VALUES (100,'First Idea','Create your first business idea','­ƒÆí','milestone',100,'ideas_created',1,NULL,'common',NULL),(101,'Idea Machine','Create 10 business ideas','­ƒÜÇ','milestone',500,'ideas_created',10,NULL,'rare',NULL),(102,'Idea Factory','Create 50 business ideas','­ƒÅ¡','milestone',1000,'ideas_created',50,NULL,'epic',NULL),(103,'Idea Visionary','Create 100 business ideas','­ƒö¡','milestone',2500,'ideas_created',100,NULL,'legendary',NULL),(104,'First Task','Complete your first task','Ôÿæ´©Å','milestone',50,'tasks_completed',1,NULL,'common',NULL),(105,'Task Master','Complete 50 tasks','Ô£à','milestone',300,'tasks_completed',50,NULL,'rare',NULL),(106,'Productivity Guru','Complete 200 tasks','ÔÜí','milestone',800,'tasks_completed',200,NULL,'epic',NULL),(107,'Task Titan','Complete 500 tasks','­ƒÅå','milestone',2000,'tasks_completed',500,NULL,'legendary',NULL),(108,'7-Day Streak','Maintain a 7-day activity streak','­ƒöÑ','milestone',150,'streak_days',7,NULL,'common',NULL),(109,'Month of Momentum','Maintain a 30-day activity streak','­ƒôà','milestone',500,'streak_days',30,NULL,'rare',NULL),(110,'Dedicated Developer','Maintain a 90-day activity streak','­ƒÆ¬','milestone',1500,'streak_days',90,NULL,'epic',NULL),(111,'Unstoppable Force','Maintain a 365-day activity streak','­ƒîƒ','milestone',5000,'streak_days',365,NULL,'legendary',NULL),(112,'First Comment','Make your first comment','­ƒÆ¼','social',50,'comments_made',1,NULL,'common',NULL),(113,'Comment Contributor','Make 25 comments on ideas','­ƒÆ¼','social',200,'comments_made',25,NULL,'common',NULL),(114,'Active Commenter','Make 100 comments','­ƒùú´©Å','social',500,'comments_made',100,NULL,'rare',NULL),(115,'Discussion Leader','Make 500 comments','­ƒææ','social',1200,'comments_made',500,NULL,'epic',NULL),(116,'First Like','Receive your first like','­ƒæì','social',25,'likes_received',1,NULL,'common',NULL),(117,'Popular Idea','Get 100 likes on your ideas','ÔØñ´©Å','social',400,'likes_received',100,NULL,'epic',NULL),(118,'Community Favorite','Get 500 likes on your ideas','Ô¡É','social',1000,'likes_received',500,NULL,'epic',NULL),(119,'Internet Sensation','Get 1000 likes on your ideas','­ƒîÉ','social',2500,'likes_received',1000,NULL,'legendary',NULL),(120,'First Follower','Gain your first follower','­ƒæÑ','social',100,'followers_gained',1,NULL,'common',NULL),(121,'Growing Audience','Gain 10 followers','­ƒôê','social',300,'followers_gained',10,NULL,'common',NULL),(122,'Influencer','Gain 50 followers','­ƒôó','social',800,'followers_gained',50,NULL,'rare',NULL),(123,'Thought Leader','Gain 200 followers','­ƒÄ»','social',2000,'followers_gained',200,NULL,'epic',NULL),(124,'Early Bird','Complete a task before its due date','­ƒÉª','task',75,'tasks_completed_early',1,NULL,'common',NULL),(125,'Time Manager','Complete 25 tasks early','ÔÅ░','task',400,'tasks_completed_early',25,NULL,'rare',NULL),(126,'Last Minute Hero','Complete a task on the due date','­ƒª©','task',50,'tasks_completed_on_time',1,NULL,'common',NULL),(127,'Perfect Timing','Complete 50 tasks on their due date','­ƒÄ»','task',600,'tasks_completed_on_time',50,NULL,'rare',NULL),(128,'Task Explorer','Create tasks in 5 different categories','­ƒº¡','task',200,'task_categories_used',5,NULL,'common',NULL),(129,'Organized Mind','Create tasks in 10 different categories','­ƒùé´©Å','task',500,'task_categories_used',10,NULL,'rare',NULL),(130,'Detailed Thinker','Create an idea with 500+ characters','­ƒôØ','',150,'detailed_ideas',1,NULL,'common',NULL),(131,'Thorough Planner','Create 10 detailed ideas','­ƒôï','',600,'detailed_ideas',10,NULL,'rare',NULL),(132,'Idea Architect','Create an idea with attached documents','­ƒÅù´©Å','',200,'ideas_with_attachments',1,NULL,'common',NULL),(133,'Resourceful Creator','Create 20 ideas with attachments','­ƒôÄ','',800,'ideas_with_attachments',20,NULL,'rare',NULL),(134,'Team Player','Collaborate on 5 different ideas','­ƒñØ','',300,'ideas_collaborated',5,NULL,'common',NULL),(135,'Idea Partner','Collaborate on 20 different ideas','­ƒæÑ','',800,'ideas_collaborated',20,NULL,'rare',NULL),(136,'Master Collaborator','Collaborate on 50 different ideas','­ƒîƒ','',2000,'ideas_collaborated',50,NULL,'epic',NULL),(137,'Helpful Mentor','Get 10 helpful votes on your comments','­ƒÆí','',400,'helpful_votes_received',10,NULL,'rare',NULL),(138,'Weekend Warrior','Complete tasks on 5 different weekends','­ƒÄ¬','',300,'weekend_activities',5,NULL,'rare',NULL),(139,'Night Owl','Create ideas between 10 PM and 2 AM','­ƒªë','',250,'late_night_activities',5,NULL,'rare',NULL),(140,'Early Riser','Create ideas between 5 AM and 8 AM','­ƒîà','',250,'early_morning_activities',5,NULL,'rare',NULL),(141,'Platform Explorer','Use all major platform features','­ƒº®','',400,'features_used',10,NULL,'rare',NULL),(142,'Power User','Use platform for 30 consecutive days','ÔÜí','',600,'consecutive_days_used',30,NULL,'epic',NULL),(143,'Platform Veteran','Use platform for 180 days total','­ƒøí´©Å','',1500,'total_days_used',180,NULL,'epic',NULL),(144,'Creative Spark','Create ideas in 3 different categories','­ƒÄ¿','',200,'idea_categories_used',3,NULL,'common',NULL),(145,'Diverse Thinker','Create ideas in 10 different categories','­ƒîê','',700,'idea_categories_used',10,NULL,'rare',NULL),(146,'Innovation Master','Create ideas in 20 different categories','­ƒÆÄ','',1500,'idea_categories_used',20,NULL,'epic',NULL),(147,'First Share','Share your first idea externally','­ƒôñ','social',100,'ideas_shared',1,NULL,'common',NULL),(148,'Social Butterfly','Share 25 ideas externally','­ƒªï','social',500,'ideas_shared',25,NULL,'rare',NULL),(149,'Bookworm','Read 50 idea descriptions completely','­ƒôÜ','',300,'ideas_read_completely',50,NULL,'common',NULL),(150,'Knowledge Seeker','Read 200 idea descriptions completely','­ƒöì','',800,'ideas_read_completely',200,NULL,'rare',NULL),(151,'Feedback Provider','Give feedback on 10 different ideas','­ƒôØ','',400,'feedbacks_given',10,NULL,'common',NULL),(152,'Constructive Critic','Give feedback on 50 different ideas','­ƒÅù´©Å','',1000,'feedbacks_given',50,NULL,'rare',NULL),(153,'Idea Refiner','Update and improve 10 existing ideas','Ô£¿','',500,'ideas_improved',10,NULL,'rare',NULL),(154,'Perfectionist','Update and improve 50 existing ideas','­ƒÄ¡','',1200,'ideas_improved',50,NULL,'epic',NULL),(155,'Mobile User','Use the platform on mobile device','­ƒô▒','',100,'mobile_sessions',1,NULL,'common',NULL),(156,'On-the-Go','Use platform on mobile 50 times','­ƒÜÂ','',400,'mobile_sessions',50,NULL,'rare',NULL),(157,'Desktop Commander','Use platform on desktop 100 times','­ƒÆ╗','',500,'desktop_sessions',100,NULL,'rare',NULL),(158,'Multi-Platform','Use platform on 3 different devices','­ƒöä','',300,'devices_used',3,NULL,'common',NULL),(159,'Seasoned Veteran','Use platform for 1 year','­ƒÄé','milestone',1000,'account_age_days',365,NULL,'epic',NULL),(160,'Long-term Visionary','Use platform for 2 years','Ôîø','milestone',2500,'account_age_days',730,NULL,'legendary',NULL),(161,'Idea Collector','Save 20 ideas to your favorites','Ô¡É','',300,'ideas_saved',20,NULL,'common',NULL),(162,'Curator','Save 100 ideas to your favorites','­ƒÅø´©Å','',800,'ideas_saved',100,NULL,'rare',NULL),(163,'Archivist','Save 500 ideas to your favorites','­ƒôÜ','',2000,'ideas_saved',500,NULL,'epic',NULL),(164,'Tag Master','Use 50 different tags on ideas','­ƒÅÀ´©Å','',400,'unique_tags_used',50,NULL,'rare',NULL),(165,'Organized Mind','Create 10 custom categories','­ƒùâ´©Å','',500,'custom_categories_created',10,NULL,'rare',NULL),(166,'Template Creator','Create 5 idea templates','­ƒôä','',600,'templates_created',5,NULL,'epic',NULL),(167,'Quick Draw','Complete a task within 1 hour of creating it','ÔÜí','task',150,'quick_tasks_completed',1,NULL,'common',NULL),(168,'Speed Demon','Complete 20 tasks within 1 hour','­ƒÄ»','task',600,'quick_tasks_completed',20,NULL,'rare',NULL),(169,'Weekly Regular','Use platform 4 weeks in a row','­ƒôå','',300,'consecutive_weeks',4,NULL,'common',NULL),(170,'Monthly Champion','Use platform 6 months in a row','­ƒÅà','',1000,'consecutive_months',6,NULL,'epic',NULL),(171,'Welcome Committee','Welcome 10 new users','­ƒæï','',400,'new_users_welcomed',10,NULL,'rare',NULL),(172,'Community Builder','Welcome 50 new users','­ƒÅÿ´©Å','',1200,'new_users_welcomed',50,NULL,'epic',NULL),(173,'Quick Learner','Complete the platform tutorial','­ƒÄô','learning',200,'tutorial_completed',1,NULL,'common',NULL),(174,'Feature Expert','Use all advanced features','­ƒºá','learning',800,'advanced_features_used',10,NULL,'epic',NULL),(175,'New Year Innovator','Create an idea on January 1st','­ƒÄå','',250,'new_years_idea',1,NULL,'rare',NULL),(176,'Summer Thinker','Create ideas during summer months','ÔÿÇ´©Å','',300,'summer_ideas',5,NULL,'common',NULL),(177,'Challenge Accepted','Participate in your first challenge','­ƒÄ¬','',200,'challenges_participated',1,NULL,'common',NULL),(178,'Challenge Champion','Win 5 challenges','­ƒÅå','',1500,'challenges_won',5,NULL,'epic',NULL),(179,'Level Up','Reach level 10','Ô¼å´©Å','',500,'user_level',10,NULL,'common',NULL),(180,'Master Level','Reach level 50','­ƒÄ»','',2000,'user_level',50,NULL,'epic',NULL),(181,'Achievement Hunter','Earn 50 different achievements','­ƒÅ╣','',1000,'achievements_earned',50,NULL,'rare',NULL),(182,'Completionist','Earn 100 different achievements','­ƒÆ»','',3000,'achievements_earned',100,NULL,'legendary',NULL),(183,'First Project','Create your first project','­ƒôü','milestone',150,'projects_created',1,NULL,'common',NULL),(184,'Project Manager','Create 10 projects','­ƒæ¿ÔÇì­ƒÆ╝','milestone',600,'projects_created',10,NULL,'rare',NULL),(185,'Portfolio Builder','Create 25 projects','­ƒÆ╝','milestone',1200,'projects_created',25,NULL,'epic',NULL),(186,'Enterprise Architect','Create 50 projects','­ƒÅó','milestone',2500,'projects_created',50,NULL,'legendary',NULL),(187,'Task Streak','Complete tasks for 7 days straight','­ƒôè','task',400,'task_streak_days',7,NULL,'rare',NULL),(188,'Task Marathon','Complete tasks for 30 days straight','­ƒÅâ','task',1000,'task_streak_days',30,NULL,'epic',NULL),(189,'Priority Handler','Complete 20 high priority tasks','­ƒö┤','task',500,'high_priority_tasks',20,NULL,'rare',NULL),(190,'Urgent Expert','Complete 50 urgent tasks','­ƒÜ¿','task',1200,'urgent_tasks',50,NULL,'epic',NULL),(191,'Like Giver','Like 50 different ideas','­ƒæì','social',300,'likes_given',50,NULL,'common',NULL),(192,'Supportive Member','Like 200 different ideas','­ƒÆØ','social',800,'likes_given',200,NULL,'rare',NULL),(193,'Community Pillar','Like 500 different ideas','­ƒÅø´©Å','social',1500,'likes_given',500,NULL,'epic',NULL),(194,'Following Active','Follow 20 other users','­ƒæÇ','social',300,'users_followed',20,NULL,'common',NULL),(195,'Network Builder','Follow 50 other users','­ƒò©´©Å','social',700,'users_followed',50,NULL,'rare',NULL),(196,'Well Structured','Create idea with multiple sections','­ƒôæ','',200,'structured_ideas',1,NULL,'common',NULL),(197,'Detailed Planner','Create 15 well-structured ideas','­ƒôï','',600,'structured_ideas',15,NULL,'rare',NULL),(198,'Research Expert','Add research to 10 ideas','­ƒö¼','',800,'researched_ideas',10,NULL,'epic',NULL),(199,'Market Analyst','Conduct market research for 5 ideas','­ƒôè','',1000,'market_researched_ideas',5,NULL,'epic',NULL),(200,'Team Builder','Invite 5 users to collaborate','­ƒæÑ','',400,'collaborators_invited',5,NULL,'common',NULL),(201,'Collaboration Champion','Invite 20 users to collaborate','­ƒñØ','',1000,'collaborators_invited',20,NULL,'rare',NULL),(202,'Feedback Receiver','Receive feedback on 10 ideas','­ƒôÑ','',300,'feedbacks_received',10,NULL,'common',NULL),(203,'Open to Feedback','Receive feedback on 50 ideas','­ƒÄü','',800,'feedbacks_received',50,NULL,'rare',NULL),(204,'Settings Explorer','Customize your profile settings','ÔÜÖ´©Å','',100,'settings_customized',1,NULL,'common',NULL),(205,'Profile Perfect','Complete your profile 100%','­ƒæñ','',300,'profile_completed',1,NULL,'common',NULL),(206,'Notification Master','Configure all notification settings','­ƒöö','',200,'notifications_configured',1,NULL,'common',NULL),(207,'Theme Customizer','Change your theme','­ƒÄ¿','',150,'theme_changed',1,NULL,'common',NULL),(208,'Brainstormer','Create 5 ideas in one day','­ƒî¬´©Å','',400,'ideas_in_one_day',5,NULL,'rare',NULL),(209,'Idea Storm','Create 10 ideas in one day','Ôøê´©Å','',1000,'ideas_in_one_day',10,NULL,'epic',NULL),(210,'Creative Flow','Create ideas for 5 days straight','­ƒîè','',600,'creative_streak_days',5,NULL,'rare',NULL),(211,'Inspiration Wave','Create ideas for 14 days straight','­ƒîÇ','',1500,'creative_streak_days',14,NULL,'epic',NULL),(212,'Category Expert','Use 10 different categories','­ƒôé','',400,'categories_used',10,NULL,'common',NULL),(213,'Tag Innovator','Create 10 custom tags','­ƒÅÀ´©Å','',300,'custom_tags_created',10,NULL,'common',NULL),(214,'Folder Organizer','Organize ideas into folders','­ƒôü','',200,'folders_created',1,NULL,'common',NULL),(215,'System Architect','Create complex organization system','­ƒÅù´©Å','',800,'organization_systems',1,NULL,'epic',NULL),(216,'Daily Visitor','Visit platform for 10 consecutive days','­ƒôà','',300,'consecutive_visits',10,NULL,'common',NULL),(217,'Loyal User','Visit platform for 30 consecutive days','­ƒÆØ','',800,'consecutive_visits',30,NULL,'rare',NULL),(218,'Platform Advocate','Refer 5 friends to the platform','­ƒôó','',500,'friends_referred',5,NULL,'rare',NULL),(219,'Community Ambassador','Refer 20 friends to the platform','­ƒÄô','',1500,'friends_referred',20,NULL,'epic',NULL),(220,'Holiday Creator','Create idea on a holiday','­ƒÄä','',300,'holiday_ideas',1,NULL,'rare',NULL),(221,'Birthday Idea','Create idea on your birthday','­ƒÄé','',400,'birthday_ideas',1,NULL,'rare',NULL),(222,'Anniversary User','Use platform on account anniversary','­ƒÄë','',500,'anniversary_activities',1,NULL,'epic',NULL),(223,'Challenge Regular','Participate in 10 challenges','­ƒÄ¬','',600,'challenges_participated',10,NULL,'rare',NULL),(224,'Challenge Expert','Participate in 25 challenges','­ƒÅà','',1200,'challenges_participated',25,NULL,'epic',NULL),(225,'Top Performer','Finish in top 3 of a challenge','­ƒÑç','',800,'top_3_finishes',1,NULL,'epic',NULL),(226,'Challenge Dominator','Finish in top 3 of 10 challenges','­ƒææ','',2500,'top_3_finishes',10,NULL,'legendary',NULL),(227,'Rising Star','Reach level 5','Ô¡É','',200,'user_level',5,NULL,'common',NULL),(228,'Experienced User','Reach level 20','­ƒÄ»','',800,'user_level',20,NULL,'rare',NULL),(229,'Veteran User','Reach level 75','­ƒøí´©Å','',3000,'user_level',75,NULL,'legendary',NULL),(230,'Max Level','Reach maximum level','­ƒÅö´©Å','',5000,'user_level',100,NULL,'legendary',NULL),(231,'Trophy Collector','Earn 10 rare achievements','­ƒÅå','',800,'rare_achievements',10,NULL,'rare',NULL),(232,'Epic Collector','Earn 5 epic achievements','­ƒÆÄ','',1200,'epic_achievements',5,NULL,'epic',NULL),(233,'Legendary Collector','Earn 3 legendary achievements','­ƒîƒ','',2000,'legendary_achievements',3,NULL,'legendary',NULL),(234,'Achievement Master','Earn all common achievements','­ƒÄô','',1500,'common_achievements_all',1,NULL,'epic',NULL);
/*!40000 ALTER TABLE `achievements` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alembic_version`
--

LOCK TABLES `alembic_version` WRITE;
/*!40000 ALTER TABLE `alembic_version` DISABLE KEYS */;
INSERT INTO `alembic_version` VALUES ('ee78359866cc');
/*!40000 ALTER TABLE `alembic_version` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `calendar_events`
--

DROP TABLE IF EXISTS `calendar_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `calendar_events` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `startup_id` int DEFAULT NULL,
  `title` varchar(255) NOT NULL,
  `description` text,
  `start_date` datetime NOT NULL,
  `end_date` datetime DEFAULT NULL,
  `all_day` tinyint(1) DEFAULT NULL,
  `link` text,
  `category` enum('meeting','deadline','reminder','event') DEFAULT NULL,
  `color` varchar(20) DEFAULT NULL,
  `location` varchar(255) DEFAULT NULL,
  `is_recurring` tinyint(1) DEFAULT NULL,
  `visible_by` varchar(255) DEFAULT NULL,
  `recurrence_rule` varchar(255) DEFAULT NULL,
  `reminder_minutes` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `calendar_events_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`),
  CONSTRAINT `calendar_events_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `calendar_events`
--

LOCK TABLES `calendar_events` WRITE;
/*!40000 ALTER TABLE `calendar_events` DISABLE KEYS */;
--INSERT INTO `calendar_events` VALUES (1,104,24,'Weekly Team Sync','Weekly team meeting to discuss progress, blockers, and priorities for the upcoming week.','2025-11-10 10:00:00','2025-11-10 11:00:00',0,'meeting','#3B82F6','Zoom: https://zoom.us/j/123456789',1,'FREQ=WEEKLY;BYDAY=MO',15,'2025-11-01 17:20:56','2025-11-01 17:20:56'),(2,104,24,'Investor Pitch Practice','Practice session for upcoming investor pitch. Focus on demo flow and Q&A.','2025-11-17 14:00:00','2025-11-17 16:00:00',0,'meeting','#8B5CF6','Conference Room A',0,NULL,30,'2025-11-06 17:20:56','2025-11-06 17:20:56'),(3,104,24,'Beta Launch Deadline','Soft launch of beta version to first 100 users.','2025-11-24 00:00:00',NULL,1,'deadline','#EF4444',NULL,0,NULL,60,'2025-11-11 17:20:56','2025-11-26 17:20:56'),(4,104,24,'Tech Innovation Summit','Annual tech conference. Network with potential partners and investors.','2025-12-06 09:00:00','2025-12-06 18:00:00',0,'event','#10B981','Convention Center, Main Hall',0,NULL,60,'2025-11-16 17:20:56','2025-12-01 17:20:56'),(5,104,24,'Co-founder Sync','Weekly sync with co-founder to discuss strategy and operational items.','2025-11-17 16:00:00','2025-11-17 17:00:00',0,'meeting','#F59E0B','Co-working Space',1,'FREQ=WEEKLY;BYDAY=WE',10,'2025-11-03 17:20:56','2025-11-03 17:20:56'),(6,104,24,'Customer Feedback Session','User testing session with 5 beta customers to gather feedback on new features.','2025-12-03 13:00:00','2025-12-03 15:00:00',0,'meeting','#06B6D4','User Testing Lab',0,NULL,15,'2025-11-21 17:20:56','2025-11-29 17:20:56'),(7,104,24,'Q3 Roadmap Review','Quarterly product roadmap review with the product team.','2025-12-08 11:00:00','2025-12-08 13:00:00',0,'meeting','#8B5CF6','Product War Room',0,NULL,30,'2025-11-23 17:20:56','2025-12-01 17:20:56'),(8,104,24,'Startup Anniversary','Celebrating 1 year since founding! Team lunch and retrospective.','2025-12-11 00:00:00',NULL,1,'event','#EC4899','Office & Nearby Restaurant',0,NULL,1440,'2025-11-26 17:20:56','2025-12-01 17:20:56'),(9,104,24,'VC Firm Meeting','Meeting with potential investors from Sequoia Capital.','2025-12-04 15:00:00','2025-12-04 16:30:00',0,'meeting','#6366F1','VC Office - Downtown',0,NULL,60,'2025-11-24 17:20:56','2025-12-01 17:20:56'),(10,104,24,'Sprint Planning Session','Two-week sprint planning with engineering and product teams.','2025-12-02 09:30:00','2025-12-02 12:00:00',0,'meeting','#059669','Engineering Hub',1,'FREQ=WEEKLY;INTERVAL=2;BYDAY=FR',10,'2025-11-17 17:20:56','2025-11-28 17:20:56'),(11,104,24,'Team Building: Escape Room','Monthly team building activity to boost morale and collaboration.','2025-12-08 17:00:00','2025-12-08 20:00:00',0,'event','#F97316','Escape Room Downtown',1,'FREQ=MONTHLY;BYDAY=3FR',60,'2025-11-19 17:20:56','2025-12-01 17:20:56'),(12,104,24,'New Feature Launch','Launch of AI-powered recommendation engine feature.','2025-12-15 00:00:00',NULL,1,'reminder','#84CC16',NULL,0,NULL,1440,'2025-11-25 17:20:56','2025-12-01 17:20:56'),(13,104,24,'Legal Consultation: IP Protection','Meeting with legal team to discuss patent filing and IP strategy.','2025-12-05 10:00:00','2025-12-05 11:30:00',0,'meeting','#78716C','Law Firm Offices',0,NULL,30,'2025-11-22 17:20:56','2025-11-30 17:20:56'),(14,104,24,'Demo Day Dry Run','Full run-through of demo day presentation with mentors.','2025-12-07 14:00:00','2025-12-07 17:00:00',0,'meeting','#DC2626','Accelerator Space',0,NULL,15,'2025-11-27 17:20:56','2025-12-01 17:20:56'),(15,104,24,'Monthly Metrics Review','Review key performance indicators and metrics with leadership team.','2025-12-09 09:00:00','2025-12-09 10:30:00',0,'meeting','#0EA5E9','Board Room',1,'FREQ=MONTHLY;BYMONTHDAY=15',30,'2025-11-09 17:20:56','2025-11-24 17:20:56'),(16,104,NULL,'Dentist Appointment','Regular dental check-up and cleaning.','2025-12-03 16:00:00','2025-12-03 17:00:00',0,'reminder','#6B7280','Family Dental Clinic',0,NULL,60,'2025-11-26 17:20:57','2025-12-01 17:20:57'),(17,104,NULL,'Friend\'s Birthday Party','Celebrating Sarah\'s 30th birthday.','2025-12-04 19:00:00','2025-12-04 23:00:00',0,'event','#EC4899','The Rooftop Bar',0,NULL,120,'2025-11-28 17:20:57','2025-12-01 17:20:57'),(18,104,NULL,'Gym Session','Personal training session','2025-12-02 07:00:00','2025-12-02 08:00:00',0,'reminder','#10B981','Fitness Center',1,'FREQ=WEEKLY;BYDAY=MO,WE,FR',10,'2025-11-01 17:20:57','2025-11-01 17:20:57');
/*!40000 ALTER TABLE `calendar_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_conversations`
--

DROP TABLE IF EXISTS `chat_conversations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_conversations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `parent_startup_id` int DEFAULT NULL,
  `conversation_type` varchar(20) DEFAULT NULL,
  `created_by_id` int NOT NULL,
  `description` text,
  `avatar_url` varchar(500) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `settings` json DEFAULT NULL,
  `unread_count` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `chat_conversations_ibfk_1` FOREIGN KEY (`created_by_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=131 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_conversations`
--

LOCK TABLES `chat_conversations` WRITE;
/*!40000 ALTER TABLE `chat_conversations` DISABLE KEYS */;
--INSERT INTO `chat_conversations` VALUES (1,'Test Group Chat','group',11,'This is a test group',NULL,1,'{}',NULL,'2025-11-21 22:40:34','2025-11-26 05:46:14'),(2,NULL,'direct',11,NULL,NULL,1,'{}',NULL,'2025-11-22 01:40:06','2025-11-22 03:28:37'),(3,'sf collab group','group',11,'sf collab group group chat',NULL,1,'{}',NULL,'2025-11-22 03:44:55','2025-11-24 08:13:16'),(4,NULL,'direct',11,NULL,NULL,1,'{}',NULL,'2025-11-22 04:39:20','2025-11-26 19:35:12'),(100,'new','group',11,'new group chat',NULL,1,'{}',0,'2025-11-28 04:52:48','2025-11-28 04:52:48'),(101,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:16','2025-11-28 16:52:16'),(102,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:22','2025-11-28 16:52:22'),(103,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:27','2025-11-28 16:52:27'),(104,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:32','2025-11-28 16:53:33'),(105,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:38','2025-11-28 16:52:38'),(106,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:43','2025-11-28 16:52:43'),(107,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:48','2025-11-28 16:52:48'),(108,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:54','2025-11-28 16:52:54'),(109,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:52:59','2025-11-28 16:52:59'),(110,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:53:04','2025-11-28 16:53:04'),(111,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:53:10','2025-11-28 16:53:10'),(112,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:53:15','2025-11-28 16:53:15'),(113,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:53:20','2025-11-28 16:53:20'),(114,NULL,'direct',11,NULL,NULL,1,'{}',0,'2025-11-28 16:53:26','2025-11-28 16:53:26'),(115,NULL,'direct',104,NULL,NULL,1,'{}',0,'2025-12-05 01:17:41','2025-12-11 03:08:44'),(116,NULL,'direct',107,NULL,NULL,1,'{}',0,'2025-12-05 17:32:34','2025-12-05 17:32:34'),(117,'sf collab ui/ux','group',107,'sf collab ui/ux group chat',NULL,1,'{}',0,'2025-12-05 17:34:47','2025-12-05 17:35:13'),(118,NULL,'direct',104,NULL,NULL,1,'{}',0,'2025-12-07 02:35:45','2025-12-07 19:26:08'),(119,'','group',104,' group chat',NULL,1,'{}',0,'2025-12-07 03:12:30','2025-12-07 03:14:50'),(120,NULL,'direct',111,NULL,NULL,1,'{}',0,'2025-12-07 17:25:05','2025-12-07 17:25:05'),(121,NULL,'direct',111,NULL,NULL,1,'{}',0,'2025-12-07 17:25:08','2025-12-07 19:54:58'),(122,'test 2','group',104,'test 2 group chat',NULL,1,'{}',0,'2025-12-07 19:28:00','2025-12-11 18:48:08'),(123,NULL,'direct',108,NULL,NULL,1,'{}',0,'2025-12-08 18:14:27','2025-12-08 18:14:27'),(124,NULL,'direct',108,NULL,NULL,1,'{}',0,'2025-12-08 18:14:29','2025-12-08 18:14:29'),(125,NULL,'direct',118,NULL,NULL,1,'{}',0,'2025-12-11 22:34:38','2025-12-14 01:33:02'),(126,NULL,'direct',108,NULL,NULL,1,'{}',0,'2025-12-14 04:03:12','2025-12-14 04:03:12'),(127,NULL,'direct',108,NULL,NULL,1,'{}',0,'2025-12-14 04:03:14','2025-12-14 04:03:14'),(128,NULL,'direct',108,NULL,NULL,1,'{}',0,'2025-12-14 04:03:17','2025-12-14 04:03:17'),(129,NULL,'direct',108,NULL,NULL,1,'{}',0,'2025-12-14 04:03:18','2025-12-14 04:03:18'),(130,NULL,'direct',100,NULL,NULL,1,'{}',0,'2025-12-14 05:01:24','2025-12-14 05:01:52');
/*!40000 ALTER TABLE `chat_conversations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_messages`
--

DROP TABLE IF EXISTS `chat_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_messages` (
  `id` int NOT NULL AUTO_INCREMENT,
  `conversation_id` int NOT NULL,
  `sender_id` int NOT NULL,
  `original_content` text NOT NULL,
  `sender_timezone` varchar(50) DEFAULT NULL,
  `message_type` varchar(20) DEFAULT NULL,
  `metadata_data` json DEFAULT NULL,
  `is_deleted` tinyint(1) DEFAULT 0,
  `is_edited` tinyint(1) DEFAULT NULL,
  `edited_at` datetime DEFAULT NULL,
  `reply_to_id` int DEFAULT NULL,
  `file_url` varchar(500) DEFAULT NULL,
  `file_name` varchar(255) DEFAULT NULL,
  `file_size` int DEFAULT NULL,
  `file_type` varchar(100) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `reply_to_id` (`reply_to_id`),
  KEY `sender_id` (`sender_id`),
  CONSTRAINT `chat_messages_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `chat_conversations` (`id`),
  CONSTRAINT `chat_messages_ibfk_2` FOREIGN KEY (`reply_to_id`) REFERENCES `chat_messages` (`id`),
  CONSTRAINT `chat_messages_ibfk_3` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=151 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_messages`
--

LOCK TABLES `chat_messages` WRITE;
/*!40000 ALTER TABLE `chat_messages` DISABLE KEYS */;
--INSERT INTO `chat_messages` VALUES (24,4,11,'hello emily','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 02:17:28','2025-11-24 02:17:28'),(25,4,11,'landing','America/Los_Angeles','file','{\"file_info\": {\"size\": 899917, \"type\": \"image/png\", \"uploaded_at\": \"2025-11-24T02:18:08.303870\", \"original_name\": \"Capture_decran_2025-10-06_230716.png\"}}',0,NULL,NULL,'/api/chat/uploads/20251124_021808_11_Capture_decran_2025-10-06_230716.png','Capture_decran_2025-10-06_230716.png',899917,'image/png','2025-11-24 02:18:08','2025-11-24 02:18:08'),(26,3,11,'hello guys','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 02:19:54','2025-11-24 02:19:54'),(27,3,11,'here\'s database schema','America/Los_Angeles','file','{\"file_info\": {\"size\": 77573, \"type\": \"application/pdf\", \"uploaded_at\": \"2025-11-24T02:20:24.338693\", \"original_name\": \"Database_Schema_Design.pdf\"}}',0,NULL,NULL,'/api/chat/uploads/20251124_022024_11_Database_Schema_Design.pdf','Database_Schema_Design.pdf',77573,'application/pdf','2025-11-24 02:20:24','2025-11-24 02:20:24'),(28,3,11,'last update','America/Los_Angeles','file','{\"file_info\": {\"size\": 16549, \"type\": \"application/vnd.openxmlformats-officedocument.wordprocessingml.document\", \"uploaded_at\": \"2025-11-24T02:21:02.026498\", \"original_name\": \"checkList.docx\"}}',0,NULL,NULL,'/api/chat/uploads/20251124_022102_11_checkList.docx','checkList.docx',16549,'application/vnd.openxmlformats-officedocument.wordprocessingml.document','2025-11-24 02:21:02','2025-11-24 02:21:02'),(31,1,11,'nice to meet you','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 06:36:09','2025-11-24 06:36:09'),(32,1,12,'hello ','America/Toronto','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 06:44:29','2025-11-24 06:44:29'),(33,4,11,'that\'s good bro','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 08:11:54','2025-11-24 08:11:54'),(34,1,13,'hello guys','Europe/Madrid','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 08:13:02','2025-11-24 08:13:02'),(35,3,13,'good job','Europe/Madrid','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 08:13:16','2025-11-24 08:13:16'),(36,4,14,'Sent a file','Europe/London','file','{\"file_info\": {\"size\": 16549, \"type\": \"application/vnd.openxmlformats-officedocument.wordprocessingml.document\", \"uploaded_at\": \"2025-11-24T08:48:53.441124\", \"original_name\": \"checkList.docx\"}}',0,NULL,NULL,'/api/chat/uploads/20251124_084853_14_checkList.docx','checkList.docx',16549,'application/vnd.openxmlformats-officedocument.wordprocessingml.document','2025-11-24 08:48:53','2025-11-24 08:48:53'),(37,4,14,'updated content','Europe/London','file','{\"file_info\": {\"size\": 6024385, \"type\": \"application/pdf\", \"uploaded_at\": \"2025-11-24T08:49:29.209309\", \"original_name\": \"1000055985.pdf\"}}',1,'2025-11-24 08:50:48',NULL,'/api/chat/uploads/20251124_084929_14_1000055985.pdf','1000055985.pdf',6024385,'application/pdf','2025-11-24 08:49:29','2025-11-24 08:50:48'),(38,1,11,'hello','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-24 22:43:13','2025-11-24 22:43:13'),(39,1,11,'hello guys no time no seen ','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-26 05:46:14','2025-11-26 05:46:14'),(100,104,11,'meeting at 19','America/Los_Angeles','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-11-28 16:53:33','2025-11-28 16:53:33'),(101,115,104,'hello  from gmail','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-05 01:18:27','2025-12-05 01:18:27'),(102,115,107,'hello bro','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-05 02:23:44','2025-12-05 02:23:44'),(103,115,104,'what\'s up  with the project, is everything alrigh so what\'s going ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-05 03:11:46','2025-12-05 03:11:46'),(104,115,107,'dont forget to add this','UTC','file','{\"file_info\": {\"size\": 3894784, \"type\": \"image/gif\", \"uploaded_at\": \"2025-12-05T03:21:53.819051\", \"original_name\": \"demo.gif\"}}',0,NULL,NULL,'/api/chat/uploads/20251205_032153_107_demo.gif','demo.gif',3894784,'image/gif','2025-12-05 03:21:55','2025-12-05 03:21:55'),(105,117,107,'hello','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-05 17:35:14','2025-12-05 17:35:14'),(106,118,108,'yo','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 02:36:15','2025-12-07 02:36:15'),(107,118,104,'hello brother','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 02:36:41','2025-12-07 02:36:41'),(108,118,104,'wasup hhhhh','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 02:37:35','2025-12-07 02:37:35'),(109,119,104,'hello ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 03:13:20','2025-12-07 03:13:20'),(110,119,104,'Sent a file','UTC','file','{\"file_info\": {\"size\": 1422749, \"type\": \"image/png\", \"uploaded_at\": \"2025-12-07T03:14:50.350128\", \"original_name\": \"image-o53JuZpiN3JOy3N3lXQMLmskV0OslK.png\"}}',0,NULL,NULL,'/api/chat/uploads/20251207_031450_104_image-o53JuZpiN3JOy3N3lXQMLmskV0OslK.png','image-o53JuZpiN3JOy3N3lXQMLmskV0OslK.png',1422749,'image/png','2025-12-07 03:14:52','2025-12-07 03:14:52'),(111,121,111,'Hello','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 17:26:05','2025-12-07 17:26:05'),(112,118,104,'hello is it working?','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 19:26:08','2025-12-07 19:26:08'),(113,122,104,'hello brother\'s','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 19:28:39','2025-12-07 19:28:39'),(114,122,111,'hello','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 19:54:35','2025-12-07 19:54:35'),(115,121,111,'hey bro','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 19:54:58','2025-12-07 19:54:58'),(116,122,104,'need\'s improvements hhh','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 19:56:38','2025-12-07 19:56:38'),(117,122,111,'yeah lol','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 19:57:12','2025-12-07 19:57:12'),(118,122,104,'[21:10] \nwhat time do you see ?','UTC','text','{\"sent_at_utc\": \"2025-12-07T20:10:36.749877\", \"sender_timezone\": \"UTC\", \"has_time_placeholders\": true}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-07 20:10:38','2025-12-07 20:10:38'),(119,115,107,'hello ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-10 23:50:29','2025-12-10 23:50:29'),(120,115,104,'hello body ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-10 23:55:34','2025-12-10 23:55:34'),(121,115,107,'life is fucked up man','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 00:01:29','2025-12-11 00:01:29'),(122,115,107,'yes ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 00:05:18','2025-12-11 00:05:18'),(123,115,104,'so what are we going to do','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 00:17:57','2025-12-11 00:17:57'),(124,115,107,'probably nothing','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 00:19:15','2025-12-11 00:19:15'),(125,115,104,'fuck you we most never give up','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 00:22:37','2025-12-11 00:22:37'),(126,115,107,'hjhsxjhjnj','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 00:28:12','2025-12-11 00:28:12'),(127,115,104,'what the fuck ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 01:19:23','2025-12-11 01:19:23'),(128,115,107,'sorry brother we need to get rich or just died','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 03:01:22','2025-12-11 03:01:22'),(129,115,104,'yes','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 03:06:59','2025-12-11 03:06:59'),(130,115,107,'zedzedzed','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 03:08:44','2025-12-11 03:08:44'),(131,122,104,'aiuzduiuhd','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 18:48:09','2025-12-11 18:48:09'),(132,125,118,'hello bro','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 22:35:13','2025-12-11 22:35:13'),(133,125,104,'hello university','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-11 23:58:32','2025-12-11 23:58:32'),(134,125,118,'hello  ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:04:07','2025-12-12 00:04:07'),(135,125,118,'you won the lottery','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:06:19','2025-12-12 00:06:19'),(136,125,104,'whaaaaaaaaaaaat??','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:08:50','2025-12-12 00:08:50'),(137,125,118,'yes','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:10:01','2025-12-12 00:10:01'),(138,125,104,'no thanks','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:13:45','2025-12-12 00:13:45'),(139,125,104,'[01:30]  now','UTC','text','{\"sent_at_utc\": \"2025-12-12T00:14:15.271685\", \"sender_timezone\": \"UTC\", \"has_time_placeholders\": true}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:14:16','2025-12-12 00:14:16'),(140,125,118,'what\'s that time for?','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:52:50','2025-12-12 00:52:50'),(141,125,104,'here in Morocco','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:53:42','2025-12-12 00:53:42'),(142,125,118,'okay what\'s good now','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:55:54','2025-12-12 00:55:54'),(143,125,118,'yes','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 00:58:04','2025-12-12 00:58:04'),(144,125,118,'zedzedzedzed','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 01:01:23','2025-12-12 01:01:23'),(145,125,104,'same shit','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 01:02:20','2025-12-12 01:02:20'),(146,125,118,'why','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 01:04:20','2025-12-12 01:04:20'),(147,125,118,'fgffgf','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-12 06:35:42','2025-12-12 06:35:42'),(148,125,104,'hello [01:40] ','UTC','text','{\"sent_at_utc\": \"2025-12-13T02:17:44.012873\", \"sender_timezone\": \"UTC\", \"has_time_placeholders\": true}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-13 02:17:45','2025-12-13 02:17:45'),(149,125,118,'hi','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-14 01:33:03','2025-12-14 01:33:03'),(150,130,100,'hello ','UTC','text','{}',0,NULL,NULL,NULL,NULL,NULL,NULL,'2025-12-14 05:01:52','2025-12-14 05:01:52');
/*!40000 ALTER TABLE `chat_messages` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `conversation_participants`
--

DROP TABLE IF EXISTS `conversation_participants`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversation_participants` (
  `conversation_id` int NOT NULL,
  `user_id` int NOT NULL,
  `joined_at` datetime DEFAULT NULL,
  `role` varchar(20) DEFAULT NULL,
  `is_hidden` tinyint(1) DEFAULT '0',
  `is_archived` tinyint(1) DEFAULT 0 NOT NULL,
  `archived_at` datetime DEFAULT NULL,
  `is_pinned` tinyint(1) DEFAULT 0 NOT NULL,
  `pinned_at` datetime DEFAULT NULL,
  PRIMARY KEY (`conversation_id`,`user_id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `conversation_participants_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `chat_conversations` (`id`),
  CONSTRAINT `conversation_participants_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `conversation_participants`
--

LOCK TABLES `conversation_participants` WRITE;
/*!40000 ALTER TABLE `conversation_participants` DISABLE KEYS */;
--INSERT INTO `conversation_participants` VALUES (1,11,'2025-11-21 22:40:34','admin'),(1,12,'2025-11-21 22:40:34','member'),(1,13,'2025-11-21 22:40:34','member'),(2,11,'2025-11-22 01:40:06','admin'),(2,12,'2025-11-22 01:40:06','member'),(2,13,'2025-11-22 01:40:06','member'),(3,11,'2025-11-22 03:44:56','admin'),(3,13,'2025-11-22 03:44:56','member'),(3,14,'2025-11-22 03:44:56','member'),(3,15,'2025-11-22 03:44:56','member'),(4,11,'2025-11-22 04:39:20','admin'),(4,14,'2025-11-22 04:39:20','member'),(100,11,'2025-11-28 04:52:48','admin'),(100,12,'2025-11-28 04:52:49','member'),(100,13,'2025-11-28 04:52:50','member'),(101,11,'2025-11-28 16:52:17','admin'),(101,14,'2025-11-28 16:52:18','member'),(102,11,'2025-11-28 16:52:22','admin'),(102,14,'2025-11-28 16:52:23','member'),(103,11,'2025-11-28 16:52:28','admin'),(103,14,'2025-11-28 16:52:29','member'),(104,11,'2025-11-28 16:52:33','admin'),(104,14,'2025-11-28 16:52:34','member'),(105,11,'2025-11-28 16:52:38','admin'),(105,14,'2025-11-28 16:52:39','member'),(106,11,'2025-11-28 16:52:44','admin'),(106,14,'2025-11-28 16:52:45','member'),(107,11,'2025-11-28 16:52:49','admin'),(107,14,'2025-11-28 16:52:50','member'),(108,11,'2025-11-28 16:52:54','admin'),(108,14,'2025-11-28 16:52:55','member'),(109,11,'2025-11-28 16:53:00','admin'),(109,14,'2025-11-28 16:53:01','member'),(110,11,'2025-11-28 16:53:05','admin'),(110,14,'2025-11-28 16:53:06','member'),(111,11,'2025-11-28 16:53:10','admin'),(111,14,'2025-11-28 16:53:11','member'),(112,11,'2025-11-28 16:53:16','admin'),(112,14,'2025-11-28 16:53:17','member'),(113,11,'2025-11-28 16:53:21','admin'),(113,14,'2025-11-28 16:53:22','member'),(114,11,'2025-11-28 16:53:26','admin'),(114,14,'2025-11-28 16:53:27','member'),(115,104,'2025-12-05 01:17:42','admin'),(115,107,'2025-12-05 01:17:43','member'),(116,104,'2025-12-05 17:32:35','member'),(116,107,'2025-12-05 17:32:35','admin'),(117,105,'2025-12-05 17:34:48','member'),(117,106,'2025-12-05 17:34:49','member'),(117,107,'2025-12-05 17:34:48','admin'),(118,104,'2025-12-07 02:35:46','admin'),(118,108,'2025-12-07 02:35:47','member'),(119,104,'2025-12-07 03:12:31','admin'),(119,105,'2025-12-07 03:12:32','member'),(119,106,'2025-12-07 03:12:33','member'),(119,108,'2025-12-07 03:12:34','member'),(120,100,'2025-12-07 17:25:07','member'),(120,111,'2025-12-07 17:25:05','admin'),(121,100,'2025-12-07 17:25:10','member'),(121,111,'2025-12-07 17:25:09','admin'),(122,104,'2025-12-07 19:28:01','admin'),(122,108,'2025-12-07 19:28:02','member'),(122,111,'2025-12-07 19:28:03','member'),(123,11,'2025-12-08 18:14:28','member'),(123,108,'2025-12-08 18:14:27','admin'),(124,11,'2025-12-08 18:14:31','member'),(124,108,'2025-12-08 18:14:30','admin'),(125,104,'2025-12-11 22:34:39','member'),(125,118,'2025-12-11 22:34:38','admin'),(126,108,'2025-12-14 04:03:13','admin'),(126,109,'2025-12-14 04:03:14','member'),(127,108,'2025-12-14 04:03:14','admin'),(127,109,'2025-12-14 04:03:15','member'),(128,108,'2025-12-14 04:03:18','admin'),(128,109,'2025-12-14 04:03:19','member'),(129,108,'2025-12-14 04:03:18','admin'),(129,109,'2025-12-14 04:03:19','member'),(130,100,'2025-12-14 05:01:25','admin'),(130,104,'2025-12-14 05:01:26','member');
/*!40000 ALTER TABLE `conversation_participants` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `conversation_user_reads`
--

DROP TABLE IF EXISTS `conversation_user_reads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `conversation_user_reads` (
  `conversation_id` int NOT NULL,
  `user_id` int NOT NULL,
  `last_read_at` datetime DEFAULT NULL,
  `unread_count` int DEFAULT NULL,
  PRIMARY KEY (`conversation_id`,`user_id`),
  KEY `conversation_id` (`conversation_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `conversation_user_reads_ibfk_1` FOREIGN KEY (`conversation_id`) REFERENCES `chat_conversations` (`id`),
  CONSTRAINT `conversation_user_reads_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `conversation_user_reads`
--

LOCK TABLES `conversation_user_reads` WRITE;
/*!40000 ALTER TABLE `conversation_user_reads` DISABLE KEYS */;
--INSERT INTO `conversation_user_reads` VALUES (1,11,'2025-11-26 19:33:11',0),(1,12,'2025-11-24 06:43:26',3),(1,13,'2025-11-24 08:12:47',2),(2,11,'2025-11-24 08:13:24',0),(2,13,'2025-11-24 08:12:21',0),(3,11,'2025-11-24 22:38:46',0),(3,13,'2025-11-24 08:13:04',0),(3,14,'2025-11-24 10:24:44',0),(3,15,'2025-11-24 08:13:16',1),(4,11,'2025-11-28 02:41:59',0),(4,14,'2025-11-24 10:26:08',1),(104,14,'2025-11-28 16:53:33',1),(115,104,'2025-12-11 03:15:25',0),(115,107,'2025-12-11 03:07:57',0),(116,104,'2025-12-07 02:37:16',0),(116,107,'2025-12-11 02:14:10',0),(117,105,'2025-12-05 17:35:14',1),(117,106,'2025-12-05 17:35:14',1),(117,107,'2025-12-11 02:18:30',0),(118,104,'2025-12-13 06:04:17',0),(118,108,'2025-12-07 03:19:46',1),(119,104,'2025-12-12 01:17:35',0),(119,105,'2025-12-07 03:13:19',2),(119,106,'2025-12-07 03:13:20',2),(119,108,'2025-12-07 03:19:40',0),(121,100,'2025-12-07 17:26:05',2),(121,111,'2025-12-07 19:54:42',0),(122,104,'2025-12-12 00:11:13',0),(122,108,'2025-12-08 18:16:53',1),(122,111,'2025-12-07 19:56:43',2),(125,104,'2025-12-14 20:25:49',0),(125,118,'2025-12-14 20:25:57',0),(127,108,'2025-12-14 04:03:29',0),(130,104,'2025-12-14 20:45:23',0);
/*!40000 ALTER TABLE `conversation_user_reads` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `goal_milestones`
--

DROP TABLE IF EXISTS `goal_milestones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `goal_milestones` (
  `id` int NOT NULL AUTO_INCREMENT,
  `goal_id` int NOT NULL,
  `user_id` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text,
  `order` int DEFAULT NULL,
  `is_completed` tinyint(1) DEFAULT NULL,
  `completed_date` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `goal_id` (`goal_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `goal_milestones_ibfk_1` FOREIGN KEY (`goal_id`) REFERENCES `project_goals` (`id`),
  CONSTRAINT `goal_milestones_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `goal_milestones`
--

LOCK TABLES `goal_milestones` WRITE;
/*!40000 ALTER TABLE `goal_milestones` DISABLE KEYS */;
/*!40000 ALTER TABLE `goal_milestones` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `growth_metrics`
--

DROP TABLE IF EXISTS `growth_metrics`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `growth_metrics` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `metric_type` enum('user_growth','revenue','market_share','overall') NOT NULL,
  `current_value` float DEFAULT NULL,
  `previous_value` float DEFAULT NULL,
  `growth_percentage` float DEFAULT NULL,
  `user_growth_percentage` float DEFAULT NULL,
  `revenue_amount` float DEFAULT NULL,
  `market_share_percentage` float DEFAULT NULL,
  `period_start` datetime NOT NULL,
  `period_end` datetime NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `growth_metrics_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`),
  CONSTRAINT `growth_metrics_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `growth_metrics`
--

LOCK TABLES `growth_metrics` WRITE;
/*!40000 ALTER TABLE `growth_metrics` DISABLE KEYS */;
/*!40000 ALTER TABLE `growth_metrics` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `idea_bookmarks`
--

DROP TABLE IF EXISTS `idea_bookmarks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `idea_bookmarks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `idea_id` int NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `content_preview` text,
  `url` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idea_id` (`idea_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `idea_bookmarks_ibfk_1` FOREIGN KEY (`idea_id`) REFERENCES `ideas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `idea_bookmarks_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `idea_bookmarks`
--

LOCK TABLES `idea_bookmarks` WRITE;
/*!40000 ALTER TABLE `idea_bookmarks` DISABLE KEYS */;
/*!40000 ALTER TABLE `idea_bookmarks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `idea_comments`
--

DROP TABLE IF EXISTS `idea_comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `idea_comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `idea_id` int NOT NULL,
  `content` text NOT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `suggestion` boolean DEFAULT FALSE,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `idea_id` (`idea_id`),
  CONSTRAINT `idea_comments_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`),
  CONSTRAINT `idea_comments_ibfk_2` FOREIGN KEY (`idea_id`) REFERENCES `ideas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `idea_comments`
--

LOCK TABLES `idea_comments` WRITE;
/*!40000 ALTER TABLE `idea_comments` DISABLE KEYS */;
/*!40000 ALTER TABLE `idea_comments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ideas`
--

DROP TABLE IF EXISTS `ideas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ideas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` text NOT NULL,
  `project_details` text NOT NULL,
  `industry` varchar(100) NOT NULL,
  `stage` varchar(100) NOT NULL,
  `tags` json DEFAULT NULL,
  `image_url` varchar(255) DEFAULT NULL,
  `privacy` enum('public','private') DEFAULT NULL,
  `creator_id` int NOT NULL,
  `creator_first_name` varchar(100) DEFAULT NULL,
  `creator_last_name` varchar(100) DEFAULT NULL,
  `status` enum('active','inactive') DEFAULT NULL,
  `likes` int DEFAULT NULL,
  `views` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `creator_id` (`creator_id`),
  CONSTRAINT `ideas_ibfk_1` FOREIGN KEY (`creator_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ideas`
--

LOCK TABLES `ideas` WRITE;
/*!40000 ALTER TABLE `ideas` DISABLE KEYS */;
--INSERT INTO `ideas` VALUES (16,'AI-Powered Learning Platform for Kids','An adaptive learning platform that uses AI to personalize educational content for children based on their learning style and pace.','The platform will use machine learning algorithms to analyze student performance and adapt content difficulty. Will include gamification elements and progress tracking for parents.','Education Technology','Concept','[\"AI\", \"Education\", \"Machine Learning\", \"EdTech\", \"Children\"]','public',104,'','','active',178,779,'2025-11-01 17:07:35','2025-12-11 20:34:25'),(17,'Sustainable Vertical Farming System','A modular vertical farming system for urban environments that uses 90% less water than traditional farming.','System includes automated nutrient delivery, LED lighting optimized for plant growth, and IoT sensors for monitoring plant health. Targeting restaurants and urban communities.','Agriculture','Prototype','[\"Sustainability\", \"Agriculture\", \"Urban Farming\", \"IoT\", \"Green Tech\"]','public',104,'','','active',150,806,'2025-11-06 17:07:35','2025-12-07 06:34:36'),(18,'Blockchain-Based Digital Identity Solution','A decentralized digital identity system that gives users control over their personal data and verification credentials.','Using blockchain technology to create tamper-proof digital identities. Solution includes mobile app for identity management and API for third-party verification.','FinTech','Research','[\"Blockchain\", \"Security\", \"Digital Identity\", \"Privacy\", \"FinTech\"]','private',104,'','','active',55,349,'2025-11-11 17:07:35','2025-11-30 17:07:35'),(19,'Mental Health Companion App','An AI-powered mental health app that provides daily check-ins, coping strategies, and connects users with resources.','Features include mood tracking, guided meditation, cognitive behavioral therapy exercises, and emergency resource directory. Will use natural language processing for conversational support.','Healthcare','Planning','[\"Mental Health\", \"AI\", \"Healthcare\", \"Wellness\", \"Mobile App\"]','public',104,'','','active',87,510,'2025-11-16 17:07:35','2025-11-28 17:07:35'),(20,'Smart Waste Management System','IoT-based waste management system that optimizes collection routes and schedules based on fill levels.','Smart bins with sensors transmit fill level data to central system. Algorithm optimizes collection routes to reduce fuel consumption and operational costs.','Clean Tech','Development','[\"IoT\", \"Sustainability\", \"Smart Cities\", \"Waste Management\", \"Clean Tech\"]','public',104,'','','active',152,654,'2025-11-21 17:07:35','2025-12-01 17:07:35'),(21,'AR Interior Design Platform','Augmented Reality app that lets users visualize furniture and decor in their space before purchasing.','Users upload room dimensions or use phone camera to create AR overlay of products. Integration with furniture retailers and interior design services.','Retail Technology','Concept','[\"AR\", \"Interior Design\", \"Retail\", \"Mobile App\", \"Visualization\"]','public',104,'','','active',101,944,'2025-11-23 17:07:35','2025-11-30 17:07:35'),(22,'Remote Team Collaboration Tool','Virtual workspace designed for distributed teams with integrated project management and communication features.','Includes virtual whiteboards, task management, video conferencing, and document collaboration. Focus on reducing meeting fatigue and improving asynchronous work.','SaaS','Beta','[\"Remote Work\", \"SaaS\", \"Collaboration\", \"Productivity\", \"B2B\"]','private',104,'','','active',144,147,'2025-11-26 17:07:35','2025-12-01 17:07:35'),(23,'Plant-Based Meat Alternatives Marketplace','Online platform connecting consumers with local producers of plant-based meat alternatives.','Subscription box service and a la carte ordering. Focus on locally-sourced, sustainable plant-based proteins with transparent sourcing information.','Food Tech','Planning','[\"Food Tech\", \"Sustainability\", \"Plant-Based\", \"E-commerce\", \"Health\"]','public',104,'','','active',18,401,'2025-11-28 17:07:35','2025-12-11 01:05:04'),(24,'Renewable Energy Microgrid Controller','Smart controller for managing microgrids with mixed renewable energy sources (solar, wind, battery storage).','Uses AI to predict energy production and consumption, optimizing energy distribution and storage. Targets rural communities and commercial campuses.','Energy','Research','[\"Renewable Energy\", \"AI\", \"Smart Grid\", \"Sustainability\", \"Clean Energy\"]','public',104,'','','active',47,370,'2025-11-29 17:07:35','2025-12-01 17:07:35'),(25,'Personal Finance AI Assistant','AI-powered financial advisor that helps users with budgeting, saving, and investment decisions.','Analyzes spending patterns, suggests budgets, identifies saving opportunities, and provides personalized investment recommendations based on risk profile.','FinTech','Concept','[\"FinTech\", \"AI\", \"Personal Finance\", \"Investing\", \"Budgeting\"]','public',104,'','','active',131,545,'2025-11-30 17:07:35','2025-12-01 17:07:35');
/*!40000 ALTER TABLE `ideas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `join_requests`
--

DROP TABLE IF EXISTS `join_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `join_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int NOT NULL,
  `startup_name` varchar(255) DEFAULT NULL,
  `user_id` int NOT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `message` text,
  `role` varchar(100) DEFAULT NULL,
  `status` enum('pending','approved','rejected') DEFAULT NULL,
  `media_links` json DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `join_requests_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `join_requests_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `join_requests`
--

LOCK TABLES `join_requests` WRITE;
/*!40000 ALTER TABLE `join_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `join_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `knowledge`
--

DROP TABLE IF EXISTS `knowledge`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `title_description` text NOT NULL,
  `content_preview` text NOT NULL,
  `category` varchar(100) NOT NULL,
  `file_url` varchar(500) DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `status` enum('active','inactive') DEFAULT NULL,
  `views` int DEFAULT NULL,
  `downloads` int DEFAULT NULL,
  `likes` int DEFAULT NULL,
  `image_buffer` blob,
  `image_content_type` varchar(100) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `file_size_mb` float NOT NULL DEFAULT 0.0,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  CONSTRAINT `knowledge_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `knowledge`
--

LOCK TABLES `knowledge` WRITE;
/*!40000 ALTER TABLE `knowledge` DISABLE KEYS */;
/*!40000 ALTER TABLE `knowledge` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `knowledge_bookmarks`
--

DROP TABLE IF EXISTS `knowledge_bookmarks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_bookmarks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `knowledge_id` int NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `content_preview` text,
  `url` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `knowledge_id` (`knowledge_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `knowledge_bookmarks_ibfk_1` FOREIGN KEY (`knowledge_id`) REFERENCES `knowledge` (`id`) ON DELETE CASCADE,
  CONSTRAINT `knowledge_bookmarks_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `knowledge_bookmarks`
--

LOCK TABLES `knowledge_bookmarks` WRITE;
/*!40000 ALTER TABLE `knowledge_bookmarks` DISABLE KEYS */;
/*!40000 ALTER TABLE `knowledge_bookmarks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `knowledge_comments`
--

DROP TABLE IF EXISTS `knowledge_comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `knowledge_comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `resource_id` int NOT NULL,
  `content` text NOT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `resource_id` (`resource_id`),
  CONSTRAINT `knowledge_comments_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`),
  CONSTRAINT `knowledge_comments_ibfk_2` FOREIGN KEY (`resource_id`) REFERENCES `knowledge` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `knowledge_comments`
--

LOCK TABLES `knowledge_comments` WRITE;
/*!40000 ALTER TABLE `knowledge_comments` DISABLE KEYS */;
/*!40000 ALTER TABLE `knowledge_comments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notifications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `actor_id` int DEFAULT NULL,
  `notification_type` varchar(50) DEFAULT 'info',
  `category` varchar(50) DEFAULT 'system',
  `priority` varchar(20) DEFAULT 'medium',
  `title` varchar(255),
  `message` text,
  `entity_type` varchar(50) DEFAULT NULL,
  `entity_id` int DEFAULT NULL,
  `data` json DEFAULT NULL,
  `link_url` varchar(500) DEFAULT NULL,
  `is_read` tinyint(1) DEFAULT 0,
  `read_at` datetime DEFAULT NULL,
  `email_sent` tinyint(1) DEFAULT 0,
  `email_sent_at` datetime DEFAULT NULL,
  `push_sent` tinyint(1) DEFAULT 0,
  `push_sent_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `actor_id` (`actor_id`),
  KEY `entity_type_id` (`entity_type`, `entity_id`),
  KEY `is_read` (`is_read`),
  KEY `created_at` (`created_at`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `notifications_ibfk_2` FOREIGN KEY (`actor_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notifications`
--

LOCK TABLES `notifications` WRITE;
/*!40000 ALTER TABLE `notifications` DISABLE KEYS */;
-- INSERT INTO `notifications` VALUES (1,104,'system','Welcome to the Platform','Thank you for joining our platform! We are excited to have you here.','{\"page\": \"dashboard\", \"action\": \"welcome\"}',0,NULL,'2025-11-29 03:44:24','2025-11-29 03:44:24'),(2,104,'system','Profile Update Required','Please complete your profile information to get the most out of our platform.','{\"page\": \"profile\", \"action\": \"update_profile\"}',1,'2025-11-29 04:44:24','2025-11-29 02:44:24','2025-11-29 04:44:24'),(3,104,'suggestion','New Suggestion Available','You have a new suggestion waiting for your review.','{\"type\": \"feature\", \"status\": \"pending\", \"suggestion_id\": 456}',1,'2025-11-29 05:47:13','2025-11-29 05:14:24','2025-11-29 05:47:13'),(4,104,'suggestion','Suggestion Approved','Your suggestion \"Dark Mode Feature\" has been approved by the admin.','{\"title\": \"Dark Mode Feature\", \"status\": \"approved\", \"suggestion_id\": 123}',1,'2025-11-29 05:29:24','2025-11-29 04:59:24','2025-11-29 05:29:24'),(5,104,'system','Weekly Summary','Here is your weekly activity summary. You have been very active this week!','{\"period\": \"week\", \"activities\": 15, \"achievements\": 3}',1,'2025-11-29 05:47:10','2025-11-29 05:34:24','2025-11-29 05:47:10'),(6,104,'system','System Maintenance','Scheduled maintenance will occur this weekend. The system may be unavailable for 2 hours.','{\"duration\": \"2 hours\", \"maintenance_date\": \"2024-01-15\"}',1,'2025-11-28 03:44:24','2025-11-27 23:44:24','2025-11-28 03:44:24'),(7,104,'suggestion','Suggestion Feedback','Your suggestion needs some modifications before it can be approved.','{\"status\": \"rejected\", \"feedback\": \"Please provide more details about implementation\", \"suggestion_id\": 789}',1,'2025-11-29 00:44:24','2025-11-28 21:44:24','2025-11-29 00:44:24'),(8,104,'urgent','Security Alert','Unusual login activity detected on your account. Please review your account security.','{\"ip_address\": \"192.168.1.100\", \"alert_level\": \"high\", \"action_required\": true}',1,'2025-11-29 05:46:57','2025-11-29 05:39:24','2025-11-29 05:46:57');
/*!40000 ALTER TABLE `notifications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `post_comments`
--

DROP TABLE IF EXISTS `post_comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `post_comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `post_id` int NOT NULL,
  `content` text NOT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `post_id` (`post_id`),
  CONSTRAINT `post_comments_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`),
  CONSTRAINT `post_comments_ibfk_2` FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `post_comments`
--

LOCK TABLES `post_comments` WRITE;
/*!40000 ALTER TABLE `post_comments` DISABLE KEYS */;
/*!40000 ALTER TABLE `post_comments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `post_likes`
--

DROP TABLE IF EXISTS `post_likes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `post_likes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `post_id` int NOT NULL,
  `user_id` int NOT NULL,
  `liked_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `post_id` (`post_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `post_likes_ibfk_1` FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `post_likes_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `post_likes`
--

LOCK TABLES `post_likes` WRITE;
/*!40000 ALTER TABLE `post_likes` DISABLE KEYS */;
/*!40000 ALTER TABLE `post_likes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `post_likes`
--

DROP TABLE IF EXISTS `post_saves`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `post_saves` (
  `id` int NOT NULL AUTO_INCREMENT,
  `post_id` int NOT NULL,
  `user_id` int NOT NULL,
  `saved_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `post_id` (`post_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `post_saves_ibfk_1` FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `post_saves_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `post_saves`
--

LOCK TABLES `post_saves` WRITE;
/*!40000 ALTER TABLE `post_saves` DISABLE KEYS */;
/*!40000 ALTER TABLE `post_saves` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `post_media`
--

DROP TABLE IF EXISTS `post_media`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `post_media` (
  `id` int NOT NULL AUTO_INCREMENT,
  `post_id` int NOT NULL,
  `media_url` varchar(500) NOT NULL,
  `content_type` varchar(100) DEFAULT NULL,
  `file_name` varchar(255) DEFAULT NULL,
  `file_size` int DEFAULT NULL,
  `caption` text,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `post_id` (`post_id`),
  CONSTRAINT `post_media_ibfk_1` FOREIGN KEY (`post_id`) REFERENCES `posts` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `post_media`
--

LOCK TABLES `post_media` WRITE;
/*!40000 ALTER TABLE `post_media` DISABLE KEYS */;
/*!40000 ALTER TABLE `post_media` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `posts`
--

DROP TABLE IF EXISTS `posts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `posts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `content` text NOT NULL,
  `type` enum('professional','social','image','video','text') DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `likes` int DEFAULT NULL,
  `comments_count` int DEFAULT NULL,
  `shares` int DEFAULT NULL,
  `saves` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `posts_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`),
  CONSTRAINT `posts_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `posts`
--

LOCK TABLES `posts` WRITE;
/*!40000 ALTER TABLE `posts` DISABLE KEYS */;
/*!40000 ALTER TABLE `posts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `project_goals`
--

DROP TABLE IF EXISTS `project_goals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_goals` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text,
  `progress_percentage` float DEFAULT NULL,
  `milestones_completed` int DEFAULT NULL,
  `milestones_total` int DEFAULT NULL,
  `is_on_track` tinyint(1) DEFAULT NULL,
  `next_milestone` varchar(255) DEFAULT NULL,
  `start_date` datetime DEFAULT NULL,
  `target_date` datetime DEFAULT NULL,
  `completed_date` datetime DEFAULT NULL,
  `status` enum('active','completed','on_hold','cancelled') DEFAULT NULL,
  `visible_by` varchar(50) DEFAULT 'team',
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `team_size` int DEFAULT 1,
  `members_involved` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `project_goals_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`),
  CONSTRAINT `project_goals_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `project_goals`
--

LOCK TABLES `project_goals` WRITE;
/*!40000 ALTER TABLE `project_goals` DISABLE KEYS */;
/*!40000 ALTER TABLE `project_goals` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `refresh_tokens`
--

DROP TABLE IF EXISTS `refresh_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `refresh_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `token` varchar(500) NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `refresh_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=117 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `refresh_tokens`
--

LOCK TABLES `refresh_tokens` WRITE;
/*!40000 ALTER TABLE `refresh_tokens` DISABLE KEYS */;
-- INSERT INTO `refresh_tokens` VALUES (1,0,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDI5NTM3OSwianRpIjoiMTA5MGZmMTItNWUwOC00NTM2LTlmN2UtNWU3N2ZmMjU0Y2U1IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIwIiwibmJmIjoxNzY0Mjk1Mzc5LCJjc3JmIjoiZWFhZjg3ZjMtZmIzMC00ZWEzLWFiMjYtMDNmYTljMDExZDk0IiwiZXhwIjoxNzY2ODg3Mzc5fQ.cxyGKlrka7LsGsIzLhhVhyn4zbBflqiA_6ZYgGq2CPY','2025-11-28 02:02:59','2025-11-28 02:02:59'),(2,21,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDI5NTQ4MiwianRpIjoiZWI2NjM4NWUtNzZhZS00ODE1LWFkYzMtNDFlOWZmMTI0N2I5IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIyMSIsIm5iZiI6MTc2NDI5NTQ4MiwiY3NyZiI6IjhhZjA4NWNjLWEyNGYtNDRlZC1iYzhhLTc2NTA0OTVkMzMwZSIsImV4cCI6MTc2Njg4NzQ4Mn0.1SyaQyWulSG2Z-xC_rv1o9pdTDsxQPoiFb1vepeTXPE','2025-11-28 02:04:42','2025-11-28 02:04:42'),(4,101,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDMwMDMzMywianRpIjoiY2YwZTQ5ODktNDA4NS00NDI0LWE1Y2QtM2ViMjBjYWQxOWUzIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDEiLCJuYmYiOjE3NjQzMDAzMzMsImNzcmYiOiI1OTg1ODFiZi1lYzhmLTQ5NDUtYjUyNy1hY2M5NDg3MTY2ZjgiLCJleHAiOjE3NjY4OTIzMzN9.lryZtBB7yOdgCSD9ocgWbRT69KOC-8hC_46sGyXsYsw','2025-11-28 03:25:33','2025-11-28 03:25:33'),(11,102,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDM1MzIxMiwianRpIjoiOTAxODk4OGQtNDk1My00ZTQ1LWFiYjQtNGZhNTk3MGYxMTYzIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDIiLCJuYmYiOjE3NjQzNTMyMTIsImNzcmYiOiI5YjY2Zjk4ZC1jNDJhLTQyNjUtOGUxNi01YWU2OWQzZTY4OWQiLCJleHAiOjE3NjY5NDUyMTJ9.9tjcx6EMy2f13q0hmnr5MQugQfWEkl9WsOBiG81N6Kk','2025-11-28 18:06:52','2025-11-28 18:06:52'),(13,103,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDM1MzI2MywianRpIjoiNjI2NmM2OWQtODE3MC00MzNhLThkYmEtZjZmMjEyNzI2M2Q3IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDMiLCJuYmYiOjE3NjQzNTMyNjMsImNzcmYiOiI5YjQyNjIwNS0zMDc2LTQxMDUtYWRmMC0xNDIyZTdlMzQ1ZTgiLCJleHAiOjE3NjY5NDUyNjN9.5AiYV_8YZ1ON8z-bFaVUN59HbcbsNl2P6U0YirmX4EM','2025-11-28 18:07:43','2025-11-28 18:07:43'),(20,105,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDM2MDk1OCwianRpIjoiNWQ5YmYyZTMtNDZmNC00Y2RhLThhYTEtMDEyMDE1ZGEwMjEzIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDUiLCJuYmYiOjE3NjQzNjA5NTgsImNzcmYiOiJkM2NmMDQzZC03Mzg1LTQxODgtODVhMi02NDJiN2Q4YWZiOGMiLCJleHAiOjE3NjY5NTI5NTh9.8akyIhkXC7pqiem3LKIhfCD2SYZTea-AN5IrS7yJSwg','2025-11-28 20:15:58','2025-11-28 20:15:58'),(37,106,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NDYxMTk4MSwianRpIjoiZGViYmUyNTMtNWFlNC00ODIxLWE2MjQtYmM0NzYwZTlhNDg4IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDYiLCJuYmYiOjE3NjQ2MTE5ODEsImNzcmYiOiJlMDYxZTE0OS1lZDhlLTRlYTctYThlNC0wYjBhNmYxOTFkM2QiLCJleHAiOjE3NjcyMDM5ODF9.RSf-JBZMfyPZNdlXvVu7IL9a6ESmXyfS4MVcSL8Aohk','2025-12-01 17:59:41','2025-12-01 17:59:41'),(66,109,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTA4MjkyOCwianRpIjoiODI5ZGI4ZGEtZDcyMS00ODA0LWExMTItMmUyYTNhZDhmMTI0IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDkiLCJuYmYiOjE3NjUwODI5MjgsImNzcmYiOiI5YWM3NjMxNy1jNjFlLTQ1MzMtYjhkMi04M2Y0MGM3ZWI1NTIiLCJleHAiOjE3Njc2NzQ5Mjh9.NmCk6zvQ1URlq5GPLmtqFCv4HFk2mjHxcC3I3mzrDRg','2025-12-07 04:48:49','2025-12-07 04:48:49'),(67,110,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTEyODA2OCwianRpIjoiMmFjZmI4NWYtMWU5NC00YTZjLWI1ZWQtOGRiOGFmODA3ZDc1IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTAiLCJuYmYiOjE3NjUxMjgwNjgsImNzcmYiOiJiOWM4YTc0NC1hNDEyLTQ0ZTAtOGM2MS0zZjI2NzJlNzVlN2IiLCJleHAiOjE3Njc3MjAwNjh9.KgpyGqilB3fOcmq_D4knSwuT7OE3TDn5tDhiDJOCNMs','2025-12-07 17:21:09','2025-12-07 17:21:09'),(72,112,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTEzNTUwOSwianRpIjoiYTA4MDRlM2QtYzA2OC00MTBhLThjZjktOGUxNDc5MTFjYjBmIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTIiLCJuYmYiOjE3NjUxMzU1MDksImNzcmYiOiJiYjU1MTljYS02ZWRiLTQ1MTgtYTBkNi0wNWUwNjdkNjQ0ODEiLCJleHAiOjE3Njc3Mjc1MDl9.qu1Zzk64vS1RuyXXTtM5bERQYGWeYiiBYDJHxSKyYMg','2025-12-07 19:25:10','2025-12-07 19:25:10'),(73,111,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTEzNzIxNCwianRpIjoiMjdkMzZhOTktZGY0ZS00MmNkLThiODEtYTU1OWVkNDI4YzViIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTEiLCJuYmYiOjE3NjUxMzcyMTQsImNzcmYiOiI0ZTMzZTgzMy04Y2M1LTQ2OTktODFlMy1lZmMyMzY3YWE4YTciLCJleHAiOjE3Njc3MjkyMTR9.xz2nRM-m5qUF3sxy8V8ccoy2e9XtlK800_YmOjYzEW8','2025-12-07 19:53:35','2025-12-07 19:53:35'),(76,113,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTIxMDk4MywianRpIjoiZmI1NTQ5YTktODU1YS00MGVmLWE5Y2EtMDcxZDA5ZjcyOTYwIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTMiLCJuYmYiOjE3NjUyMTA5ODMsImNzcmYiOiI1YWY2ZTZhYy1kM2I0LTQ1NjYtYjAzYS01YzNiMGEyZmJlZTAiLCJleHAiOjE3Njc4MDI5ODN9.4stuC4wcLSv5EnbFqQHwthsjplDqLdV4pmz_wH8XSdc','2025-12-08 16:23:04','2025-12-08 16:23:04'),(82,114,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTI4MjUxMiwianRpIjoiN2NkMzFkZjAtNTE5Zi00M2ViLWJlOWYtMTVmMWJjYWRmOGM1IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTQiLCJuYmYiOjE3NjUyODI1MTIsImNzcmYiOiI3ZjViNDA4ZC0yOGY2LTRhZjAtYjhjYy05MjI1ZTI4MmQyYjciLCJleHAiOjE3Njc4NzQ1MTJ9.sWjBGBkwlvYGwFGD5YxyNa-nBHG1iXCGn1rjCXlOjgM','2025-12-09 12:15:13','2025-12-09 12:15:13'),(83,115,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTI4Mjk4OSwianRpIjoiOGI2ODRmOWUtOGY0Ni00MDFhLWI5NDUtNGU3MDU1ZjRjZTk4IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTUiLCJuYmYiOjE3NjUyODI5ODksImNzcmYiOiI2NjM5NWVhYi0zZjg0LTQxODgtOTE1ZC00NmQ4ZGVjN2YwZDAiLCJleHAiOjE3Njc4NzQ5ODl9.UxI4_RjqCO10xF-EiOmDPYITJplB1o0vWlIrWzGo6pE','2025-12-09 12:23:09','2025-12-09 12:23:09'),(88,107,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTQxMDUwNywianRpIjoiOTA4YWFhZjItYzRhMC00ZmVhLThhOGItZGQ2NTUyMWE1YTQ3IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDciLCJuYmYiOjE3NjU0MTA1MDcsImNzcmYiOiJlN2MyY2E4OS1mNDRjLTQ5YTMtYjVmNy0xNjc4M2I1NDg5MTYiLCJleHAiOjE3NjgwMDI1MDd9.6DwtPc8T1c6RMkLcKuWcewX73hkui3ZP_wJQit8roro','2025-12-10 23:48:28','2025-12-10 23:48:28'),(90,116,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTQzMDY5NSwianRpIjoiMTVkZjY0YzEtNWZiYi00NjVlLWE5YjMtM2U1ZGUyMjEwMzFmIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTYiLCJuYmYiOjE3NjU0MzA2OTUsImNzcmYiOiJhMmQ3ZTg1Yi01MzA1LTRlYjgtOGQ2MC0wMWQwZWIyM2M0YzUiLCJleHAiOjE3NjgwMjI2OTV9.nOcc2oXFg-KHHbtHUXAKZEMg_bU76DyPy7cx_Oo0JcE','2025-12-11 05:24:56','2025-12-11 05:24:56'),(93,117,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTQ5MDg1MywianRpIjoiYzJmNmVjMGYtODFiNy00ZjI3LTljZjYtYzE5ZTExMTBiMTJhIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTciLCJuYmYiOjE3NjU0OTA4NTMsImNzcmYiOiIxNjFhZTRiYy05Nzc5LTQwM2UtOTdlNS0xZDU2MGM4MjgxYjUiLCJleHAiOjE3NjgwODI4NTN9.9sT8FKma6FixLy9lpqsrDDzHttDEACULvVJSQ3ZnB_k','2025-12-11 22:07:34','2025-12-11 22:07:34'),(109,108,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTY4NDkxOSwianRpIjoiMmY5NzQ0Y2MtNThiMi00MGQ0LTg1ZGQtNjBiZDk5OWVlYTM5IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDgiLCJuYmYiOjE3NjU2ODQ5MTksImNzcmYiOiIwN2RiM2FmYS0xYWEyLTRlOTUtOTY3MC0zMmJhZmI5NzllNjciLCJleHAiOjE3NjgyNzY5MTl9.5zuF253IHzfBVxwVmad9ACk94RSbKATYwZPuO_s-OAQ','2025-12-14 04:02:00','2025-12-14 04:02:00'),(110,100,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTY4NzY1OCwianRpIjoiYWI2ZmM3NTgtYWQ5ZS00MmZlLTgyN2ItMTVkNTFmYjAzZWMyIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDAiLCJuYmYiOjE3NjU2ODc2NTgsImNzcmYiOiIwZDNkOGM5YS05MTY1LTRkNjktYTE4MS02NTBjMzRkOGU2MmUiLCJleHAiOjE3NjgyNzk2NTh9.yk8oPnwy8XWpSJd_l6wk1t8k8eJj96KqbGy7XrnnoRs','2025-12-14 04:47:39','2025-12-14 04:47:39'),(115,118,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTc3NjM2NywianRpIjoiZGE5ZDIwNDctNmVjMC00MzEyLWI0NmMtZDM4ZjFkOTY4OTc0IiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMTgiLCJuYmYiOjE3NjU3NzYzNjcsImNzcmYiOiIwZGM2MGE2NS04NDc2LTQ4NzktOTlhMi1kMzEyYjg4MDY3ZDUiLCJleHAiOjE3NjgzNjgzNjd9.lzh2m1VvLo2iDe8GqzKiSFSKc42wVNeBedZCw3rDosE','2025-12-15 05:26:07','2025-12-15 05:26:07'),(116,104,'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTc2NTgyMDgyOSwianRpIjoiZTc3OTQ5YWEtNzY2Ny00ZTVlLTg1YTItMGJjODM3ZGY0YTljIiwidHlwZSI6InJlZnJlc2giLCJzdWIiOiIxMDQiLCJuYmYiOjE3NjU4MjA4MjksImNzcmYiOiJjNjM3NzY1Mi05ODhhLTRkNzEtOWQzNS1hMGI2MGFiNGI1NzEiLCJleHAiOjE3Njg0MTI4Mjl9.BN9Jd7N-JP6o6fAxs4ydkYZnpr9mQU7W8kWDMSxH5EA','2025-12-15 17:47:10','2025-12-15 17:47:10');
/*!40000 ALTER TABLE `refresh_tokens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `resource_downloads`
--

DROP TABLE IF EXISTS `resource_downloads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `resource_downloads` (
  `id` int NOT NULL AUTO_INCREMENT,
  `resource_id` int NOT NULL,
  `user_id` int NOT NULL,
  `downloaded_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `resource_id` (`resource_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `resource_downloads_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `knowledge` (`id`) ON DELETE CASCADE,
  CONSTRAINT `resource_downloads_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `resource_downloads`
--

LOCK TABLES `resource_downloads` WRITE;
/*!40000 ALTER TABLE `resource_downloads` DISABLE KEYS */;
/*!40000 ALTER TABLE `resource_downloads` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `resource_likes`
--

DROP TABLE IF EXISTS `resource_likes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `resource_likes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `resource_id` int NOT NULL,
  `user_id` int NOT NULL,
  `liked_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `resource_id` (`resource_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `resource_likes_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `knowledge` (`id`) ON DELETE CASCADE,
  CONSTRAINT `resource_likes_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `resource_likes`
--

LOCK TABLES `resource_likes` WRITE;
/*!40000 ALTER TABLE `resource_likes` DISABLE KEYS */;
/*!40000 ALTER TABLE `resource_likes` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `resource_views`
--

DROP TABLE IF EXISTS `resource_views`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `resource_views` (
  `id` int NOT NULL AUTO_INCREMENT,
  `resource_id` int NOT NULL,
  `user_id` int NOT NULL,
  `viewed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `resource_id` (`resource_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `resource_views_ibfk_1` FOREIGN KEY (`resource_id`) REFERENCES `knowledge` (`id`) ON DELETE CASCADE,
  CONSTRAINT `resource_views_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `resource_views`
--

LOCK TABLES `resource_views` WRITE;
/*!40000 ALTER TABLE `resource_views` DISABLE KEYS */;
/*!40000 ALTER TABLE `resource_views` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `startup_bookmarks`
--

DROP TABLE IF EXISTS `startup_bookmarks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startup_bookmarks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `startup_id` int NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `content_preview` text,
  `url` varchar(500) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `startup_bookmarks_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `startup_bookmarks_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `startup_bookmarks`
--

LOCK TABLES `startup_bookmarks` WRITE;
/*!40000 ALTER TABLE `startup_bookmarks` DISABLE KEYS */;
/*!40000 ALTER TABLE `startup_bookmarks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `startup_documents`
--

DROP TABLE IF EXISTS `startup_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startup_documents` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int NOT NULL,
  `filename` varchar(255) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_url` varchar(500) DEFAULT NULL,
  `content_type` varchar(100) NOT NULL,
  `document_type` varchar(50) DEFAULT NULL,
  `visible_by` varchar(50) DEFAULT 'public',
  `file_size_mb` float NOT NULL DEFAULT 0.0,
  `uploaded_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  CONSTRAINT `startup_documents_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `startup_documents`
--

LOCK TABLES `startup_documents` WRITE;
/*!40000 ALTER TABLE `startup_documents` DISABLE KEYS */;
-- INSERT INTO `startup_documents` VALUES (1,21,'1000055985.pdf','E:\\LLMs_test\\uploads\\startups\\21\\20251125_184120_25647868.pdf',NULL,'application/pdf','general',6024385,'2025-11-25 18:41:20'),(2,21,'checkList.docx','E:\\LLMs_test\\uploads\\startups\\21\\20251125_184120_948cbc55.docx',NULL,'application/vnd.openxmlformats-officedocument.wordprocessingml.document','general',16549,'2025-11-25 18:41:20'),(3,22,'SX.pdf','E:\\LLMs_test\\uploads\\startups\\22\\20251125_192849_d2785b85.pdf',NULL,'application/pdf','general',89974,'2025-11-25 19:28:49'),(4,23,'nice.pdf','E:\\LLMs_test\\uploads\\startups\\23\\20251125_202432_4d3f81f8_nice.pdf','/api/startups/23/documents/20251125_202432_4d3f81f8_nice.pdf','application/pdf','general',52367,'2025-11-25 20:24:32'),(5,24,'checkList.docx','E:\\LLMs_test\\uploads\\startups\\24\\20251126_184943_be06e303_checkList.docx','/startups/24/documents/20251126_184943_be06e303_checkList.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document','general',16549,'2025-11-26 18:49:43'),(6,24,'Weekly Working Hours Availability (12_11_25 - 15_11_25) - Google Forms.pdf','E:\\LLMs_test\\uploads\\startups\\24\\20251126_184943_b70ecc95_Weekly_Working_Hours_Availability_12_11_25_-_15_11_25_-_Google_Forms.pdf','/startups/24/documents/20251126_184943_b70ecc95_Weekly_Working_Hours_Availability_12_11_25_-_15_11_25_-_Google_Forms.pdf','application/pdf','general',63779,'2025-11-26 18:49:43'),(7,0,'Nouveau Microsoft Word Document (2).docx','/opt/render/project/src/uploads/startups/0/20251128_023402_6f8f1976_Nouveau_Microsoft_Word_Document_2.docx','/startups/0/documents/20251128_023402_6f8f1976_Nouveau_Microsoft_Word_Document_2.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document','general',0,'2025-11-28 02:34:02'),(8,0,'Schema For The Ai Interviewer Based On The Dashboa.pdf','/opt/render/project/src/uploads/startups/0/20251128_023403_1efe6daf_Schema_For_The_Ai_Interviewer_Based_On_The_Dashboa.pdf','/startups/0/documents/20251128_023403_1efe6daf_Schema_For_The_Ai_Interviewer_Based_On_The_Dashboa.pdf','application/pdf','general',70534,'2025-11-28 02:34:03'),(9,0,'Weekly Working Hours Availability (12_11_25 - 15_11_25) - Google Forms.pdf','/opt/render/project/src/uploads/startups/0/20251128_023403_e23d53e0_Weekly_Working_Hours_Availability_12_11_25_-_15_11_25_-_Google_Forms.pdf','/startups/0/documents/20251128_023403_e23d53e0_Weekly_Working_Hours_Availability_12_11_25_-_15_11_25_-_Google_Forms.pdf','application/pdf','general',63779,'2025-11-28 02:34:04');
/*!40000 ALTER TABLE `startup_documents` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `startup_members`
--
DROP TABLE IF EXISTS `startup_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startup_members` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int NOT NULL,
  `user_id` int NOT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `role` varchar(100) DEFAULT NULL,
  `admin` tinyint(1) DEFAULT NULL,
  `joined_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `startup_members_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `startup_members_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `startup_members`
--

LOCK TABLES `startup_members` WRITE;
/*!40000 ALTER TABLE `startup_members` DISABLE KEYS */;
-- INSERT INTO `startup_members` VALUES (1,21,11,'','','founder','2025-11-25 18:41:20',1,'2025-11-25 18:41:20','2025-11-25 18:41:20'),(2,22,11,'Oskar','Alaoui','founder','2025-11-25 19:28:49',1,'2025-11-25 19:28:49','2025-11-25 19:28:49'),(3,23,11,'Oskar','ufgyufyu','founder','2025-11-25 20:24:32',1,'2025-11-25 20:24:32','2025-11-25 20:24:32'),(4,24,11,'','','founder','2025-11-26 18:49:43',1,'2025-11-26 18:49:43','2025-11-26 18:49:43'),(5,0,100,'Mohamed','','founder','2025-11-28 02:34:04',1,'2025-11-28 02:34:04','2025-11-28 02:34:04');
/*!40000 ALTER TABLE `startup_members` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `startups`
--

DROP TABLE IF EXISTS `startups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startups` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `industry` varchar(100) NOT NULL,
  `location` varchar(255) DEFAULT NULL,
  `description` text,
  `stage` enum('idea','validation','early','growth','scale') DEFAULT NULL,
  `revenue` float DEFAULT NULL,
  `funding_amount` float DEFAULT NULL,
  `funding_round` varchar(50) DEFAULT NULL,
  `burn_rate` float DEFAULT NULL,
  `runway_months` int DEFAULT NULL,
  `valuation` float DEFAULT NULL,
  `financial_notes` text,
  `logo_path` varchar(500) DEFAULT NULL,
  `logo_content_type` varchar(100) DEFAULT NULL,
  `banner_path` varchar(500) DEFAULT NULL,
  `banner_content_type` varchar(100) DEFAULT NULL,
  `logo_url` varchar(500) DEFAULT NULL,
  `banner_url` varchar(500) DEFAULT NULL,
  `tech_stack` json NOT NULL,
  `positions` int DEFAULT NULL,
  `roles` json DEFAULT NULL,
  `creator_id` int NOT NULL,
  `creator_first_name` varchar(100) DEFAULT NULL,
  `creator_last_name` varchar(100) DEFAULT NULL,
  `status` varchar(50) DEFAULT NULL,
  `member_count` int DEFAULT NULL,
  `views` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `creator_id` (`creator_id`),
  CONSTRAINT `startups_ibfk_1` FOREIGN KEY (`creator_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=26 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `startups`
--

LOCK TABLES `startups` WRITE;
/*!40000 ALTER TABLE `startups` DISABLE KEYS */;
-- INSERT INTO `startups` VALUES (21,'InterviewGenieAI','Manufacturing','MOROCCO ','edazdazd','idea',1000,1000,'pre-seed',1000,1,1000,'lzekjklzejdkjzed','E:\\LLMs_test\\uploads\\startups\\21\\20251125_184120_da634bd8.png','image/png','E:\\LLMs_test\\uploads\\startups\\21\\20251125_184120_6cf5cf0f.png','image/png','/startups/23/logo','/startups/23/banner','[\"JavaScript\", \"TypeScript\", \"Python\", \"React\"]',2,'{\"backend\": {\"roleType\": \"Full Time\", \"positionsNumber\": 1}, \"frontend\": {\"roleType\": \"Full Time\", \"positionsNumber\": 1}}',11,'','','active',1,4,'2025-11-25 18:41:20','2025-12-14 04:54:46'),(22,'SF MANAGER','Technology','MOROCCO ','azsazsaz','idea',1000,2000,'pre-seed',1000,1,1000,'erferferf','E:\\LLMs_test\\uploads\\startups\\22\\20251125_192849_1b0e0ba2.jpg','image/jpeg',NULL,'image/jpeg','/startups/23/logo','/startups/23/banner','[\"JavaScript\", \"TypeScript\", \"Python\", \"React\"]',3,'{\"backend\": {\"roleType\": \"Full Time\", \"positionsNumber\": 2}, \"frontend\": {\"roleType\": \"Full Time\", \"positionsNumber\": 1}}',11,'Oskar','Alaoui','active',1,4,'2025-11-25 19:28:49','2025-12-11 18:57:11'),(23,'new startup','Technology','Morocco','zertfyguhiokplhgfg','idea',1000,1000,'pre-seed',1000,1,1000,'xeyuiop;m','E:\\LLMs_test\\uploads\\startups\\23\\20251125_202431_052e644a_file_000000000a9861f5868855fffc87f260.png','image/png','E:\\LLMs_test\\uploads\\startups\\23\\20251125_202431_2f276357_Capture_decran_2025-11-05_230140.png','image/png','/startups/23/logo','/startups/23/banner','[\"JavaScript\", \"Python\"]',3,'{\"AI Engineer\": {\"roleType\": \"Full Time\", \"positionsNumber\": 3}}',11,'Oskar','ufgyufyu','active',1,430,'2025-11-25 20:24:31','2025-12-12 03:24:30'),(24,'SF COLLAB','Technology','USA','sjkhkldjklsjd','idea',2000,2000,'pre-seed',1000,1,3000,'notess','E:\\LLMs_test\\uploads\\startups\\24\\20251126_184943_5256296a_stars.png','image/png','E:\\LLMs_test\\uploads\\startups\\24\\20251126_184943_906abcb6_ChatGPT_Image_5_nov._2025_00_44_28.png','image/png','/startups/24/logo','/startups/24/banner','[\"JavaScript\", \"Angular\", \"Python\"]',6,'{\"backend\": {\"roleType\": \"Intern\", \"positionsNumber\": 2}, \"frontend \": {\"roleType\": \"Intern\", \"positionsNumber\": 4}}',104,'','','active',1,12,'2025-11-26 18:49:43','2025-12-14 04:54:02'),(25,'PatternsChange','Finance','Morocco','uhdihzdz \"Tell us more about your vision and stage\r\n\"','',4000,35000,'pre-seed',4000,2,4000,'zkladjlazjdkazd','/opt/render/project/src/uploads/startups/0/20251128_023402_e5d23a3a_file_000000000a9861f5868855fffc87f260.png','image/png','/opt/render/project/src/uploads/startups/0/20251128_023402_8a64f726_file_0000000037f46246aaeebb8a0c79b3fd.png','image/png','/startups/0/logo','/startups/0/banner','[\"JavaScript\", \"TypeScript\", \"React\"]',4,'{\"backend\": {\"roleType\": \"Full Time\", \"positionsNumber\": 2}, \"frontend\": {\"roleType\": \"Full Time\", \"positionsNumber\": 2}}',104,'Mohamed','','active',1,2,'2025-11-28 02:34:02','2025-11-28 14:42:34');
/*!40000 ALTER TABLE `startups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stories`
--

DROP TABLE IF EXISTS `stories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `media_url` varchar(500) NOT NULL,
  `caption` text,
  `type` enum('image','video') DEFAULT NULL,
  `views` int DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `stories_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`),
  CONSTRAINT `stories_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stories`
--

LOCK TABLES `stories` WRITE;
/*!40000 ALTER TABLE `stories` DISABLE KEYS */;
/*!40000 ALTER TABLE `stories` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `story_views`
--

DROP TABLE IF EXISTS `story_views`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `story_views` (
  `id` int NOT NULL AUTO_INCREMENT,
  `story_id` int NOT NULL,
  `user_id` int NOT NULL,
  `viewed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `story_id` (`story_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `story_views_ibfk_1` FOREIGN KEY (`story_id`) REFERENCES `stories` (`id`) ON DELETE CASCADE,
  CONSTRAINT `story_views_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `story_views`
--

LOCK TABLES `story_views` WRITE;
/*!40000 ALTER TABLE `story_views` DISABLE KEYS */;
/*!40000 ALTER TABLE `story_views` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `suggestions`
--

DROP TABLE IF EXISTS `suggestions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `suggestions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `idea_id` int NOT NULL,
  `content` text NOT NULL,
  `author_id` int NOT NULL,
  `author_first_name` varchar(100) DEFAULT NULL,
  `author_last_name` varchar(100) DEFAULT NULL,
  `status` enum('pending','accepted','rejected') DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `author_id` (`author_id`),
  KEY `idea_id` (`idea_id`),
  CONSTRAINT `suggestions_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `users` (`id`),
  CONSTRAINT `suggestions_ibfk_2` FOREIGN KEY (`idea_id`) REFERENCES `ideas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `suggestions`
--

LOCK TABLES `suggestions` WRITE;
/*!40000 ALTER TABLE `suggestions` DISABLE KEYS */;
/*!40000 ALTER TABLE `suggestions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tasks`
--

DROP TABLE IF EXISTS `tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `startup_id` int DEFAULT NULL,
  `title` varchar(255) NOT NULL,
  `description` text,
  `priority` enum('low','medium','high') DEFAULT NULL,
  `status` enum('to_do','in_progress','completed','overdue') DEFAULT NULL,
  `tags` json DEFAULT NULL,
  `labels` json DEFAULT NULL,
  `due_date` datetime DEFAULT NULL,
  `urgent` tinyint(1) DEFAULT NULL,
  `completed_date` datetime DEFAULT NULL,
  `estimated_hours` float DEFAULT NULL,
  `actual_hours` float DEFAULT NULL,
  `assigned_to` int DEFAULT NULL,
  `created_by` int NOT NULL,
  `is_on_time` tinyint(1) DEFAULT NULL,
  `progress_percentage` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `visible_by` varchar(50) DEFAULT 'all',
  PRIMARY KEY (`id`),
  KEY `assigned_to` (`assigned_to`),
  KEY `created_by` (`created_by`),
  KEY `startup_id` (`startup_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`assigned_to`) REFERENCES `users` (`id`),
  CONSTRAINT `tasks_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  CONSTRAINT `tasks_ibfk_3` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`),
  CONSTRAINT `tasks_ibfk_4` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tasks`
--

LOCK TABLES `tasks` WRITE;
/*!40000 ALTER TABLE `tasks` DISABLE KEYS */;
/*!40000 ALTER TABLE `tasks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `team_members`
--

DROP TABLE IF EXISTS `team_members`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `team_members` (
  `id` int NOT NULL AUTO_INCREMENT,
  `idea_id` int NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `position` varchar(255) DEFAULT NULL,
  `skills` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idea_id` (`idea_id`),
  CONSTRAINT `team_members_ibfk_1` FOREIGN KEY (`idea_id`) REFERENCES `ideas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `team_members`
--

LOCK TABLES `team_members` WRITE;
/*!40000 ALTER TABLE `team_members` DISABLE KEYS */;
--INSERT INTO `team_members` VALUES (1,17,'Jane Smith','CTO','\"Python, React, AWS\"'),(2,17,'Jane Smith','CTO','\"Python, React, AWS\"');
/*!40000 ALTER TABLE `team_members` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `team_performance`
--

DROP TABLE IF EXISTS `team_performance`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `team_performance` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int NOT NULL,
  `score_percentage` float DEFAULT NULL,
  `active_members` int DEFAULT NULL,
  `tasks_completed` int DEFAULT NULL,
  `productivity_level` enum('low','medium','high') DEFAULT NULL,
  `period_start` datetime NOT NULL,
  `period_end` datetime NOT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `startup_id` (`startup_id`),
  CONSTRAINT `team_performance_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `team_performance`
--

LOCK TABLES `team_performance` WRITE;
/*!40000 ALTER TABLE `team_performance` DISABLE KEYS */;
/*!40000 ALTER TABLE `team_performance` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_achievements`
--

DROP TABLE IF EXISTS `user_achievements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_achievements` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `achievement_id` int NOT NULL,
  `unlocked_at` datetime DEFAULT NULL,
  `progress_percentage` int DEFAULT NULL,
  `is_completed` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `achievement_id` (`achievement_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `user_achievements_ibfk_1` FOREIGN KEY (`achievement_id`) REFERENCES `achievements` (`id`),
  CONSTRAINT `user_achievements_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_achievements`
--

LOCK TABLES `user_achievements` WRITE;
/*!40000 ALTER TABLE `user_achievements` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_achievements` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `permissions`
--

DROP TABLE IF EXISTS `permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `key` varchar(100) NOT NULL,
  `description` text,
  `category` varchar(50) DEFAULT 'General',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `key` (`key`),
  KEY `ix_permissions_key` (`key`),
  KEY `ix_permissions_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `permissions`
--

LOCK TABLES `permissions` WRITE;
/*!40000 ALTER TABLE `permissions` DISABLE KEYS */;
INSERT INTO `permissions` (`key`, `description`, `category`) VALUES
('app_access', 'Access to the application', 'Basic'),
('profile_edit', 'Edit own profile', 'Basic'),
('notifications_view', 'View notifications', 'Basic'),
('idea_create', 'Create ideas', 'Content'),
('idea_edit', 'Edit own ideas', 'Content'),
('knowledge_create', 'Create knowledge posts', 'Content'),
('knowledge_edit', 'Edit own knowledge posts', 'Content'),
('post_create', 'Create posts', 'Content'),
('post_edit', 'Edit own posts', 'Content'),
('startup_create', 'Create startups', 'Content'),
('startup_edit', 'Edit own startups', 'Content'),
('comment_create', 'Create comments', 'Social'),
('like_content', 'Like content', 'Social'),
('follow_users', 'Follow other users', 'Social'),
('send_messages', 'Send messages', 'Social'),
('admin', 'Full admin access', 'Administration'),
('admin_dashboard', 'Access admin dashboard', 'Administration'),
('user_management', 'Manage users', 'Administration'),
('content_moderation', 'Moderate content', 'Administration'),
('system_settings', 'Manage system settings', 'Administration'),
('chat_ai_access', 'Access AI chat features', 'AI Tools'),
('chat_ai_qwen', 'Access Qwen AI model', 'AI Tools'),
('chat_ai_gemini', 'Access Gemini AI model', 'AI Tools'),
('tools_image_generate', 'Generate images', 'Media Tools'),
('tools_image_edit', 'Edit images', 'Media Tools'),
('tools_background_remove', 'Remove image backgrounds', 'Media Tools'),
('tools_anime_convert', 'Convert images to anime style', 'Media Tools'),
('tools_pdf_sign', 'Sign PDF documents', 'Document Tools'),
('tools_pdf_edit', 'Edit PDF documents', 'Document Tools'),
('tools_logo_generate', 'Generate logos', 'Document Tools'),
('tools_business_plan', 'Create business plans', 'Document Tools');
/*!40000 ALTER TABLE `permissions` ENABLE KEYS */;
UNLOCK TABLES;




DROP TABLE IF EXISTS `user_roles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_roles` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `role` VARCHAR(50) NOT NULL,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT `unique_user_role`
    UNIQUE (`user_id`, `role`)
);


LOCK TABLES `user_roles` WRITE;
/*!40000 ALTER TABLE `user_roles` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_roles` ENABLE KEYS */;
UNLOCK TABLES;
/*!40101 SET character_set_client = @saved_cs_client */;



-- Table structure for table `application_jobs`

DROP TABLE IF EXISTS `application_jobs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `application_jobs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `email` varchar(255) NOT NULL,
  `country` varchar(100) DEFAULT NULL,
  `application_type` varchar(50) NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `user_id` int DEFAULT NULL,
  `data` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_application_jobs_email` (`email`),
  KEY `ix_application_jobs_application_type` (`application_type`),
  KEY `ix_application_jobs_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `application_jobs`
--

LOCK TABLES `application_jobs` WRITE;
/*!40000 ALTER TABLE `application_jobs` DISABLE KEYS */;
/*!40000 ALTER TABLE `application_jobs` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `contribution_ideas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contribution_ideas` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` text NOT NULL,
  `impact` varchar(50) NOT NULL,
  `area` varchar(100) NOT NULL,
  `status` varchar(50) NOT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `contribution_ideas_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
LOCK TABLES `contribution_ideas` WRITE;
/*!40000 ALTER TABLE `contribution_ideas` DISABLE KEYS */;
/*!40000 ALTER TABLE `contribution_ideas` ENABLE KEYS */;
UNLOCK TABLES;
/*!40101 SET character_set_client = @saved_cs_client */;
--
-- Table structure for table `users`
--
CREATE TABLE `plans` (
  `id` varchar(50) NOT NULL,
  `name` varchar(50) NOT NULL,
  `price_cents` int NOT NULL,
  `interval` varchar(20) NOT NULL,
  `stripe_price_id` varchar(100) NOT NULL,
  `features` json DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

LOCK TABLES `plans` WRITE;
/*!40000 ALTER TABLE `plans` DISABLE KEYS */;
/*!40000 ALTER TABLE `plans` ENABLE KEYS */;
UNLOCK TABLES;





DROP TABLE IF EXISTS `contribution_polls`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contribution_polls` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` text NOT NULL,
  `options` json NOT NULL,
  `points` int NOT NULL,
  `votes` json DEFAULT NULL,
  `users_voted` json DEFAULT NULL,
  `ends_in_days` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `contribution_polls` WRITE;
/*!40000 ALTER TABLE `contribution_polls` DISABLE KEYS */;
/*!40000 ALTER TABLE `contribution_polls` ENABLE KEYS */;
UNLOCK TABLES;


SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

--
-- Table structure for table `user_permissions`
--



DROP TABLE IF EXISTS `user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_permissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  `granted_by` int DEFAULT NULL,
  `starts_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_permission` (`user_id`,`permission_id`),
  KEY `idx_user_permissions_user_id` (`user_id`),
  KEY `idx_user_permissions_permission_id` (`permission_id`),
  KEY `idx_user_permissions_expires` (`expires_at`),
  KEY `idx_user_permissions_active` (`user_id`,`permission_id`,`expires_at`),
  CONSTRAINT `fk_user_permissions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_permissions_permission_id` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_permissions_granted_by` FOREIGN KEY (`granted_by`) REFERENCES `users` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_permissions`
--

LOCK TABLES `user_permissions` WRITE;
/*!40000 ALTER TABLE `user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `access_requests`
--

DROP TABLE IF EXISTS `access_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `access_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  `status` varchar(20) DEFAULT 'pending',
  `reason` text,
  `reviewed_by` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_access_requests_user_id` (`user_id`),
  KEY `idx_access_requests_permission_id` (`permission_id`),
  KEY `idx_access_requests_status` (`status`),
  CONSTRAINT `fk_access_requests_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_access_requests_permission_id` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_access_requests_reviewed_by` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `access_requests`
--

LOCK TABLES `access_requests` WRITE;
/*!40000 ALTER TABLE `access_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `access_requests` ENABLE KEYS */;
UNLOCK TABLES;

-- Dump completed on 2025-12-15 20:46:17
DROP TABLE IF EXISTS `transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int,
  `plan_id` varchar(255),
  `stripe_payment_intent_id` varchar(255) UNIQUE,
  `stripe_checkout_session_id` varchar(255) UNIQUE,
  `type` varchar(50) DEFAULT 'subscription',
  `donation_message` text DEFAULT NULL,
  `amount` int,
  `currency` varchar(50),
  `status` varchar(50),
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_transactions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

-- Table structure for table `builder_profiles`

DROP TABLE IF EXISTS `builder_profiles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `builder_profiles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `bio` text,
  `hourly_rate` float DEFAULT NULL,
  `rating` float DEFAULT 0.0,
  `review_count` int DEFAULT 0,
  `completed_projects` int DEFAULT 0,
  `total_earnings` float DEFAULT 0.0,
  `total_equity_earned` float DEFAULT 0.0,
  `on_time_delivery_rate` float DEFAULT 100.0,
  `preferred_work_type` json DEFAULT NULL,
  `industries_interested` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_builder_profiles_user_id` (`user_id`),
  KEY `idx_builder_profiles_user_id` (`user_id`),
  CONSTRAINT `fk_builder_profiles_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

-- Table structure for table `builder_skills`

DROP TABLE IF EXISTS `builder_skills`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `builder_skills` (
  `id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int NOT NULL,
  `name` varchar(100) NOT NULL,
  `level` varchar(50) DEFAULT NULL,
  `years_of_experience` int DEFAULT NULL,
  `is_verified` tinyint(1) DEFAULT 0,
  `verified_by_user_id` int DEFAULT NULL,
  `verification_date` datetime DEFAULT NULL,
  `endorsement_count` int DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_builder_skills_profile_id` (`profile_id`),
  KEY `idx_builder_skills_verified_by` (`verified_by_user_id`),
  CONSTRAINT `fk_builder_skills_profile_id` FOREIGN KEY (`profile_id`) REFERENCES `builder_profiles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_builder_skills_verified_by` FOREIGN KEY (`verified_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

-- Table structure for table `builder_portfolio`

DROP TABLE IF EXISTS `builder_portfolio`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `builder_portfolio` (
  `id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text,
  `url` varchar(500) DEFAULT NULL,
  `image_url` varchar(500) DEFAULT NULL,
  `project_type` varchar(100) DEFAULT NULL,
  `skills_used` json DEFAULT NULL,
  `likes` int DEFAULT 0,
  `views` int DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_builder_portfolio_profile_id` (`profile_id`),
  CONSTRAINT `fk_builder_portfolio_profile_id` FOREIGN KEY (`profile_id`) REFERENCES `builder_profiles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

-- Table structure for table `builder_applications`

DROP TABLE IF EXISTS `builder_applications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `builder_applications` (
  `id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int NOT NULL,
  `startup_id` int NOT NULL,
  `status` enum('pending','under_review','accepted','rejected','withdrawn') DEFAULT 'pending',
  `role_applied_for` varchar(255) DEFAULT NULL,
  `cover_letter` text,
  `expected_commitment` varchar(100) DEFAULT NULL,
  `proposed_rate` float DEFAULT NULL,
  `last_message` text,
  `last_message_date` datetime DEFAULT NULL,
  `applied_date` datetime DEFAULT CURRENT_TIMESTAMP,
  `review_date` datetime DEFAULT NULL,
  `withdrawn_date` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_builder_applications_profile_id` (`profile_id`),
  KEY `idx_builder_applications_startup_id` (`startup_id`),
  KEY `idx_builder_applications_status` (`status`),
  KEY `idx_builder_applications_applied_date` (`applied_date`),
  CONSTRAINT `fk_builder_applications_profile_id` FOREIGN KEY (`profile_id`) REFERENCES `builder_profiles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_builder_applications_startup_id` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

-- Table structure for table `saved_startups`

DROP TABLE IF EXISTS `saved_startups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `saved_startups` (
  `id` int NOT NULL AUTO_INCREMENT,
  `profile_id` int NOT NULL,
  `startup_id` int NOT NULL,
  `notes` text,
  `is_interested` tinyint(1) DEFAULT 1,
  `saved_date` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_builder_startup_save` (`profile_id`,`startup_id`),
  KEY `idx_saved_startups_profile_id` (`profile_id`),
  KEY `idx_saved_startups_startup_id` (`startup_id`),
  KEY `idx_saved_startups_saved_date` (`saved_date`),
  CONSTRAINT `fk_saved_startups_profile_id` FOREIGN KEY (`profile_id`) REFERENCES `builder_profiles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_saved_startups_startup_id` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `builder_profiles` WRITE;
/*!40000 ALTER TABLE `builder_profiles` DISABLE KEYS */;
/*!40000 ALTER TABLE `builder_profiles` ENABLE KEYS */;
UNLOCK TABLES;

LOCK TABLES `builder_skills` WRITE;
/*!40000 ALTER TABLE `builder_skills` DISABLE KEYS */;
/*!40000 ALTER TABLE `builder_skills` ENABLE KEYS */;
UNLOCK TABLES;

LOCK TABLES `builder_portfolio` WRITE;
/*!40000 ALTER TABLE `builder_portfolio` DISABLE KEYS */;
/*!40000 ALTER TABLE `builder_portfolio` ENABLE KEYS */;
UNLOCK TABLES;

LOCK TABLES `builder_applications` WRITE;
/*!40000 ALTER TABLE `builder_applications` DISABLE KEYS */;
/*!40000 ALTER TABLE `builder_applications` ENABLE KEYS */;
UNLOCK TABLES;

LOCK TABLES `saved_startups` WRITE;
/*!40000 ALTER TABLE `saved_startups` DISABLE KEYS */;
/*!40000 ALTER TABLE `saved_startups` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `user_social`;
CREATE TABLE `user_social` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL UNIQUE,
  `followers_count` INT DEFAULT 0,
  `following_count` INT DEFAULT 0,
  `follower_ids` JSON DEFAULT NULL,
  `following_ids` JSON DEFAULT NULL,
  `total_likes_given` INT DEFAULT 0,
  `total_likes_received` INT DEFAULT 0,
  `total_shares` INT DEFAULT 0,
  `total_views` INT DEFAULT 0,
  `saved_post_ids` JSON DEFAULT NULL,
  `saved_idea_ids` JSON DEFAULT NULL,
  `saved_startup_ids` JSON DEFAULT NULL,
  `liked_post_ids` JSON DEFAULT NULL,
  `liked_idea_ids` JSON DEFAULT NULL,
  `liked_startup_ids` JSON DEFAULT NULL,
  `liked_comment_ids` JSON DEFAULT NULL,
  `stories_count` INT DEFAULT 0,
  `archived_story_ids` JSON DEFAULT NULL,
  `story_highlights` JSON DEFAULT NULL,
  `posts_count` INT DEFAULT 0,
  `pinned_post_ids` JSON DEFAULT NULL,
  `pref_suggested_accounts` BOOLEAN DEFAULT TRUE,
  `pref_suggested_content` BOOLEAN DEFAULT TRUE,
  `pref_suggested_hashtags` BOOLEAN DEFAULT TRUE,
  `interest_tags` JSON DEFAULT NULL,
  `preferred_content_types` JSON DEFAULT NULL,
  `blocked_keywords` JSON DEFAULT NULL,
  `match_preferences` JSON DEFAULT NULL,
  `blocked_user_ids` JSON DEFAULT NULL,
  `muted_user_ids` JSON DEFAULT NULL,
  `profile_visibility` ENUM('public', 'private') DEFAULT 'public',
  `allow_messages_from` VARCHAR(50) DEFAULT 'everyone',
  `allow_collaboration_requests` BOOLEAN DEFAULT TRUE,
  `engagement_rate` FLOAT DEFAULT 0.0,
  `reputation_score` FLOAT DEFAULT 0.0,
  `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `idea_likes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `idea_likes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `idea_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `idea_id` (`idea_id`),
  CONSTRAINT `idea_likes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `idea_likes_ibfk_2` FOREIGN KEY (`idea_id`) REFERENCES `ideas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `idea_likes` WRITE;
/*!40000 ALTER TABLE `idea_likes` DISABLE KEYS */;
/*!40000 ALTER TABLE `idea_likes` ENABLE KEYS */;
UNLOCK TABLES;

-- Table structure for table `user_wallets`

DROP TABLE IF EXISTS `user_wallets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_wallets` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `sf_coins` int DEFAULT 0,
  `credits` int DEFAULT 0,
  `premium_gems` int DEFAULT 0,
  `event_tokens` int DEFAULT 0,
  `total_coins_earned` int DEFAULT 0,
  `total_coins_spent` int DEFAULT 0,
  `daily_earnings` int DEFAULT 0,
  `daily_earning_limit` int DEFAULT 1000,
  `last_earning_reset` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_user_wallet` (`user_id`),
  KEY `idx_user_wallets_user_id` (`user_id`),
  CONSTRAINT `fk_user_wallets_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `user_wallets` WRITE;
/*!40000 ALTER TABLE `user_wallets` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_wallets` ENABLE KEYS */;
UNLOCK TABLES;

-- Table structure for table `wallet_transactions`

DROP TABLE IF EXISTS `wallet_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wallet_transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `wallet_id` int NOT NULL,
  `user_id` int NOT NULL,
  `transaction_type` varchar(20) NOT NULL,
  `currency_type` varchar(20) NOT NULL,
  `amount` int NOT NULL,
  `balance_before` int NOT NULL,
  `balance_after` int NOT NULL,
  `xp_amount` int DEFAULT 0,
  `exchange_rate` float DEFAULT 0,
  `reference_type` text,
  `reference_id` varchar(255),
  `description` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_wallet_transactions_wallet_id` (`wallet_id`),
  KEY `idx_wallet_transactions_user_id` (`user_id`),
  KEY `idx_wallet_transactions_created_at` (`created_at`),
  CONSTRAINT `fk_wallet_transactions_wallet_id` FOREIGN KEY (`wallet_id`) REFERENCES `user_wallets` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_wallet_transactions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `wallet_transactions` WRITE;
/*!40000 ALTER TABLE `wallet_transactions` DISABLE KEYS */;
/*!40000 ALTER TABLE `wallet_transactions` ENABLE KEYS */;
UNLOCK TABLES;

-- Table structure for table `event_token_balances`

DROP TABLE IF EXISTS `event_token_balances`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `event_token_balances` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `wallet_id` int NOT NULL,
  `event_key` varchar(255) NOT NULL,
  `balance` int DEFAULT 0,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_event_token_balances_user_id` (`user_id`),
  KEY `idx_event_token_balances_wallet_id` (`wallet_id`),
  KEY `idx_event_token_balances_event_key` (`event_key`),
  CONSTRAINT `fk_event_token_balances_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_event_token_balances_wallet_id` FOREIGN KEY (`wallet_id`) REFERENCES `user_wallets` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `event_token_balances` WRITE;
/*!40000 ALTER TABLE `event_token_balances` DISABLE KEYS */;
/*!40000 ALTER TABLE `event_token_balances` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `errors`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `errors` (
  `id` int NOT NULL AUTO_INCREMENT,
  `error_message` varchar(500) NOT NULL,
  `error_from_backend` varchar(255) DEFAULT NULL,
  `stack` text,
  `page` varchar(255) DEFAULT NULL,
  `component` varchar(255) DEFAULT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_errors_timestamp` (`timestamp`),
  KEY `idx_errors_created_at` (`created_at`),
  KEY `idx_errors_error_from_backend` (`error_from_backend`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `errors` WRITE;
/*!40000 ALTER TABLE `errors` DISABLE KEYS */;
/*!40000 ALTER TABLE `errors` ENABLE KEYS */;
UNLOCK TABLES;


DROP TABLE IF EXISTS `startup_views`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startup_views` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `startup_id` int NOT NULL,
  `viewed_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `startup_id` (`startup_id`),
  CONSTRAINT `startup_views_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `startup_views_ibfk_2` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `startup_views`
--

LOCK TABLES `startup_views` WRITE;
/*!40000 ALTER TABLE `startup_views` DISABLE KEYS */;
/*!40000 ALTER TABLE `startup_views` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `idea_comment_likes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `idea_comment_likes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `comment_id` int NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `comment_id` (`comment_id`),
  CONSTRAINT `idea_comment_likes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `idea_comment_likes_ibfk_2` FOREIGN KEY (`comment_id`) REFERENCES `idea_comments` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `idea_comment_likes` WRITE;
/*!40000 ALTER TABLE `idea_comment_likes` DISABLE KEYS */;
/*!40000 ALTER TABLE `idea_comment_likes` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `pitch_decks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pitch_decks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `company_name` varchar(255) NOT NULL,
  `tagline` varchar(500) DEFAULT NULL,
  `template` varchar(50) NOT NULL DEFAULT 'general',
  `sector` varchar(100) DEFAULT NULL,
  `form_data` json DEFAULT NULL,
  `generated_content` json DEFAULT NULL,
  `file_path` varchar(500) DEFAULT NULL,
  `file_name` varchar(255) DEFAULT NULL,
  `status` varchar(50) DEFAULT 'pending',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `status` (`status`),
  CONSTRAINT `pitch_decks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `pitch_decks` WRITE;
/*!40000 ALTER TABLE `pitch_decks` DISABLE KEYS */;
/*!40000 ALTER TABLE `pitch_decks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sessions` (Flask-Session)
--

DROP TABLE IF EXISTS `sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sessions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `session_id` varchar(255) DEFAULT NULL,
  `data` blob,
  `expiry` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_id` (`session_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `sessions` WRITE;
/*!40000 ALTER TABLE `sessions` DISABLE KEYS */;
/*!40000 ALTER TABLE `sessions` ENABLE KEYS */;
UNLOCK TABLES;


DROP TABLE IF EXISTS `plan_versions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `plan_versions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `plan_id` int NOT NULL,
  `version_number` int NOT NULL,
  `trigger_type` varchar(50) DEFAULT NULL,
  `summary` text,
  `health_score` int DEFAULT NULL,
  `health_status` varchar(30) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `plan_id` (`plan_id`),
  CONSTRAINT `plan_versions_ibfk_1` FOREIGN KEY (`plan_id`) REFERENCES `business_plans` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `plan_versions` WRITE;
/*!40000 ALTER TABLE `plan_versions` DISABLE KEYS */;
/*!40000 ALTER TABLE `plan_versions` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `startup_invitations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startup_invitations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `startup_id` int NOT NULL,
  `invited_user_id` int NOT NULL,
  `invited_by_id` int DEFAULT NULL,
  `role` varchar(100) NOT NULL,
  `status` enum('pending','accepted','rejected','expired') DEFAULT 'pending',
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `responded_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_startup_invitation` (`startup_id`,`invited_user_id`),
  KEY `startup_id` (`startup_id`),
  KEY `invited_user_id` (`invited_user_id`),
  KEY `invited_by_id` (`invited_by_id`),
  CONSTRAINT `startup_invitations_ibfk_1` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`) ON DELETE CASCADE,
  CONSTRAINT `startup_invitations_ibfk_2` FOREIGN KEY (`invited_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `startup_invitations_ibfk_3` FOREIGN KEY (`invited_by_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `startup_invitations` WRITE;
/*!40000 ALTER TABLE `startup_invitations` DISABLE KEYS */;
/*!40000 ALTER TABLE `startup_invitations` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `ai_news_articles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ai_news_articles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(500) NOT NULL,
  `url` varchar(750) NOT NULL,
  `summary` text,
  `author` varchar(255) DEFAULT NULL,
  `image_url` varchar(750) DEFAULT NULL,
  `source` varchar(100) NOT NULL,
  `source_label` varchar(100) DEFAULT NULL,
  `category` varchar(100) DEFAULT NULL,
  `tags` text,
  `impact_score` int DEFAULT 5,
  `published_at` datetime DEFAULT NULL,
  `scraped_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `is_active` tinyint(1) DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_url` (`url`),
  KEY `idx_source` (`source`),
  KEY `idx_category` (`category`),
  KEY `idx_published_at` (`published_at`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `ai_news_articles` WRITE;
/*!40000 ALTER TABLE `ai_news_articles` DISABLE KEYS */;
/*!40000 ALTER TABLE `ai_news_articles` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `idea_collab_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `idea_collab_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `idea_id` int NOT NULL,
  `idea_title` varchar(255) DEFAULT NULL,
  `user_id` int NOT NULL,
  `first_name` varchar(100) DEFAULT NULL,
  `last_name` varchar(100) DEFAULT NULL,
  `message` text,
  `role` varchar(100) DEFAULT 'co-developer',
  `status` enum('pending','approved','rejected','cancelled') DEFAULT 'pending',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idea_id` (`idea_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `idea_collab_requests_ibfk_1` FOREIGN KEY (`idea_id`) REFERENCES `ideas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `idea_collab_requests_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `idea_collab_requests` WRITE;
/*!40000 ALTER TABLE `idea_collab_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `idea_collab_requests` ENABLE KEYS */;
UNLOCK TABLES;
--
-- Table structure for table `startup_ratings`
--

DROP TABLE IF EXISTS `startup_ratings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `startup_ratings` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `startup_id` int NOT NULL,
  `rating` float NOT NULL,
  `review_text` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`,`startup_id`),
  KEY `startup_id` (`startup_id`),
  CONSTRAINT `startup_ratings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `startup_ratings_ibfk_2` FOREIGN KEY (`startup_id`) REFERENCES `startups` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

DROP TABLE IF EXISTS `friend_request`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `friend_request` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sender_id` int NOT NULL,
  `receiver_id` int NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'pending',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_friend_request` (`sender_id`,`receiver_id`),
  CHECK (`sender_id` != `receiver_id`),
  KEY `ix_friend_request_sender_id` (`sender_id`),
  KEY `ix_friend_request_receiver_id` (`receiver_id`),
  KEY `ix_friend_request_status` (`status`),
  CONSTRAINT `friend_request_ibfk_1` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `friend_request_ibfk_2` FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `friend_request` WRITE;
/*!40000 ALTER TABLE `friend_request` DISABLE KEYS */;
/*!40000 ALTER TABLE `friend_request` ENABLE KEYS */;
UNLOCK TABLES;
-- ------------------------------------------------------
-- ADDED VIA POWERSHELL: Economy & Escrow Layer
-- ------------------------------------------------------

CREATE TABLE IF NOT EXISTS crystal_wallets (
  id int NOT NULL AUTO_INCREMENT,
  user_id int NOT NULL,
  alance int DEFAULT 0,
  updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY user_id (user_id),
  CONSTRAINT crystal_wallets_ibfk_1 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS isibility_boosts (
  id int NOT NULL AUTO_INCREMENT,
  user_id int NOT NULL,
  startup_id int NOT NULL,
  oost_type varchar(50) NOT NULL,
  expires_at datetime NOT NULL,
  is_active tinyint(1) DEFAULT 1,
  PRIMARY KEY (id),
  CONSTRAINT isibility_boosts_ibfk_1 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alances (
  id int NOT NULL AUTO_INCREMENT,
  user_id int NOT NULL,
  vailable int NOT NULL DEFAULT 0,
  pending int NOT NULL DEFAULT 0,
  escrow_locked int NOT NULL DEFAULT 0,
  	otal_deposited int NOT NULL DEFAULT 0,
  	otal_withdrawn int NOT NULL DEFAULT 0,
  	otal_paid_out int NOT NULL DEFAULT 0,
  currency varchar(3) NOT NULL DEFAULT 'USD',
  created_at datetime DEFAULT CURRENT_TIMESTAMP,
  updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY ux_balances_user_id (user_id),
  CONSTRAINT alances_ibfk_1 FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS escrow_transactions (
  id int NOT NULL AUTO_INCREMENT,
  payer_id int NOT NULL,
  payee_id int NOT NULL,
  payer_balance_id int NOT NULL,
  payee_balance_id int DEFAULT NULL,
  mount_cents int NOT NULL,
  currency varchar(3) NOT NULL DEFAULT 'USD',
  status varchar(30) NOT NULL DEFAULT 'created',
  created_at datetime DEFAULT CURRENT_TIMESTAMP,
  updated_at datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT escrow_ibfk_1 FOREIGN KEY (payer_id) REFERENCES users (id),
  CONSTRAINT escrow_ibfk_2 FOREIGN KEY (payee_id) REFERENCES users (id),
  CONSTRAINT escrow_ibfk_3 FOREIGN KEY (payer_balance_id) REFERENCES alances (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS alance_transactions (
  id int NOT NULL AUTO_INCREMENT,
  alance_id int NOT NULL,
  user_id int NOT NULL,
  	x_type varchar(30) NOT NULL,
  mount int NOT NULL,
  alance_before int NOT NULL,
  alance_after int NOT NULL,
  created_at datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  CONSTRAINT alance_tx_ibfk_1 FOREIGN KEY (alance_id) REFERENCES alances (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DROP TABLE IF EXISTS `visions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;

CREATE TABLE `visions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `creator_id` int NOT NULL,
  `title` varchar(255) NOT NULL,
  `problem_statement` text NOT NULL,
  `solution` text NOT NULL,
  `sector` varchar(100) DEFAULT NULL,
  `technologies` json DEFAULT NULL,
  `roles_needed` json DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (`id`),
  KEY `creator_id` (`creator_id`),
  KEY `sector` (`sector`),

  CONSTRAINT `visions_ibfk_1`
    FOREIGN KEY (`creator_id`)
    REFERENCES `users` (`id`)
    ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `visions` WRITE;
/*!40000 ALTER TABLE `visions` DISABLE KEYS */;
/*!40000 ALTER TABLE `visions` ENABLE KEYS */;
UNLOCK TABLES;

DROP TABLE IF EXISTS `collaboration_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;

CREATE TABLE `collaboration_requests` (
  `id` int NOT NULL AUTO_INCREMENT,
  `vision_id` int NOT NULL,
  `sender_id` int NOT NULL,
  `receiver_id` int NOT NULL,
  `role` varchar(100) NOT NULL,
  `commitment` varchar(100) DEFAULT NULL,
  `equity` varchar(50) DEFAULT NULL,
  `description` text,
  `status` varchar(50) DEFAULT 'PENDING',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `responded_at` datetime DEFAULT NULL,

  PRIMARY KEY (`id`),

  KEY `vision_id` (`vision_id`),
  KEY `sender_id` (`sender_id`),
  KEY `receiver_id` (`receiver_id`),
  KEY `status` (`status`),

  CONSTRAINT `collaboration_requests_ibfk_1`
    FOREIGN KEY (`vision_id`)
    REFERENCES `visions` (`id`)
    ON DELETE CASCADE,

  CONSTRAINT `collaboration_requests_ibfk_2`
    FOREIGN KEY (`sender_id`)
    REFERENCES `users` (`id`)
    ON DELETE CASCADE,

  CONSTRAINT `collaboration_requests_ibfk_3`
    FOREIGN KEY (`receiver_id`)
    REFERENCES `users` (`id`)
    ON DELETE CASCADE

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `collaboration_requests` WRITE;
/*!40000 ALTER TABLE `collaboration_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `collaboration_requests` ENABLE KEYS */;
UNLOCK TABLES;