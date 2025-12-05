# PharmaCheck

<p align="center">
  <img src="Logo.svg" alt="PharmaCheck Logo" width="400">
</p>

<p align="center">
  A database-managed web application for identifying drug interactions using MySQL, web scraping, and AI-powered descriptions.
</p>

## Authors
- Anish Goyal [@anishgoyal1108](https://github.com/anishgoyal1108)
- Aishwaryaa Udeshi [@AishwaryaaUdeshi](https://github.com/AishwaryaaUdeshi)
- Olivia Duan ([od0883@princeton.edu](mailto:od0883@princeton.edu))
- Jennifer Dong ([jd6311@princeton.edu](mailto:jd6311@princeton.edu))

## Overview

PharmaCheck was originally developed during **HackPrinceton Fall 2024** to address a critical problem in healthcare: drug interactions. A drug interaction occurs when two or more medications affect each other's effectiveness or produce harmful side effects. Over 100,000 hospitalizations occur annually due to adverse drug interactions, and patients often lack visibility into the medications prescribed by multiple providers.

This repository contains a complete rewrite of the original hackathon project by Anish Goyal, transforming it into a database-managed application for the CSCI 3432: Database Systems course at Georgia Southern University. The rewrite introduces:

- **MySQL database backend** with SQLAlchemy ORM for persistent storage
- **User account system** with JWT authentication and bcrypt password hashing
- **Role-based access** supporting Patient and Doctor user types
- **Doctor-patient relationship management** allowing physicians to monitor patient searches
- **Search history tracking** with clickable restoration of previous queries
- **Food and disease interaction support** in addition to drug-drug interactions
- **Improved frontend** with dedicated dashboard, login, and registration pages
- **Caching layer** for scraped interactions to reduce redundant web requests

## Screenshots

### Welcome Page
<p align="center">
  <img src="Report/img/welcome_page.png" alt="Welcome Page" width="700">
</p>

### User Dashboard
<p align="center">
  <img src="Report/img/dashboard.png" alt="Dashboard" width="700">
</p>

### Drug Interaction Checker
<p align="center">
  <img src="Report/img/drug_checker.png" alt="Drug Checker" width="400">
</p>

### Doctor Patient Management
<p align="center">
  <img src="Report/img/my_patients.png" alt="My Patients" width="700">
</p>

## Tech Stack

<p align="center">
  <img src="Report/img/tech_stack.png" alt="Tech Stack" width="400">
</p>

- **Backend**: Python 3.8+ with Flask
- **Database**: MySQL 8.0+ with SQLAlchemy ORM
- **Web Scraping**: BeautifulSoup and requests
- **AI Translation**: Ollama with llama3.2:3b model
- **Authentication**: JWT tokens with bcrypt password hashing
- **Frontend**: Vanilla HTML, CSS, and JavaScript

## Installation

### Prerequisites

- Python 3.8 or higher
- MySQL Server 8.0 or higher
- Ollama (optional, for AI translation feature)

### Step 1: Clone the Repository

```bash
git clone https://github.com/anishgoyal1108/PharmaCheck.git
cd PharmaCheck
```

### Step 2: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Create a `.env` file in the project root with the following format:

```
DATABASE_URL=mysql+mysqlconnector://root:your_password@localhost:3306/pharmacheck
JWT_SECRET_KEY=your-secure-secret-key-here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

Replace `your_password` with your MySQL root password and `your-secure-secret-key-here` with a random string for JWT signing.

### Step 4: Set Up the MySQL Database

Open the MySQL command line client and run the schema file:

```bash
mysql -u root -p < schema.sql
```

Or connect to MySQL and execute manually:

```sql
SOURCE schema.sql;
```

### Step 5: Import Initial Data

```bash
python import_data.py
```

This imports 2,123 medical conditions and 15,773 drugs from the JSON data files.

### Step 6: Start the Flask Server

```bash
python api.py
```

The API server runs on `http://localhost:5000`.

### Step 7: Open the Application

Open `welcome.html` in your browser, or serve the files with a static file server.

### Optional: Ollama Setup for AI Translation

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull the language model:
   ```bash
   ollama pull llama3.2:3b
   ```
3. Ollama runs automatically after installation on port 11434

## SQL Files

The project includes three SQL files for database management:

### schema.sql

Creates the `pharmacheck` database and all required tables:

- **User**: Stores user accounts with username, password hash, email, and role (PATIENT or DOCTOR)
- **Condition**: Medical conditions with name, description, and URL
- **Drug**: Drug information with name, generic name, description, and foreign key to Condition
- **Interaction**: Drug-drug interaction records with severity and descriptions
- **Drug_Interaction**: Junction table linking drugs to interactions (many-to-many)
- **FoodInteraction**: Food and lifestyle interaction data for each drug
- **DiseaseInteraction**: Disease interaction data with applicable conditions
- **SearchHistory**: User search history with timestamps and query data
- **Doctor_Patient**: Assignment table linking doctors to their patients

The schema includes full-text indexes on Drug and Condition names for autocomplete functionality.

### migration_add_search_data.sql

Adds the `search_data` column to the SearchHistory table and extends the `search_type` enum to include FOOD_INTERACTION and DISEASE_INTERACTION types. Run this migration if you have an existing database from an earlier version:

```bash
mysql -u root -p pharmacheck < migration_add_search_data.sql
```

### clear_database.sql

Truncates all tables for a clean reset. Temporarily disables foreign key checks to allow truncation in any order. Use this when you need to clear all data and start fresh:

```bash
mysql -u root -p pharmacheck < clear_database.sql
```

## Project Structure

```
PharmaCheck/
├── api.py                  # Flask API server with all endpoints
├── auth.py                 # Authentication module (JWT, bcrypt)
├── config.py               # Configuration management from .env
├── database.py             # SQLAlchemy models and database setup
├── scraper.py              # Web scraping for drug interactions
├── import_data.py          # Data import script for drugs and conditions
├── schema.sql              # MySQL database schema
├── migration_add_search_data.sql  # Schema migration for search data
├── clear_database.sql      # Database reset script
├── requirements.txt        # Python dependencies
├── welcome.html            # Landing page
├── welcome.css             # Landing page styles
├── index.html              # Main drug search page
├── index.js                # Main page JavaScript
├── index.css               # Main page styles
├── login/                  # Login page (HTML, CSS, JS)
├── register/               # Registration page (HTML, CSS, JS)
├── dashboard/              # User dashboard (HTML, CSS, JS)
├── interactions/           # Interaction results page (HTML, CSS, JS)
├── descriptions/           # Detailed interaction view (HTML, CSS, JS)
├── drugs.json              # Drug names and URLs (15,773 entries)
├── conditions.json         # Medical conditions data (2,123 entries)
├── Logo.svg                # PharmaCheck logo
├── Report/                 # Project final report
│   └── goyal_pharmacheck_report.pdf
└── Presentation/           # Project presentation slides
    └── Main.pdf
```

## Database Schema

The MySQL database follows Boyce-Codd Normal Form (BCNF) with the following functional dependencies:

- **User**: user_id → username, password_hash, email, role, created_at, updated_at
- **Drug**: drug_id → name, generic_name, description, url, condition_id
- **Condition**: condition_id → name, description, url
- **Interaction**: interaction_id → severity, professional_description, patient_description, ai_description

Foreign key constraints use CASCADE for updates and deletes to maintain referential integrity.

## API Endpoints

### Authentication

- `POST /auth/register` - Create new user account
- `POST /auth/login` - Authenticate user and receive JWT token
- `POST /auth/logout` - End session
- `GET /auth/me` - Get current user information

### Drug Search

- `GET /drugs/autocomplete?q=` - Autocomplete drug names
- `GET /conditions/autocomplete?q=` - Autocomplete condition names
- `GET /search_drugs?input=` - Search for drugs by name
- `GET /search_conditions?input=` - Search for conditions by name

### Interactions

- `GET /drug_interactions?active_ingredient=` - Get drug-drug interactions
- `GET /food_interactions?active_ingredient=` - Get food/lifestyle interactions
- `GET /disease_interactions?active_ingredient=` - Get disease interactions
- `GET /all_interactions?active_ingredient=` - Get all interaction types
- `POST /check_drug_interactions` - Check interactions between multiple drugs
- `POST /translate_description` - Translate professional description using AI

### User Data

- `GET /users/search_history` - Get user's search history
- `DELETE /users/search_history/:id` - Delete specific history entry
- `DELETE /users/search_history` - Clear all search history

### Doctor Features

- `GET /doctors/patients` - List assigned patients
- `POST /doctors/patients` - Assign a patient to the doctor
- `DELETE /doctors/patients/:id` - Remove patient assignment
- `GET /doctors/patients/:id/search_history` - View patient's search history

## Documentation

For more detailed information about the project, see:

- [Project Final Report](Report/goyal_pharmacheck_report.pdf) - Comprehensive documentation of design decisions, database normalization, and implementation details
- [Project Presentation](Presentation/Main.pdf) - Slide deck covering project overview, architecture, and demonstration

## Future Work

- Alternative drug suggestions when unsafe combinations are detected
- Quantized LLM deployment for faster AI responses
- Mobile application for on-the-go interaction checking
- Integration with electronic health record (EHR) systems
- Background job queue for asynchronous scraping operations

## License

See [LICENSE](LICENSE) for details.

## Acknowledgments

This project originated at HackPrinceton Fall 2024 as a hackathon prototype. The database-managed version was developed as the final project for CSCI 3432: Database Systems at Georgia Southern University under Dr. Weitian Tong. All drug interaction data is sourced from Drugs.com.
