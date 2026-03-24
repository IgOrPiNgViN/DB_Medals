import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import SERVER_HOST, SERVER_PORT
from database import engine, Base

app = FastAPI(
    title="ООН ПКР API",
    description="API для базы данных лауреатов премий ООН ПКР",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import awards, laureates, committee, voting, reports, backup

app.include_router(awards.router, prefix="/api/awards", tags=["awards"])
app.include_router(laureates.router, prefix="/api/laureates", tags=["laureates"])
app.include_router(committee.router, prefix="/api/committee", tags=["committee"])
app.include_router(voting.router, prefix="/api/voting", tags=["voting"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"status": "ok", "service": "ООН ПКР API"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
