from typing import List
import base64
"""
Uploads multiple files and returns a list of their contents.
Args:
    files (List[UploadFile]): A list of files to be uploaded.
Returns:
    dict: A dictionary containing the uploaded images.
Raises:
    None
Example:
    >>> upload_files([file1, file2])
    {'images': ['image1_contents', 'image2_contents']}
"""
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return HTMLResponse("""
        <html>
            <body>
                <h1>Upload Images</h1>
                <form action="/upload" enctype="multipart/form-data" method="post">
                    <input name="files" type="file" multiple>
                    <input type="submit">
                </form>
                {% for image in images %}
                    <img src="data:image/png;base64,{{ image }}" alt="Image">
                    <img src="data:image/jpeg;base64,{{ myImage | safe }}">
                {% endfor %}
            </body>
        </html>
    """)

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    images = []
    for file in files:
        contents = await file.read()
        base64_string = base64.b64encode(contents).decode('utf-8')
        #images.append(base64_string)
        images.append(contents)
            
    return {"images": images}
    return templates.TemplateResponse("index.html", {"request": request,  "myImage": base64_encoded_image})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)