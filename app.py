from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests
import csv
import os
from dotenv import load_dotenv

# Load API Key
load_dotenv()
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

app = FastAPI()

# Enable CORS for Webflow
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domains for security
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Global variable to track progress
scrape_progress = {"progress": 0}

# Function to scrape Google Places data based on user-selected fields
def scrape_google_maps(search_queries, list_name, fields):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": fields  # Use only selected fields
    }

    results = []
    total_queries = len(search_queries)

    for index, query in enumerate(search_queries):
        response = requests.post(url, json={"textQuery": query}, headers=headers).json()

        for place in response.get("places", []):
            row = [place.get(field, "") for field in fields.split(",")]
            results.append(row)

        scrape_progress["progress"] = int(((index + 1) / total_queries) * 100)

    # Save CSV file
    safe_list_name = list_name.replace(" ", "_")
    csv_filename = f"{safe_list_name}.csv"

    with open(csv_filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(fields.split(","))  # CSV Header
        writer.writerows(results)

    scrape_progress["progress"] = 100
    return csv_filename

# API Endpoint to Start Scraping
@app.post("/start_scraping/")
async def start_scraping(data: dict, background_tasks: BackgroundTasks):
    global scrape_progress
    search_queries = data.get("queries", [])
    list_name = data.get("list_name", "scraped_results")
    fields = data.get("fields", "places.displayName.text,places.formattedAddress")  # Default fields

    scrape_progress["progress"] = 0
    background_tasks.add_task(scrape_google_maps, search_queries, list_name, fields)
    
    return {"message": "Scraping started. You will be able to download the results when complete."}

# API Endpoint to Check Scraping Progress
@app.get("/progress/")
async def get_progress():
    return scrape_progress

# API Endpoint to Download CSV File
@app.get("/download_csv/")
async def download_csv(list_name: str = Query("scraped_results", title="List Name")):
    safe_list_name = list_name.replace(" ", "_")
    csv_filename = f"{safe_list_name}.csv"

    if os.path.exists(csv_filename):
        return FileResponse(csv_filename, media_type="text/csv", filename=csv_filename)
    else:
        return {"error": f"No CSV file found for '{csv_filename}'. Please start a new scrape first."}
