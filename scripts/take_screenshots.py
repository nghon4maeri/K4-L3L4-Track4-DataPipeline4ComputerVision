#!/usr/bin/env python3
"""Take lab screenshots: Airflow graph (green), MinIO lake, Metabase dashboard."""
import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "report" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


def shot_airflow(pw):
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1920, "height": 1080})
    pg = ctx.new_page()
    pg.goto("http://localhost:8080/login/")
    pg.fill("input#username", "admin")
    pg.fill("input#password", "admin")
    pg.press("input#password", "Enter")
    pg.wait_for_load_state("networkidle")
    # open the latest successful run's graph view
    pg.goto("http://localhost:8080/dags/day09_video_pipeline/grid")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(3000)
    # click the latest success run then switch to Graph
    try:
        pg.click("text=Graph", timeout=3000)
        pg.wait_for_timeout(2000)
    except Exception:
        pass
    pg.screenshot(path=str(OUT / "airflow_graph.png"), full_page=False)
    b.close()
    print("airflow_graph.png saved")


def shot_minio(pw):
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1920, "height": 1080})
    pg = ctx.new_page()
    pg.goto("http://localhost:9001/login")
    pg.fill("#accessKey", "minioadmin")
    pg.fill("#secretKey", "minioadmin")
    pg.press("#secretKey", "Enter")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(2000)
    pg.goto("http://localhost:9001/buckets/lake/browse")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=str(OUT / "minio_lake.png"), full_page=False)
    b.close()
    print("minio_lake.png saved")


def shot_metabase(pw):
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1920, "height": 1080})
    pg = ctx.new_page()
    pg.goto("http://localhost:3000/auth/login")
    pg.wait_for_load_state("networkidle")
    pg.fill("input[name=username]", "lab@example.com")
    pg.fill("input[name=password]", "Day9-lab-pass!")
    pg.press("input[name=password]", "Enter")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(2000)
    pg.goto("http://localhost:3000/dashboard/2")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(5000)
    pg.screenshot(path=str(OUT / "metabase_dashboard.png"), full_page=False)
    b.close()
    print("metabase_dashboard.png saved")


def shot_failed_task(pw):
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(viewport={"width": 1920, "height": 1080})
    pg = ctx.new_page()
    pg.goto("http://localhost:8080/login/")
    pg.fill("input#username", "admin")
    pg.fill("input#password", "admin")
    pg.press("input#password", "Enter")
    pg.wait_for_load_state("networkidle")
    log_url = ("http://localhost:8080/dags/day09_video_pipeline/grid"
               "?dag_run_id=manual__2026-10-12T16%3A58%3A52%2B00%3A00&task_id=silver_frames&map_index=3")
    pg.goto(log_url)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(3000)
    pg.screenshot(path=str(OUT / "failed_task_log.png"), full_page=False)
    b.close()
    print("failed_task_log.png saved")


with sync_playwright() as pw:
    shot_airflow(pw)
    shot_minio(pw)
    shot_metabase(pw)
    # shot_failed_task is run separately during the LAB_FAIL_ONCE exercise
print("all screenshots saved to", OUT)
