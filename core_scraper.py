# core_scraper.py
import arxiv
import os
import re
import json
import io
import requests
import tarfile
import gzip
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import posixpath
from datetime import datetime
from bs4 import BeautifulSoup

# =============== Const ===============
SEARCH_DELAY_SECONDS = 3
TIMEOUT = 60
SEMANTIC_SCHOLAR_API_KEY = "v3qmwZ0rHH7JsdzxzCHAD6xsjLtgDbP24PRuU4sY" 
USER_AGENT = "arxiv-Lab01-scraper/1.0"
HTTP_TIMEOUT = 300
# =====================================

def make_session(user_agent=USER_AGENT, retries=5, backoff=0.5):
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def safe_join(root, name):
    norm = posixpath.normpath(name)
    if norm.startswith("/"):
        norm = norm.lstrip("/")
    parts = [p for p in norm.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        raise ValueError("Unsafe path")
    joined = os.path.join(root, *parts) if parts else os.path.join(root, "")
    root_abs = os.path.abspath(root)
    joined_abs = os.path.abspath(joined)
    if os.path.commonpath([root_abs, joined_abs]) != root_abs:
        raise ValueError("Path outside destination")
    return joined_abs

def download_version_source(arxiv_id_ver, session):
    url = f"https://arxiv.org/e-print/{arxiv_id_ver}"
    r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    return r.content

def extract_tar_gz(tar_bytes: bytes, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.isdir():
                    continue
                if not member.isfile():
                    continue
                base = os.path.basename(member.name)
                if not base or not base.lower().endswith((".tex", ".bib")):
                    continue
                try:
                    src = tar.extractfile(member)
                    if src:
                        dst = safe_join(out_dir, member.name)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with open(dst, "wb") as f:
                            f.write(src.read())
                except Exception:
                    continue
    except tarfile.ReadError:
        # Fallback for single .gz file
        try:
            decompressed = gzip.decompress(tar_bytes)
            # Create a dummy filename for the single tex file
            dst = os.path.join(out_dir, "main_source.tex")
            with open(dst, "wb") as f:
                f.write(decompressed)
        except Exception:
            pass 

def get_dates_from_html(base_id):
    url = f"https://arxiv.org/abs/{base_id}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200: return [], []
        soup = BeautifulSoup(res.text, "html.parser")
        history = soup.find("div", class_="submission-history")
        if not history: return []
        dates = []
        for line in history.text.split("\n"):
            m_date = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", line)
            if m_date:
                dt = datetime.strptime(m_date.group(1), "%d %b %Y")
                dates.append(dt.strftime("%Y-%m-%d"))
        return dates
    except:
        return []

def fetch_arxiv_metadata(base_id, client):
    revised_dates = get_dates_from_html(base_id)
    try:
        search = arxiv.Search(id_list=[base_id])
        paper = next(client.results(search))
    except:
        return None
    
    title = getattr(paper, "title", "N/A")
    authors = [getattr(a, "name", str(a)) for a in getattr(paper, "authors", [])]
    venue = getattr(paper, "journal_ref", None) or "arXiv"
    submission_date = revised_dates[0] if len(revised_dates) >= 1 else (
        paper.published.date().isoformat() if getattr(paper, "published", None) else "N/A"
    )
    return {
        "paper_title": title,
        "authors": authors,
        "publication_venue": venue,
        "submission_date": submission_date,
        "revised_dates": list(dict.fromkeys(revised_dates))
    }

def fetch_references_semanticscholar(arxiv_id, session):
    base_id = arxiv_id.split('v')[0]
    fields = 'references.title,references.authors,references.externalIds,references.paperId,references.publicationDate'
    url = f"https://api.semanticscholar.org/graph/v1/paper/ARXIV:{base_id}?fields={fields}"
    headers = {"User-Agent": USER_AGENT}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    
    try:
        r = session.get(url, headers=headers, timeout=30) # Reduced timeout for web
        if r.status_code == 200:
            data = r.json()
            refs = {}
            for ref in data.get('references', []):
                ext = ref.get('externalIds') or {}
                arx = ext.get('ArXiv') or ext.get('arXiv')
                if not arx: continue
                
                # Simple extraction logic for demo
                arx_val = arx.get('value') if isinstance(arx, dict) else arx
                if not arx_val: continue
                arx_norm = str(arx_val).replace("arXiv:", "").split("v")[0]
                
                refs[arx_norm.replace('.', '-')] = {
                    'paper_title': ref.get('title'),
                    'authors': [a.get('name') for a in ref.get('authors', [])],
                    'submission_date': ref.get('publicationDate')
                }
            return refs
    except:
        pass
    return {}

def fetch_all_versions(yymm, id, save_root, client, session):
    arxiv_id = f"{yymm}.{id}"
    try:
        paper = next(client.results(arxiv.Search(id_list=[arxiv_id])))
    except StopIteration:
        return
    
    # Logic to find latest version
    latest_v = 1
    m = re.search(r'v(\d+)$', paper.entry_id or "")
    if m: latest_v = int(m.group(1))

    # Download source
    for v in range(1, latest_v + 1):
        vers_id = f"{arxiv_id}v{v}"
        out_dir = os.path.join(save_root, "tex", f"{yymm}-{id}v{v}")
        try:
            tar_bytes = download_version_source(vers_id, session)
            extract_tar_gz(tar_bytes, out_dir)
        except Exception:
            pass

    # Metadata & Refs
    md = fetch_arxiv_metadata(arxiv_id, client)
    if md:
        with open(os.path.join(save_root, "metadata.json"), 'w', encoding='utf-8') as f:
            json.dump(md, f, ensure_ascii=False, indent=2)
    
    refs = fetch_references_semanticscholar(arxiv_id, session)
    if refs:
        with open(os.path.join(save_root, "references.json"), 'w', encoding='utf-8') as f:
            json.dump(refs, f, ensure_ascii=False, indent=2)

# MAIN FUNCTION CALLED BY WEB APP 
def run_scraper(yymm, start_id, end_id, output_folder, celery_task=None):
    session = make_session()
    client = arxiv.Client(page_size=1, delay_seconds=SEARCH_DELAY_SECONDS, num_retries=3)
    
    total_papers = end_id - start_id + 1
    processed_count = 0

    for i in range(start_id, end_id + 1):
        id_str = str(i).zfill(5)
        paper_dir = os.path.join(output_folder, f"{yymm}-{id_str}")
        os.makedirs(paper_dir, exist_ok=True)
        
        # Gọi hàm cào dữ liệu (như cũ)
        fetch_all_versions(yymm, id_str, paper_dir, client, session)
        
        # --- UPDATE PROGRESS ---
        processed_count += 1
        if celery_task:
            # Calculate percentage
            percent = int((processed_count / total_papers) * 100)
            celery_task.update_state(
                state='PROGRESS',
                meta={
                    'current': processed_count,
                    'total': total_papers,
                    'percent': percent,
                    'status': f"Đang xử lý bài {yymm}.{id_str}..."
                }
            )
        
        time.sleep(1) # Delay
    
    session.close()