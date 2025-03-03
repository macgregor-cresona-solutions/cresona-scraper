from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests
import csv
import os

app = FastAPI()

# Enable CORS to allow Webflow requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your Webflow URL later for security
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Define API Key
GOOGLE_PLACES_API_KEY = "AIzaSyCf3hGwBpAm_90mEiCFc_4F9Levblv-gaw"

# Global variable to track progress
scrape_progress = {"progress": 0}

# Function to scrape Google Maps data with progress tracking
def scrape_google_maps(search_queries):
    global scrape_progress
    results = []
    total_queries = len(search_queries)
    
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.displayName.text,places.formattedAddress,places.rating,places.userRatingCount,places.internationalPhoneNumber,places.websiteUri,places.currentOpeningHours.weekdayDescriptions,places.priceLevel,places.types,places.location"
    }

    for index, query in enumerate(search_queries):
        payload = {"textQuery": query}
        response = requests.post(url, json=payload, headers=headers).json()

        # Log errors if API request fails
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

        # Update progress percentage
        scrape_progress["progress"] = int(((index + 1) / total_queries) * 100)

    # Ensure CSV is created even if no results
    csv_filename = "scraped_results.csv"
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Name", "Address", "Rating", "Total Reviews", "Phone", "Website", "Opening Hours", "Price Level", "Types", "Latitude", "Longitude"])
        writer.writerows(results)

    print(f"CSV saved: {csv_filename}")
    scrape_progress["progress"] = 100  # Mark as complete
    return csv_filename

# API Endpoint to Start Scraping
@app.post("/start_scraping/")
async def start_scraping(data: dict, background_tasks: BackgroundTasks):
    global scrape_progress
    search_queries = data.get("queries", [])
    
    # Reset progress
    scrape_progress["progress"] = 0
    
    background_tasks.add_task(scrape_google_maps, search_queries)
    return {"message": "Scraping started. You will be able to download the results when complete."}

# API Endpoint to Check Scraping Progress
@app.get("/progress/")
async def get_progress():
    return scrape_progress

# API Endpoint to Serve the CSV File
@app.get("/download_csv/")
async def download_csv():
    if os.path.exists("scraped_results.csv"):
        return FileResponse("scraped_results.csv", media_type="text/csv", filename="scraped_results.csv")
    else:
        return {"error": "No CSV file found. Please start a new scrape first."}
