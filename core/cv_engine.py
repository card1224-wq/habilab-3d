import cv2
import numpy as np
import trimesh
from shapely.geometry import Polygon

def process_image_to_3d(image_path: str, output_glb_path: str, wall_height: float = 30.0):
    # Load image in grayscale (supports Unicode / Korean paths on Windows)
    img_array = np.fromfile(image_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image file {image_path}")
    
    # 1. Binarization (Assume white background, black lines)
    _, thresh = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 2. Advanced AI Filtering for Architectural Walls
    # (a) Opening: Erase small thin noise, text, and furniture vectors
    kernel_open = np.ones((5, 5), np.uint8)
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open)
    
    # (b) Closing & Dilation: Fuse chunky structural walls into solid rigid blocks
    kernel_close = np.ones((25, 25), np.uint8)
    solid = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel_close)
    
    kernel_dilate = np.ones((8, 8), np.uint8)
    solid = cv2.dilate(solid, kernel_dilate, iterations=1)
    
    # 3. Find structural Contours
    contours, hierarchy = cv2.findContours(solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    meshes = []
    
    # Get image dimension for scaling
    h, w = img.shape
    scale_factor = 0.1
    
    # 3.1 Create a global ground plane (Site Context Base)
    # This acts as the large 'earth' around the building
    ground_size = max(w, h) * 1.5 * scale_factor
    ground_poly = Polygon([
        (-ground_size, -ground_size), (ground_size, -ground_size), 
        (ground_size, ground_size), (-ground_size, ground_size)
    ])
    ground_mesh = trimesh.creation.extrude_polygon(ground_poly, height=0.1)
    ground_mesh.apply_translation([0, 0, -0.1])
    meshes.append(ground_mesh)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 1500: continue
            
        epsilon = 0.015 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        if len(approx) < 3: continue
            
        points = []
        for pt in approx:
            x, y = pt[0]
            px = (x - w/2) * scale_factor
            py = (y - h/2) * scale_factor
            points.append((px, -py))
            
        try:
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
                
            if poly.geom_type == 'MultiPolygon':
                polys = list(poly.geoms)
            else:
                polys = [poly]
                
            for p in polys:
                if p.area < 2: continue
                
                # 4.1 Wall Extrusion
                wall_mesh = trimesh.creation.extrude_polygon(p, height=wall_height)
                meshes.append(wall_mesh)
                
                # 4.2 Floor Mesh (Down at 0)
                floor_mesh = trimesh.creation.extrude_polygon(p, height=0.5)
                meshes.append(floor_mesh)
                
                # 4.3 Ceiling/Roof Mesh (Up at wall_height)
                ceiling_mesh = trimesh.creation.extrude_polygon(p, height=0.5)
                ceiling_mesh.apply_translation([0, 0, wall_height])
                meshes.append(ceiling_mesh)
                
        except Exception as e:
            print(f"Error processing contour: {e}")
            continue
            
    if meshes:
        # Combine all and rotate to Y-up
        full_mesh = trimesh.util.concatenate(meshes)
        rm = trimesh.transformations.rotation_matrix(-np.pi/2, [1, 0, 0])
        full_mesh.apply_transform(rm)
        
        # Expert Polish: Merge close vertices and fix normals for "Nano Banana" lighting
        full_mesh.merge_vertices()
        full_mesh.fix_normals()
        
        full_mesh.export(output_glb_path)
    else:
        raise ValueError("벽체를 찾을 수 없습니다.")
