import logging
from flask import current_app, jsonify
import json
import requests
import re
from google import genai
import os
import mimetypes
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
import io

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


def get_document_message_input(recipient, document_id, caption=None):
    """
    Create a document message payload for WhatsApp API
    """
    message = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "document",
        "document": {
            "id": document_id
        }
    }
    
    # Add caption if provided
    if caption:
        message["document"]["caption"] = caption
        
    return json.dumps(message)


def extract_patient_name(text):
    """
    Extract patient name from the message text
    Returns the name if found, otherwise None
    """
    # Try to find patterns like "Patient: John Doe" or "Name: John Doe"
    name_patterns = [
        r"(?i)patient\s*(?:name)?[\s:]*([A-Za-z\s]+)(?:\n|$)",
        r"(?i)name[\s:]*([A-Za-z\s]+)(?:\n|$)",
        r"(?i)patient[\s:]*([A-Za-z\s]+)(?:\n|$)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            # Get the captured name and clean it up
            name = match.group(1).strip()
            if name and len(name) > 1:  # Ensure name is not just a single character
                return name
    
    return None


def translate_to_english(text):
    try:        
        if not current_app.config.get("GEMINI_API_KEY"):
            return f"Translation failed: Gemini API key is not configured. Original text: {text}"
        
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
    
        prompt = '''
Translate the following text to English and convert it into a medical report. Format with bold section headers (**Section:**) and proper structure following standard hospital format. Include: Patient Details, Chief Complaint, History, Examination, Assessment, and Plan. Use simple formatting that works in WhatsApp (bold, bullet points).
Dont include the translation in the response
Text to translate: '''+text
        logging.info(f"Translation prompt created: {prompt}")
        
        response = client.models.generate_content(model = "gemini-2.0-flash",contents=prompt)
        logging.info("response: ",response)
        return response.text

    except Exception as e:
        error_msg = f"Translation error: {str(e)}"
        logging.error(error_msg)
        return f"Sorry, I couldn't translate your message: {text}. Error: {str(e)}"


def send_message(data):
    logging.info("Preparing to send WhatsApp message")
    
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    logging.info("Headers prepared (token hidden)")

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"
    logging.info(f"Target URL: {url}")
    
    logging.info(f"Request payload: {data}")

    try:
        logging.info("Sending POST request to WhatsApp API")
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        logging.info(f"Received response with status code: {response.status_code}")
        
        # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        response.raise_for_status()  
        logging.info("Request was successful")
        
        # Process the response as normal
        logging.info("Logging HTTP response details")
        log_http_response(response)
        logging.info("Message sent successfully")
        return response
    except requests.Timeout:
        error_msg = "Timeout occurred while sending message"
        logging.error(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 408
    except requests.HTTPError as e:
        error_msg = f"HTTP error occurred: {e}, Response: {e.response.text if hasattr(e, 'response') else 'No response text'}"
        logging.error(error_msg)
        return jsonify({"status": "error", "message": error_msg}), e.response.status_code if hasattr(e, 'response') else 500
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        error_msg = f"Request failed due to: {e}"
        logging.error(error_msg)
        logging.exception("Full exception details:")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def get_media_url(media_id):
    """Get the URL for downloading media content"""
    headers = {
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{media_id}"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.json().get("url")


def download_media(url):
    """Download media content from the provided URL"""
    headers = {
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    return response.content


def generate_pdf_from_text(text, patient_name=None):
    """
    Generate a PDF document from the given text with patient name embedded in the document.
    Returns the PDF file as bytes.
    """
    logging.info("Generating PDF from text")
    buffer = io.BytesIO()

    # Determine the PDF title
    if patient_name and patient_name.strip():
        title_text = f"{patient_name}'s Medical Report"
    else:
        title_text = "Your Medical Report"

    # Create the PDF document wit
    #h title metadata
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=title_text)
    styles = getSampleStyleSheet()

    # Create custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.blue,
        spaceAfter=6
    )

    normal_style = styles['Normal']

    elements = []

    # Add title
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 12))

    # Process each line of the text
    lines = text.split('\n')
    for line in lines:
        if re.search(r'\*\*(.*?)\*\*', line):
            header_text = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
            elements.append(Paragraph(header_text, header_style))
        else:
            if line.strip():  # Avoid empty lines
                elements.append(Paragraph(line, normal_style))
                elements.append(Spacer(1, 6))

    # Build PDF
    doc.build(elements)

    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data



