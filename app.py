from flask import Flask, render_template, request, jsonify, send_file
import os
import pandas as pd
import subprocess
import json
import tempfile
import shutil
from datetime import datetime
import sys

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Error handlers to ensure JSON responses
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error. Please check the server logs for details.'}), 500

@app.errorhandler(404)
def not_found(error):
    # Log the requested path for debugging
    print(f"404 Error - Requested path: {request.path}")
    return jsonify({'error': f'Resource not found: {request.path}. Please check the URL.'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.route('/')
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'index.html'))

@app.route('/api/schedule', methods=['POST'])
def schedule():
    try:
        # Log request for debugging
        print(f"Received schedule request from {request.remote_addr}")
        
        # Check if files are present
        if 'groupwise_file' not in request.files or 'students_file' not in request.files:
            return jsonify({'error': 'Both files are required'}), 400
        
        groupwise_file = request.files['groupwise_file']
        students_file = request.files['students_file']
        
        if groupwise_file.filename == '' or students_file.filename == '':
            return jsonify({'error': 'Both files must be selected'}), 400
        
        # Create a temporary directory for this request
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Save uploaded files
            groupwise_path = os.path.join(temp_dir, 'groupwise_course_tags_fall2025.xlsx')
            students_path = os.path.join(temp_dir, 'number-of-students-fall-2024-extracted.csv')
            
            groupwise_file.save(groupwise_path)
            students_file.save(students_path)
            
            # Copy the scheduler script to temp directory
            scheduler_script = os.path.join(temp_dir, 'Course_Scheduler.py')
            shutil.copy('Course_Scheduler.py', scheduler_script)
            
            # Modify the script to work in temp directory
            with open(scheduler_script, 'r') as f:
                script_content = f.read()
            
            # Update paths in the script
            script_content = script_content.replace(
                'pd.read_excel("groupwise_course_tags_fall2025.xlsx")',
                f'pd.read_excel(r"{groupwise_path}")'
            )
            script_content = script_content.replace(
                'pd.read_csv("number-of-students-fall-2024-extracted.csv")',
                f'pd.read_csv(r"{students_path}")'
            )
            
            # Change output path
            output_excel = os.path.join(temp_dir, 'weekly_timetable_fall2025.xlsx')
            script_content = script_content.replace(
                'timetable_df.to_excel("weekly_timetable_fall2025.xlsx")',
                f'timetable_df.to_excel(r"{output_excel}")'
            )
            
            # Add code to export JSON data at the end of the script
            json_export_code = f'''
# === Export JSON for web interface ===
import json
import os

output_data = {{
    "timetable": {{}},
    "assignments": assignments_df.to_dict('records'),
    "stats": {{
        "totalCourses": len(assignments_df),
        "unassigned": len(unassigned),
        "softConflicts": int(assignments_df["SoftConflict"].sum())
    }}
}}

# Convert timetable to nested dict
for slot in slots:
    output_data["timetable"][slot] = {{}}
    for day in days:
        output_data["timetable"][slot][day] = timetable[slot].get(day, "")

# Save JSON
json_output = os.path.join(r"{temp_dir}", "output.json")
with open(json_output, 'w') as f:
    json.dump(output_data, f, indent=2)
'''
            
            # Insert before the final print statements
            script_content = script_content + '\n' + json_export_code
            
            # Write modified script
            with open(scheduler_script, 'w') as f:
                f.write(script_content)
            
            # Run the scheduler script
            try:
                result = subprocess.run(
                    [sys.executable, scheduler_script],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            except subprocess.TimeoutExpired:
                return jsonify({'error': 'Processing timeout. The schedule is too complex. Please try with smaller datasets.'}), 500
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or 'Unknown error occurred'
                # Clean up error message
                error_msg = error_msg.replace('\n', ' ').strip()[:500]
                return jsonify({'error': f'Scheduler error: {error_msg}'}), 500
            
            # Read the JSON output
            json_path = os.path.join(temp_dir, 'output.json')
            if not os.path.exists(json_path):
                return jsonify({'error': 'Output file not generated'}), 500
            
            with open(json_path, 'r') as f:
                output_data = json.load(f)
            
            # Copy Excel file to outputs folder with unique name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_filename = f'weekly_timetable_{timestamp}.xlsx'
            output_excel_path = os.path.join(app.config['OUTPUT_FOLDER'], excel_filename)
            shutil.copy(output_excel, output_excel_path)
            
            output_data['excelFile'] = excel_filename
            
            return jsonify(output_data)
            
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in schedule endpoint: {error_trace}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/api/download/<filename>')
def download(filename):
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        return send_file(file_path, as_attachment=True, download_name='weekly_timetable.xlsx')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable (for cloud platforms) or use default
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

