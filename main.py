from fastapi import FastAPI, File, UploadFile, Form
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

@app.post("/generate")
async def generate_floorplan(prompt: str = Form(...)):
    print(f"Generating AI floorplan for: {prompt}")
    try:
        import cv2
        import numpy as np
        
        # 1. AI Logic: Draw 2D architectural blueprint based on semantic prompt (Demonstration)
        # Create an 800x1200 white canvas
        img = np.ones((800, 1200), dtype=np.uint8) * 255
        
        # Draw structural walls (Black, thick)
        wall_thickness = 12
        cv2.rectangle(img, (200, 200), (1000, 600), (0,0,0), wall_thickness) # Main boundary
        cv2.line(img, (500, 200), (500, 600), (0,0,0), wall_thickness)       # Split wall
        cv2.line(img, (500, 400), (1000, 400), (0,0,0), wall_thickness)      # Split room 1, 2
        
        # Add stylish semantic text to the floorplan
        font = cv2.FONT_HERSHEY_DUPLEX
        cv2.putText(img, "LIVING ROOM", (250, 420), font, 1.2, (0,0,0), 2)
        cv2.putText(img, "MASTER BED", (650, 320), font, 1.2, (0,0,0), 2)
        cv2.putText(img, "BATH ROOM", (650, 520), font, 1.0, (0,0,0), 2)
        cv2.putText(img, f"AI Prompt: {prompt}", (200, 150), font, 0.8, (0,0,0), 2)
        
        # 2. Save Generated 2D Plan
        filename = f"ai_gen_{int(time.time())}"
        img_path = f"uploads/{filename}.jpg"
        cv2.imwrite(img_path, img)
        
        demo_model_path = f"static/models/{filename}.glb"
        bg_path = f"static/models/{filename}_bg.jpg"
        cv2.imwrite(bg_path, img)
        
        # 3. Trigger 3D Extrusion directly from the generated AI layout
        from core.cv_engine import process_image_to_3d
        process_image_to_3d(img_path, demo_model_path, wall_height=18.0)
        
        return {
            "status": "success", 
            "message": "AI generated layout", 
            "model_url": f"/static/models/{filename}.glb",
            "bg_url": f"/static/models/{filename}_bg.jpg",
            "width": 1200 * 0.1,
            "height": 800 * 0.1
        }
    except Exception as e:
        print(f"Error in AI generation: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
