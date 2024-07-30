from flask import Flask, request, jsonify
from function_signatures import ask_chatGPT_function_signature
app = Flask(__name__)

app.config['TIMEOUT'] = 60

MAX_FILE_SIZE = 1024 * 1024 * 2

def validate_file(file):
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    print("uploadedfilename:" + file.filename)

    file.seek(0, 2)  # Move the cursor to the end of the file
    file_size = file.tell()  # Get the current position of cursor, which is the size of the file
    file.seek(0)  # Reset the cursor to the beginning of the file for further processing
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': 'File size exceeds 2MB limit'}), 400
    
    return "", 200

@app.route('/upload_file', methods=['POST'])
def upload_file():
    try:
        file = request.files['file']
        json, code = validate_file(file)
        if code == 400:
            return json, code
        json = ask_chatGPT_function_signature(file.read().decode('utf-8'))
        return json, 200
    except Exception as e:
        error_msg = str(e)
        return jsonify({'error': error_msg}), 400 

@app.route('/status', methods=['GET'])
def hello():  
    return jsonify({'status': 'ok'}), 200 

if __name__ == '__main__':
    app.run(debug=True, port=5000)

