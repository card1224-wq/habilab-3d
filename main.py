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
            
            # Read image dimensions to map it as a floor texture in 3D (Robustly for Windows)
            import cv2
            import numpy as np
            img_array = np.fromfile(file_path, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is not None:
                h, w = img.shape[:2]
                sw, sh = w * 0.1, h * 0.1
            else:
                # Fallback if image reading fails
                sw, sh = 100.0, 100.0
            
            # Copy uploaded image to static for frontend loading
            bg_filename = model_filename.replace('.glb', f'_bg.{ext}')
            bg_path = f"static/models/{bg_filename}"
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
        
        # 1. Advanced Layout Logic based on Prompt
        img = np.ones((1000, 1500), dtype=np.uint8) * 255
        wall_thickness = 15
        font = cv2.FONT_HERSHEY_DUPLEX
        
        # Draw Main Boundary
        cv2.rectangle(img, (100, 100), (1400, 900), (0,0,0), wall_thickness)
        
        # Heuristic: Split rooms based on keywords
        if "거실" in prompt or "living" in prompt.lower():
            cv2.line(img, (600, 100), (600, 900), (0,0,0), wall_thickness) # Main divider
            cv2.putText(img, "LIVING ROOM", (150, 500), font, 1.5, (0,0,0), 3)
            
            if "방" in prompt or "room" in prompt.lower():
                 cv2.line(img, (600, 500), (1400, 500), (0,0,0), wall_thickness) # Horizontal split
                 cv2.putText(img, "MASTER BED", (800, 300), font, 1.2, (0,0,0), 2)
                 cv2.putText(img, "GUEST ROOM", (800, 750), font, 1.2, (0,0,0), 2)
            else:
                 cv2.putText(img, "OPEN BALCONY", (800, 500), font, 1.2, (0,0,0), 2)
        else:
            # Default Studio Layout
            cv2.line(img, (750, 100), (750, 900), (0,0,0), wall_thickness)
            cv2.putText(img, "STUDIO A", (250, 500), font, 1.5, (0,0,0), 3)
            cv2.putText(img, "STUDIO B", (950, 500), font, 1.5, (0,0,0), 3)

        if "주방" in prompt or "kitchen" in prompt.lower():
            cv2.rectangle(img, (100, 100), (400, 300), (0,0,0), wall_thickness)
            cv2.putText(img, "KITCHEN", (150, 200), font, 1.0, (0,0,0), 2)

        cv2.putText(img, f"AI DESIGNED FOR: {prompt[:30]}...", (100, 60), font, 1.0, (50,50,50), 2)
        
        # 2. Save Generated 2D Plan
        filename = f"ai_gen_{int(time.time())}"
        img_path = f"uploads/{filename}.jpg"
        cv2.imwrite(img_path, img)
        
        demo_model_path = f"static/models/{filename}.glb"
        bg_path = f"static/models/{filename}_bg.jpg"
        cv2.imwrite(bg_path, img)
        
        from core.cv_engine import process_image_to_3d
        # Nano Banana level extrusion: higher walls for premium feel
        process_image_to_3d(img_path, demo_model_path, wall_height=25.0)
        
        return {
            "status": "success", 
            "message": "AI premium layout generated", 
            "model_url": f"/static/models/{filename}.glb",
            "bg_url": f"/static/models/{filename}_bg.jpg",
            "width": 1500 * 0.1,
            "height": 1000 * 0.1
        }
    except Exception as e:
        print(f"Error in AI generation: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
