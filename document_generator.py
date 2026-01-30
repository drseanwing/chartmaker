#!/usr/bin/env python3
"""
Medical Form Document Generator

Uses field mapping presets to generate populated medical forms from JSON patient data.
Works with presets created by the Form Field Mapper tool.

Usage:
    from document_generator import FormRenderer
    
    renderer = FormRenderer('presets/QADDS_Adult.json')
    renderer.render(patient_data, 'output/populated_form.png')

Or from command line:
    python document_generator.py --preset presets/QADDS_Adult.json --data patient.json --output form.png

Author: Claude (Anthropic)
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).parent
FORM_IMAGES_DIR = BASE_DIR / "form_images"
PRESETS_DIR = BASE_DIR / "presets"
OUTPUT_DIR = BASE_DIR / "output"

# Ensure output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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


FONTS_DIR = BASE_DIR / "fonts" / "handwriting"

FONT_FAMILIES = {
    'default': {
        'regular': [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ],
        'bold': [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ],
    },
    'handwriting-casual': {
        'regular': [str(FONTS_DIR / "Caveat-Regular.ttf")],
        'bold': [str(FONTS_DIR / "Caveat-Bold.ttf"), str(FONTS_DIR / "Caveat-Regular.ttf")],
    },
    'handwriting-elegant': {
        'regular': [str(FONTS_DIR / "DancingScript-Regular.ttf")],
        'bold': [str(FONTS_DIR / "DancingScript-Bold.ttf"), str(FONTS_DIR / "DancingScript-Regular.ttf")],
    },
    'handwriting-print': {
        'regular': [str(FONTS_DIR / "PatrickHand-Regular.ttf")],
        'bold': [str(FONTS_DIR / "PatrickHand-Regular.ttf")],
    },
}


def get_font(size: int = 12, bold: bool = False, font_family: str = 'default') -> ImageFont.FreeTypeFont:
    """Get a font of the specified size and family."""
    family = FONT_FAMILIES.get(font_family, FONT_FAMILIES['default'])
    variant = 'bold' if bold else 'regular'
    font_paths = family.get(variant, family.get('regular', []))
    if not font_paths:
        font_paths = FONT_FAMILIES['default'].get(variant, [])
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    for path in FONT_FAMILIES['default']['regular']:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def extract_nested_value(data: Dict, path: str) -> Any:
    """
    Extract a value from nested dict using dot notation.
    
    Example:
        extract_nested_value({'patient': {'name': 'John'}}, 'patient.name')
        -> 'John'
    """
    if not path:
        return data
    
    keys = path.split('.')
    value = data
    
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and key.isdigit():
            idx = int(key)
            value = value[idx] if idx < len(value) else None
        else:
            return None
        
        if value is None:
            return None
    
    return value


# =============================================================================
# FIELD RENDERERS
# =============================================================================

class FieldRenderer:
    """Base class for field rendering."""
    
    def __init__(self, draw: ImageDraw.ImageDraw):
        self.draw = draw
    
    def render(self, field: Dict, data: Any) -> None:
        """Override in subclasses."""
        raise NotImplementedError


class TextRenderer(FieldRenderer):
    """Renders text fields."""

    def render(self, field: Dict, data: Any) -> None:
        if data is None:
            return

        bounds = field.get('bounds', {})
        style = field.get('style', {})
        padding = style.get('padding', {})
        pad_top = padding.get('top', 0)
        pad_right = padding.get('right', 0)
        pad_left = padding.get('left', 0)

        x = bounds.get('x', 0) + pad_left
        y = bounds.get('y', 0) + pad_top
        available_width = bounds.get('width', 100) - pad_left - pad_right

        font_size = style.get('font_size', 12)
        color = hex_to_rgba(style.get('color', '#000000'))
        alignment = style.get('alignment', 'left')
        bold = style.get('bold', False)
        font_family = style.get('font_family', 'default')

        font = get_font(font_size, bold, font_family)
        text = str(data)

        # Calculate position based on alignment
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]

        if alignment == 'center':
            x = x + (available_width - text_width) // 2
        elif alignment == 'right':
            x = x + available_width - text_width

        self.draw.text((x, y), text, font=font, fill=color)
        logger.debug(f"Rendered text '{text[:20]}...' at ({x}, {y})")


class CheckboxRenderer(FieldRenderer):
    """Renders checkbox fields. Mark fills the defined field bounds."""

    def render(self, field: Dict, data: Any) -> None:
        if not data:  # Only render if checked/truthy
            return

        bounds = field.get('bounds', {})
        style = field.get('style', {})
        padding = style.get('padding', {})
        pad_top = padding.get('top', 0)
        pad_right = padding.get('right', 0)
        pad_bottom = padding.get('bottom', 0)
        pad_left = padding.get('left', 0)

        x = bounds.get('x', 0) + pad_left
        y = bounds.get('y', 0) + pad_top
        w = bounds.get('width', 20) - pad_left - pad_right
        h = bounds.get('height', 20) - pad_top - pad_bottom
        color = hex_to_rgba(style.get('color', '#000000'))
        mark_type = style.get('mark_type', 'x')
        line_w = max(1, min(w, h) // 6)

        if mark_type == 'x':
            self.draw.line([x, y, x + w, y + h], fill=color, width=line_w)
            self.draw.line([x, y + h, x + w, y], fill=color, width=line_w)
        elif mark_type == 'check':
            self.draw.line([x, y + h * 0.5, x + w * 0.3, y + h], fill=color, width=line_w)
            self.draw.line([x + w * 0.3, y + h, x + w, y], fill=color, width=line_w)
        elif mark_type == 'fill':
            self.draw.rectangle([x, y, x + w, y + h], fill=color)

        logger.debug(f"Rendered checkbox at ({x}, {y}), size {w}x{h}")


class MultilineTextRenderer(FieldRenderer):
    """Renders multiline text fields with word-wrap. Row height derived from bounds."""

    def render(self, field: Dict, data: Any) -> None:
        if data is None:
            return

        bounds = field.get('bounds', {})
        style = field.get('style', {})
        padding = style.get('padding', {})
        pad_top = padding.get('top', 0)
        pad_right = padding.get('right', 0)
        pad_bottom = padding.get('bottom', 0)
        pad_left = padding.get('left', 0)

        x = bounds.get('x', 0) + pad_left
        y = bounds.get('y', 0) + pad_top
        available_width = bounds.get('width', 200) - pad_left - pad_right
        available_height = bounds.get('height', 60) - pad_top - pad_bottom
        text_rows = style.get('text_rows', 3)

        row_height = available_height / max(text_rows, 1)
        font_size = int(row_height * 0.8)
        font_size = max(6, min(font_size, 72))

        color = hex_to_rgba(style.get('color', '#000000'))
        font_family = style.get('font_family', 'default')
        bold = style.get('bold', False)
        alignment = style.get('alignment', 'left')
        font = get_font(font_size, bold, font_family)

        text = str(data)

        # Word-wrap text into lines
        words = text.split()
        lines = []
        current_line = ''
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            bbox = self.draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] <= available_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        lines = lines[:text_rows]

        for i, line in enumerate(lines):
            line_x = x
            line_y = y + i * row_height

            if alignment == 'center':
                bbox = self.draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                line_x = x + (available_width - text_width) // 2
            elif alignment == 'right':
                bbox = self.draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                line_x = x + available_width - text_width

            self.draw.text((line_x, line_y), line, font=font, fill=color)

        logger.debug(f"Rendered multiline text ({len(lines)} lines) at ({x}, {y})")


class LineGraphRenderer(FieldRenderer):
    """Renders line graphs with time-series data."""
    
    def render(self, field: Dict, data: Any) -> None:
        if not data or not isinstance(data, list):
            return
        
        bounds = field.get('bounds', {})
        x_axis = field.get('x_axis', {})
        y_axis = field.get('y_axis', {})
        style = field.get('style', {})
        
        graph_left = bounds.get('x', 0)
        graph_top = bounds.get('y', 0)
        graph_width = bounds.get('width', 100)
        graph_height = bounds.get('height', 100)
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
            if x_max == x_min:
                px = graph_left
            else:
                px = graph_left + (time_val - x_min) / (x_max - x_min) * graph_width
            
            if y_max == y_min:
                py = graph_top + graph_height / 2
            else:
                py = graph_bottom - (y_val - y_min) / (y_max - y_min) * graph_height
            
            return (int(px), int(py))
        
        # Convert all points
        pixels = []
        for point in data:
            t = point.get('time', 0)
            v = point.get('value')
            if v is not None:
                pixels.append(to_pixel(t, v))
        
        # Draw connecting lines
        if connect_points and len(pixels) > 1:
            for i in range(len(pixels) - 1):
                self.draw.line([pixels[i], pixels[i + 1]], fill=color, width=line_width)
        
        # Draw dots
        if show_dots:
            for px, py in pixels:
                self.draw.ellipse([px - dot_radius, py - dot_radius,
                                  px + dot_radius, py + dot_radius], fill=color)
        
        logger.debug(f"Rendered line graph with {len(pixels)} points")


class BarGraphRenderer(FieldRenderer):
    """Renders bar/column graphs."""
    
    def render(self, field: Dict, data: Any) -> None:
        if not data or not isinstance(data, list):
            return
        
        bounds = field.get('bounds', {})
        x_axis = field.get('x_axis', {})
        y_axis = field.get('y_axis', {})
        style = field.get('style', {})
        
        graph_left = bounds.get('x', 0)
        graph_width = bounds.get('width', 100)
        graph_height = bounds.get('height', 100)
        graph_bottom = bounds.get('y', 0) + graph_height
        
        x_min = x_axis.get('min', 0)
        x_max = x_axis.get('max', 100)
        y_min = y_axis.get('min', 0)
        y_max = y_axis.get('max', 100)
        
        bar_width = style.get('bar_width', 5)
        color = hex_to_rgba(style.get('color', '#0000FF'))
        
        for point in data:
            t = point.get('time', 0)
            v = point.get('value')
            if v is None:
                continue
            
            if x_max != x_min:
                px = graph_left + (t - x_min) / (x_max - x_min) * graph_width
            else:
                px = graph_left
            
            if y_max != y_min:
                bar_height = (v - y_min) / (y_max - y_min) * graph_height
            else:
                bar_height = 0
            
            self.draw.rectangle([
                px - bar_width // 2,
                graph_bottom - bar_height,
                px + bar_width // 2,
                graph_bottom
            ], fill=color)
        
        logger.debug(f"Rendered bar graph with {len(data)} bars")


class DotSeriesRenderer(FieldRenderer):
    """Renders dot series (e.g., medication administration times)."""
    
    def render(self, field: Dict, data: Any) -> None:
        if not data or not isinstance(data, list):
            return
        
        bounds = field.get('bounds', {})
        x_axis = field.get('x_axis', {})
        style = field.get('style', {})
        
        row_y = bounds.get('y', 0)
        graph_left = bounds.get('x', 0)
        graph_width = bounds.get('width', 100)
        
        x_min = x_axis.get('min', 0)
        x_max = x_axis.get('max', 100)
        
        dot_radius = style.get('dot_radius', 3)
        color = hex_to_rgba(style.get('color', '#000000'))
        
        for point in data:
            t = point.get('time', 0)
            
            if x_max != x_min:
                px = graph_left + (t - x_min) / (x_max - x_min) * graph_width
            else:
                px = graph_left
            
            self.draw.ellipse([px - dot_radius, row_y - dot_radius,
                              px + dot_radius, row_y + dot_radius], fill=color)
            
            # Optional label
            label = point.get('label')
            if label:
                font = get_font(8)
                self.draw.text((px, row_y - dot_radius - 12), str(label),
                              font=font, fill=color, anchor="mm")
        
        logger.debug(f"Rendered dot series with {len(data)} dots")


class BPLadderRenderer(FieldRenderer):
    """Renders blood pressure ladder (systolic/diastolic pairs)."""
    
    def render(self, field: Dict, data: Any) -> None:
        if not data or not isinstance(data, list):
            return
        
        bounds = field.get('bounds', {})
        x_axis = field.get('x_axis', {})
        y_axis = field.get('y_axis', {})
        style = field.get('style', {})
        
        graph_left = bounds.get('x', 0)
        graph_top = bounds.get('y', 0)
        graph_width = bounds.get('width', 100)
        graph_height = bounds.get('height', 100)
        graph_bottom = graph_top + graph_height
        
        x_min = x_axis.get('min', 0)
        x_max = x_axis.get('max', 100)
        y_min = y_axis.get('min', 40)
        y_max = y_axis.get('max', 200)
        
        color = hex_to_rgba(style.get('color', '#FF0000'))
        line_width = style.get('line_width', 2)
        marker_size = style.get('marker_size', 4)
        
        def y_to_pixel(val):
            if y_max == y_min:
                return graph_top + graph_height / 2
            return graph_bottom - (val - y_min) / (y_max - y_min) * graph_height
        
        for point in data:
            t = point.get('time', 0)
            systolic = point.get('systolic')
            diastolic = point.get('diastolic')
            
            if systolic is None or diastolic is None:
                continue
            
            if x_max != x_min:
                px = graph_left + (t - x_min) / (x_max - x_min) * graph_width
            else:
                px = graph_left
            
            py_sys = y_to_pixel(systolic)
            py_dia = y_to_pixel(diastolic)
            
            # Draw vertical line
            self.draw.line([(px, py_sys), (px, py_dia)], fill=color, width=line_width)
            
            # Systolic marker (triangle down)
            self.draw.polygon([
                (px, py_sys + marker_size),
                (px - marker_size, py_sys - marker_size),
                (px + marker_size, py_sys - marker_size)
            ], fill=color)
            
            # Diastolic marker (triangle up)
            self.draw.polygon([
                (px, py_dia - marker_size),
                (px - marker_size, py_dia + marker_size),
                (px + marker_size, py_dia + marker_size)
            ], fill=color)
        
        logger.debug(f"Rendered BP ladder with {len(data)} readings")


# =============================================================================
# FORM RENDERER
# =============================================================================

class FormRenderer:
    """
    Main class for rendering populated medical forms.
    
    Usage:
        renderer = FormRenderer('presets/QADDS_Adult.json')
        renderer.render(patient_data, 'output/form.png')
    """
    
    # Map field types to renderer classes
    RENDERERS = {
        'text': TextRenderer,
        'multiline_text': MultilineTextRenderer,
        'checkbox': CheckboxRenderer,
        'line_graph': LineGraphRenderer,
        'bar_graph': BarGraphRenderer,
        'dot_series': DotSeriesRenderer,
        'bp_ladder': BPLadderRenderer,
    }
    
    def __init__(self, preset_path: Union[str, Path]):
        """
        Initialize the renderer with a preset file.
        
        Args:
            preset_path: Path to the preset JSON file
        """
        self.preset_path = Path(preset_path)
        self.preset = self._load_preset()
        self.form_image_path = self._resolve_form_image_path()
        
        logger.info(f"Initialized FormRenderer for {self.preset.get('form_name', 'unknown')}")
        logger.info(f"  Form image: {self.form_image_path}")
        logger.info(f"  Fields: {len(self.preset.get('fields', []))}")
    
    def _load_preset(self) -> Dict:
        """Load and validate the preset file."""
        if not self.preset_path.exists():
            raise FileNotFoundError(f"Preset not found: {self.preset_path}")
        
        with open(self.preset_path, 'r') as f:
            preset = json.load(f)
        
        # Validate required fields
        if 'fields' not in preset:
            raise ValueError("Preset must contain 'fields' array")
        
        return preset
    
    def _resolve_form_image_path(self) -> Path:
        """Resolve the form image path."""
        form_image = self.preset.get('form_image', '')
        
        # Try relative to preset directory
        path = self.preset_path.parent / form_image
        if path.exists():
            return path
        
        # Try in form_images directory
        path = FORM_IMAGES_DIR / form_image
        if path.exists():
            return path
        
        # Try absolute path
        path = Path(form_image)
        if path.exists():
            return path
        
        raise FileNotFoundError(f"Form image not found: {form_image}")
    
    def render(
        self,
        data: Dict,
        output_path: Union[str, Path],
        data_path_prefix: str = ''
    ) -> Path:
        """
        Render the populated form.
        
        Args:
            data: Patient data dictionary
            output_path: Path to save the rendered form
            data_path_prefix: Optional prefix for data paths (e.g., 'patient.')
        
        Returns:
            Path to the rendered form
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Rendering form to {output_path}")
        
        # Load form template
        with Image.open(self.form_image_path) as base_img:
            base_img = base_img.convert('RGBA')
            width, height = base_img.size
        
        # Create transparent overlay
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Render each field
        fields_rendered = 0
        for field in self.preset.get('fields', []):
            field_id = field.get('id', '')
            field_type = field.get('type', 'text')
            
            # Get data for this field
            data_path = field.get('data_path', field_id)
            if data_path_prefix:
                data_path = f"{data_path_prefix}.{data_path}"
            
            field_data = data.get(field_id) or extract_nested_value(data, data_path)
            
            # Skip if no data and not mandatory
            if field_data is None:
                if field.get('mandatory', False):
                    logger.warning(f"Missing data for mandatory field: {field_id}")
                continue
            
            # Get renderer for field type
            renderer_class = self.RENDERERS.get(field_type)
            if not renderer_class:
                logger.warning(f"Unknown field type: {field_type}")
                continue
            
            # Render the field
            try:
                renderer = renderer_class(draw)
                renderer.render(field, field_data)
                fields_rendered += 1
            except Exception as e:
                logger.error(f"Error rendering field {field_id}: {e}")
        
        logger.info(f"Rendered {fields_rendered} fields")
        
        # Composite overlay onto base
        composited = Image.alpha_composite(base_img, overlay)
        
        # Save result
        if output_path.suffix.lower() in ['.jpg', '.jpeg']:
            composited = composited.convert('RGB')
        
        composited.save(output_path)
        logger.info(f"Saved rendered form to {output_path}")
        
        return output_path
    
    def render_overlay_only(self, data: Dict, output_path: Union[str, Path]) -> Path:
        """
        Render just the overlay (without the form background).
        Useful for debugging or for PDF composition.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get dimensions from preset or form image
        dims = self.preset.get('image_dimensions', {})
        if dims:
            width = dims.get('width', 1000)
            height = dims.get('height', 1000)
        else:
            with Image.open(self.form_image_path) as img:
                width, height = img.size
        
        # Create transparent overlay
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Render each field
        for field in self.preset.get('fields', []):
            field_id = field.get('id', '')
            field_type = field.get('type', 'text')
            field_data = data.get(field_id)
            
            if field_data is None:
                continue
            
            renderer_class = self.RENDERERS.get(field_type)
            if renderer_class:
                try:
                    renderer = renderer_class(draw)
                    renderer.render(field, field_data)
                except Exception as e:
                    logger.error(f"Error rendering field {field_id}: {e}")
        
        overlay.save(output_path)
        logger.info(f"Saved overlay to {output_path}")
        
        return output_path


# =============================================================================
# BATCH RENDERER
# =============================================================================

class BatchRenderer:
    """
    Renders multiple forms for a patient case.
    
    Usage:
        batch = BatchRenderer('presets/')
        batch.render_case(patient_data, 'output/case_001/')
    """
    
    def __init__(self, presets_dir: Union[str, Path]):
        """
        Initialize with directory containing preset files.
        """
        self.presets_dir = Path(presets_dir)
        self.renderers = {}
        
        # Load all presets
        for preset_file in self.presets_dir.glob('*.json'):
            try:
                renderer = FormRenderer(preset_file)
                form_name = renderer.preset.get('form_name', preset_file.stem)
                self.renderers[form_name] = renderer
                logger.info(f"Loaded preset: {form_name}")
            except Exception as e:
                logger.error(f"Failed to load preset {preset_file}: {e}")
        
        logger.info(f"Loaded {len(self.renderers)} presets")
    
    def render_case(
        self,
        data: Dict,
        output_dir: Union[str, Path],
        forms: Optional[List[str]] = None
    ) -> List[Path]:
        """
        Render all (or specified) forms for a patient case.
        
        Args:
            data: Patient data dictionary
            output_dir: Directory to save rendered forms
            forms: Optional list of form names to render (default: all)
        
        Returns:
            List of paths to rendered forms
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        rendered = []
        renderers_to_use = self.renderers
        
        if forms:
            renderers_to_use = {k: v for k, v in self.renderers.items() if k in forms}
        
        for form_name, renderer in renderers_to_use.items():
            try:
                output_path = output_dir / f"{form_name}.png"
                renderer.render(data, output_path)
                rendered.append(output_path)
            except Exception as e:
                logger.error(f"Failed to render {form_name}: {e}")
        
        logger.info(f"Rendered {len(rendered)} forms for case")
        return rendered


# =============================================================================
# CLI
# =============================================================================

def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description='Generate populated medical forms from JSON data'
    )
    parser.add_argument(
        '--preset', '-p',
        required=True,
        help='Path to preset JSON file'
    )
    parser.add_argument(
        '--data', '-d',
        required=True,
        help='Path to patient data JSON file'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output file path'
    )
    parser.add_argument(
        '--overlay-only',
        action='store_true',
        help='Generate only the overlay (no form background)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load patient data
    with open(args.data, 'r') as f:
        data = json.load(f)
    
    # Create renderer and generate
    renderer = FormRenderer(args.preset)
    
    if args.overlay_only:
        renderer.render_overlay_only(data, args.output)
    else:
        renderer.render(data, args.output)
    
    print(f"Generated: {args.output}")


if __name__ == '__main__':
    main()
