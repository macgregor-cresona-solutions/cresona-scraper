from fastapi import FastAPI, HTTPException, Query
import requests
import csv
import os
from dotenv import load_dotenv
from fastapi.responses import FileResponse
import tempfile

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Get API Key from environment variable
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Base URL for Google Places API
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

# Default fields to pull if the user does not select any
DEFAULT_FIELDS = [
    "name", "formatted_address", "place_id", "website", "formatted_phone_number",
    "international_phone_number", "opening_hours", "secondary_opening_hours",
    "regularSecondaryOpeningHours", "rating", "user_ratings_total", "reviews",
    "price_level", "business_status", "permanently_closed", "geometry",
    "photo", "editorial_summary", "paymentOptions", "parkingOptions",
    "delivery", "takeout", "dine_in", "curbside_pickup", "reservable",
    "servesBreakfast", "servesBrunch", "servesLunch", "servesDinner",
    "servesDessert", "servesCocktails", "servesCoffee", "servesBeer",
    "servesWine", "servesVegetarianFood", "goodForChildren", "goodForGroups",
    "goodForWatchingSports", "outdoorSeating", "liveMusic", "menuForChildren",
    "allowsDogs", "restroom", "wheelchairAccessibleEntrance",
    "wheelchairAccessibleParking", "wheelchairAccessibleRestroom",
    "wheelchairAccessibleSeating", "fuelOptions", "evChargeOptions",
    "subDestinations", "primaryType", "primaryTypeDisplayName", "type",
    "shortFormattedAddress", "vicinity", "icon", "icon_mask_base_uri",
    "icon_background_color", "url", "plus_code", "adr_address",
    "address_component"
]

# Temporary file for CSV storage
TEMP_CSV_FILE = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")

@app.get("/start_scraping/")
async def start_scraping(
    search_query: str = Query(..., description="Search query (e.g., 'Landscaping Companies in 99507')"),
    selected_fields: str = Query("", description="Comma-separated list of selected fields")
):
    """
    Search Google Places API and return results as a CSV file.
    """
    # If no fields were selected, use all default fields
    selected_fields_list = selected_fields.split(",") if selected_fields else DEFAULT_FIELDS

    # Format field mask for Google API
    field_mask = ",".join(selected_fields_list)

    # Prepare the request payload
    payload = {
        "textQuery": search_query,
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": field_mask  # This ensures we only get required fields
    }

    # Send request to Google Places API
    response = requests.post(GOOGLE_PLACES_URL, json=payload, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    data = response.json()

    # Extract results
    places = data.get("places", [])

    # Write results to CSV
    with open(TEMP_CSV_FILE.name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Write headers
        writer.writerow(selected_fields_list)

        # Write data
        for place in places:
            row = [place.get(field, "") for field in selected_fields_list]
            writer.writerow(row)

    return {"message": "Scraping complete! Download your CSV file.", "csv_url": "/download_csv"}

@app.get("/download_csv/")
async def download_csv():
    """
    Serve the generated CSV file for download.
    """
    return FileResponse(TEMP_CSV_FILE.name, filename="scraped_data.csv", media_type="text/csv")
