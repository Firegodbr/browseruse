from fastapi import FastAPI
from api.graphql import graphql_app
from api.scrapper import router as scraper
from contextlib import asynccontextmanager
import db.database_ops as db
from logs.logging_config import setup_logging
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
load_dotenv()

# Initialize logging
logger = setup_logging()
# Initialize FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    """
    Manages the lifespan of the FastAPI application.

    This function executes startup and shutdown code for the application.
    On startup, it initializes the database and adds default data if not present.
    On shutdown, it performs any necessary cleanup tasks.

    Args:
        app (FastAPI): The FastAPI application instance.
    """

    print("Application startup: Initializing database...")
    db.create_db()
    db.add_data_default_db() # Add default service/transport if not present
    print("Database initialized.")
    yield
    # Code to run on shutdown (if any)
    print("Application shutdown.")
app = FastAPI(name=f"{os.getenv('SDS_URL')[8:].split(".")[0].capitalize()} SDSweb API",
              title=f"{os.getenv('SDS_URL')[8:].split(".")[0].capitalize()} SDSweb API",
              description=f"Scrape info of different cars from {os.getenv('SDS_URL')[8:].split(".")[0].capitalize()} SDSweb.",
              version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, OPTIONS, etc.)
    allow_headers=["*"],  # Allows all headers
)

@app.get("/", tags=["Root"], summary="Root endpoint")
async def root():
    """
    Hello world
    """
    return {"message": "Hello, World!"}

app.include_router(graphql_app, prefix="/graphql", tags=["GraphQL"])
app.include_router(scraper, prefix="/scraper", tags=["Scrapers"])
