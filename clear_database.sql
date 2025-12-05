-- Disable foreign key checks temporarily
SET FOREIGN_KEY_CHECKS = 0;

-- Clear all data from tables
TRUNCATE TABLE SearchHistory;
TRUNCATE TABLE Doctor_Patient;
TRUNCATE TABLE Drug_Interaction;
TRUNCATE TABLE Interaction;
TRUNCATE TABLE FoodInteraction;
TRUNCATE TABLE DiseaseInteraction;
TRUNCATE TABLE Drug;
TRUNCATE TABLE `Condition`;
TRUNCATE TABLE User;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;