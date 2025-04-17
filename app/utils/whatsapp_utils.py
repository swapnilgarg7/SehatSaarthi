import logging
from flask import current_app, jsonify
import json
import requests
import re
from google import genai
import os

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


def translate_to_english(text):
    try:        
        if not current_app.config.get("GEMINI_API_KEY"):
            return f"Translation failed: Gemini API key is not configured. Original text: {text}"
        
        client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
    
        prompt = f"Translate the following text to English: '{text}' and only give the best translation, no other useless text"
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
    else:
        # Process the response as normal
        logging.info("Logging HTTP response details")
        log_http_response(response)
        logging.info("Message sent successfully")
        return response


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


def transcribe_audio(audio_data):
    import google.generativeai as genai
    
    logging.info("Starting audio transcription and translation")
    
    # Configure the Gemini API
    try:
        logging.info("Configuring Gemini API")
        genai.configure(api_key=current_app.config["GEMINI_API_KEY"])
        logging.info("Gemini API configured successfully")
        
        assumed_transcription = "This is a placeholder for actual transcription"
        logging.info(f"Placeholder transcription: {assumed_transcription}")
        
        # Now translate this transcription to English
        logging.info("Creating Gemini model instance for audio transcript translation")
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"Translate the following text to English : '{assumed_transcription}' and only give the best translation, no other useless text"
        logging.info(f"Audio translation prompt: {prompt}")
        
        logging.info("Sending audio transcript to Gemini API for translation")
        response = model.generate_content(prompt)
        logging.info("Received translation response from Gemini API")
        
        translated_transcript = response.text.strip()
        logging.info(f"Translated transcript: {translated_transcript}")
        
        return translated_transcript
    
    except Exception as e:
        error_msg = f"Error in audio transcription/translation: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full exception details:")
        return f"Sorry, I couldn't process the audio. Error: {e}"


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

        # Initialize response text
        response = ""

        if message_type == "text":
            message_body = message["text"]["body"]
            logging.info(f"Received text message: {message_body}")

            if message_body.strip().lower() == "hi":
                logging.info("Special case: 'hi' detected")
                response = "Hi, this is Sehat Saarthi"
            else:
                # Translate to English
                logging.info("Translating text message to English")
                translated_text = translate_to_english(message_body)
                response = f"{translated_text}"

        elif message_type == "audio":
            logging.info("Audio message detected")
            audio_id = message["audio"]["id"]
            audio_url = get_media_url(audio_id)
            audio_data = download_media(audio_url)

            translated_transcript = transcribe_audio(audio_data)
            response = f"English transcript: {translated_transcript}"
        else:
            logging.info(f"Unsupported message type: {message_type}")
            response = "I can only understand text or voice notes."

        # Format and send the response
        formatted_response = process_text_for_whatsapp(response)
        data = get_text_message_input(wa_id, formatted_response)
        send_result = send_message(data)

        logging.info(f"Message sent. Result: {send_result}")
        return send_result

    except Exception as e:
        error_msg = f"Error processing WhatsApp message: {str(e)}"
        logging.error(error_msg)
        logging.exception("Full exception details:")
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