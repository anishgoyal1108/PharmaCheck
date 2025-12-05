-- Migration to add search_data column and update search_type enum
-- Run this migration to update the SearchHistory table

ALTER TABLE SearchHistory 
  MODIFY COLUMN search_type ENUM('DRUG', 'CONDITION', 'INTERACTION', 'FOOD_INTERACTION', 'DISEASE_INTERACTION') NOT NULL,
  ADD COLUMN search_data TEXT AFTER search_type;

