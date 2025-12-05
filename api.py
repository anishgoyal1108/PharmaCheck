"""
PharmaCheck API
Flask API with MySQL database integration, authentication, and Ollama LLM support
"""

import os
from flask import Flask, request, jsonify, g, send_from_directory, redirect
from flask_cors import CORS
import requests
import json
from datetime import datetime

from config import config
from database import (
    Session, init_db, Drug, Condition, Interaction, 
    FoodInteraction, DiseaseInteraction, SearchHistory, User,
    search_drugs, search_conditions, get_or_create_drug, get_or_create_condition
)
from auth import (
    login_required, role_required, get_current_user,
    register_user, login_user, get_user_by_id,
    assign_patient_to_doctor, remove_patient_from_doctor,
    get_doctor_patients, get_patient_doctors
)
from scraper import (
    DrugInteractionChecker, DrugInteractionScraper,
    FoodInteractionScraper, DiseaseInteractionScraper,
    levenshtein_distance, is_similar, check_interaction
)

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = config.SECRET_KEY


# ============== Helper Functions ==============

def search_existing_conditions_db(input_query: str):
    """Search conditions from database with fuzzy matching"""
    session = Session()
    try:
        # First try exact prefix match
        conditions = session.query(Condition).filter(
            Condition.name.ilike(f'{input_query}%')
        ).limit(10).all()
        
        if conditions:
            return [(c.name, c.url) for c in conditions]
        
        # Fallback to fuzzy search
        all_conditions = session.query(Condition).all()
        min_distance = float("inf")
        closest_match = None
        
        for condition in all_conditions:
            distance = levenshtein_distance(input_query.lower(), condition.name.lower())
            ratio = 1 - distance / max(len(input_query), len(condition.name))
            if ratio > 0.5 and distance < min_distance:
                min_distance = distance
                closest_match = (condition.name, condition.url)
        
        return closest_match
    finally:
        session.close()


def search_existing_conditions(input_query: str):
    """Search conditions from JSON file (fallback)"""
    try:
        with open("conditions.json") as f:
            conditions = json.load(f)
            min_distance = float("inf")
            closest_match = None

            for condition, url in conditions.items():
                distance = levenshtein_distance(input_query.lower(), condition.lower())
                ratio = 1 - distance / max(len(input_query), len(condition))
                if ratio > 0.5 and distance < min_distance:
                    min_distance = distance
                    closest_match = (condition, url)

            return closest_match
    except FileNotFoundError:
        return search_existing_conditions_db(input_query)


def search_existing_drugs_db(input_query: str):
    """Search drugs from database with fuzzy matching"""
    session = Session()
    try:
        # First try exact match (case-insensitive)
        drug = session.query(Drug).filter(
            Drug.name.ilike(input_query)
        ).first()
        
        if drug:
            return (drug.name, drug.url)
        
        # Then try prefix match
        drugs = session.query(Drug).filter(
            Drug.name.ilike(f'{input_query}%')
        ).limit(10).all()
        
        if drugs:
            return (drugs[0].name, drugs[0].url)
        
        # Fallback to fuzzy search
        all_drugs = session.query(Drug).all()
        min_distance = float("inf")
        closest_match = None
        
        for drug in all_drugs:
            distance = levenshtein_distance(input_query.lower(), drug.name.lower())
            ratio = 1 - distance / max(len(input_query), len(drug.name))
            if ratio > 0.6 and distance < min_distance:
                min_distance = distance
                closest_match = (drug.name, drug.url)
        
        return closest_match
    finally:
        session.close()


def search_existing_drugs(input_query: str):
    """Search drugs from JSON file then database"""
    # Try database first
    db_result = search_existing_drugs_db(input_query)
    if db_result:
        return db_result
    
    # Fallback to JSON
    try:
        with open("drugs.json") as f:
            drugs = json.load(f)
            
            # Try exact match first
            for drug, url in drugs.items():
                if drug.lower() == input_query.lower():
                    return (drug, url)
            
            # Then fuzzy match
            min_distance = float("inf")
            closest_match = None

            for drug, url in drugs.items():
                distance = levenshtein_distance(input_query.lower(), drug.lower())
                ratio = 1 - distance / max(len(input_query), len(drug))
                if ratio > 0.6 and distance < min_distance:
                    min_distance = distance
                    closest_match = (drug, url)

            return closest_match
    except FileNotFoundError:
        return None


