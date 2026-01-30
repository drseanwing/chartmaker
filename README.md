# Medical Form Field Mapper

A visual tool for defining field mappings on Queensland Health medical forms. Enables programmatic population of clinical documents from JSON patient data.

## Overview

This tool allows you to:

1. **Load** a blank form template (PDF converted to image, or scanned image)
2. **Define fields** by drawing rectangles on the form
3. **Configure** each field's type, styling, and behavior
4. **Test** the mapping with sample data
5. **Save** the preset for use in automated document generation

## Quick Start

### 1. Install Dependencies

```bash
pip install flask pillow
```

### 2. Run the Server

```bash
cd form_mapper
python app.py
```

### 3. Open in Browser

Navigate to: **http://localhost:5000**

## Usage Guide

### Step 1: Load a Form Template

1. Select an existing form from the dropdown, or
2. Click "Upload New Form" to add a new template image

**Tip**: Convert PDFs to high-resolution PNG (300 DPI) for best results.

### Step 2: Define Fields

**Method A - Draw on Form:**
- Click and drag on the form image to draw a field rectangle
- A new field is automatically created with those bounds
- Hold **Shift** while clicking to force drawing mode (skip drag detection)

**Method B - Add Field Button:**
- Click "+ Add Field" to create a new field
- Manually enter the pixel coordinates in the Properties panel

**Moving Fields:**
- Click and drag an existing field overlay to reposition it
- Or click "Redraw" in the Properties panel to draw a new rectangle keeping all settings

**Deleting Fields:**
- Click the **X** button on any field in the list to delete it inline
- Or select a field and click "Delete Field" in the Properties panel

**Switching Forms:**
- When loading a new form image, you'll be prompted to clear existing fields

### Step 3: Configure Field Properties

For each field, configure:

| Property | Description |
|----------|-------------|
| **Field ID** | Unique identifier used in JSON data (e.g., `patient_name`) |
| **Description** | Human-readable description |
| **Type** | text, multiline_text, checkbox, line_graph, bar_graph, dot_series, bp_ladder |
| **Mandatory** | Whether this field must have data |

#### Field Types

**Text** - Single-line text annotation
- Font family (default, handwriting-casual, handwriting-elegant, handwriting-print)
- Font size, color, alignment, bold
- Padding (top, right, bottom, left)

**Multiline Text** - Word-wrapped text within defined bounds
- Font family, color, alignment, bold
- **Text Rows**: number of rows; font size auto-calculated from row height
- Padding (top, right, bottom, left)

**Checkbox** - Tick/cross mark
- Mark type (X, checkmark, fill)
- Mark fills the drawn field bounds (width x height)
- Padding (top, right, bottom, left)

**Line Graph** - Connected data points (e.g., heart rate trace)
- X axis: time range and increments
- Y axis: value range and increments
- Line width, dot radius, connect points option

**Bar Graph** - Vertical bars (e.g., fluid volumes)
- Same axis configuration as line graph
- Bar width

**Dot Series** - Single-row dots (e.g., medication administration times)
- X axis for time scaling
- Dot radius

**BP Ladder** - Blood pressure display (systolic/diastolic connected)
- X axis for time
- Y axis for BP range (typically 40-200)
- Triangular markers for systolic (down) and diastolic (up)

### Step 4: Test with Sample Data

1. Switch to the **Test Data** tab
2. Click "Generate Sample Data" to create placeholder data
3. Edit the JSON to match your test case
4. Click "▶️ Test Render" to preview

### Step 5: Save Preset

1. Enter a **Preset Name** (e.g., `QADDS_Adult`)
2. Click "💾 Save Preset"
3. Presets are saved to `/form_mapper/presets/`

## Preset JSON Format

```json
{
  "form_name": "QADDS_Adult",
  "form_image": "QADDS_Adult_Page_1.jpg",
  "image_dimensions": {
    "width": 1413,
    "height": 2000
  },
  "fields": [
    {
      "id": "patient_name",
      "description": "Patient's full name",
      "type": "text",
      "mandatory": true,
      "bounds": {
        "x": 450,
        "y": 85,
        "width": 300,
        "height": 25
      },
      "style": {
        "color": "#000000",
        "font_size": 14,
        "alignment": "left",
        "bold": false
      }
    },
    {
      "id": "heart_rate",
      "description": "Heart rate trace on vital signs graph",
      "type": "line_graph",
      "mandatory": false,
      "bounds": {
        "x": 150,
        "y": 600,
        "width": 800,
        "height": 200
      },
      "style": {
        "color": "#00AA00",
        "line_width": 2,
        "dot_radius": 3,
        "connect_points": true,
        "show_dots": true
      },
      "x_axis": {
        "min": 0,
        "max": 120,
        "increment": 5
      },
      "y_axis": {
        "min": 40,
        "max": 200,
        "increment": 20
      }
    }
  ]
}
```

