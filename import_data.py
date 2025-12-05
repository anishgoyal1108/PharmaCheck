"""
PharmaCheck Data Import Script
Imports drugs and conditions from JSON files into the MySQL database
"""

import json
import sys
from database import Session, Drug, Condition, init_db, get_or_create_drug, get_or_create_condition


def import_conditions(filepath='conditions.json'):
    """Import conditions from JSON file"""
    print(f"Importing conditions from {filepath}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            conditions = json.load(f)
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Skipping conditions import.")
        return 0
    except json.JSONDecodeError as e:
        print(f"Error parsing {filepath}: {e}")
        return 0
    
    session = Session()
    count = 0
    
    try:
        for name, url in conditions.items():
            try:
                # Check if condition already exists
                existing = session.query(Condition).filter(Condition.name == name).first()
                if not existing:
                    condition = Condition(name=name, url=url)
                    session.add(condition)
                    count += 1
                    
                    # Commit in batches
                    if count % 100 == 0:
                        session.commit()
                        print(f"  Imported {count} conditions...")
            except Exception as e:
                print(f"  Error importing condition '{name}': {e}")
                session.rollback()
        
        session.commit()
        print(f"Successfully imported {count} conditions.")
        return count
        
    except Exception as e:
        session.rollback()
        print(f"Error during conditions import: {e}")
        return 0
    finally:
        session.close()


def import_drugs(filepath='drugs.json'):
    """Import drugs from JSON file"""
    print(f"Importing drugs from {filepath}...")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            drugs = json.load(f)
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Skipping drugs import.")
        return 0
    except json.JSONDecodeError as e:
        print(f"Error parsing {filepath}: {e}")
        return 0
    
    session = Session()
    count = 0
    
    try:
        for name, url in drugs.items():
            try:
                # Check if drug already exists
                existing = session.query(Drug).filter(Drug.name == name).first()
                if not existing:
                    drug = Drug(name=name, url=url)
                    session.add(drug)
                    count += 1
                    
                    # Commit in batches
                    if count % 100 == 0:
                        session.commit()
                        print(f"  Imported {count} drugs...")
            except Exception as e:
                print(f"  Error importing drug '{name}': {e}")
                session.rollback()
        
        session.commit()
        print(f"Successfully imported {count} drugs.")
        return count
        
    except Exception as e:
        session.rollback()
        print(f"Error during drugs import: {e}")
        return 0
    finally:
        session.close()


def import_drug_urls_from_xml(filepath='drug-drug-interactions.xml'):
    """Parse drug interaction URLs from sitemap XML"""
    import xml.etree.ElementTree as ET
    
    print(f"Parsing drug URLs from {filepath}...")
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Handle namespace
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        urls = []
        for url_elem in root.findall('.//ns:url/ns:loc', namespace):
            url = url_elem.text
            if url and '/drug-interactions/' in url:
                urls.append(url)
        
        print(f"Found {len(urls)} drug interaction URLs.")
        return urls
        
    except FileNotFoundError:
        print(f"Warning: {filepath} not found.")
        return []
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return []


def main():
    """Main import function"""
    print("=" * 50)
    print("PharmaCheck Data Import")
    print("=" * 50)
    
    # Initialize database tables
    print("\nInitializing database tables...")
    try:
        init_db()
        print("Database tables ready.")
    except Exception as e:
        print(f"Error initializing database: {e}")
        print("\nMake sure your MySQL server is running and the DATABASE_URL is correct.")
        print("You can set the DATABASE_URL environment variable or create a .env file.")
        sys.exit(1)
    
    # Import conditions
    print("\n" + "-" * 50)
    conditions_count = import_conditions()
    
    # Import drugs
    print("\n" + "-" * 50)
    drugs_count = import_drugs()
    
    # Summary
    print("\n" + "=" * 50)
    print("Import Summary")
    print("=" * 50)
    print(f"Conditions imported: {conditions_count}")
    print(f"Drugs imported: {drugs_count}")
    print("\nImport complete!")
    
    # Optional: Show sample of imported data
    session = Session()
    try:
        total_conditions = session.query(Condition).count()
        total_drugs = session.query(Drug).count()
        print(f"\nDatabase now contains:")
        print(f"  - {total_conditions} conditions")
        print(f"  - {total_drugs} drugs")
    finally:
        session.close()


if __name__ == '__main__':
    main()

