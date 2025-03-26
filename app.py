from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests
import csv
import os
import time

app = FastAPI()

# Enable CORS for Webflow
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scrape_progress = {"progress": 0}

def scrape_google_places_textsearch(search_queries, list_name, user_api_key):
    global scrape_progress
    results = []
    total_queries = len(search_queries)

    base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    for index, query in enumerate(search_queries):
        params = {
            "query": query,
            "key": user_api_key
        }

        pages_scraped = 0
        while True:
            response = requests.get(base_url, params=params).json()

            if "error_message" in response:
                print(f"API Error: {response['error_message']}")
                break

            for place in response.get("results", []):
                results.append([
                    place.get("name", ""),
                    place.get("formatted_address", ""),
                    place.get("rating", ""),
                    place.get("user_ratings_total", ""),
                    place.get("formatted_phone_number", ""),
                    place.get("website", ""),
                    "",  # opening hours not provided in textsearch
                    "",  # price level
                    ", ".join(place.get("types", [])),
                    place.get("geometry", {}).get("location", {}).get("lat", ""),
                    place.get("geometry", {}).get("location", {}).get("lng", "")
                ])

            pages_scraped += 1
            next_page_token = response.get("next_page_token")

            if next_page_token and pages_scraped < 3:
                time.sleep(2)  # Wait before next page becomes available
                params = {
                    "pagetoken": next_page_token,
                    "key": user_api_key
                }
            else:
                break

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
    background_tasks.add_task(scrape_google_places_textsearch, search_queries, list_name, user_api_key)
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
        return {"error": f"No CSV file found with name '{csv_filename}'. Please start a new scrape first."}
