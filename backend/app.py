import os
import re
from datetime import datetime, UTC
from bson import ObjectId
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import ASCENDING




#
#
# app = Flask(__name__, static_folder='../frontend')
# CORS(app)
#
# # MongoDB setup
# app.config["MONGO_URI"] = "mongodb://localhost:27017/voting_system"
# mongo = PyMongo(app)
#
# # Collections
# db = mongo.db
# users_collection = db["users"]
# candidates_collection = db["candidates"]
# elections_collection = db["elections"]
# votes_collection = db["votes"]

from flask import Flask
from flask_pymongo import PyMongo
from flask_cors import CORS

app = Flask(__name__, static_folder='../frontend')
CORS(app)

# MongoDB Atlas connection
app.config["MONGO_URI"] = "mongodb+srv://rajesh3656r:h0w09iMnXKrTtp9Z@cluster0.w3hbcpb.mongodb.net/voting_system?retryWrites=true&w=majority"

mongo = PyMongo(app)
app.config["MONGO_URI"] =   os.environ.get("MONGO_URI")
# Access collections
db = mongo.db
users_collection = db["users"]
candidates_collection = db["candidates"]
elections_collection = db["elections"]
votes_collection = db["votes"]

#Developed by Rajesh K
#contact: Rajesh3656r@gmail.com || 8217354109

# Utility
def serialize(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    return obj


def election_status(election):
    now = datetime.utcnow()
    if election["start_time"] > now:
        return "Upcoming"
    elif election["end_time"] < now:
        return "Ended"
    else:
        return "Live"


users_collection.create_index("email", unique=True)


# Serve frontend
@app.route('/')
def home():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)


# ========= AUTH ROUTES =========

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password')
    phone = data.get('phone', '').strip()
    age = data.get('age')

    if not all([name, email, password, phone, age]):
        return jsonify({"message": "All fields are required"}), 400

    try:
        age = int(age)
        if age < 18 or age > 120:
            raise ValueError
    except ValueError:
        return jsonify({"message": "Age must be a number between 18 and 120"}), 400

    if not re.match(r'^\S+@\S+\.\S+$', email):
        return jsonify({"message": "Invalid email format"}), 400

    if users_collection.find_one({'email': email}):
        return jsonify({"message": "Email already registered"}), 409

    user = {
        "name": name,
        "email": email,
        "password": generate_password_hash(password),
        "phone": phone,
        "age": age,
        "role": "voter",
        "status": "pending",
        "is_approved": False,
        "has_voted": False
    }
    users_collection.insert_one(user)
    return jsonify({"message": "User registered successfully"}), 201


@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password')

    user = users_collection.find_one({'email': email})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'message': 'Invalid credentials'}), 401

    if not user.get('is_approved'):
        return jsonify({'message': 'Account not approved yet'}), 403

    return jsonify({
        'message': 'Login successful',
        'user': {
            'id': str(user['_id']),
            'email': user['email'],
            'role': user.get('role', 'voter'),
            'is_approved': True
        }
    }), 200


# ========= ADMIN - VOTER MANAGEMENT =========

@app.route('/admin/pending', methods=['GET'])
def get_pending_voters():
    voters = list(users_collection.find({"role": "voter", "status": "pending", "is_approved": False}, {"password": 0}))
    return jsonify(serialize(voters)), 200


@app.route('/admin/approve/<email>', methods=['POST'])
def approve_voter(email):
    result = users_collection.update_one({"email": email}, {"$set": {"is_approved": True, "status": "approved"}})
    if result.modified_count:
        return jsonify({"message": "Voter approved"}), 200
    return jsonify({"message": "Voter not found or already approved"}), 404


@app.route('/admin/reject/<email>', methods=['DELETE'])
def reject_voter(email):
    result = users_collection.delete_one({"email": email, "status": "pending"})
    if result.deleted_count:
        return jsonify({"message": "Voter rejected"}), 200
    return jsonify({"message": "Voter not found or already handled"}), 404


# ========= ADMIN - CANDIDATE MANAGEMENT =========

@app.route('/admin/candidates/pending', methods=['GET'])
def fetch_pending_candidates():
    candidates = list(candidates_collection.find({"is_approved": False}))
    return jsonify(serialize(candidates)), 200


