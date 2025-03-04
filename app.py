from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests
import csv
import os
import firebase_admin
from firebase_admin import auth, credentials
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Securely fetch API Key
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Load Firebase credentials from environment variables
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")

if FIREBASE_CREDENTIALS_JSON:
    cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
else:
    raise Exception("Firebase credentials not found! Ensure FIREBASE_CREDENTIALS_JSON is set in Render.")

app = FastAPI()

# Enable CORS for Webflow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# ---- AUTHENTICATION SYSTEM (Firebase) ---- #

# Verify Firebase token
def verify_firebase_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    token = auth_header.split("Bearer ")[-1]
    
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token["uid"]
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ---- SCRAPER FUNCTION ---- #

def scrape_google_maps(search_queries):
    results = []
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName.text,places.formattedAddress,places.rating,places.userRatingCount,places.internationalPhoneNumber,places.websiteUri,places.currentOpeningHours.weekdayDescriptions,places.priceLevel,places.types,places.location"
    }

    for query in search_queries:
        payload = {"textQuery": query}
        response = requests.post(url, json=payload, headers=headers).json()

        if "error" in response:
            print(f"API Error: {response['error']}")

        for place in response.get("places", []):
            results.append([
                place.get("displayName", {}).get("text", ""),
                place.get("formattedAddress", ""),
                place.get("rating", ""),
                place.get("userRatingCount", ""),
                place.get("internationalPhoneNumber", ""),
                place.get("websiteUri", ""),
                ", ".join(place.get("currentOpeningHours", {}).get("weekdayDescriptions", [])),  
                place.get("priceLevel", ""),
                ", ".join(place.get("types", [])),  
                place.get("location", {}).get("latitude", ""),
                place.get("location", {}).get("longitude", "")
            ])

    csv_filename = "scraped_results.csv"
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Name", "Address", "Rating", "Total Reviews", "Phone", "Website", "Opening Hours", "Price Level", "Types", "Latitude", "Longitude"])
        writer.writerows(results)

    return csv_filename

@app.post("/start_scraping/")
async def start_scraping(data: dict, background_tasks: BackgroundTasks, user: str = Depends(verify_firebase_token)):
    search_queries = data.get("queries", [])
    background_tasks.add_task(scrape_google_maps, search_queries)
    return {"message": "Scraping started. You will be able to download the results when complete."}

@app.get("/download_csv/")
async def download_csv(user: str = Depends(verify_firebase_token)):
    if os.path.exists("scraped_results.csv"):
        return FileResponse("scraped_results.csv", media_type="text/csv", filename="scraped_results.csv")
    else:
        return {"error": "No CSV file found. Please start a new scrape first."}
