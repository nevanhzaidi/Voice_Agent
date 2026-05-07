from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from database.session import get_db
from models.db_operations import DBOperations
from services.vision_service import VisionService
from pathlib import Path
import os


router = APIRouter(prefix="/visual", tags=["visual"])


def _uploads_dir() -> Path:
    # Place uploads under backend/uploads so it's inside the repo workspace
    base = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "uploads" / "visual"
    base.mkdir(parents=True, exist_ok=True)
    return base


@router.get("/upload/{token}", response_class=HTMLResponse)
def upload_form(token: str, db: Session = Depends(get_db)):
    vu = DBOperations().get_visual_upload_by_token(db, token)
    if not vu:
        raise HTTPException(status_code=404, detail="Upload link not found or expired.")

    html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>AppliFix Upload</title>
        <style>
          body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#0b1220; color:#e5e7eb; }}
          .card {{ max-width: 720px; margin: 48px auto; padding: 24px; background:#111827; border:1px solid #1f2937; border-radius: 12px; }}
          h1 {{ margin: 0 0 8px; font-size: 20px; }}
          p {{ margin: 0 0 16px; color:#cbd5e1; }}
          input[type=file] {{ width: 100%; padding: 12px; background:#0b1220; border:1px solid #334155; border-radius: 10px; color:#e5e7eb; }}
          button {{ margin-top: 12px; padding: 10px 14px; border-radius: 10px; border: 0; background:#6366f1; color:white; font-weight:600; cursor:pointer; }}
          .muted {{ font-size: 12px; color:#94a3b8; margin-top: 8px; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h1>Upload a photo for AppliFix</h1>
          <p>Please upload a clear photo of the appliance and (if relevant) the error display area.</p>
          <form method="post" enctype="multipart/form-data" action="/visual/upload/{token}">
            <input type="file" name="image" accept="image/*" required />
            <button type="submit">Upload</button>
          </form>
          <div class="muted">Token: {token}</div>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/upload/{token}", response_class=HTMLResponse)
async def upload_image(token: str, image: UploadFile = File(...), db: Session = Depends(get_db)):
    vu = DBOperations().get_visual_upload_by_token(db, token)
    if not vu:
        raise HTTPException(status_code=404, detail="Upload link not found or expired.")

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    safe_name = (image.filename or "upload").replace("/", "_").replace("\\", "_")
    out_path = _uploads_dir() / f"{token}_{safe_name}"
    out_path.write_bytes(data)

    DBOperations().mark_visual_uploaded(db, token, image_path=str(out_path))

    # Run vision (best effort)
    analysis = {}
    ok = False
    try:
        analysis = await VisionService().analyze_image_bytes(data)
        ok = True
    except Exception as e:
        analysis = {"error": str(e), "note": "Vision analysis failed or not configured."}
        ok = False

    DBOperations().save_visual_analysis(db, token, analysis=analysis, success=ok)

    html = """
    <!doctype html>
    <html>
      <head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Upload complete</title>
        <style>
          body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:#0b1220; color:#e5e7eb; }
          .card { max-width: 720px; margin: 48px auto; padding: 24px; background:#111827; border:1px solid #1f2937; border-radius: 12px; }
          pre { white-space: pre-wrap; background:#0b1220; border:1px solid #334155; padding: 12px; border-radius: 10px; }
        </style>
      </head>
      <body>
        <div class="card">
          <h1>Thanks — upload received.</h1>
          <p>You can return to the call. AppliFix will use this photo to improve diagnosis.</p>
        </div>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/status/{token}")
def get_status(token: str, db: Session = Depends(get_db)):
    vu = DBOperations().get_visual_upload_by_token(db, token)
    if not vu:
        raise HTTPException(status_code=404, detail="Not found.")
    return JSONResponse(
        {
            "token": vu.token,
            "call_id": vu.call_id,
            "email": vu.email,
            "status": vu.status,
            "image_path": vu.image_path,
            "analysis": vu.analysis,
            "created_at": vu.created_at.isoformat() if vu.created_at else None,
            "uploaded_at": vu.uploaded_at.isoformat() if vu.uploaded_at else None,
            "analyzed_at": vu.analyzed_at.isoformat() if vu.analyzed_at else None,
        }
    )