@app.route('/admin/candidate/approve/<candidate_id>', methods=['POST'])
def api_approve_candidate(candidate_id):
    try:
        result = candidates_collection.update_one(
            {"_id": ObjectId(candidate_id)},
            {"$set": {"is_approved": True}}
        )
        if result.modified_count:
            return jsonify({"message": "Candidate approved"}), 200
    except:
        return jsonify({"message": "Invalid candidate ID"}), 400
    return jsonify({"message": "Candidate not found"}), 404


@app.route('/admin/candidate/reject/<candidate_id>', methods=['DELETE'])
def api_reject_candidate(candidate_id):
    try:
        result = candidates_collection.delete_one({"_id": ObjectId(candidate_id)})
        if result.deleted_count:
            return jsonify({"message": "Candidate rejected"}), 200
    except:
        return jsonify({"message": "Invalid candidate ID"}), 400
    return jsonify({"message": "Candidate not found"}), 404

#Developed  by Rajesh
# contact: Rajesh3656r@gmail.com || 8217354109
# ========= ADMIN - ELECTION MANAGEMENT =========

@app.route('/api/create_election', methods=['POST'])
def create_election():
    data = request.json
    required = ['title', 'voting_type', 'position', 'election_date', 'start_time', 'end_time']

    # ✅ Check all fields
    if not all(data.get(field) for field in required):
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    title = data['title'].strip()

    # ✅ Duplicate check
    if elections_collection.find_one({'title': title}):
        return jsonify({'success': False, 'message': 'Election already exists.'}), 400

    try:
        # ✅ Parse and validate date and time
        election_date = datetime.strptime(data['election_date'], '%Y-%m-%d').date()
        start_dt = datetime.strptime(data['start_time'], '%H:%M').time()
        end_dt = datetime.strptime(data['end_time'], '%H:%M').time()

        if start_dt >= end_dt:
            raise ValueError("Start time must be before end time")

    except Exception as e:
        return jsonify({'success': False, 'message': f'Invalid date/time format or range: {str(e)}'}), 400

    # ✅ Save to DB (as date + time separately)
    elections_collection.insert_one({
        'title': title,
        'voting_type': data['voting_type'],
        'position': data['position'],
        'election_date': election_date.strftime('%Y-%m-%d'),    # stored as string for simplicity
        'start_time': start_dt.strftime('%H:%M'),               # store as plain time string
        'end_time': end_dt.strftime('%H:%M'),
        'status': 'upcoming',
        'created_at': datetime.utcnow()
    })

    return jsonify({'success': True, 'message': 'Election created'}), 201

# ========= VOTER DASHBOARD =========
import pytz
IST = pytz.timezone('Asia/Kolkata')
# ✅ Helper function to check if voter has voted in an election
def has_voter_voted(email, election_id):
    vote = mongo.db.votes.find_one({
        "email": email,
        "election_id": election_id
    })
    return vote is not None




# ✅ Get candidates for a specific election
@app.route('/api/get_candidates', methods=['POST'])
def get_candidates():
    data = request.get_json()
    election_id = data.get('election_id')

    candidates = list(mongo.db.candidates.find({
        "election_id": election_id,
        "status": "approved"
    }))

    formatted = [{
        "id": str(c["_id"]),
        "name": c["name"],
        "party": c["party"]
    } for c in candidates]

    return jsonify(formatted), 200


# ✅ Cast Vote
@app.route('/api/cast_vote_confirmed', methods=['POST'])
def cast_vote_c():
    data = request.get_json()
    email = data.get("email")
    election_id = data.get("election_id")
    candidate_id = data.get("candidate_id")

    # Check if already voted
    if has_voter_voted(email, election_id):
        return jsonify({"message": "You have already voted in this election."}), 400

    # Insert vote
    vote = {
        "email": email,
        "election_id": election_id,
        "candidate_id": candidate_id,
        "timestamp": datetime.now(IST)
    }
    mongo.db.votes.insert_one(vote)

    return jsonify({"message": "Vote cast successfully."}), 200


# Utility: Convert ObjectId
def serialize_candidate(candidate):
    return {
        "_id": str(candidate["_id"]),
        "name": candidate["name"],
        "party": candidate["party"],
        "election_id": str(candidate["election_id"])
    }

def serialize_election(election):
    return {
        "_id": str(election["_id"]),
        "title": election["title"],
        "start_time": election.get("start_time"),
        "end_time": election.get("end_time")
    }

