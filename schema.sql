-- PharmaCheck MySQL Database Schema
-- Based on Stage 3 requirements with additional tables for Food and Disease interactions

-- Create database
CREATE DATABASE IF NOT EXISTS pharmacheck;
USE pharmacheck;

-- User table with PATIENT/DOCTOR roles
CREATE TABLE User (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash CHAR(60) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    role ENUM('PATIENT', 'DOCTOR') NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Condition table for medical conditions
CREATE TABLE `Condition` (
    condition_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    url VARCHAR(512),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Drug table with foreign key to Condition
CREATE TABLE Drug (
    drug_id INT PRIMARY KEY AUTO_INCREMENT,
    condition_id INT,
    name VARCHAR(255) NOT NULL UNIQUE,
    generic_name VARCHAR(255),
    description TEXT,
    url VARCHAR(512),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (condition_id) REFERENCES `Condition`(condition_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    INDEX idx_drug_name (name),
    INDEX idx_drug_generic_name (generic_name)
);

-- Interaction table for drug-drug interactions
CREATE TABLE Interaction (
    interaction_id INT PRIMARY KEY AUTO_INCREMENT,
    severity ENUM('Major', 'Moderate', 'Minor', 'Unknown') NOT NULL,
    professional_description TEXT NOT NULL,
    patient_description TEXT,
    ai_description TEXT,
    url VARCHAR(512),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Junction table for Drug-Interaction many-to-many relationship
CREATE TABLE Drug_Interaction (
    drug_id INT NOT NULL,
    interaction_id INT NOT NULL,
    interacting_drug_name VARCHAR(255),
    PRIMARY KEY (drug_id, interaction_id),
    FOREIGN KEY (drug_id) REFERENCES Drug(drug_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (interaction_id) REFERENCES Interaction(interaction_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Food/Lifestyle Interaction table
CREATE TABLE FoodInteraction (
    food_interaction_id INT PRIMARY KEY AUTO_INCREMENT,
    drug_id INT NOT NULL,
    interaction_name VARCHAR(255) NOT NULL,
    severity ENUM('Major', 'Moderate', 'Minor', 'Unknown') NOT NULL,
    hazard_level VARCHAR(100),
    plausibility ENUM('High', 'Moderate', 'Low', 'Unknown'),
    professional_description TEXT NOT NULL,
    patient_description TEXT,
    ai_description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (drug_id) REFERENCES Drug(drug_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    INDEX idx_food_drug (drug_id)
);

-- Disease Interaction table
CREATE TABLE DiseaseInteraction (
    disease_interaction_id INT PRIMARY KEY AUTO_INCREMENT,
    drug_id INT NOT NULL,
    disease_name VARCHAR(255) NOT NULL,
    severity ENUM('Major', 'Moderate', 'Minor', 'Unknown') NOT NULL,
    hazard_level VARCHAR(100),
    plausibility ENUM('High', 'Moderate', 'Low', 'Unknown'),
    applicable_conditions TEXT,
    professional_description TEXT NOT NULL,
    patient_description TEXT,
    ai_description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (drug_id) REFERENCES Drug(drug_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    INDEX idx_disease_drug (drug_id)
);

-- Search History table
CREATE TABLE SearchHistory (
    search_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    query TEXT NOT NULL,
    search_type ENUM('DRUG', 'CONDITION', 'INTERACTION') DEFAULT 'DRUG',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    INDEX idx_search_user (user_id),
    INDEX idx_search_created (created_at)
);

-- Doctor-Patient assignment table
CREATE TABLE Doctor_Patient (
    doctor_id INT NOT NULL,
    patient_id INT NOT NULL,
    assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (doctor_id, patient_id),
    FOREIGN KEY (doctor_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES User(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- Add full-text search indexes for autocomplete
ALTER TABLE Drug ADD FULLTEXT INDEX ft_drug_name (name, generic_name);
ALTER TABLE `Condition` ADD FULLTEXT INDEX ft_condition_name (name);

