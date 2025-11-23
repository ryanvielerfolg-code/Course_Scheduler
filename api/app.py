"""
Flask app for Vercel deployment
This is a copy of app.py adapted for Vercel
"""
from flask import Flask, request, jsonify, send_file
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

# Error handlers
@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error. Please check the server logs for details.'}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': f'Resource not found: {request.path}'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.route('/api/schedule', methods=['POST'])
def schedule():
    try:
        print(f"Received schedule request from {request.remote_addr if hasattr(request, 'remote_addr') else 'unknown'}")
        
        if 'groupwise_file' not in request.files or 'students_file' not in request.files:
            return jsonify({'error': 'Both files are required'}), 400
        
        groupwise_file = request.files['groupwise_file']
        students_file = request.files['students_file']
        
        if groupwise_file.filename == '' or students_file.filename == '':
            return jsonify({'error': 'Both files must be selected'}), 400
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Save files
            groupwise_path = os.path.join(temp_dir, 'groupwise_course_tags_fall2025.xlsx')
            students_path = os.path.join(temp_dir, 'number-of-students-fall-2024-extracted.csv')
            
            groupwise_file.save(groupwise_path)
            students_file.save(students_path)
            
            # Copy scheduler script
            scheduler_script = os.path.join(temp_dir, 'Course_Scheduler.py')
            # Get the parent directory (project root)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_source = os.path.join(project_root, 'Course_Scheduler.py')
            
            # Check if file exists, if not try current directory
            if not os.path.exists(script_source):
                # Try in api directory (for Vercel)
                script_source = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Course_Scheduler.py')
            
            if not os.path.exists(script_source):
                return jsonify({'error': 'Course_Scheduler.py not found'}), 500
            
            shutil.copy(script_source, scheduler_script)
            
            # Modify script
            with open(scheduler_script, 'r') as f:
                script_content = f.read()
            
            script_content = script_content.replace(
                'pd.read_excel("groupwise_course_tags_fall2025.xlsx")',
                f'pd.read_excel(r"{groupwise_path}")'
            )
            script_content = script_content.replace(
                'pd.read_csv("number-of-students-fall-2024-extracted.csv")',
                f'pd.read_csv(r"{students_path}")'
            )
            
            output_excel = os.path.join(temp_dir, 'weekly_timetable_fall2025.xlsx')
            script_content = script_content.replace(
                'timetable_df.to_excel("weekly_timetable_fall2025.xlsx")',
                f'timetable_df.to_excel(r"{output_excel}")'
            )
            
            # Add JSON export
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

for slot in slots:
    output_data["timetable"][slot] = {{}}
    for day in days:
        output_data["timetable"][slot][day] = timetable[slot].get(day, "")

json_output = os.path.join(r"{temp_dir}", "output.json")
with open(json_output, 'w') as f:
    json.dump(output_data, f, indent=2)
'''
            script_content = script_content + '\n' + json_export_code
            
            with open(scheduler_script, 'w') as f:
                f.write(script_content)
            
            # Run script
            try:
                result = subprocess.run(
                    [sys.executable, scheduler_script],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=50  # Vercel pro tier has 60s limit
                )
            except subprocess.TimeoutExpired:
                return jsonify({'error': 'Processing timeout. The schedule is too complex.'}), 500
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or 'Unknown error'
                error_msg = error_msg.replace('\n', ' ').strip()[:500]
                return jsonify({'error': f'Scheduler error: {error_msg}'}), 500
            
            # Read JSON output
            json_path = os.path.join(temp_dir, 'output.json')
            if not os.path.exists(json_path):
                return jsonify({'error': 'Output file not generated'}), 500
            
            with open(json_path, 'r') as f:
                output_data = json.load(f)
            
            # In Vercel, we can't save files persistently
            # Return Excel as base64 encoded string
            import base64
            with open(output_excel, 'rb') as f:
                excel_data = base64.b64encode(f.read()).decode('utf-8')
            
            output_data['excelFile'] = excel_data
            output_data['excelFileName'] = f'weekly_timetable_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            
            return jsonify(output_data)
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error in schedule endpoint: {error_trace}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

# Note: Vercel doesn't support persistent file storage
# So we'll handle downloads differently
@app.route('/api/download', methods=['POST'])
def download():
    # In Vercel, files are returned as base64 in the response
    # This endpoint is not needed, but kept for compatibility
    return jsonify({'error': 'Files are included in the schedule response as base64'}), 501

# Export app for Vercel
# Vercel will automatically detect and use this
if __name__ == '__main__':
    app.run(debug=True, port=5000)