# ✅ Route: Get all elections
@app.route("/api/elections/list", methods=["GET"])
def list_elections():
    try:
        elections = elections_collection.find()
        return jsonify([serialize_election(e) for e in elections]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Route: Get candidates by election ID
@app.route("/api/candidates/by-election/<election_id>", methods=["GET"])
def get_candidates_for_election(election_id):
    try:
        candidates = candidates_collection.find({ "election_id": ObjectId(election_id) })
        return jsonify([serialize_candidate(c) for c in candidates]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Route: Add a new candidate
@app.route("/api/candidates/add", methods=["POST"])
def add_candidate():
    data = request.get_json()
    name = data.get("name")
    party = data.get("party")
    election_id = data.get("election_id")

    if not all([name, party, election_id]):
        return jsonify({"message": "Missing fields"}), 400

    try:
        # Check for duplicates
        existing = candidates_collection.find_one({
            "name": {"$regex": f"^{name}$", "$options": "i"},
            "party": {"$regex": f"^{party}$", "$options": "i"},
            "election_id": ObjectId(election_id)
        })
        if existing:
            return jsonify({"message": "Candidate already exists for this election"}), 409

        new_candidate = {
            "name": name,
            "party": party,
            "election_id": ObjectId(election_id),
            "status":"pending"
        }
        candidates_collection.insert_one(new_candidate)
        return jsonify({"message": "Candidate added successfully"}), 201
    except Exception as e:
        return jsonify({"message": str(e)}), 500


# candidate Approval

@app.route("/api/candidates/pending", methods=["GET"])
def get_pending_candidates():
    candidates = list(candidates_collection.find({"status": "pending"}))
    for c in candidates:
        c["_id"] = str(c["_id"])
    return jsonify(candidates), 200

@app.route("/api/candidates/approve/<candidate_id>", methods=["POST"])
def approve_candidate(candidate_id):
    result = candidates_collection.update_one(
        {"_id": ObjectId(candidate_id)},
        {"$set": {"status": "approved"}}
    )
    if result.modified_count == 1:
        return jsonify({"message": "Candidate approved"}), 200
    return jsonify({"message": "Candidate not found or already approved"}), 404

@app.route("/api/candidates/reject/<candidate_id>", methods=["DELETE"])
def reject_candidate(candidate_id):
    result = candidates_collection.delete_one({"_id": ObjectId(candidate_id)})
    if result.deleted_count == 1:
        return jsonify({"message": "Candidate rejected"}), 200
    return jsonify({"message": "Candidate not found"}), 404
@app.route("/api/get_ele", methods=["POST"])
def get_elections_for_voter():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email is required"}), 400

    # Case-insensitive match
    voter = votes_collection.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
    voted_elections = voter.get("voted_elections", [])  # should be a list of election _id strings
    all_elections = list(elections_collection.find())
    now = datetime.now()

    not_voted_live = []
    voted = []
    upcoming = []

    for election in all_elections:
        election_id = str(election["_id"])
        start = election["start_time"]
        end = election["end_time"]

        status = "Upcoming"
        if start <= now <= end:
            status = "Live"
        elif now > end:
            status = "Ended"

        ele_info = {
            "_id": election_id,
            "title": election["name"],
            "description": election.get("description", ""),
            "status": status
        }

        if election_id in voted_elections:
            voted.append(ele_info)
        elif status == "Live":
            not_voted_live.append(ele_info)
        elif status == "Upcoming":
            upcoming.append(ele_info)

    return jsonify({
        "not_voted": not_voted_live,
        "voted": voted,
        "upcoming": upcoming
    }), 200



@app.route("/api/get_available_elections", methods=["POST"])
def voter_get_available_elections():
    data = request.json
    email = data.get("email")

    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"message": "User not found"}), 404

    all_elections = list(elections_collection.find({}))
    response = []

    for election in all_elections:
        has_voted = votes_collection.find_one({
            "email": email,
            "election_id": str(election["_id"])
        }) is not None

        # Determine live or upcoming
        now = datetime.now()
        start = datetime.strptime(f"{election['election_date']} {election['start_time']}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{election['election_date']} {election['end_time']}", "%Y-%m-%d %H:%M")

        if now < start:
            status = "upcoming"
        elif start <= now <= end:
            status = "live"
        else:
            status = "completed"

        response.append({
            "id": str(election["_id"]),
            "title": election["title"],
            "status": status,
            "voted": has_voted
        })

    return jsonify(response)

