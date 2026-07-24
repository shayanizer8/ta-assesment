import json
from app.main import app

if __name__ == "__main__":
    openapi_data = app.openapi()
    with open("openapi.json", "w", encoding="utf-8") as f:
        json.dump(openapi_data, f, indent=2)
    print("Exported openapi.json successfully!")
