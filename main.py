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
os.makedirs("static/bg", exist_ok=True) # Added for background textures

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
            bg_filename = model_filename.replace('.glb', '_bg.png')
            bg_path = f"static/models/{bg_filename}"
            
            process_image_to_3d(file_path, demo_model_path, wall_height=15.0, output_png_path=bg_path)
            
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
        style = "gallery"
        if any(keyword in prompt.lower() for keyword in ["스튜디오", "studio", "은밀", "프라이빗", "벙커", "bunker", "hideout", "은신처", "방패"]):
            style = "studio"
            
        img = np.ones((1000, 1500), dtype=np.uint8) * 255
        wall_thickness = 15
        font = cv2.FONT_HERSHEY_DUPLEX
        
        # ... We don't really care about this draft drawing anymore since cv_engine overrides it, but we keep it to not break img shape parsing.
        cv2.rectangle(img, (100, 100), (1400, 900), (0,0,0), wall_thickness)
        cv2.putText(img, f"HABILAB PREMIUM AI DESIGN", (100, 60), font, 0.8, (120,120,120), 2)
        
        # 2. Save Generated 2D Plan
        filename = f"ai_gen_{int(time.time())}"
        img_path = f"uploads/{filename}.jpg"
        cv2.imwrite(img_path, img)
        
        demo_model_path = f"static/models/{filename}.glb"
        bg_path = f"static/models/{filename}_bg.png"
        
        from core.cv_engine import process_image_to_3d
        # Premium extrusion: 35.0 for dramatic interior feel, pass the dynamically chosen style
        process_image_to_3d(img_path, demo_model_path, wall_height=35.0, style=style, output_png_path=bg_path)
        
        return {
            "status": "success", 
            "message": "AI premium spatial construction complete", 
            "model_url": f"/static/models/{filename}.glb",
            "bg_url": f"/static/models/{filename}_bg.png",
            "width": 150.0,
            "height": 100.0
        }
    except Exception as e:
        print(f"Error in AI generation: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
