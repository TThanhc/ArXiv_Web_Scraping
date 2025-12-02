import os
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from celery.result import AsyncResult
from celery_worker import scrape_task

app = FastAPI()
templates = Jinja2Templates(directory="Gui")

os.makedirs("downloads", exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start-scrape")
async def start_scrape(
    yymm: str = Form(...),
    start: int = Form(...),
    end: int = Form(...)
):
    # Push task to Celery queue
    task = scrape_task.delay(yymm, start, end)
    # Return Task ID immediately to Frontend
    return JSONResponse({"task_id": task.id})

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    # Check task status based on ID
    task_result = AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        response = {
            'state': task_result.state,
            'percent': 0,
            'status': 'Đang chờ xử lý...'
        }
    elif task_result.state == 'PROGRESS':
        response = {
            'state': task_result.state,
            'percent': task_result.info.get('percent', 0),
            'status': task_result.info.get('status', '')
        }
    elif task_result.state == 'SUCCESS':
        response = {
            'state': task_result.state,
            'percent': 100,
            'status': 'Hoàn tất!',
            'filename': task_result.result.get('filename')
        }
    else:
        # FAILURE
        response = {
            'state': task_result.state,
            'percent': 100,
            'status': str(task_result.info),
        }
    return JSONResponse(response)

@app.get("/download-file/{filename}")
async def download_file(filename: str):
    file_path = os.path.join("downloads", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/zip', filename=filename)
    return JSONResponse({"error": "File not found"}, status_code=404)