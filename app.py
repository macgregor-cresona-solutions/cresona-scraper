from fastapi import FastAPI, BackgroundTasks, Query, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import requests
import csv
import os
from dotenv import load_dotenv
from hunter_search import process_hunter_search  # Import the Hunter.io processing function

# Load environment variables
load_dotenv()

# Fetch API Key securely
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

# Function to scrape Google Maps data with progress tracking
def scrape_google_maps(search_queries, list_name):
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

    # Ensure CSV filename is based on user input
    safe_list_name = list_name.replace(" ", "_").replace("/", "_")  # Prevent issues with spaces or slashes
    csv_filename = f"{safe_list_name}.csv"

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
    list_name = data.get("list_name", "scraped_results")  # Default to 'scraped_results' if no name is provided

    scrape_progress["progress"] = 0  # Reset progress

    background_tasks.add_task(scrape_google_maps, search_queries, list_name)
    return {"message": "Scraping started. You will be able to download the results when complete."}

# API Endpoint to Check Scraping Progress
@app.get("/progress/")
async def get_progress():
    return scrape_progress

# API Endpoint to Serve the CSV File
@app.get("/download_csv/")
async def download_csv(list_name: str = Query("scraped_results", title="List Name")):
    """ Serve the requested CSV file """
    safe_list_name = list_name.replace(" ", "_").replace("/", "_")  # Sanitize filename
    csv_filename = f"{safe_list_name}.csv"

    if os.path.exists(csv_filename):
        return FileResponse(csv_filename, media_type="text/csv", filename=csv_filename)
    else:
        return {"error": f"No CSV file found with name '{csv_filename}'. Please start a new scrape first."}

# API Endpoint to Handle CSV Upload for Hunter.io Domain Search
@app.post("/hunter_upload/")
async def upload_csv_file(file: UploadFile = File(...)):
    """ Handles CSV upload and processes Hunter.io Domain Search """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")

    file_path = f"./uploads/{file.filename}"
    os.makedirs("./uploads", exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Process Hunter.io Search
    results = process_hunter_search(file_path)

    return JSONResponse(content=results)
