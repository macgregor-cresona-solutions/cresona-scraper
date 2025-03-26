from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests
import csv
import os

app = FastAPI()

# Enable CORS for Webflow
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domain for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to track progress
scrape_progress = {"progress": 0}


def fetch_place_details(place_id, user_api_key):
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": user_api_key,
        "X-Goog-FieldMask": (
            "displayName.text,formattedAddress,rating,userRatingCount,"
            "internationalPhoneNumber,websiteUri,currentOpeningHours.weekdayDescriptions,"
            "priceLevel,types,location"
        )
    }
    response = requests.get(url, headers=headers)
    return response.json()


# Function to scrape Google Maps data using user's API key
def scrape_google_maps(search_queries, list_name, user_api_key):
    global scrape_progress
    results = []
    total_queries = len(search_queries)

    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": user_api_key,
        "X-Goog-FieldMask": "places.placeId"
    }

    for index, query in enumerate(search_queries):
        payload = {"textQuery": query}
        response = requests.post(search_url, json=payload, headers=headers).json()

        if "error" in response:
            print(f"API Error: {response['error']}")
            continue

        place_ids = [place["placeId"] for place in response.get("places", [])]

        for place_id in place_ids:
            details = fetch_place_details(place_id, user_api_key)

            results.append([
                details.get("displayName", {}).get("text", ""),
                details.get("formattedAddress", ""),
                details.get("rating", ""),
                details.get("userRatingCount", ""),
                details.get("internationalPhoneNumber", ""),
                details.get("websiteUri", ""),
                ", ".join(details.get("currentOpeningHours", {}).get("weekdayDescriptions", [])),
                details.get("priceLevel", ""),
                ", ".join(details.get("types", [])),
                details.get("location", {}).get("latitude", ""),
                details.get("location", {}).get("longitude", "")
            ])

        scrape_progress["progress"] = int(((index + 1) / total_queries) * 100)

    safe_list_name = list_name.replace(" ", "_").replace("/", "_")
    csv_filename = f"{safe_list_name}.csv"

    with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Name", "Address", "Rating", "Total Reviews", "Phone", "Website",
            "Opening Hours", "Price Level", "Types", "Latitude", "Longitude"
        ])
        writer.writerows(results)

    print(f"✅ CSV saved: {csv_filename}")
    scrape_progress["progress"] = 100
    return csv_filename


@app.post("/start_scraping/")
async def start_scraping(data: dict, background_tasks: BackgroundTasks):
    global scrape_progress
    search_queries = data.get("queries", [])
    list_name = data.get("list_name", "scraped_results")
    user_api_key = data.get("user_api_key", "")

    if not user_api_key:
        return {"error": "Missing user API key."}

    scrape_progress["progress"] = 0
    background_tasks.add_task(scrape_google_maps, search_queries, list_name, user_api_key)
    return {"message": "Scraping started. You will be able to download the results when complete."}


@app.get("/progress/")
async def get_progress():
    return scrape_progress


@app.get("/download_csv/")
async def download_csv(list_name: str = Query("scraped_results", title="List Name")):
    safe_list_name = list_name.replace(" ", "_").replace("/", "_")
    csv_filename = f"{safe_list_name}.csv"

    if os.path.exists(csv_filename):
        return FileResponse(csv_filename, media_type="text/csv", filename=csv_filename)
    else:
        return {"error": f"No CSV file found with name '{csv_filename}'."}