@app.route("/api/cast_vote_confirmed", methods=["POST"])
def cast_vote_confirmed():
    data = request.json
    email = data.get("email")
    election_id = data.get("election_id")
    candidate_id = data.get("candidate_id")

    if not all([email, election_id, candidate_id]):
        return jsonify({"message": "Missing data"}), 400

    existing_vote = votes_collection.find_one({
        "email": email,
        "election_id": election_id
    })

    if existing_vote:
        return jsonify({"message": "You have already voted in this election"}), 400

    vote_doc = {
        "email": email,
        "election_id": election_id,
        "candidate_id": candidate_id,
        "voted_at": datetime.now()
    }

    votes_collection.insert_one(vote_doc)

    # Optionally update has_voted field in user record
    users_collection.update_one({"email": email}, {"$set": {"has_voted": True}})

    return jsonify({"message": "Your vote has been recorded successfully."})



def serialize_election(election):
    return {
        "_id": str(election["_id"]),
        "title": election.get("title", "Unnamed"),
        "election_date": election["election_date"],
        "start_time": election["start_time"],
        "end_time": election["end_time"],
        "position": election.get("position", "Not Specified"),
        "status": election.get("status", "upcoming")
    }

# ✅ GET all elections
@app.route('/api/elections', methods=['GET'])
def c_get_elections():
    elections = list(elections_collection.find())
    return jsonify([serialize_election(e) for e in elections]), 200

# ✅ PUT update election status
@app.route('/api/elections/status/<string:election_id>', methods=['PUT'])
def update_election_status(election_id):
    new_status = request.json.get("status")
    if new_status not in ["upcoming", "live", "ended"]:
        return jsonify({"error": "Invalid status"}), 400

    result = elections_collection.update_one(
        {"_id": ObjectId(election_id)},
        {"$set": {"status": new_status}}
    )

    if result.matched_count == 0:
        return jsonify({"error": "Election not found"}), 404

    return jsonify({"message": "Election status updated"}), 200

# ✅ Get all elections
@app.route("/api/elections/voter", methods=["GET"])
def get_elections_vote():
    data = list(elections_collection.find())
    for e in data:
        e["_id"] = str(e["_id"])
    return jsonify(data), 200

# ✅ Get approved candidates for an election
@app.route("/api/candidates/<election_id>", methods=["GET"])
def get_approved_candidates(election_id):
    data = list(candidates_collection.find({
        "election_id": election_id,
        "status": "approved"
    }))
    for c in data:
        c["_id"] = str(c["_id"])
    return jsonify(data), 200

# ✅ Cast a vote (one vote per election)
@app.route("/api/vote/voter", methods=["POST"])
def cast_vote_voter():
    data = request.json
    voter_id = data.get("voter_id")
    election_id = data.get("election_id")
    candidate_id = data.get("candidate_id")

    if votes_collection.find_one({"voter_id": voter_id, "election_id": election_id}):
        return jsonify({"message": "You have already voted in this election."}), 400

    vote = {
        "voter_id": voter_id,
        "election_id": election_id,
        "candidate_id": candidate_id,
        "timestamp": datetime.utcnow()
    }
    votes_collection.insert_one(vote)
    return jsonify({"message": "Vote successfully cast."}), 200

# ✅ Get voter by email
@app.route("/api/voter_by_email", methods=["POST"])
def get_voter_by_email():
    data = request.json
    voter = votes_collection.find_one({"email": data.get("email")})
    if not voter:
        return jsonify({"message": "Voter not found"}), 404
    voter["_id"] = str(voter["_id"])
    return jsonify(voter), 200
def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

@app.route("/api/vote_by_email", methods=["POST"])
def vote_by_email():
    data = request.get_json()
    email = data.get("email")
    election_id = data.get("election_id")
    candidate_id = data.get("candidate_id")

    if not all([email, election_id, candidate_id]):
        return jsonify({"message": "Missing data"}), 400

    voter = votes_collection.find_one({"email": email})
    if not voter:
        return jsonify({"message": "Voter not found"}), 404

    # Check if already voted
    if election_id in voter.get("voted_elections", []):
        return jsonify({"message": "You have already voted in this election"}), 400

    # Save vote (you may also want to update candidate vote count here)
    votes_collection.update_one(
        {"_id": voter["_id"]},
        {"$push": {"voted_elections": election_id}}
    )

    return jsonify({"message": "Vote cast successfully"}), 200




# ----------------------
# 1. Get Voter Details
def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

