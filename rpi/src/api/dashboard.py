"""
FastAPI Dashboard for tank visualization
Shows temperatures and tank level with Plotly
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import logging
from pathlib import Path
from database.db_handler import DatabaseHandler
from utils.plot_generator import (
    create_30day_html,
    create_7day_html,
    create_30day_with_forecast_html,
    create_forecast_html
)
import config

logger = logging.getLogger(__name__)

app = FastAPI(title="Tank Monitoring Dashboard")

# Setup templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Database handler with configured path
db_handler = DatabaseHandler(db_path=config.DATABASE_PATH)




@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main page with links to views"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/30days", response_class=HTMLResponse)
async def view_30days(request: Request):
    """30-day view with forecast as 3rd diagram"""
    try:
        plot_html = create_30day_with_forecast_html(db_handler)
        return templates.TemplateResponse(
            "view.html",
            {
                "request": request,
                "title": "30-Day View + Forecast",
                "plot": plot_html,
                "back_link": "/"
            }
        )
    except Exception as e:
        logger.error(f"Error creating 30-day view: {e}")
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/7days", response_class=HTMLResponse)
async def view_7days(request: Request):
    """7-day view"""
    try:
        plot_html = create_7day_html(db_handler)
        return templates.TemplateResponse(
            "view.html",
            {
                "request": request,
                "title": "7-Day View",
                "plot": plot_html,
                "back_link": "/"
            }
        )
    except Exception as e:
        logger.error(f"Error creating 7-day view: {e}")
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/30days-forecast", response_class=HTMLResponse)
async def view_30days_with_forecast(request: Request):
    """
    30-day view WITH forecast
    """
    try:
        plot_html = create_30day_with_forecast_html(db_handler)
        return templates.TemplateResponse(
            "view.html",
            {
                "request": request,
                "title": "30-Day View + Forecast",
                "plot": plot_html,
                "back_link": "/"
            }
        )
    except Exception as e:
        logger.error(f"Error creating 30-day + forecast view: {e}")
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/forecast", response_class=HTMLResponse)
async def view_forecast(request: Request):
    """
    Forecast view (only forecast)
    """
    try:
        plot_html = create_forecast_html(db_handler)
        return templates.TemplateResponse(
            "view.html",
            {
                "request": request,
                "title": "Tank Level Forecast",
                "plot": plot_html,
                "back_link": "/"
            }
        )
    except Exception as e:
        logger.error(f"Error creating forecast view: {e}")
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=500)


@app.get("/health")
async def health_check():
    """Health Check Endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)