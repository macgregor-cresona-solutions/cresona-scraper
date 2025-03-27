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
    allow_origins=["*"],  # Replace with your domain for better security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scrape_progress = {"progress": 0}

# Scraping function
def scrape_google_maps(search_queries, list_name, user_api_key):
    global scrape_progress
    results = []
    total_queries = len(search_queries)

    search_url = "https://places.googleapis.com/v1/places:searchText"
    detail_url_template = "https://places.googleapis.com/v1/places/{}?fields=displayName,formattedAddress,rating,userRatingCount,internationalPhoneNumber,websiteUri,currentOpeningHours,priceLevel,types,location&key={}"

    for index, query in enumerate(search_queries):
        all_place_ids = []
        page_token = None
        pages_scraped = 0

        # Loop through up to 3 pages (max ~60 results per query)
        while pages_scraped < 3:
            payload = {"textQuery": query}
            if page_token:
                payload["pageToken"] = page_token

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": user_api_key,
                "X-Goog-FieldMask": "places.id,nextPageToken"
            }

            response = requests.post(search_url, json=payload, headers=headers).json()

            if "error" in response:
                print(f"API Error (searchText): {response['error']}")
                return {"error": f"API Error: {response['error']['message']}"}

            place_ids = [place["id"] for place in response.get("places", [])]
            all_place_ids.extend(place_ids)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

            pages_scraped += 1

        # For each place_id, get more details
        for place_id in all_place_ids:
            detail_url = detail_url_template.format(place_id, user_api_key)
            detail_response = requests.get(detail_url).json()

            if "error" in detail_response:
                print(f"API Error (getPlace): {detail_response['error']}")
                continue

            results.append([ 
                detail_response.get("displayName", {}).get("text", ""),
                detail_response.get("formattedAddress", ""),
                detail_response.get("rating", ""),
                detail_response.get("userRatingCount", ""),
                detail_response.get("internationalPhoneNumber", ""),
                detail_response.get("websiteUri", ""),
                ", ".join(detail_response.get("currentOpeningHours", {}).get("weekdayDescriptions", [])),
                detail_response.get("priceLevel", ""),
                ", ".join(detail_response.get("types", [])),
                detail_response.get("location", {}).get("latitude", ""),
                detail_response.get("location", {}).get("longitude", "")
            ])

        scrape_progress["progress"] = int(((index + 1) / total_queries) * 100)

    # Save results to CSV
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

# Start scraping endpoint
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

# Check progress endpoint
@app.get("/progress/")
async def get_progress():
    return scrape_progress

# Download CSV endpoint
@app.get("/download_csv/")
async def download_csv(list_name: str = Query("scraped_results", title="List Name")):
    safe_list_name = list_name.replace(" ", "_").replace("/", "_")
    csv_filename = f"{safe_list_name}.csv"

    if os.path.exists(csv_filename):
        return FileResponse(csv_filename, media_type="text/csv", filename=csv_filename)
    else:
        return {"error": f"No CSV file found with name '{csv_filename}'. Please start a new scrape first."}
