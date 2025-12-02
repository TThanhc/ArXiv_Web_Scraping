## 📚 ArXiv & Semantic Scholar Web Scraper

- A Web application designed to automate the collection of scientific papers including TeX source, metadata by ArXiv API and references from Semantic Scholar API.

## ✨ Key Features

- Bulk Scraping: Download multiple papers by specifying Year-Month (YYMM) and ID ranges.

- Comprehensive Data: Retrieves full TeX sources, standardized metadata (JSON), and reference lists (JSON).

- Asynchronous Architecture: Uses Celery + Redis to handle long-running scraping tasks without freezing the web interface.

- Real-time Progress: Live progress bar and status updates using polling mechanisms.

- Cross-Reference Data: Integrates with the Semantic Scholar Graph API to fetch citation details and external IDs.

- User-Friendly UI: Clean interface built with Bootstrap 5 and Jinja2 templates.

## 🛠️ Tech Stack

- Backend: **Python 3.x**, **FastAPI**, **Uvicorn**

- Task Queue & Broker: **Celery**, **Redis**

- Scraping & APIs: arxiv library, requests, Semantic Scholar API

- Frontend: HTML5, CSS3 (Bootstrap), JavaScript (Fetch API)

## 🚀 Usage

1. **Create virtual environment**
    ```bash
    python -m venv venv
    ```

2. **Activate virtual environment**
    ```bash
    source venv/bin/activate    
    ```

3.  **Import necessary library in requirements.txt**
    ```bash
    pip install -r requirements.txt
    ```

4.  **(Optional) Add your Semantic Scholar API key**
    - `SEMANTIC_SCHOLAR_API_KEY = "<YOUR_API_KEY>"`.

5.  **Terminal 1: Starting Redis server**
    ```bash
    sudo service redis-server start
    ```

6. **Terminal 2: Run Celery worke**
    ```bash
    celery -A celery_worker.celery_app worker --loglevel=info
    ```

7. **Terminal 3: Run Web server**
    ```bash
    uvicorn main:app --reload
    ```