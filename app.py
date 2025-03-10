import os
import json
import csv
import requests
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# Set your Google API Key
GOOGLE_PLACES_API_KEY = "YOUR_GOOGLE_API_KEY"

# Store progress in memory (for simplicity)
scraping_progress = {"progress": 0}

@app.route('/start_scraping/', methods=['POST'])
def start_scraping():
    try:
        data = request.json
        search_queries = data.get("queries", [])
        selected_fields = data.get("fields", "").split(",")
        list_name = data.get("list_name", "output")

        if not search_queries or not selected_fields:
            return jsonify({"error": "Missing search queries or selected fields"}), 400

        results = []

        for index, query in enumerate(search_queries):
            print(f"🔍 Searching: {query}")

            # Construct API Request
            url = "https://places.googleapis.com/v1/places:searchText"
            params = {
                "textQuery": query,
                "fields": ",".join(selected_fields),
                "key": GOOGLE_PLACES_API_KEY
            }

            print(f"📤 API Request: {url}")
            print(f"📤 Parameters: {json.dumps(params, indent=2)}")

            response = requests.post(url, headers={"Content-Type": "application/json"}, json=params)

            print(f"🔄 Raw API Response: {response.text}")  # Log full response

            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                continue

            data = response.json()

            if "places" not in data:
                print("⚠️ No 'places' key in API response")
                continue

            for place in data["places"]:
                row = {field: place.get(field, "N/A") for field in selected_fields}
                results.append(row)

            # Update progress
            scraping_progress["progress"] = int(((index + 1) / len(search_queries)) * 100)

        # Save results to CSV
        csv_file = f"{list_name}.csv"
        csv_path = os.path.join(os.getcwd(), csv_file)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=selected_fields)
            writer.writeheader()
            writer.writerows(results)

        return jsonify({"message": "Scraping completed", "file": csv_file})

    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/progress/', methods=['GET'])
def get_progress():
    return jsonify({"progress": scraping_progress["progress"]})

@app.route('/download_csv/', methods=['GET'])
def download_csv():
    list_name = request.args.get("list_name", "output")
    csv_file = f"{list_name}.csv"
    csv_path = os.path.join(os.getcwd(), csv_file)

    if not os.path.exists(csv_path):
        return jsonify({"error": "CSV file not found"}), 404

    return send_file(csv_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
