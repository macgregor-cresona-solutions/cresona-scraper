from fastapi import FastAPI, BackgroundTasks, HTTPException, Response
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
    allow_methods=["GET", "POST", "OPTIONS"],  # Explicitly allow OPTIONS
    allow_headers=["Content-Type", "Authorization"],  # Only allow needed headers
)

# Define your API key
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Function to scrape Google Maps data with selected fields
def scrape_google_maps(search_queries, selected_fields):
    results = []
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # Ensure selected_fields is a valid list and remove None values
    if not selected_fields or not isinstance(selected_fields, list):
        selected_fields = []
    selected_fields = [field for field in selected_fields if field]  # Remove None values

    # If no fields are selected, use default fields
    if not selected_fields:
        selected_fields = [
            "places.displayName.text", "places.formattedAddress", "places.rating", 
            "places.userRatingCount", "places.internationalPhoneNumber", "places.websiteUri", 
            "places.currentOpeningHours.weekdayDescriptions", "places.priceLevel", "places.types", 
            "places.location", "places.geometry", "places.editorialSummary", "places.paymentOptions", 
            "places.parkingOptions", "places.delivery", "places.takeout", "places.dineIn", 
            "places.reservable", "places.servesBreakfast", "places.servesBrunch", "places.servesLunch", 
            "places.servesDinner", "places.servesDessert", "places.servesCocktails", "places.servesCoffee", 
            "places.servesBeer", "places.servesWine", "places.servesVegetarianFood", "places.goodForChildren", 
            "places.goodForGroups", "places.goodForWatchingSports", "places.outdoorSeating", "places.liveMusic", 
            "places.menuForChildren", "places.allowsDogs", "places.restroom", "places.wheelchairAccessibleEntrance", 
            "places.wheelchairAccessibleParking", "places.wheelchairAccessibleRestroom", "places.wheelchairAccessibleSeating", 
            "places.fuelOptions", "places.evChargeOptions", "places.subDestinations", "places.primaryType", 
            "places.primaryTypeDisplayName", "places.type", "places.shortFormattedAddress", "places.vicinity", 
            "places.icon", "places.icon_mask_base_uri", "places.icon_background_color", "places.url", "places.plus_code", 
            "places.adr_address", "places.address_component"
        ]

    # Convert selected fields into the API request format
    fields_string = ",".join(selected_fields)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,  # API key in headers
        "X-Goog-FieldMask": fields_string  # Dynamically include only selected fields
    }

    for query in search_queries:
        payload = {"textQuery": query}
        response = requests.post(url, json=payload, headers=headers).json()

        # Log errors if API request fails
        if "error" in response:
            print(f"API Error: {response['error']}")

        for place in response.get("places", []):
            result_row = []
            for field in selected_fields:
                field_path = field.replace("places.", "").split(".")  # Remove 'places.' prefix
                value = place
                for path in field_path:
                    value = value.get(path, "") if isinstance(value, dict) else ""
                result_row.append(value)
            results.append(result_row)

    # Ensure CSV is created even if no results
    csv_filename = "scraped_results.csv"
    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(selected_fields)  # Write headers dynamically
        writer.writerows(results)

    print(f"CSV saved: {csv_filename}")
    return csv_filename

# API Endpoint to Start Scraping
@app.post("/start_scraping/")
async def start_scraping(data: dict, background_tasks: BackgroundTasks):
    search_queries = data.get("queries", [])
    selected_fields = data.get("fields", [])  # Get selected fields from request
    
    if not search_queries:
        raise HTTPException(status_code=400, detail="No search queries provided.")

    # Ensure selected_fields is a list and contains valid values
    if not isinstance(selected_fields, list):
        selected_fields = []
    selected_fields = [field for field in selected_fields if field]  # Remove None values

    background_tasks.add_task(scrape_google_maps, search_queries, selected_fields)
    return {"message": "Scraping started. You will be able to download the results when complete."}

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
