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
    
    # Initialize BIM Scene Architecture
    bim_scene = trimesh.Scene()
    
    # Get image dimension for scaling
    h, w = img.shape
    scale_factor = 0.1
    
    # 3.1 Create a global ground plane (Site Context Base)
    # Increased size for immersive atmosphere
    ground_size = max(w, h) * 3.0 * scale_factor 
    ground_poly = Polygon([
        (-ground_size, -ground_size), (ground_size, -ground_size), 
        (ground_size, ground_size), (-ground_size, ground_size)
    ])
    
    # Floor texture base (slightly smaller than ground)
    floor_base_size = max(w, h) * 1.2 * scale_factor
    floor_base_poly = Polygon([
        (-floor_base_size, -floor_base_size), (floor_base_size, -floor_base_size), 
        (floor_base_size, floor_base_size), (-floor_base_size, floor_base_size)
    ])

    rm = trimesh.transformations.rotation_matrix(-np.pi/2, [1, 0, 0])

    ground_mesh = trimesh.creation.extrude_polygon(ground_poly, height=0.5)
    ground_mesh.apply_translation([0, 0, -0.6])
    ground_mesh.apply_transform(rm)
    bim_scene.add_geometry(ground_mesh, geom_name='layer_floor_ground', node_name='layer_floor_ground')
    
    floor_base_mesh = trimesh.creation.extrude_polygon(floor_base_poly, height=0.1)
    floor_base_mesh.apply_translation([0, 0, -0.05])
    floor_base_mesh.apply_transform(rm)
    bim_scene.add_geometry(floor_base_mesh, geom_name='layer_floor_base', node_name='layer_floor_base')

    idx = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 800: continue # Lowered threshold to capture more details
            
        epsilon = 0.01 * cv2.arcLength(cnt, True) # More precise approximation
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
                poly = poly.buffer(0.01) # Small buffer to fix self-intersections
                
            if poly.geom_type == 'MultiPolygon':
                polys = list(poly.geoms)
            else:
                polys = [poly]
                
            for p in polys:
                if p.area < 0.5: continue
                
                # 4.1 Structural Walls
                wall_mesh = trimesh.creation.extrude_polygon(p, height=wall_height)
                # Ensure geometry is clean
                wall_mesh.merge_vertices()
                wall_mesh.fix_normals()
                wall_mesh.apply_transform(rm)
                bim_scene.add_geometry(wall_mesh, geom_name=f'layer_wall_{idx}', node_name=f'layer_wall_{idx}')
                
                # 4.2 Floor Finish
                inner_floor = trimesh.creation.extrude_polygon(p, height=0.2)
                inner_floor.apply_translation([0, 0, 0.05])
                inner_floor.apply_transform(rm)
                bim_scene.add_geometry(inner_floor, geom_name=f'layer_floor_{idx}', node_name=f'layer_floor_{idx}')
                
                # 4.3 High-End Architecture Paradigm: Glass Ceilings / Panoramic Roof
                ceiling = trimesh.creation.extrude_polygon(p, height=0.3)
                ceiling.apply_translation([0, 0, wall_height])
                ceiling.apply_transform(rm)
                bim_scene.add_geometry(ceiling, geom_name=f'layer_window_{idx}', node_name=f'layer_window_{idx}')
                
                idx += 1
                
        except Exception as e:
            print(f"Error processing contour: {e}")
            continue
            
    if len(bim_scene.geometry) > 0:
        # Export as layered GLB
        bim_scene.export(output_glb_path)
    else:
        raise ValueError("공간 구조를 파악하지 못했습니다. 더 명확한 도면을 사용해 주세요.")