@app.route("/api/get_voter_details/fetch", methods=["POST"])
def get_voter_details_vv():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    voter = users_collection.find_one({"email": email})

    if not voter:
        return jsonify({"error": "Voter not found"}), 404

    return jsonify(serialize_doc(voter)), 200


# --------------------------------
# 2. Get Elections for Voter
# --------------------------------
@app.route("/api/elections/voter/vote", methods=["GET"])
def get_elections_V():
    now = datetime.now()
    elections = elections_collection.find()

    live, upcoming, ended = [], [], []
    for e in elections:
        start_dt = datetime.strptime(f"{e['election_date']} {e['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{e['election_date']} {e['end_time']}", "%Y-%m-%d %H:%M")

        e_serialized = serialize(e)
        if start_dt <= now <= end_dt:
            live.append(e_serialized)
        elif now < start_dt:
            upcoming.append(e_serialized)
        else:
            ended.append(e_serialized)

    return jsonify({
        "live": live,
        "upcoming": upcoming,
        "ended": ended
    })

# ----------------------------------------
# 3. Get Approved Candidates for Election
# ----------------------------------------
from bson import ObjectId
from bson.errors import InvalidId

@app.route("/api/candidates/v/<election_id>", methods=["GET"])
def get_candidates_v(election_id):
    try:
        obj_id = ObjectId(election_id)
    except InvalidId:
        return jsonify({"error": "Invalid election ID format"}), 400

    candidates = candidates_collection.find({
        "election_id": obj_id,
        "status": "approved"
    })

    return jsonify([serialize(c) for c in candidates])


# ----------------------------
# 4. Cast Vote by Voter ID
# ----------------------------
@app.route("/api/vote/voter/v", methods=["POST"])
def cast_vote_v():
    data = request.json
    voter_id = data.get("voter_id")
    election_id = data.get("election_id")
    candidate_id = data.get("candidate_id")

    # Prevent double voting
    existing_vote = votes_collection.find_one({
        "voter_id": voter_id,
        "election_id": election_id
    })
    if existing_vote:
        return jsonify({"message": "You have already voted in this election."}), 400

    vote_doc = {
        "voter_id": voter_id,
        "election_id": election_id,
        "candidate_id": candidate_id,
        "timestamp": datetime.utcnow()
    }
    votes_collection.insert_one(vote_doc)

    return jsonify({"message": "Vote cast successfully!"})

# Result

@app.route("/api/get_all_election_results")
def get_all_election_results():
    elections = list(db.elections.find({}))
    results = []

    for election in elections:
        election_id_str = str(election["_id"])

        candidates = list(db.candidates.find({
            "election_id": ObjectId(election_id_str),
            "status": "approved"
        }))

        formatted_candidates = []
        for c in candidates:
            candidate_id_str = str(c["_id"])
            vote_count = db.votes.count_documents({
                "election_id": election_id_str,
                "candidate_id": candidate_id_str
            })

            formatted_candidates.append({
                "name": c["name"],
                "party": c["party"],
                "votes": vote_count
            })

        results.append({
            "title": election.get("title"),
            "election_date": election.get("election_date"),
            "status": election.get("status"),
            "candidates": formatted_candidates
        })

    return jsonify(results)

#Election manage


def serialize_elections(election):
    return {
        "_id": str(election["_id"]),
        "title": election.get("title", ""),
        "position": election.get("position", ""),
        "election_date": election.get("election_date", ""),
        "start_time": election.get("start_time", ""),
        "end_time": election.get("end_time", ""),
        "status": election.get("status", "upcoming")
    }

# Route: Get all elections
@app.route('/api/elections/mm', methods=['GET'])
def get_all_elections_mm():
    elections = list(elections_collection.find())
    return jsonify([serialize_elections(e) for e in elections])

@app.route('/api/elections/status/mm/<election_id>', methods=['PUT'])
def update_election_status_mm(election_id):
    try:
        new_status = request.json.get('status')
        if new_status not in ['upcoming', 'live', 'ended']:
            return jsonify({'error': 'Invalid status'}), 400

        result = elections_collection.update_one(
            {'_id': ObjectId(election_id)},
            {'$set': {'status': new_status}}
        )

        if result.modified_count == 1:
            return jsonify({'message': 'Status updated successfully'}), 200
        else:
            return jsonify({'message': 'No update performed or election not found'}), 404

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ========= SERVER =========
if __name__ == '__main__':
    app.run(debug=True)

#Developed  by Rajesh
# contact: Rajesh3656r@gmail.com || 8217354109