def validate_drug(drug_name: str) -> dict:
    """Validate a drug exists in our data sources"""
    result = search_existing_drugs(drug_name)
    
    if result:
        return {
            "valid": True,
            "drug_name": result[0],
            "url": result[1]
        }
    return {
        "valid": False,
        "drug_name": drug_name,
        "url": None
    }


def translate_professional_to_consumer(professional_description: str) -> str:
    """Translate professional description to consumer-friendly using Ollama"""
    prompt = f"""Pretend you are a clinical physician. Translate the following professional drug interaction description into a more consumer-friendly description. Write the consumer-friendly description only; do not prepend anything before your response:

{professional_description}"""
    
    try:
        response = requests.post(
            f"{config.OLLAMA_BASE_URL}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60
        )

        if response.status_code != 200:
            return None

        response_json = response.json()
        return response_json.get("response", "")
    except Exception as e:
        print(f"Ollama error: {e}")
        return None


def cache_ai_description(interaction_id: int, ai_description: str):
    """Cache AI-generated description in database"""
    session = Session()
    try:
        interaction = session.query(Interaction).filter(
            Interaction.interaction_id == interaction_id
        ).first()
        if interaction:
            interaction.ai_description = ai_description
            session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error caching AI description: {e}")
    finally:
        session.close()


def log_search(user_id: int, query: str, search_type: str = 'DRUG', search_data: str = None):
    """Log search to history"""
    session = Session()
    try:
        search_entry = SearchHistory(
            user_id=user_id,
            query=query,
            search_type=search_type,
            search_data=search_data
        )
        session.add(search_entry)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error logging search: {e}")
    finally:
        session.close()


# ============== Authentication Endpoints ==============

@app.route("/auth/register", methods=["POST"])
def api_register():
    """Register a new user"""
    data = request.get_json()
    
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "PATIENT")
    
    if not all([username, email, password]):
        return jsonify({"error": "Username, email, and password are required"}), 400
    
    result = register_user(username, email, password, role)
    
    if result["success"]:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@app.route("/auth/login", methods=["POST"])
def api_login():
    """Login user"""
    data = request.get_json()
    
    username = data.get("username")
    password = data.get("password")
    
    if not all([username, password]):
        return jsonify({"error": "Username and password are required"}), 400
    
    result = login_user(username, password)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 401


@app.route("/auth/me", methods=["GET"])
@login_required
def api_me():
    """Get current user info"""
    return jsonify({"user": g.current_user.to_dict()}), 200


@app.route("/auth/logout", methods=["POST"])
@login_required
def api_logout():
    """Logout user (client should discard token)"""
    return jsonify({"message": "Logged out successfully"}), 200


# ============== Drug Search Endpoints ==============

@app.route("/drugs/autocomplete", methods=["GET"])
def drugs_autocomplete():
    """Autocomplete drug names from database"""
    query = request.args.get("q", "")
    if len(query) < 2:
        return jsonify([])
    
    session = Session()
    try:
        drugs = session.query(Drug).filter(
            Drug.name.ilike(f'{query}%')
        ).limit(20).all()
        
        results = [{"name": d.name, "url": d.url, "generic_name": d.generic_name} for d in drugs]
        
        # If no database results, try JSON file
        if not results:
            try:
                with open("drugs.json") as f:
                    drugs_json = json.load(f)
                    for name, url in drugs_json.items():
                        if name.lower().startswith(query.lower()):
                            results.append({"name": name, "url": url})
                            if len(results) >= 20:
                                break
            except FileNotFoundError:
                pass
        
        return jsonify(results)
    finally:
        session.close()


@app.route("/conditions/autocomplete", methods=["GET"])
def conditions_autocomplete():
    """Autocomplete condition names from database"""
    query = request.args.get("q", "")
    if len(query) < 2:
        return jsonify([])
    
    session = Session()
    try:
        conditions = session.query(Condition).filter(
            Condition.name.ilike(f'{query}%')
        ).limit(20).all()
        
        results = [{"name": c.name, "url": c.url} for c in conditions]
        
        # If no database results, try JSON file
        if not results:
            try:
                with open("conditions.json") as f:
                    conditions_json = json.load(f)
                    for name, url in conditions_json.items():
                        if name.lower().startswith(query.lower()):
                            results.append({"name": name, "url": url})
                            if len(results) >= 20:
                                break
            except FileNotFoundError:
                pass
        
        return jsonify(results)
    finally:
        session.close()