def upload_media_to_whatsapp(file_data, file_type="application/pdf", file_name="medical_report.pdf"):
    """
    Upload media to WhatsApp servers and get the media ID
    """
    logging.info(f"Uploading {file_type} file to WhatsApp Media API")
    
    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/media"
    
    headers = {
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }
    
    files = {
        'file': (file_name, file_data, file_type)
    }
    
    # Additional form data
    data = {
        'messaging_product': 'whatsapp',
        'type': file_type
    }
    
    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        
        media_id = response.json().get('id')
        logging.info(f"Media uploaded successfully, ID: {media_id}")
        return media_id
    except Exception as e:
        logging.error(f"Error uploading media: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logging.error(f"Response: {e.response.text}")
        raise


def process_whatsapp_message(body):
    logging.info("Starting to process WhatsApp message")

    try:
        wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
        logging.info(f"Processing message from wa_id: {wa_id}")

        name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
        logging.info(f"User name: {name}")

        message = body["entry"][0]["changes"][0]["value"]["messages"][0]
        message_type = message.get("type")
        logging.info(f"Message type: {message_type}")

        # Send acknowledgment message
        ack_data = get_text_message_input(wa_id, "Processing your request. Please wait...")
        send_message(ack_data)

        if message_type == "text":
            message_body = message["text"]["body"]
            logging.info(f"Received text message: {message_body}")

            if message_body.strip().lower() == "hi":
                logging.info("Special case: 'hi' detected")
                response_data = get_text_message_input(wa_id, "Hi, this is Sehat Saarthi. How can I help you today?")
                return send_message(response_data)
            else:
                # Translate to English
                logging.info("Translating text message to English")
                translated_text = translate_to_english(message_body)
                
                # Try to extract patient name from the translated text
                patient_name = extract_patient_name(translated_text)
                logging.info(f"Extracted patient name: {patient_name if patient_name else 'None found'}")
                
                # Generate PDF from the translated text with patient name
                pdf_data = generate_pdf_from_text(translated_text, patient_name=patient_name)
                
                # Create filename based on patient name
                if patient_name and patient_name.strip():
                    file_name = f"{patient_name} Medical Report.pdf"
                else:
                    file_name = "Your Medical Report.pdf"
                
                # Upload the PDF to WhatsApp
                media_id = upload_media_to_whatsapp(pdf_data, file_type="application/pdf", file_name=file_name)
                
                # Create a caption
                caption = "Your medical report is ready."
                
                # Send the PDF document
                document_data = get_document_message_input(wa_id, media_id, caption)
                return send_message(document_data)

        elif message_type == "audio":
            logging.info("Audio message detected")
            audio_id = message["audio"]["id"]
            audio_url = get_media_url(audio_id)
            audio_data = download_media(audio_url)

            # You would need to implement this function
            transcript = transcribe_audio(audio_data)
            translated_transcript = translate_to_english(transcript)
            
            # Try to extract patient name from the transcript
            patient_name = extract_patient_name(translated_transcript)
            logging.info(f"Extracted patient name from audio: {patient_name if patient_name else 'None found'}")
            
            # Generate PDF from the transcribed and translated text
            pdf_data = generate_pdf_from_text(translated_transcript, patient_name=patient_name)
            
            # Create filename based on patient name
            if patient_name and patient_name.strip():
                file_name = f"{patient_name} Medical Report.pdf"
            else:
                file_name = "Your Medical Report.pdf"
            
            # Upload the PDF to WhatsApp
            media_id = upload_media_to_whatsapp(pdf_data, file_type="application/pdf", file_name=file_name)
            
            # Send the PDF document
            document_data = get_document_message_input(wa_id, media_id, "Your audio message has been transcribed and translated")
            return send_message(document_data)
        else:
            logging.info(f"Unsupported message type: {message_type}")
            response_data = get_text_message_input(wa_id, "I can only understand text or voice notes.")
            return send_message(response_data)

    except Exception as e:
        error_msg = f"Error processing WhatsApp message: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full exception details:")
        
        # Try to send error message to user if possible
        try:
            if 'wa_id' in locals():
                error_data = get_text_message_input(wa_id, "Sorry, there was an error processing your request. Please try again later.")
                send_message(error_data)
        except:
            logging.error("Could not send error message to user")
            
        return jsonify({"status": "error", "message": error_msg}), 500


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    logging.info("Validating WhatsApp message structure")
    logging.info(f"Message body structure: {json.dumps(body)[:500]}...")  # Log first 500 chars to avoid huge logs
    
    # Check each part of the expected structure
    if not body.get("object"):
        logging.error("Missing 'object' in the request body")
        return False
        
    if not body.get("entry"):
        logging.error("Missing 'entry' in the request body")
        return False
        
    if not body["entry"][0].get("changes"):
        logging.error("Missing 'changes' in entry[0]")
        return False
        
    if not body["entry"][0]["changes"][0].get("value"):
        logging.error("Missing 'value' in changes[0]")
        return False
        
    if not body["entry"][0]["changes"][0]["value"].get("messages"):
        logging.error("Missing 'messages' in value")
        return False
        
    if not body["entry"][0]["changes"][0]["value"]["messages"][0]:
        logging.error("Empty messages array or missing first message")
        return False
    
    # Message exists but could be text or audio
    logging.info("WhatsApp message structure is valid")
    return True


def transcribe_audio(audio_data):
    import tempfile
    import wave
    from pydub import AudioSegment
    import speech_recognition as sr
    try:
        logging.info("Starting audio transcription")

        # Save original audio to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_input:
            temp_input.write(audio_data)
            temp_input_path = temp_input.name
        
        logging.info(f"Saved input audio to temporary file: {temp_input_path}")

        # Convert audio to WAV format using pydub
        sound = AudioSegment.from_file(temp_input_path)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
            sound.export(temp_wav.name, format="wav")
            wav_path = temp_wav.name
        
        logging.info(f"Converted audio to WAV format at: {wav_path}")

        # Transcribe using SpeechRecognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)

        transcript = recognizer.recognize_google(audio)
        logging.info(f"Transcription successful: {transcript}")

        return transcript

    except sr.UnknownValueError:
        logging.warning("Speech Recognition could not understand audio")
        return "Sorry, I could not understand the audio."

    except sr.RequestError as e:
        logging.error(f"Speech Recognition request failed: {e}")
        return "Speech recognition service is currently unavailable. Please try again later."

    except Exception as e:
        logging.error(f"Error in transcribe_audio: {str(e)}")
        return "An error occurred while processing your audio."

