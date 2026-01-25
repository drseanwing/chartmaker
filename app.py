#!/usr/bin/env python3
"""
Form Field Mapping Tool - Backend Server

A visual tool for defining field mappings on medical forms.
Supports static fields, time-scaled graphs, and various display types.

Usage:
    python app.py
    Then open http://localhost:5000 in your browser

Author: Claude (Anthropic)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from flask import Flask, render_template, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).parent
FORM_IMAGES_DIR = BASE_DIR / "form_images"
PRESETS_DIR = BASE_DIR / "presets"
TEST_OUTPUTS_DIR = BASE_DIR / "test_outputs"
STATIC_DIR = BASE_DIR / "static"

# Ensure directories exist
for d in [FORM_IMAGES_DIR, PRESETS_DIR, TEST_OUTPUTS_DIR, STATIC_DIR]:
    d.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / "form_mapper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# FLASK APP
# =============================================================================

app = Flask(__name__, 
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(STATIC_DIR))

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    """Convert hex color string to RGBA tuple."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b, alpha)
    return (0, 0, 0, alpha)


def get_font(size: int = 12, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font of the specified size."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def list_available_forms() -> List[Dict[str, Any]]:
    """List all available form images."""
    forms = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        for img_path in FORM_IMAGES_DIR.glob(ext):
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                forms.append({
                    'filename': img_path.name,
                    'path': str(img_path),
                    'width': width,
                    'height': height
                })
            except Exception as e:
                logger.warning(f"Could not read image {img_path}: {e}")
    return sorted(forms, key=lambda x: x['filename'])


def list_presets() -> List[Dict[str, Any]]:
    """List all saved presets."""
    presets = []
    for preset_path in PRESETS_DIR.glob("*.json"):
        try:
            with open(preset_path, 'r') as f:
                data = json.load(f)
            presets.append({
                'filename': preset_path.name,
                'form_name': data.get('form_name', preset_path.stem),
                'field_count': len(data.get('fields', [])),
                'modified': datetime.fromtimestamp(preset_path.stat().st_mtime).isoformat()
            })
        except Exception as e:
            logger.warning(f"Could not read preset {preset_path}: {e}")
    return sorted(presets, key=lambda x: x['filename'])


def generate_test_overlay(preset: Dict, test_data: Dict, form_image_path: str) -> str:
    """
    Generate a test overlay with the given preset and test data.
    Returns base64-encoded PNG image.
    """
    logger.info(f"Generating test overlay for {preset.get('form_name', 'unknown')}")
    
    # Load form image
    with Image.open(form_image_path) as base_img:
        base_img = base_img.convert('RGBA')
        width, height = base_img.size
    
    # Create transparent overlay
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Render each field
    for field in preset.get('fields', []):
        field_id = field.get('id', '')
        field_data = test_data.get(field_id)
        
        if field_data is None and not field.get('mandatory', False):
            continue
        
        try:
            render_field(draw, field, field_data, width, height)
        except Exception as e:
            logger.error(f"Error rendering field {field_id}: {e}")
    
    # Composite overlay onto base
    composited = Image.alpha_composite(base_img, overlay)
    
    # Convert to base64
    buffer = BytesIO()
    composited.save(buffer, format='PNG')
    buffer.seek(0)
    base64_img = base64.b64encode(buffer.read()).decode('utf-8')
    
    return f"data:image/png;base64,{base64_img}"


def render_field(draw: ImageDraw.ImageDraw, field: Dict, data: Any, 
                 img_width: int, img_height: int) -> None:
    """Render a single field onto the overlay."""
    field_type = field.get('type', 'text')
    bounds = field.get('bounds', {})
    style = field.get('style', {})
    
    if field_type == 'text':
        render_text_field(draw, field, data, style)
    
    elif field_type == 'checkbox':
        render_checkbox_field(draw, field, data, style)
    
    elif field_type == 'line_graph':
        render_line_graph(draw, field, data, style)
    
    elif field_type == 'bar_graph':
        render_bar_graph(draw, field, data, style)
    
    elif field_type == 'dot_series':
        render_dot_series(draw, field, data, style)
    
    elif field_type == 'bp_ladder':
        render_bp_ladder(draw, field, data, style)


def render_text_field(draw: ImageDraw.ImageDraw, field: Dict, data: Any, style: Dict) -> None:
    """Render a text field."""
    bounds = field.get('bounds', {})
    x = bounds.get('x', 0)
    y = bounds.get('y', 0)
    
    font_size = style.get('font_size', 12)
    font_color = hex_to_rgba(style.get('color', '#000000'))
    font = get_font(font_size, style.get('bold', False))
    
    text = str(data) if data is not None else ''
    
    # Handle alignment
    alignment = style.get('alignment', 'left')
    if alignment == 'center':
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        field_width = bounds.get('width', text_width)
        x = x + (field_width - text_width) // 2
    elif alignment == 'right':
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        field_width = bounds.get('width', text_width)
        x = x + field_width - text_width
    
    draw.text((x, y), text, font=font, fill=font_color)


def render_checkbox_field(draw: ImageDraw.ImageDraw, field: Dict, data: Any, style: Dict) -> None:
    """Render a checkbox field."""
    bounds = field.get('bounds', {})
    x = bounds.get('x', 0)
    y = bounds.get('y', 0)
    size = style.get('size', 10)
    color = hex_to_rgba(style.get('color', '#000000'))
    
    if data:  # Checkbox is checked
        mark_type = style.get('mark_type', 'x')
        if mark_type == 'x':
            draw.line([x, y, x + size, y + size], fill=color, width=2)
            draw.line([x, y + size, x + size, y], fill=color, width=2)
        elif mark_type == 'check':
            draw.line([x, y + size * 0.5, x + size * 0.3, y + size], fill=color, width=2)
            draw.line([x + size * 0.3, y + size, x + size, y], fill=color, width=2)
        elif mark_type == 'fill':
            draw.rectangle([x, y, x + size, y + size], fill=color)


def render_line_graph(draw: ImageDraw.ImageDraw, field: Dict, data: List[Dict], style: Dict) -> None:
    """
    Render a line graph with time-series data.
    
    Expected data format:
    [
        {"time": 0, "value": 75},
        {"time": 5, "value": 80},
        ...
    ]
    """
    if not data or not isinstance(data, list):
        return
    
    bounds = field.get('bounds', {})
    x_axis = field.get('x_axis', {})
    y_axis = field.get('y_axis', {})
    
    graph_left = bounds.get('x', 0)
    graph_top = bounds.get('y', 0)
    graph_width = bounds.get('width', 100)
    graph_height = bounds.get('height', 100)
    graph_right = graph_left + graph_width
    graph_bottom = graph_top + graph_height
    
    x_min = x_axis.get('min', 0)
    x_max = x_axis.get('max', 100)
    y_min = y_axis.get('min', 0)
    y_max = y_axis.get('max', 100)
    
    color = hex_to_rgba(style.get('color', '#FF0000'))
    line_width = style.get('line_width', 2)
    show_dots = style.get('show_dots', True)
    dot_radius = style.get('dot_radius', 3)
    connect_points = style.get('connect_points', True)
    
    def to_pixel(time_val, y_val):
        """Convert data coordinates to pixel coordinates."""
        px = graph_left + (time_val - x_min) / (x_max - x_min) * graph_width
        py = graph_bottom - (y_val - y_min) / (y_max - y_min) * graph_height
        return (int(px), int(py))
    
    # Convert all points
    pixels = []
    for point in data:
        t = point.get('time', 0)
        v = point.get('value', 0)
        if v is not None:
            pixels.append(to_pixel(t, v))
    
    # Draw connecting lines
    if connect_points and len(pixels) > 1:
        for i in range(len(pixels) - 1):
            draw.line([pixels[i], pixels[i + 1]], fill=color, width=line_width)
    
    # Draw dots
    if show_dots:
        for px, py in pixels:
            draw.ellipse([px - dot_radius, py - dot_radius, 
                         px + dot_radius, py + dot_radius], fill=color)


def render_bar_graph(draw: ImageDraw.ImageDraw, field: Dict, data: List[Dict], style: Dict) -> None:
    """
    Render a bar/column graph (useful for fluid balance, etc.)
    """
    if not data or not isinstance(data, list):
        return
    
    bounds = field.get('bounds', {})
    x_axis = field.get('x_axis', {})
    y_axis = field.get('y_axis', {})
    
    graph_left = bounds.get('x', 0)
    graph_top = bounds.get('y', 0)
    graph_width = bounds.get('width', 100)
    graph_height = bounds.get('height', 100)
    graph_bottom = graph_top + graph_height
    
    x_min = x_axis.get('min', 0)
    x_max = x_axis.get('max', 100)
    y_min = y_axis.get('min', 0)
    y_max = y_axis.get('max', 100)
    
    bar_width = style.get('bar_width', 5)
    color = hex_to_rgba(style.get('color', '#0000FF'))
    
    for point in data:
        t = point.get('time', 0)
        v = point.get('value', 0)
        if v is None:
            continue
        
        px = graph_left + (t - x_min) / (x_max - x_min) * graph_width
        bar_height = (v - y_min) / (y_max - y_min) * graph_height
        
        draw.rectangle([
            px - bar_width // 2,
            graph_bottom - bar_height,
            px + bar_width // 2,
            graph_bottom
        ], fill=color)


def render_dot_series(draw: ImageDraw.ImageDraw, field: Dict, data: List[Dict], style: Dict) -> None:
    """
    Render dots at specific positions (like medication administration times).
    """
    if not data or not isinstance(data, list):
        return
    
    bounds = field.get('bounds', {})
    x_axis = field.get('x_axis', {})
    
    row_y = bounds.get('y', 0)
    graph_left = bounds.get('x', 0)
    graph_width = bounds.get('width', 100)
    
    x_min = x_axis.get('min', 0)
    x_max = x_axis.get('max', 100)
    
    dot_radius = style.get('dot_radius', 3)
    color = hex_to_rgba(style.get('color', '#000000'))
    
    for point in data:
        t = point.get('time', 0)
        px = graph_left + (t - x_min) / (x_max - x_min) * graph_width
        
        draw.ellipse([px - dot_radius, row_y - dot_radius,
                     px + dot_radius, row_y + dot_radius], fill=color)
        
        # Optional: add text label (like dose)
        label = point.get('label')
        if label:
            font = get_font(8)
            draw.text((px, row_y - dot_radius - 10), str(label), 
                     font=font, fill=color, anchor="mm")


def render_bp_ladder(draw: ImageDraw.ImageDraw, field: Dict, data: List[Dict], style: Dict) -> None:
    """
    Render blood pressure as vertical bars connecting systolic and diastolic.
    
    Expected data format:
    [
        {"time": 0, "systolic": 120, "diastolic": 80},
        ...
    ]
    """
    if not data or not isinstance(data, list):
        return
    
    bounds = field.get('bounds', {})
    x_axis = field.get('x_axis', {})
    y_axis = field.get('y_axis', {})
    
    graph_left = bounds.get('x', 0)
    graph_top = bounds.get('y', 0)
    graph_width = bounds.get('width', 100)
    graph_height = bounds.get('height', 100)
    graph_bottom = graph_top + graph_height
    
    x_min = x_axis.get('min', 0)
    x_max = x_axis.get('max', 100)
    y_min = y_axis.get('min', 0)
    y_max = y_axis.get('max', 200)
    
    color = hex_to_rgba(style.get('color', '#FF0000'))
    line_width = style.get('line_width', 2)
    marker_size = style.get('marker_size', 4)
    
    def y_to_pixel(val):
        return graph_bottom - (val - y_min) / (y_max - y_min) * graph_height
    
    for point in data:
        t = point.get('time', 0)
        systolic = point.get('systolic')
        diastolic = point.get('diastolic')
        
        if systolic is None or diastolic is None:
            continue
        
        px = graph_left + (t - x_min) / (x_max - x_min) * graph_width
        py_sys = y_to_pixel(systolic)
        py_dia = y_to_pixel(diastolic)
        
        # Draw vertical line connecting systolic and diastolic
        draw.line([(px, py_sys), (px, py_dia)], fill=color, width=line_width)
        
        # Draw markers at systolic (triangle down) and diastolic (triangle up)
        # Systolic - triangle pointing down
        draw.polygon([
            (px, py_sys + marker_size),
            (px - marker_size, py_sys - marker_size),
            (px + marker_size, py_sys - marker_size)
        ], fill=color)
        
        # Diastolic - triangle pointing up
        draw.polygon([
            (px, py_dia - marker_size),
            (px - marker_size, py_dia + marker_size),
            (px + marker_size, py_dia + marker_size)
        ], fill=color)


# =============================================================================
# ROUTES
# =============================================================================

@app.route('/')
def index():
    """Main page - form field mapper interface."""
    return render_template('index.html')


@app.route('/api/forms')
def api_list_forms():
    """List available form images."""
    forms = list_available_forms()
    return jsonify({'forms': forms})


@app.route('/api/presets')
def api_list_presets():
    """List saved presets."""
    presets = list_presets()
    return jsonify({'presets': presets})


@app.route('/api/preset/<filename>')
def api_get_preset(filename):
    """Get a specific preset."""
    preset_path = PRESETS_DIR / filename
    if not preset_path.exists():
        return jsonify({'error': 'Preset not found'}), 404
    
    with open(preset_path, 'r') as f:
        preset = json.load(f)
    return jsonify(preset)


@app.route('/api/preset', methods=['POST'])
def api_save_preset():
    """Save a preset."""
    data = request.json
    filename = data.get('filename', 'untitled.json')
    if not filename.endswith('.json'):
        filename += '.json'
    
    preset_path = PRESETS_DIR / filename
    
    # Add metadata
    data['saved_at'] = datetime.now().isoformat()
    
    with open(preset_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved preset to {preset_path}")
    return jsonify({'success': True, 'filename': filename})


@app.route('/api/test-render', methods=['POST'])
def api_test_render():
    """Generate a test render with sample data."""
    data = request.json
    preset = data.get('preset', {})
    test_data = data.get('test_data', {})
    form_image = data.get('form_image', '')
    
    # Find form image path
    form_path = FORM_IMAGES_DIR / form_image
    if not form_path.exists():
        return jsonify({'error': f'Form image not found: {form_image}'}), 404
    
    try:
        result_image = generate_test_overlay(preset, test_data, str(form_path))
        return jsonify({'image': result_image})
    except Exception as e:
        logger.error(f"Error generating test render: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/form_images/<path:filename>')
def serve_form_image(filename):
    """Serve form images."""
    return send_from_directory(str(FORM_IMAGES_DIR), filename)


@app.route('/api/upload-form', methods=['POST'])
def api_upload_form():
    """Upload a new form image."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save the file
    filename = file.filename
    save_path = FORM_IMAGES_DIR / filename
    file.save(str(save_path))
    
    # Get image dimensions
    with Image.open(save_path) as img:
        width, height = img.size
    
    logger.info(f"Uploaded form image: {filename} ({width}x{height})")
    return jsonify({
        'success': True,
        'filename': filename,
        'width': width,
        'height': height
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Form Field Mapping Tool")
    logger.info("=" * 60)
    logger.info(f"Form images directory: {FORM_IMAGES_DIR}")
    logger.info(f"Presets directory: {PRESETS_DIR}")
    logger.info(f"Starting server on http://localhost:5000")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