@app.route("/search_conditions", methods=["GET"])
def api_search_conditions():
    """Search conditions"""
    input_query = request.args.get("input")
    if not input_query:
        return jsonify({"error": "input parameter is required"}), 400

    result = search_existing_conditions(input_query)
    
    # Don't log condition searches separately - they're part of interaction searches
    
    return jsonify(result)


@app.route("/search_drugs", methods=["GET"])
def api_search_drugs():
    """Search drugs"""
    input_query = request.args.get("input")
    if not input_query:
        return jsonify({"error": "input parameter is required"}), 400

    result = search_existing_drugs(input_query)
    
    # Don't log autocomplete searches - only log actual interaction checks
    
    return jsonify(result)


# ============== Drug Interaction Endpoints ==============

@app.route("/drug_interactions", methods=["GET"])
def get_drug_interactions():
    """Get drug interactions for a given active ingredient"""
    active_ingredient = request.args.get("active_ingredient")
    if not active_ingredient:
        return jsonify({"error": "active_ingredient parameter is required"}), 400

    try:
        checker = DrugInteractionChecker(active_ingredient)
        interactions = checker.get_drug_interactions()
        
        # Log search if user is authenticated
        user = get_current_user()
        if user:
            log_search(user.user_id, active_ingredient, 'INTERACTION')
        
        return jsonify(interactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/food_interactions", methods=["GET"])
@login_required
def get_food_interactions():
    """Get food/lifestyle interactions for a drug"""
    active_ingredient = request.args.get("active_ingredient")
    if not active_ingredient:
        return jsonify({"error": "active_ingredient parameter is required"}), 400

    try:
        checker = DrugInteractionChecker(active_ingredient)
        interactions = checker.get_food_interactions()
        
        # Log search with results
        import json
        response_data = {"interactions": interactions, "drug": active_ingredient}
        log_search(g.current_user.user_id, active_ingredient, 'FOOD_INTERACTION', json.dumps(response_data))
        
        return jsonify(interactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/disease_interactions", methods=["GET"])
@login_required
def get_disease_interactions():
    """Get disease interactions for a drug"""
    active_ingredient = request.args.get("active_ingredient")
    if not active_ingredient:
        return jsonify({"error": "active_ingredient parameter is required"}), 400

    try:
        checker = DrugInteractionChecker(active_ingredient)
        interactions = checker.get_disease_interactions()
        
        # Log search with results
        import json
        response_data = {"interactions": interactions, "drug": active_ingredient}
        log_search(g.current_user.user_id, active_ingredient, 'DISEASE_INTERACTION', json.dumps(response_data))
        
        return jsonify(interactions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/all_interactions", methods=["GET"])
def get_all_interactions():
    """Get all types of interactions for a drug"""
    active_ingredient = request.args.get("active_ingredient")
    if not active_ingredient:
        return jsonify({"error": "active_ingredient parameter is required"}), 400

    try:
        checker = DrugInteractionChecker(active_ingredient)
        checker.build_all_interactions()
        
        # Log search if user is authenticated
        user = get_current_user()
        if user:
            log_search(user.user_id, active_ingredient, 'INTERACTION')
        
        return jsonify({
            "drug_interactions": checker.interactions,
            "food_interactions": checker.food_interactions,
            "disease_interactions": checker.disease_interactions
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/translate_description", methods=["POST"])
@login_required
def api_translate_description():
    """Translate professional description to consumer-friendly"""
    data = request.get_json()
    professional_description = data.get("professional_description")
    interaction_id = data.get("interaction_id")
    
    if not professional_description:
        return jsonify({"error": "professional_description parameter is required"}), 400

    try:
        # Check if we have a cached translation
        if interaction_id:
            session = Session()
            try:
                interaction = session.query(Interaction).filter(
                    Interaction.interaction_id == interaction_id
                ).first()
                if interaction and interaction.ai_description:
                    return jsonify({"consumer_description": interaction.ai_description})
            finally:
                session.close()
        
        # Generate new translation
        consumer_description = translate_professional_to_consumer(professional_description)
        
        if consumer_description is None:
            return jsonify({"error": "Failed to generate translation. Ollama may be unavailable."}), 503
        
        # Cache the translation
        if interaction_id:
            cache_ai_description(interaction_id, consumer_description)
        
        return jsonify({"consumer_description": consumer_description})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/validate_drugs", methods=["POST"])
def validate_drugs():
    """Validate a list of drugs exist in our data sources (fast, no scraping)"""
    data = request.get_json()
    drugs_list = data.get("drugs", [])
    
    if not drugs_list:
        return jsonify({"error": "drugs parameter is required"}), 400
    
    if len(drugs_list) > 5:
        return jsonify({"error": "Maximum 5 drugs allowed"}), 400
    
    valid_drugs = []
    not_found_drugs = []
    
    for drug in drugs_list:
        drug = drug.strip()
        if not drug:
            continue
            
        result = validate_drug(drug)
        if result["valid"]:
            valid_drugs.append({
                "drug_name": result["drug_name"],
                "url": result["url"]
            })
        else:
            not_found_drugs.append(drug)
    
    return jsonify({
        "valid_drugs": valid_drugs,
        "not_found_drugs": not_found_drugs
    })


@app.route("/process_current_meds", methods=["POST"])
def process_current_meds():
    """Process list of current medications (simplified - no scraping)"""
    data = request.get_json()
    drugs_list = data.get("drugs")

    if not drugs_list:
        return jsonify({"error": "drugs parameter is required"}), 400
    
    # Handle both string and list inputs
    if isinstance(drugs_list, str):
        drugs_list = [d.strip() for d in drugs_list.split(",") if d.strip()]

    if len(drugs_list) > 5:
        return jsonify({"error": "Maximum 5 drugs allowed"}), 400

    not_found_drugs = []
    valid_drugs = []

    for drug in drugs_list:
        drug = drug.strip()
        if not drug:
            continue
            
        result = validate_drug(drug)

        if result["valid"]:
            valid_drugs.append({
                "drug_name": result["drug_name"],
                "url": result["url"]
            })
        else:
            not_found_drugs.append(drug)

    return jsonify({"valid_drugs": valid_drugs, "not_found_drugs": not_found_drugs})


@app.route("/check_drug_interactions", methods=["POST"])
@login_required
def check_drug_interactions():
    """Check interactions between multiple drugs"""
    data = request.get_json()
    drugs_input = data.get("drugs", [])
    prescribed_drug = data.get("prescribed_drug")

    # Support both old format (prescribed_drug + drugs) and new format (just drugs list)
    all_drugs = []
    
    if prescribed_drug:
        all_drugs.append(prescribed_drug)
    
    if isinstance(drugs_input, str):
        all_drugs.extend([d.strip() for d in drugs_input.split(",") if d.strip()])
    elif isinstance(drugs_input, list):
        all_drugs.extend([d.strip() for d in drugs_input if d.strip()])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_drugs = []
    for d in all_drugs:
        if d.lower() not in seen:
            seen.add(d.lower())
            unique_drugs.append(d)
    
    if len(unique_drugs) < 1:
        return jsonify({"error": "At least one drug is required"}), 400
    
    if len(unique_drugs) > 5:
        return jsonify({"error": "Maximum 5 drugs allowed"}), 400

    all_interactions = []
    food_interactions = []
    disease_interactions = []
    
    # Create a set of drug names (lowercase) for matching
    drug_names_lower = set(d.lower() for d in unique_drugs)

    try:
        # For each drug, get its interactions and check if other drugs in our list are mentioned
        for drug in unique_drugs:
            checker = DrugInteractionChecker(drug)
            
            # Get drug-drug interactions
            drug_interactions = checker.get_drug_interactions(use_cache=True)
            
            # Check if any of these interactions involve other drugs in our list
            for interaction in drug_interactions:
                interaction_name = interaction.get("name", "").lower()
                # Check if this interaction mentions any of our other drugs
                for other_drug in unique_drugs:
                    if other_drug.lower() != drug.lower():
                        if other_drug.lower() in interaction_name or is_similar(other_drug, interaction_name, 0.4):
                            # This is an interaction between our drugs
                            interaction_copy = interaction.copy()
                            interaction_copy["drug"] = f"{drug} ↔ {other_drug}"
                            interaction_copy["drugs_involved"] = [drug, other_drug]
                            # Avoid duplicates (A-B is same as B-A)
                            pair_key = tuple(sorted([drug.lower(), other_drug.lower()]))
                            already_added = any(
                                tuple(sorted([d.lower() for d in i.get("drugs_involved", [])])) == pair_key
                                for i in all_interactions
                            )
                            if not already_added:
                                all_interactions.append(interaction_copy)
                            break
            
            # Get food interactions for this drug
            drug_food = checker.get_food_interactions(use_cache=True)
            for fi in drug_food:
                fi["drug"] = drug  # Mark which drug this is for
                # Check if already in list (avoid duplicates)
                if not any(existing.get("interaction_name") == fi.get("interaction_name") and 
                          existing.get("drug") == drug for existing in food_interactions):
                    food_interactions.append(fi)
            
            # Get disease interactions for this drug
            drug_disease = checker.get_disease_interactions(use_cache=True)
            for di in drug_disease:
                di["drug"] = drug  # Mark which drug this is for
                # Check if already in list
                if not any(existing.get("disease_name") == di.get("disease_name") and 
                          existing.get("drug") == drug for existing in disease_interactions):
                    disease_interactions.append(di)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error checking interactions: {str(e)}"}), 500
    
    # Prepare response
    response_data = {
        "interactions": all_interactions,
        "food_interactions": food_interactions,
        "disease_interactions": disease_interactions,
        "drugs": unique_drugs
    }
    
    # Log search with full results data
    import json
    log_search(g.current_user.user_id, ', '.join(unique_drugs), 'INTERACTION', json.dumps(response_data))

    return jsonify(response_data)


# ============== Search History Endpoints ==============

@app.route("/users/search_history", methods=["GET"])
@login_required
def get_search_history():
    """Get current user's search history"""
    session = Session()
    try:
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        
        history = session.query(SearchHistory).filter(
            SearchHistory.user_id == g.current_user.user_id
        ).order_by(SearchHistory.created_at.desc()).offset(offset).limit(limit).all()
        
        return jsonify([h.to_dict() for h in history])
    finally:
        session.close()


@app.route("/users/search_history/<int:search_id>", methods=["GET"])
@login_required
def get_search_history_item(search_id):
    """Get a specific search history entry with its data"""
    session = Session()
    try:
        entry = session.query(SearchHistory).filter(
            SearchHistory.search_id == search_id,
            SearchHistory.user_id == g.current_user.user_id
        ).first()
        
        if not entry:
            return jsonify({"error": "Search history entry not found"}), 404
        
        result = entry.to_dict()
        # Parse search_data if it exists
        if result.get('search_data'):
            import json
            try:
                result['search_data'] = json.loads(result['search_data'])
            except:
                pass
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/users/search_history/<int:search_id>", methods=["DELETE"])
@login_required
def delete_search_history(search_id):
    """Delete a search history entry"""
    session = Session()
    try:
        entry = session.query(SearchHistory).filter(
            SearchHistory.search_id == search_id,
            SearchHistory.user_id == g.current_user.user_id
        ).first()
        
        if not entry:
            return jsonify({"error": "Search history entry not found"}), 404
        
        session.delete(entry)
        session.commit()
        
        return jsonify({"message": "Search history entry deleted"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/users/search_history", methods=["DELETE"])
@login_required
def clear_search_history():
    """Clear all search history for current user"""
    session = Session()
    try:
        session.query(SearchHistory).filter(
            SearchHistory.user_id == g.current_user.user_id
        ).delete()
        session.commit()
        
        return jsonify({"message": "Search history cleared"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ============== Doctor-Patient Endpoints ==============

@app.route("/doctors/search", methods=["GET"])
@login_required
def api_search_doctors():
    """Search for doctors by username (for patients to find doctors)"""
    query = request.args.get("query", "").strip()
    
    if not query or len(query) < 2:
        return jsonify([])
    
    session = Session()
    try:
        # Search for doctors whose username contains the query
        doctors = session.query(User).filter(
            User.role == 'DOCTOR',
            User.username.ilike(f'%{query}%')
        ).limit(10).all()
        
        # Return minimal info for selection
        return jsonify([{
            'user_id': d.user_id,
            'username': d.username
        } for d in doctors])
    finally:
        session.close()


@app.route("/doctors/patients", methods=["GET"])
@login_required
@role_required("DOCTOR")
def api_get_doctor_patients():
    """Get all patients assigned to the current doctor with their recent searches"""
    session = Session()
    try:
        doctor = session.query(User).filter(User.user_id == g.current_user.user_id, User.role == 'DOCTOR').first()
        if not doctor:
            return jsonify([])
        
        patients_data = []
        for patient in doctor.patients:
            # Get patient's recent searches (last 5)
            recent_searches = session.query(SearchHistory).filter(
                SearchHistory.user_id == patient.user_id
            ).order_by(SearchHistory.created_at.desc()).limit(5).all()
            
            patient_dict = patient.to_dict()
            patient_dict['recent_searches'] = [s.to_dict() for s in recent_searches]
            patient_dict['total_searches'] = session.query(SearchHistory).filter(
                SearchHistory.user_id == patient.user_id
            ).count()
            patients_data.append(patient_dict)
        
        return jsonify(patients_data)
    finally:
        session.close()


@app.route("/patients/request_doctor", methods=["POST"])
@login_required
@role_required("PATIENT")
def api_patient_request_doctor():
    """Patient requests to be assigned to a doctor"""
    data = request.get_json()
    doctor_id = data.get("doctor_id")
    doctor_username = data.get("doctor_username")
    
    session = Session()
    try:
        # Find doctor by ID or username
        if doctor_id:
            doctor = session.query(User).filter(User.user_id == doctor_id, User.role == 'DOCTOR').first()
        elif doctor_username:
            doctor = session.query(User).filter(User.username == doctor_username, User.role == 'DOCTOR').first()
        else:
            return jsonify({"error": "doctor_id or doctor_username is required"}), 400
        
        if not doctor:
            return jsonify({"error": "Doctor not found"}), 404
        
        # Get patient
        patient = session.query(User).filter(User.user_id == g.current_user.user_id).first()
        
        # Check if already assigned
        if patient in doctor.patients:
            return jsonify({"error": "You are already assigned to this doctor"}), 400
        
        # Assign patient to doctor
        doctor.patients.append(patient)
        session.commit()
        
        return jsonify({
            "success": True, 
            "message": f"Successfully requested oversight from Dr. {doctor.username}"
        }), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@app.route("/patients/my_doctor", methods=["DELETE"])
@login_required
@role_required("PATIENT")
def api_patient_remove_doctor():
    """Patient removes themselves from a doctor"""
    data = request.get_json()
    doctor_id = data.get("doctor_id")
    
    if not doctor_id:
        return jsonify({"error": "doctor_id is required"}), 400
    
    result = remove_patient_from_doctor(doctor_id, g.current_user.user_id)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route("/doctors/patients/<int:patient_id>", methods=["DELETE"])
@login_required
@role_required("DOCTOR")
def api_remove_patient(patient_id):
    """Remove a patient from the current doctor (doctor can also remove patients)"""
    result = remove_patient_from_doctor(g.current_user.user_id, patient_id)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route("/doctors/all", methods=["GET"])
def api_get_all_doctors():
    """Get list of all doctors (for registration dropdown)"""
    session = Session()
    try:
        doctors = session.query(User).filter(User.role == 'DOCTOR').all()
        return jsonify([{
            'user_id': d.user_id,
            'username': d.username
        } for d in doctors])
    finally:
        session.close()


@app.route("/doctors/patients/<int:patient_id>/search_history", methods=["GET"])
@login_required
@role_required("DOCTOR")
def api_get_patient_history(patient_id):
    """Get a patient's search history (doctor only)"""
    # Verify patient is assigned to this doctor
    patients = get_doctor_patients(g.current_user.user_id)
    patient_ids = [p["user_id"] for p in patients]
    
    if patient_id not in patient_ids:
        return jsonify({"error": "Patient not assigned to you"}), 403
    
    session = Session()
    try:
        limit = request.args.get("limit", 50, type=int)
        
        history = session.query(SearchHistory).filter(
            SearchHistory.user_id == patient_id
        ).order_by(SearchHistory.created_at.desc()).limit(limit).all()
        
        return jsonify([h.to_dict() for h in history])
    finally:
        session.close()


@app.route("/patients/doctors", methods=["GET"])
@login_required
@role_required("PATIENT")
def api_get_patient_doctors():
    """Get all doctors assigned to the current patient"""
    doctors = get_patient_doctors(g.current_user.user_id)
    return jsonify(doctors)


# ============== Utility Endpoints ==============

@app.route("/drug_table", methods=["GET"])
def drug_table():
    """Parse drug table from a condition page"""
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "url parameter is required"}), 400

    try:
        from bs4 import BeautifulSoup
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to retrieve data from {url}"}), 500

        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table", class_="ddc-table-secondary ddc-table-sortable")

        if not table:
            return jsonify({"error": "Drug table not found"}), 404

        drugs = []
        tbody = table.find("tbody")
        if tbody:
            for row in tbody.find_all("tr", class_="ddc-table-row-medication"):
                cells = row.find_all("td")
                a_tag = row.find("a", class_="ddc-text-wordbreak")
                if a_tag and len(cells) >= 3:
                    activity_div = cells[2].find("div")
                    drug = {
                        "name": a_tag.text.strip(),
                        "activity": activity_div["aria-label"].split(":")[1][0:4].strip() if activity_div else "",
                        "url": a_tag["href"],
                    }
                    drugs.append(drug)

        return jsonify(drugs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


# ============== Static File Serving ==============

# Get the directory where this script is located
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def serve_root():
    """Redirect root to welcome page"""
    return redirect('/welcome.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files from the project directory"""
    # If it's a directory, serve index.html from that directory
    full_path = os.path.join(STATIC_DIR, filename)
    if os.path.isdir(full_path):
        return send_from_directory(full_path, 'index.html')
    return send_from_directory(STATIC_DIR, filename)

@app.route('/login/')
def serve_login():
    """Serve login page"""
    return send_from_directory(os.path.join(STATIC_DIR, 'login'), 'index.html')

@app.route('/login/<path:filename>')
def serve_login_files(filename):
    """Serve login static files"""
    return send_from_directory(os.path.join(STATIC_DIR, 'login'), filename)

@app.route('/register/')
def serve_register():
    """Serve register page"""
    return send_from_directory(os.path.join(STATIC_DIR, 'register'), 'index.html')

@app.route('/register/<path:filename>')
def serve_register_files(filename):
    """Serve register static files"""
    return send_from_directory(os.path.join(STATIC_DIR, 'register'), filename)

@app.route('/dashboard/')
def serve_dashboard():
    """Serve dashboard page"""
    return send_from_directory(os.path.join(STATIC_DIR, 'dashboard'), 'index.html')

@app.route('/dashboard/<path:filename>')
def serve_dashboard_files(filename):
    """Serve dashboard static files"""
    return send_from_directory(os.path.join(STATIC_DIR, 'dashboard'), filename)

@app.route('/interactions/')
def serve_interactions():
    """Serve interactions page"""
    return send_from_directory(os.path.join(STATIC_DIR, 'interactions'), 'index.html')

@app.route('/interactions/<path:filename>')
def serve_interactions_files(filename):
    """Serve interactions static files"""
    return send_from_directory(os.path.join(STATIC_DIR, 'interactions'), filename)

@app.route('/descriptions/')
def serve_descriptions():
    """Serve descriptions page"""
    return send_from_directory(os.path.join(STATIC_DIR, 'descriptions'), 'index.html')

@app.route('/descriptions/<path:filename>')
def serve_descriptions_files(filename):
    """Serve descriptions static files"""
    return send_from_directory(os.path.join(STATIC_DIR, 'descriptions'), filename)


# ============== Database Initialization ==============

@app.before_request
def before_request():
    """Initialize database session for request"""
    pass


@app.teardown_appcontext
def teardown_db(exception):
    """Close database session after request"""
    from database import close_session
    close_session()


# ============== Main ==============

if __name__ == "__main__":
    # Initialize database tables
    init_db()
    print("Database initialized!")
    
    # Run the Flask app
    app.run(debug=config.DEBUG, host="0.0.0.0", port=5000)
