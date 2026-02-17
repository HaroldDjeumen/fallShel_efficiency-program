# backend/app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BASE_URL = f"{SUPABASE_URL}/rest/v1"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200


@app.route('/api/Outfit', methods=['GET'])
def get_Outfit():
    try:
        response = httpx.get(f"{BASE_URL}/Outfit?select=*", headers=headers)
        return jsonify(response.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
