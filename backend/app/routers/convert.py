import os
import subprocess
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

router = APIRouter(prefix="/convert", tags=["convert"])


@router.post("/docx-to-pdf")
async def docx_to_pdf(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx document")

    content = await file.read()
    safe_name = os.path.basename(file.filename or "input.docx")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, safe_name)
        with open(input_path, "wb") as f:
            f.write(content)

        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", tmpdir,
                    input_path,
                ],
                check=True,
                timeout=60,
                capture_output=True,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=501,
                detail="LibreOffice is not installed on this server",
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="PDF conversion timed out")
        except subprocess.CalledProcessError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Conversion failed: {exc.stderr.decode(errors='replace')}",
            )

        pdf_name = os.path.splitext(safe_name)[0] + ".pdf"
        pdf_path = os.path.join(tmpdir, pdf_name)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="PDF output file not found after conversion")

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_name}"'},
    )