## Test Data JSON Format

The test data JSON should have field IDs as keys:

```json
{
  "patient_name": "SULLIVAN, Terri Anne",
  "heart_rate": [
    {"time": 0, "value": 75},
    {"time": 5, "value": 78},
    {"time": 10, "value": 82}
  ],
  "blood_pressure": [
    {"time": 0, "systolic": 120, "diastolic": 80},
    {"time": 5, "systolic": 115, "diastolic": 75}
  ],
  "checkbox_field": true
}
```

## Directory Structure

```
form_mapper/
├── app.py                 # Flask backend
├── document_generator.py  # Production document renderer
├── templates/
│   └── index.html         # Web interface
├── fonts/
│   └── handwriting/       # Bundled handwriting fonts (OFL licensed)
│       ├── Caveat-Regular.ttf
│       ├── Caveat-Bold.ttf
│       ├── DancingScript-Regular.ttf
│       ├── DancingScript-Bold.ttf
│       └── PatrickHand-Regular.ttf
├── form_images/           # Form template images
│   ├── QADDS_Adult_Page_1.jpg
│   ├── Medication_Chart_Page_1.jpg
│   └── ...
├── presets/               # Saved field mappings
│   ├── QADDS_Adult.json
│   └── ...
├── test_outputs/          # Generated test renders
└── form_mapper.log        # Application log
```

## Tips for Accurate Mapping

### Coordinate System
- Origin (0,0) is **top-left** of the image
- X increases to the right
- Y increases downward
- All values are in **pixels**

### For Graph Fields
1. Identify the exact pixel bounds of the graph area
2. Note the axis labels to determine min/max values
3. Count grid lines to determine increment values
4. Test with known data points to verify scaling

### For Text Fields
1. Position the field where text baseline should start
2. Set width to contain expected text length
3. Height should accommodate font size (typically font_size + 4)

### For Checkbox Fields
1. Draw the rectangle to match the checkbox square on the form
2. The check/cross mark will fill the drawn bounds automatically
3. Use padding to inset the mark within the drawn area
4. Use appropriate mark type for the form style

### Font Families
Three handwriting fonts are bundled for realistic form fills:
- **Handwriting - Casual (Caveat)**: relaxed handwriting style
- **Handwriting - Elegant (Dancing Script)**: flowing cursive
- **Handwriting - Print (Patrick Hand)**: neat printed handwriting

## Workflow for New Forms

1. **Prepare Template**
   - Convert PDF to PNG at 300 DPI
   - Save to `form_images/`

2. **Map Static Fields First**
   - Patient demographics (name, DOB, URN)
   - Procedure details
   - Dates and signatures

3. **Map Time-Scaled Fields**
   - Identify graph bounds precisely
   - Configure axis ranges from form labels
   - Test with sample vital signs data

4. **Test Thoroughly**
   - Use realistic test data
   - Verify all fields render correctly
   - Check edge cases (min/max values)

5. **Save and Document**
   - Save preset with descriptive name
   - Note any special requirements

## Integration with Document Generator

Once presets are defined, use them with the document generator:

```python
from document_generator import FormRenderer

# Load preset
renderer = FormRenderer('presets/QADDS_Adult.json')

# Generate populated form
renderer.render(
    patient_data=case_data,
    output_path='output/patient_001_qadds.png'
)
```

## Troubleshooting

### Form image not loading
- Ensure image is in `form_images/` directory
- Check file permissions
- Supported formats: PNG, JPG, JPEG

### Field rectangles not visible
- Check zoom level
- Verify bounds are within image dimensions
- Ensure color has contrast with form background

### Test render not working
- Validate JSON syntax in test data
- Ensure field IDs match between preset and test data
- Check browser console for errors

### Graph scaling incorrect
- Verify axis min/max match form labels
- Check bounds accurately cover graph area
- Test with data at known positions

## License

Internal tool for Queensland Health simulation training.
