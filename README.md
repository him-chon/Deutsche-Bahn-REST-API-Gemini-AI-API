## This is an extension of v6.db.transport.rest API for Deutsche Bahn powered by Google Gemini API for tourism guide generation

### Getting Started

1. This program requires the following packages to be installed.
```
   pip install python-dotenv==1.0.1
   pip install google-generativeai==0.4.1
   pip install flask==3.0.2
   pip install flask_restx==1.3.0
   pip install requests==2.31.0
```
   Alternatively, you can use requirement.txt by
```
   pip install -r requirements.txt
```

2. Create a file called `.env` in the same directory as this file.  This file
   will contain the Google API key you generatea in the next step.

3. Go to the following page, click on the link to "Get an API key", and follow
   the instructions to generate an API key:

   https://ai.google.dev/tutorials/python_quickstart

4. Add the following line to your `.env` file, replacing `your-api-key` with
   the API key you generated, and save the file:

   GOOGLE_API_KEY=your-api-key

### Using the API

You can check out the API documentation at http://127.0.0.1:5000 when you run the program
<img width="1512" alt="Screenshot 2567-12-06 at 23 37 44" src="https://github.com/user-attachments/assets/84521dd1-a4a3-4752-9817-63a79590a8bd">

Fetch Stops from v6.db.transport.rest API and store in database
<img width="874" alt="Screenshot 2567-12-06 at 23 40 33" src="https://github.com/user-attachments/assets/2ce09758-6271-49cc-9b21-ed79aa291f71">

Update stop detail by stop id
<img width="874" alt="Screenshot 2567-12-06 at 23 42 42" src="https://github.com/user-attachments/assets/beca0fbb-85c9-4003-9477-3bb1948c0452">

Get stop detail by stop id
<img width="874" alt="Screenshot 2567-12-06 at 23 43 36" src="https://github.com/user-attachments/assets/686492a9-5b61-449b-aaa9-4f2c21a4999c">

Get get detail of operator operating at a stop by stop id
<img width="874" alt="Screenshot 2567-12-06 at 23 44 36" src="https://github.com/user-attachments/assets/78804382-0876-49fb-b8c0-1b1cc7295793">

Delete stop from database by stop id
<img width="874" alt="Screenshot 2567-12-06 at 23 46 06" src="https://github.com/user-attachments/assets/00e8ff0a-c0dc-4ffd-8d6d-34491bf916b6">

Generate a tourism guide from available stops in database using Google Gemini AI
<img width="874" alt="Screenshot 2567-12-06 at 23 45 39" src="https://github.com/user-attachments/assets/ab60dde3-a5de-42a9-b56c-3cfef53854ec">

