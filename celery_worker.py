import os
import shutil
import tempfile
from celery import Celery
from core_scraper import run_scraper

# Configure Celery to connect with Redis
# Broker: Send message (Redis)
# Backend: Store results (Redis)
celery_app = Celery(
    "arxiv_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task(bind=True)
def scrape_task(self, yymm, start, end):
    # 1. Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 2. Run scraper and pass self (task instance) to update progress
        run_scraper(yymm, start, end, temp_dir, celery_task=self)
        
        # 3. Compress file
        archive_name = f"arxiv_{yymm}.{start}_{yymm}.{end}"
        # Save zip file to 'downloads' folder in the project for user to download later
        download_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        zip_base_path = os.path.join(download_dir, archive_name)
        shutil.make_archive(zip_base_path, 'zip', temp_dir)
        
        # Clean up temporary folder
        shutil.rmtree(temp_dir)
        
        return {
            'status': 'Completed',
            'percent': 100,
            'filename': f"{archive_name}.zip"
        }
        
    except Exception as e:
        return {'status': 'Failed', 'error': str(e)}