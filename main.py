from fastapi import FastAPI, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import shutil
import uvicorn
import time
import trimesh

app = FastAPI()

# Make directories
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("static/models", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/upload")
async def upload_floorplan(file: UploadFile = File(...)):
    print(f"File uploaded: {file.filename}")
    # Save the file
    file_path = f"uploads/{int(time.time())}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        from core.cv_engine import process_image_to_3d
        model_filename = f"{int(time.time())}.glb"
        demo_model_path = f"static/models/{model_filename}"
        
        ext = file.filename.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png']:
            process_image_to_3d(file_path, demo_model_path, wall_height=15.0)
            
            # Read image dimensions to map it as a floor texture in 3D
            import cv2
            img = cv2.imread(file_path)
            h, w = img.shape[:2]
            sw, sh = w * 0.1, h * 0.1
            
            # Copy uploaded image to static for frontend loading
            bg_filename = model_filename.replace('.glb', f'_bg.{ext}')
            bg_path = f"static/models/{bg_filename}"
            import shutil
            shutil.copy(file_path, bg_path)
            
            return {
                "status": "success", 
                "message": f"Uploaded {file.filename}", 
                "model_url": f"/static/models/{model_filename}",
                "bg_url": f"/static/models/{bg_filename}",
                "width": sw,
                "height": sh
            }
        else:
            raise ValueError("현재는 이미지 파일(JPG, PNG) 도면만 지원됩니다. PDF는 JPG로 변환 후 올려주세요! (DXF 업데이트 예정)")
    except Exception as e:
        print(f"Error processing: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
