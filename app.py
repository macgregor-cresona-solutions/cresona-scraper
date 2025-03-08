from fastapi import FastAPI, BackgroundTasks, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests
import csv
import os
import time

app = FastAPI()

# Enable CORS to allow Webflow requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your Webflow URL later for security
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Define your API key
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Store scraping status
scraping_status = {"progress": 0, "status": "idle"}

# List of valid fields (to prevent errors)
VALID_FIELDS = {
    "places.displayName.text", "places.formattedAddress", "places.rating",
    "places.userRatingCount", "places.internationalPhoneNumber", "places.websiteUri",
    "places.currentOpeningHours.weekdayDescriptions", "places.priceLevel", "places.types",
    "places.editorialSummary", "places.paymentOptions", "places.parkingOptions",
    "places.delivery", "places.takeout", "places.dineIn", "places.reservable",
    "places.servesBreakfast", "places.servesBrunch", "places.servesLunch",
    "places.servesDinner", "places.servesDessert", "places.servesCocktails",
    "places.servesCoffee", "places.servesBeer", "places.servesWine",
    "places.servesVegetarianFood", "places.goodForChildren", "places.goodForGroups",
    "places.goodForWatchingSports", "places.outdoorSeating", "places.liveMusic",
    "places.menuForChildren", "places.allowsDogs", "places.restroom",
    "places.wheelchairAccessibleParking", "places.wheelchairAccessibleRestroom",
    "places.wheelchairAccessibleSeating", "places.fuelOptions", "places.evChargeOptions",
    "places.subDestinations", "places.primaryType", "places.primaryTypeDisplayName",
    "places.type", "places.shortFormattedAddress", "places.vicinity", "places.icon",
    "places.icon_mask_base_uri", "places.icon_background_color", "places.url",
    "places.plus_code", "places.adr_address", "places.address_component"
}

# Function to scrape Google Maps data with selected fields
def scrape_google_maps(search_queries, selected_fields):
    global scraping_status
    scraping_status["progress"] = 0
    scraping_status["status"] = "running"

    results = []
    url = "https://places.googleapis.com/v1/places:searchText"

    # Ensure selected_fields contains only valid values
    selected_fields = set(selected_fields).intersection(VALID_FIELDS)  # Keep only valid fields

    # If no fields are selected, use all valid fields
    if not selected_fields:
        selected_fields = VALID_FIELDS

    # Convert fields to API format
    fields_string = ",".join(selected_fields)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": fields_string
    }

    total_queries = len(search_queries)
    for idx, query in enumerate(search_queries):
        payload = {"textQuery": query}
        response = requests.post(url, json=payload, headers=headers).json()

        if "error" in response:
            print(f"API Error: {response['error']}")
            continue

        for place in response.get("places", []):
            result_row = {field: "" for field in selected_fields}  # Ensure correct column order
            for field in selected_fields:
                field_path = field.replace("places.", "").split(".")  # Normalize field names
                value = place
                for path in field_path:
                    value = value.get(path, "") if isinstance(value, dict) else ""
                result_row[field] = value
            results.append(result_row)

        # Update progress
        scraping_status["progress"] = int(((idx + 1) / total_queries) * 100)

        # Prevent API rate limiting (optional)
        time.sleep(0.5)

    # Save results to CSV
    csv_filename = "scraped_results.csv"
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=selected_fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV saved: {csv_filename}")
    scraping_status["status"] = "completed"
    return csv_filename

# API Endpoint to Start Scraping
@app.post("/start_scraping/")
async def start_scraping(data: dict, background_tasks: BackgroundTasks):
    search_queries = data.get("queries", [])
    selected_fields = data.get("fields", [])

    if not search_queries:
        raise HTTPException(status_code=400, detail="No search queries provided.")

    # Validate selected fields
    selected_fields = list(set(selected_fields).intersection(VALID_FIELDS))

    # Start background scraping
    background_tasks.add_task(scrape_google_maps, search_queries, selected_fields)
    return {"message": "Scraping started. Check progress using /progress endpoint."}

# API Endpoint to Track Scraping Progress
@app.get("/progress/")
async def get_progress():
    return scraping_status

# API Endpoint to Serve the CSV File
@app.get("/download_csv/")
async def download_csv():
    if os.path.exists("scraped_results.csv"):
        return FileResponse("scraped_results.csv", media_type="text/csv", filename="scraped_results.csv")
    else:
        return {"error": "No CSV file found. Please start a new scrape first."}

# Explicitly handle OPTIONS request for /start_scraping/ to prevent CORS issues
@app.options("/start_scraping/")
async def options_scraping(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response
